"""Film look checks: the three film presets measured against their windows, plus goldens.

`--preset NAME` runs one preset (film_1999, reloaded or resurrections); the default runs all
three. Each preset is measured with its own settings (film_targets.PRESET_CFG: film_1999
with pulse on, reloaded with pulse off, resurrections with depth on; everything else default).

1. Saver run: matrix_saver.py /s --seconds 6 with that settings.json. Stdout must report the
   look line and an average fps of at least MIN_SAVER_FPS_SHARE of the cap.
2. Gated measurements on in-process GPU frames (tools/checks/frame_harness.py) at 1920x1080, FSR
   quality, t = 6, 9, 12, 15 s, top 10 percent cropped, px distances scaled to 1915 wide:
   lit share, tone buckets, near-white share, leader columns, background and hue, halo, edge
   rise, ink columns, stroke fill, row pitch (film_1999 and reloaded again at 2880x1800, dpi
   1.5), ink grain, background grain, scanline parity; film_1999 also the clarity and follow-up
   gates (film_metrics.py, windows in film_targets.py).
3. GPU golden frames in tools/checks/golden/ (film_1999, reloaded, custom, resurrections). The
   resurrections part adds: bucket hue drift, square cells, columns and glyph tiles, glint
   existence and locality, a classic monitor beside a resurrections one, the flat (depth off)
   combination and the depth slices.
4. With `--side-dir DIR`, writes the saver shot beside the centre crop of the matching film
   still there (nothing is written outside the run's temp root otherwise).

Needs a GL window and the real display driver. Run it alone: the GL frames and the saver run
share the GPU, and its timing gate wants an idle machine. Pre-existing windows that fail on a
given machine fail here too; the summary lists every one.

Usage: <venv python> tools/checks/check_film.py [--preset NAME] [--no-run] [--side-dir DIR] [--show]
"""

import os
import sys
from functools import partial

import numpy as np
from PIL import Image

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TOOLS))
for folder in (ROOT, TOOLS):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import hidden

hidden.setup()

import film_metrics as fm
import frame_harness as fh
import imgmeasure as pix
import shot_stats
from _gate import Checker, RunRoot, require_python, run_check
from film_targets import (
    BIG_DPI,
    BIG_SIZE,
    BUCKETS,
    CLARITY_GATES,
    FOLLOWUP_GATES,
    MONITORS,
    PRESET_CFG,
    SIZE,
    TARGETS,
    TIMES,
)

gate = Checker("film")

# Saver run: the average fps must reach this share of the refresh cap (check_perf uses 0.9 too).
MIN_SAVER_FPS_SHARE = 0.9
# Golden frames: share of pixels off by more than 1 and the largest channel difference. GPU
# drivers differ by a few levels, so a real change shows as a wide or strong difference.
GOLDEN_MAX_SHARE = 0.001
GOLDEN_MAX_DIFF = 8
# Leader columns share (film stills 0.07 to 0.22) and leader halo radii in px at 1915 wide.
LEADER_COLUMNS = (0.07, 0.22)
LEADER_H50 = (2.5, 8.0)
LEADER_H10 = (10.0, 38.0)
# Background grain, per channel standard deviation: the film background is nearly flat.
MAX_BG_GRAIN = 1.2
# Scanline parity (even rows over odd rows): 1.0 is no scanline pattern.
PARITY = (0.97, 1.03)
# Resurrections cells are square (width equals height within a rounding error), 69 to 72
# columns at 1920 wide and a 135 tile glyph set.
CELL_SQUARE_TOLERANCE = 0.001
COLUMNS_AT_1920 = (69, 72)
GLYPH_TILES = 135
# Glint on and off with the same seed: the mean rise within 2 px of ink, the share of added
# light within 4 px of lit pixels, and the share removed.
GLINT_MIN_RISE = 3.0
GLINT_MIN_NEAR_SHARE = 0.80
GLINT_MAX_REMOVED = 0.10
# Hue drift between the 80-120 and the 200-230 tone bucket, degrees: dim glyphs are bluer.
MIN_HUE_DRIFT = 6.0
# Depth slices (resurrections): near glyph rows at least this much taller than far ones, near
# slices alone cover this share, the emptiest of the 8 x 4 regions keeps this share and this
# share of the mean, and near glyphs are bright enough to read.
MIN_NEAR_FAR_PITCH = 2.2
MIN_NEAR_LIT = 0.02
MIN_COVERAGE_REGION = 0.03
MIN_COVERAGE_RATIO = 0.15
MIN_NEAR_P95 = 160.0
MIN_NEAR_BRIGHT = 0.20
# Reloaded with depth on stays below this lit fraction.
MAX_DEPTH_ON_LIT = 0.65
# Grain: lit-pixel frame-to-frame noise relative to the mean. film_1999 follows its own
# grain_ink (0.8 to 1.25 times); the others use TARGETS["grain"] or this default window.
DEFAULT_GRAIN = (0.02, 0.045)
GRAIN_INK_OFF_MAX = {"film_1999": 0.02}
DEFAULT_GRAIN_INK_OFF_MAX = 0.03
# Mixed monitors: the classic rect compared between two renders; the compared strip must be lit
# enough for the comparison to mean something.
MIXED_MAX_SHARE = 0.001
MIXED_MAX_DIFF = 8.0
# Measured 0.41; a blank strip is 0.
MIN_MIXED_LIT_SHARE = 0.1
# Run value: two runs share fewer lit pixels than this (IoU), the same run twice is identical.
MAX_RUN_IOU = 0.5
SAVER_TIMEOUT_S = 180


def gated(name, value, lo, hi, fmt="{:.3f}", prefix=""):
    """Print one value with its window and record it (None is an open side; nan fails)."""
    name = prefix + name
    low = "-" if lo is None else fmt.format(lo)
    high = "-" if hi is None else fmt.format(hi)
    if not gate.within(name, value, lo, hi, fmt):
        print(f"  {name:34s} {fmt.format(value):>10s}  window {low} to {high}  FAIL")
    else:
        print(f"  {name:34s} {fmt.format(value):>10s}  window {low} to {high}")


def owner_cfg(preset="film_1999", **extra):
    return fh.case_cfg(
        ROOT, preset, **dict(PRESET_CFG[preset], glyph_scale=fh.GPU_GLYPH_SCALE, **extra)
    )


def grain_rel(size, upscaling, preset="film_1999"):
    cfg = owner_cfg(preset, upscaling=upscaling)
    f1 = fh.gpu_frames(ROOT, cfg, size, [9.0], frames=[540])[0]
    f2 = fh.gpu_frames(ROOT, cfg, size, [9.0], frames=[541])[0]
    g1 = fm.crop(f1)[..., 1].astype(np.float64)
    g2 = fm.crop(f2)[..., 1].astype(np.float64)
    sel = (g1 >= 80) & (g1 <= 200)
    return float(np.std((g1[sel] - g2[sel]) / np.sqrt(2)) / np.mean(g1[sel] - 14))


def saver_run(run, preset):
    """Run the saver for six seconds with the preset's settings; returns the shot path."""
    shot = run.file(f"film_{preset}.png")
    result = run_check(
        run,
        f"film_{preset}",
        os.path.join(ROOT, "matrix_saver.py"),
        "/s",
        "--seconds",
        "6",
        "--shot",
        shot,
        timeout=SAVER_TIMEOUT_S,
        settings_json=dict(
            preset=preset, easter_egg=False, glyph_scale=fh.GPU_GLYPH_SCALE, **PRESET_CFG[preset]
        ),
    )
    print(result.stdout.strip())
    if not gate.check(result.ok, f"saver exit {result.returncode}: {result.stderr[-300:]}"):
        return None
    want = f"look: {preset}/down/{'on' if PRESET_CFG[preset]['pulse'] else 'off'}"
    gate.check(want in result.stdout, f"saver did not report {want}")
    line = next((ln for ln in result.stdout.splitlines() if "avg fps at exit" in ln), "")
    try:
        cap = float(line.split("cap: ")[1].split(" Hz")[0])
        fps = float(line.split("avg fps at exit: ")[1].split()[0])
        gated("saver avg fps / cap", fps / cap, MIN_SAVER_FPS_SHARE, None, "{:.2f}")
    except IndexError, ValueError:
        gate.fail("saver did not report cap and avg fps")
    if not gate.check(os.path.exists(shot), "saver screenshot missing"):
        return None
    return shot


def side_by_side(shot, preset, side_dir):
    """The saver shot beside the centre crop of the matching film still (information only)."""
    s = Image.open(shot).convert("RGB")
    s = s.crop((0, int(round(s.size[1] * 0.1)), s.size[0], s.size[1]))
    m = shot_stats.measure(np.asarray(s).astype(np.float32))
    print(
        "saver shot (information only):",
        {k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()},
    )
    still = {
        "film_1999": "matrix-1999-opening-bluray.jpg",
        "resurrections": "matrix-2021-street-rain-filmgrab.jpg",
    }.get(preset, "matrix-2003-revolutions-rain-field-4k.jpg")
    still_path = os.path.join(ROOT, "assets", "reference", still)
    if not side_dir or not os.path.exists(still_path):
        return
    ref = Image.open(still_path).convert("RGB")
    x0 = max(0, (ref.size[0] - 1915) // 2)
    ref = ref.crop((x0, 0, x0 + min(1915, ref.size[0]), ref.size[1]))
    h = s.size[1]
    ref = ref.resize((round(ref.size[0] * h / ref.size[1]), h), Image.LANCZOS)
    out = Image.new("RGB", (s.size[0] + ref.size[0], h))
    out.paste(s, (0, 0))
    out.paste(ref, (s.size[0], 0))
    os.makedirs(side_dir, exist_ok=True)
    path = os.path.join(side_dir, f"film_check_{preset}_side.png")
    out.save(path)
    print("side by side", path)


def gate_goldens(presets):
    gdir = os.path.join(TOOLS, "golden")
    for preset in presets:
        for up in ("off", "quality"):
            name = fh.gpu_name(preset, up)
            img = fh.gpu_frames(
                ROOT,
                fh.case_cfg(ROOT, preset, upscaling=up, glyph_scale=fh.GPU_GLYPH_SCALE),
                fh.GOLDEN_GPU_SIZE,
                [fh.GOLDEN_TIME],
            )[0]
            golden = fh.load_png(os.path.join(gdir, name))
            share, mxd = fh.gpu_compare(img, golden)
            ok = share <= GOLDEN_MAX_SHARE and mxd <= GOLDEN_MAX_DIFF
            print(f"  {name:32s} share {share:.5f}  max diff {mxd}" + ("" if ok else "  FAIL"))
            gate.check(
                ok,
                f"golden {name}: share {share:.5f}, max {mxd}; " + fh.first_difference(img, golden),
            )


def glyph_grid_gates(info):
    """Cell geometry (looks.cell_px through rain_grid) and glyph set."""
    _mx, _my, _pad, cw, ch, cols, _rows = info["grid"]
    gated("cell width == cell height (px)", abs(cw - ch), None, CELL_SQUARE_TOLERANCE)
    gated("columns at 1920 wide", float(cols), *COLUMNS_AT_1920, "{:.0f}")
    gated("resurrections glyph tiles", float(info["set_tiles"]), GLYPH_TILES, GLYPH_TILES, "{:.0f}")


def with_preset_value(preset, key, value, render):
    """Run `render()` with looks.PRESETS[preset][key] set to `value`, then restore it."""
    from digital_rain import looks

    table = looks.PRESETS[preset]
    saved = table[key]
    table[key] = value
    try:
        return render()
    finally:
        table[key] = saved


def glint_gates(preset):
    """Glint existence and locality: same seed with and without."""
    on = fh.gpu_frames(ROOT, owner_cfg(preset), SIZE, [9.0])[0]
    off = with_preset_value(
        preset, "glint_gain", 0.0, lambda: fh.gpu_frames(ROOT, owner_cfg(preset), SIZE, [9.0])[0]
    )
    on, off = fm.crop(on), fm.crop(off)
    mon, moff = on.max(-1).astype(np.int32), off.max(-1).astype(np.int32)
    near2 = pix.dilate(mon > 120, 2)
    rise = float(mon[near2].mean() - moff[near2].mean())
    gated("glint: mean rise within 2 px of ink", rise, GLINT_MIN_RISE, None, "{:.2f}")
    # Locality: glint lights dim glyph edges too and the bloom pyramid spreads that light, so a
    # per-pixel limit far from ink cannot hold (the change reaches 24 to 56 units there). The
    # added light must sit next to lit pixels instead.
    add = np.clip(mon - moff, 0, None)
    lost = np.clip(moff - mon, 0, None)
    near4 = pix.dilate(mon > pix.LIT, 4)
    gated(
        "glint: share of added light within 4 px of lit",
        float(add[near4].sum() / max(add.sum(), 1)),
        GLINT_MIN_NEAR_SHARE,
        None,
    )
    gated(
        "glint: light removed, share of added",
        float(lost.sum() / max(add.sum(), 1)),
        None,
        GLINT_MAX_REMOVED,
    )


def mixed_monitor_gate():
    """A classic monitor beside a resurrections one still samples the classic atlas.

    film_1999 on monitor a, resurrections on b, against reloaded on b (no second atlas is
    built there): the left 40 percent of a must match, as the golden frames do (the pyramid
    shares the window, so only the far side is compared)."""
    mons = [
        dict(x=0, y=0, w=640, h=360, dpi=1.0, id="a"),
        dict(x=640, y=0, w=640, h=360, dpi=1.0, id="b"),
    ]
    out = []
    for other in ("resurrections", "reloaded"):
        cfg = fh.case_cfg(
            ROOT,
            "film_1999",
            upscaling="off",
            depth=False,
            glyph_scale=fh.GPU_GLYPH_SCALE,
            monitors={"b": dict(preset=other)},
        )
        out.append(fh.gpu_frames(ROOT, cfg, (1280, 360), [5.0], mons=mons)[0][:, :256])
    share, mxd = fh.gpu_compare(out[0], out[1])
    lit_share = float((out[0].max(-1) > pix.LIT).mean())
    gated(
        "mixed monitors: compared strip lit share", lit_share, MIN_MIXED_LIT_SHARE, None, "{:.4f}"
    )
    gated(
        "mixed monitors: classic rect, share of pixels off by more than 1",
        share,
        None,
        MIXED_MAX_SHARE,
        "{:.5f}",
    )
    gated(
        "mixed monitors: classic rect, max channel diff", float(mxd), None, MIXED_MAX_DIFF, "{:.0f}"
    )


def depth_gates(frames):
    """Depth slices: size spread, near slices visible, even coverage, near glyphs readable.

    Near-only: slices 0 and 1 at density 0; far-only: slices 2 to 5 at density 0."""
    from digital_rain import looks

    orig = looks.PRESETS["resurrections"]["depth_slices"]

    def variant(keep):
        return [dict(s, density=(s["density"] if i in keep else 0.0)) for i, s in enumerate(orig)]

    def render(keep):
        return with_preset_value(
            "resurrections",
            "depth_slices",
            variant(keep),
            lambda: fh.gpu_frames(ROOT, owner_cfg("resurrections"), SIZE, TIMES),
        )

    near, far = render({2, 3, 4, 5}), render({0, 1})
    print("depth slices:")
    pn = [x for f in near for x in fm.row_pitches(f)]
    pf = [x for f in far for x in fm.row_pitches(f)]
    if pn and pf:
        print(
            f"  (row pitch median near {np.median(pn):.0f} px over {len(pn)} tiles,"
            f" far {np.median(pf):.0f} px over {len(pf)} tiles)"
        )
        gated(
            "near over far glyph row pitch",
            float(np.median(pn) / np.median(pf)),
            MIN_NEAR_FAR_PITCH,
            None,
            "{:.2f}",
        )
    else:
        gated("near over far glyph row pitch", float("nan"), MIN_NEAR_FAR_PITCH, None)
    gated(
        "near slices alone, lit share",
        float(np.mean([(f.max(-1) > 60).mean() for f in near])),
        MIN_NEAR_LIT,
        None,
        "{:.4f}",
    )
    lows, ratios = [], []
    for f in frames:
        mx = f.max(-1)
        height, width = mx.shape
        sh = [
            float(
                (
                    mx[
                        r * height // 4 : (r + 1) * height // 4,
                        c * width // 8 : (c + 1) * width // 8,
                    ]
                    > 60
                ).mean()
            )
            for r in range(4)
            for c in range(8)
        ]
        lows.append(min(sh))
        ratios.append(min(sh) / max(float(np.mean(sh)), 1e-9))
    print(
        "  (8 x 4 coverage per frame: lowest",
        [round(v, 3) for v in lows],
        "lowest over mean",
        [round(v, 3) for v in ratios],
        ")",
    )
    gated("8x4 coverage, lowest region lit share", min(lows), MIN_COVERAGE_REGION, None)
    gated("8x4 coverage, lowest over mean", min(ratios), MIN_COVERAGE_RATIO, None)
    p95, bright = [], []
    for f in near:
        mx = f.max(-1).astype(np.float32)
        lit = mx[mx > 60]
        p95.append(float(np.percentile(lit, 95)) if lit.size else 0.0)
        bright.append(float((lit > 120).mean()) if lit.size else 0.0)
    gated(
        "near slices alone, p95 max channel of lit",
        float(np.mean(p95)),
        MIN_NEAR_P95,
        None,
        "{:.1f}",
    )
    gated(
        "near slices alone, share of lit above 120", float(np.mean(bright)), MIN_NEAR_BRIGHT, None
    )


def resurrections_part(t, frames):
    """Gates beyond the shared ones."""
    print("bucket hue and geometry:")
    drift = float(np.mean([fm.bucket_hue_drift(fm.crop(f)) for f in frames]))
    gated("hue drift 80-120 minus 200-230 bucket", drift, MIN_HUE_DRIFT, None, "{:.1f}")
    info = {}
    fh.gpu_frames(ROOT, owner_cfg("resurrections"), SIZE, [6.0], info=info)
    glyph_grid_gates(info)
    glint_gates("resurrections")
    mixed_monitor_gate()
    print("flat combination (depth off): shape gates, lit, buckets and near-white printed")
    flat = fh.gpu_frames(ROOT, owner_cfg("resurrections", depth=False), SIZE, TIMES[:2])
    fv = [fm.measure(fm.crop(f), "dark") for f in flat]
    fmean = {k: float(np.mean([v[k] for v in fv])) for k in fv[0]}
    print(
        "  flat (information):",
        {
            k: round(fmean[k], 3)
            for k in ("lit", "white_pct", "b40", "b80", "b120", "b160", "b200", "b230")
        },
    )
    for c in "rgb":
        gated(f"flat background median {c}", fmean[f"bg_{c}"], *t["bg"][c], "{:.1f}")
    gated("flat lit hue median", fmean["hue"], *t["hue"], "{:.1f}")
    gated("flat bright glyph halo 50 percent px", fmean["glyph_h50"], *t["h50"], "{:.2f}")
    gated("flat bright glyph halo 10 percent px", fmean["glyph_h10"], *t["h10"], "{:.2f}")
    gated("flat edge 10-90 rise px", fmean["edge"], *t["edge"], "{:.2f}")
    gated(
        "flat hue drift",
        float(np.mean([fm.bucket_hue_drift(fm.crop(f)) for f in flat])),
        MIN_HUE_DRIFT,
        None,
        "{:.1f}",
    )
    depth_gates(frames)
    print("resurrections GPU golden frames:")
    gate_goldens(fh.GOLDEN_NEW)


def clarity_gates(frames, means, g):
    """Gate the clarity values of the cropped frames."""
    values = fm.clarity_values(frames, means)
    for key, label, lo, hi, fmt in CLARITY_GATES:
        g("clarity " + label, values[key], lo, hi, fmt)


def followup_gate(size, dpi, g):
    """film_1999 on MONITORS monitors (4 x 2 grid) of the gated size and dpi, each with its
    own rain seed; the follow-up gates are on the monitor mean."""
    width, height = size
    cols = 4
    rows = (MONITORS + cols - 1) // cols
    mons = [
        dict(x=(k % cols) * width, y=(k // cols) * height, w=width, h=height, dpi=dpi, id=str(k))
        for k in range(MONITORS)
    ]
    frames = fh.gpu_frames(
        ROOT, owner_cfg("film_1999"), (cols * width, rows * height), TIMES, mons=mons
    )
    seeds, mean = fm.monitor_values(frames, mons, dpi)
    print(
        f"  per-monitor ({MONITORS} seeds): open "
        + " ".join(f"{s['open']:.3f}" for s in seeds)
        + " | ci "
        + " ".join(f"{s['ci']:.2f}" for s in seeds)
        + " | lc239 "
        + " ".join(f"{s['lc239']:.3f}" for s in seeds)
        + " | wp "
        + " ".join(f"{s['wp']:.2f}" for s in seeds)
        + " | dot_y "
        + " ".join(f"{s['dot_y']:.2f}" for s in seeds)
    )
    print(f"  (ink dot x prominence {mean['dot_x']:.2f}, information)")
    for key, label, lo, hi, fmt in FOLLOWUP_GATES:
        g(f"{label} ({MONITORS}-seed mean)", mean[key], lo, hi, fmt)


def gated_pass(preset, t, size, dpi):
    """The preset windows at one size and monitor dpi.

    film_1999 and reloaded (the presets with a `cols` window) also get a 2880x1800 pass at dpi
    1.5, the Windows 150 percent default for that panel. Halo and edge px are normalised by
    1920 / W as tools/dev/sweep_look.py does. Returns the frames."""
    big = size != SIZE
    mons = [dict(x=0, y=0, w=size[0], h=size[1], dpi=dpi, id="")] if big else None
    info = {}
    frames = fh.gpu_frames(ROOT, owner_cfg(preset), size, TIMES, info=info, mons=mons)
    fix = 1920.0 / size[0]
    vals = [fm.measure(fm.crop(f), t.get("bg_mode", "distance"), fix) for f in frames]
    m = {k: float(np.mean([v[k] for v in vals])) for k in vals[0]}
    g = partial(gated, prefix="2880x1800 dpi 1.5: " if big else "")
    times = ", ".join(str(x) for x in TIMES)
    print(
        f"2880x1800 at dpi 1.5 (mean of t = {times}):"
        if big
        else f"gated measurements (mean of t = {times}):"
    )
    g("lit fraction", m["lit"], *t["lit"])
    for i, (lo, hi) in enumerate(BUCKETS):
        g(f"tone bucket {lo}-{hi}", m[f"b{lo}"], *t["buckets"][i])
    g("near-white percent of lit", m["white_pct"], *t["white"], "{:.2f}")
    if t["head"]:
        for c in "rgb":
            g(f"head colour {c}", m[f"head_{c}"], *t["head"][c], "{:.1f}")
    if t["leader"] and not t.get("followup"):
        g("leader columns", m["leader_cols"], *LEADER_COLUMNS)
    for c in "rgb":
        g(f"background median {c}", m[f"bg_{c}"], *t["bg"][c], "{:.1f}")
    g("lit hue median", m["hue"], *t["hue"], "{:.1f}")
    print(f"  (halo ring nmax {m['nmax']:.0f} px native)")
    g("bright glyph halo 50 percent px", m["glyph_h50"], *t["h50"], "{:.2f}")
    g("bright glyph halo 10 percent px", m["glyph_h10"], *t["h10"], "{:.2f}")
    if t["leader"]:
        g("leader halo 50 percent px", m["lead_h50"], *LEADER_H50, "{:.2f}")
        g("leader halo 10 percent px", m["lead_h10"], *LEADER_H10, "{:.2f}")
    g("edge 10-90 rise px", m["edge"], *t["edge"], "{:.2f}")
    if t["run"]:
        g("lit run median rows", m["run"], t["run"], None, "{:.1f}")
    for c in "rgb":
        if t.get("bggrain_info"):  # resurrections: dark pixels sit in the skirt, no window
            print(f"  background grain {c:23s} {m[f'bg_grain_{c}']:>10.2f}  information")
            continue
        g(f"background grain {c}", m[f"bg_grain_{c}"], None, MAX_BG_GRAIN, "{:.2f}")
    g("scanline parity", m["parity"], *PARITY)
    if t.get("clarity"):
        clarity_gates([fm.crop(f) for f in frames], m, g)
    if t.get("followup"):
        followup_gate(size, dpi, g)
    if "cols" in t:
        ch = info["grid"][4]
        g("ink columns per 1915 px", m["ink_cols"], *t["cols"], "{:.0f}")
        g("stroke fill share", m["fill"], *t["fill"], "{:.2f}")
        g("row pitch px at 1915 wide", ch * 1915.0 / size[0], *t["row"], "{:.1f}")
    return frames


def grain_gates(preset, t):
    from digital_rain import looks

    ink = looks.PRESETS[preset]["grain_ink"]
    lo, hi = (0.8 * ink, 1.25 * ink) if preset == "film_1999" else t.get("grain", DEFAULT_GRAIN)
    gated(
        "ink grain rel 1920x1080 (full-screen pass)",
        grain_rel(SIZE, "quality", preset),
        lo,
        hi,
        "{:.4f}",
    )
    gated(
        "ink grain rel 960x540 (final pass)",
        grain_rel((960, 540), "quality", preset),
        lo,
        hi,
        "{:.4f}",
    )
    # With ink grain off this measures the glyph-texture residual: the darker reloaded palette
    # floor (000402) lifts it above film_1999's (0.0246 against 0.0194); `grain` stays at
    # 0.0167 (Rezmason's value).
    limit = t.get("grain0", GRAIN_INK_OFF_MAX.get(preset, DEFAULT_GRAIN_INK_OFF_MAX))
    off = with_preset_value(preset, "grain_ink", 0.0, lambda: grain_rel(SIZE, "quality", preset))
    gated("ink grain rel, grain_ink 0", off, None, limit, "{:.4f}")


def run_preset(run, preset, do_run, side_dir):
    from digital_rain import looks

    print(f"== {preset} ==")
    shot = None
    if do_run:
        print("saver run:")
        shot = saver_run(run, preset)
    p = looks.PRESETS[preset]
    print(
        f"{preset}:",
        {
            k: p.get(k)
            for k in (
                "tooth",
                "contrast",
                "bias",
                "gamma",
                "bloom",
                "glow_r",
                "glow_g",
                "grain_ink",
                "lanes",
                "defocus",
                "lead_core",
                "lead_cap",
                "cluster",
                "ink_dots",
            )
        },
    )
    t = TARGETS[preset]
    frames = gated_pass(preset, t, SIZE, 1.0)
    if "cols" in t:  # the same windows again on a 2880x1800 panel at 150 percent
        gated_pass(preset, t, BIG_SIZE, BIG_DPI)
    grain_gates(preset, t)
    if preset == "reloaded":
        d = fh.gpu_frames(ROOT, owner_cfg(preset, depth=True), SIZE, TIMES[:2])
        dv = [fm.measure(fm.crop(f)) for f in d]
        dm = {k: float(np.mean([v[k] for v in dv])) for k in dv[0]}
        print(
            "depth on (information):",
            {
                k: round(dm[k], 3)
                for k in ("lit", "hue", "head_r", "head_g", "head_b", "white_pct", "run")
            },
        )
        gated("depth on lit fraction", dm["lit"], None, MAX_DEPTH_ON_LIT)
        print("reloaded GPU golden frames:")
        gate_goldens(("reloaded",))
    if preset == "resurrections":
        resurrections_part(t, frames)
    if shot:
        side_by_side(shot, preset, side_dir)


def lit_iou(a, b):
    """IoU of the lit masks (max channel > 40) of two frames."""
    la, lb = a.max(axis=2) > pix.LIT, b.max(axis=2) > pix.LIT
    return float((la & lb).sum()) / max(1, int((la | lb).sum()))


def run_value_gate():
    """The GPU run value moves the layout and is reproducible; run 0 is the harness default.

    960x540, t = 12, depth off."""
    print("run value (GPU, 960x540, t = 12):")
    for preset in ("film_1999", "reloaded", "resurrections", "custom"):
        cfg = fh.case_cfg(ROOT, preset, depth=False, glyph_scale=fh.GPU_GLYPH_SCALE)

        def frame(cfg=cfg, **kw):
            return fh.gpu_frames(ROOT, cfg, (960, 540), [12.0], **kw)[0]

        r1, r2, r1b, r0, dflt = frame(run=1), frame(run=2), frame(run=1), frame(run=0), frame()
        iou = lit_iou(r1, r2)
        same1 = np.array_equal(r1, r1b)
        same0 = np.array_equal(r0, dflt)
        ok = iou <= MAX_RUN_IOU and same1 and same0
        print(
            f"  {preset:14s} run 1 vs 2 lit IoU {iou:.3f}  run 1 twice "
            f"{'identical' if same1 else 'DIFFERENT'}  run 0 vs default "
            f"{'identical' if same0 else 'DIFFERENT'}" + ("" if ok else "  FAIL")
        )
        gate.within(f"run value {preset}: run 1 vs 2 lit IoU", iou, hi=MAX_RUN_IOU)
        gate.check(same1, f"run value {preset}: run 1 twice not byte-identical")
        gate.check(same0, f"run value {preset}: run 0 not byte-identical to the default call")


def option(name):
    args = sys.argv[1:]
    return args[args.index(name) + 1] if name in args else None


def main():
    if not require_python():
        return 1
    do_run = "--no-run" not in sys.argv
    presets = (
        [option("--preset")] if option("--preset") else ["film_1999", "reloaded", "resurrections"]
    )
    side_dir = option("--side-dir")
    with RunRoot("matrix_film_") as run:
        for preset in presets:
            gate.run(run_preset, run, preset, do_run, side_dir)
        if "film_1999" in presets:
            print("film_1999, reloaded and custom GPU golden frames:")
            gate.run(
                gate_goldens,
                tuple(p for p in fh.GOLDEN_PRESETS if p != "reloaded" or "reloaded" not in presets),
            )
        gate.run(run_value_gate)
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
