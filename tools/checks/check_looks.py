"""Software-renderer checks for the looks: the golden hashes of the three film presets, the run
value, the Reloaded colours, the Resurrections glyph atlas and a preset x direction x pulse matrix
of floors and lit pixels. The pure look maths is in tests/test_looks.py.

Usage: <venv python> tools/checks/check_looks.py [--perf]
Run it from the repository root. It needs no GPU: the software renderer is built on pygame's
dummy video driver. --perf adds the atlas decode time limit. Prints `looks check OK` on success.
"""

import colorsys
import json
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TOOLS))
for folder in (ROOT, TOOLS):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import frame_harness as fh
import numpy as np
import pygame
from _gate import Checker

from digital_rain import glyphs, settings, soft_renderer

pygame.display.init()
pygame.font.init()

gate = Checker("looks")
check = gate.check
PERF = "--perf" in sys.argv


def check_golden_soft():
    """Software renderer frames of every golden preset match their recorded hashes."""
    golden = os.path.join(ROOT, "tools", "checks", "golden", "soft_hashes.json")
    with open(golden, encoding="utf-8") as f:
        want = json.load(f)
    for preset in fh.GOLDEN_PRESETS:
        cfg = fh.case_cfg(ROOT, preset, glyph_scale=fh.SOFT_GLYPH_SCALE)
        img = fh.soft_frames(ROOT, cfg, fh.GOLDEN_SOFT_SIZE, [fh.GOLDEN_TIME])[0]
        got = fh.sha(img)
        check(got == want[f"soft_{preset}"], f"software golden {preset}: {got}")
    for preset in fh.GOLDEN_NEW:
        cfg = fh.case_cfg(ROOT, preset, glyph_scale=fh.SOFT_GLYPH_SCALE)
        img = fh.soft_frames(ROOT, cfg, fh.GOLDEN_SOFT_SIZE, [fh.GOLDEN_TIME])[0]
        got = fh.sha(img)
        check(got == want[f"soft_{preset}"], f"software golden {preset}: {got}")


def check_soft_run():
    """The software run value seeds the layout: run 1 and 2 differ, run 1 repeats, and
    run=SEED matches the seeded default. 960x540, t = 12, depth off."""
    for preset in ("film_1999", "reloaded", "resurrections", "custom"):
        cfg = fh.case_cfg(ROOT, preset, depth=False)
        r1 = fh.soft_frames(ROOT, cfg, (960, 540), [12.0], run=1)[0]
        r2 = fh.soft_frames(ROOT, cfg, (960, 540), [12.0], run=2)[0]
        r1b = fh.soft_frames(ROOT, cfg, (960, 540), [12.0], run=1)[0]
        rs = fh.soft_frames(ROOT, cfg, (960, 540), [12.0], run=fh.SEED)[0]
        dflt = fh.soft_frames(ROOT, cfg, (960, 540), [12.0])[0]
        la, lb = r1.max(axis=2) > 40, r2.max(axis=2) > 40
        iou = float((la & lb).sum()) / max(1, int((la | lb).sum()))
        same1 = np.array_equal(r1, r1b)
        same_seed = np.array_equal(rs, dflt)
        print(
            f"  {preset:14s} run 1 vs 2 lit IoU {iou:.3f}  run 1 twice "
            f"{'identical' if same1 else 'DIFFERENT'}  run=SEED vs default "
            f"{'identical' if same_seed else 'DIFFERENT'}"
        )
        check(iou <= 0.5, f"soft run value {preset}: run 1 vs 2 lit IoU {iou:.3f} above 0.5")
        check(same1, f"soft run value {preset}: run 1 twice not byte-identical")
        check(same_seed, f"soft run value {preset}: run=SEED differs from the default call")


def check_soft_reloaded():
    """Software Reloaded frames, depth off and on, have the film hue and head colour."""
    for depth in (False, True):
        cfg = fh.case_cfg(ROOT, "reloaded", depth=depth, glyph_scale=fh.SOFT_GLYPH_SCALE)
        a = fh.soft_frames(ROOT, cfg, (800, 600), [5.0])[0].astype(np.float32)
        mx = a.max(-1)
        lit = mx > 40
        lit_pixels = a[lit]
        hs = np.array(
            [
                colorsys.rgb_to_hsv(*(c / 255.0))[0] * 360
                for c in lit_pixels[:: max(1, len(lit_pixels) // 20000)]
            ]
        )
        hue = float(np.median(hs))
        r_, g_, b_ = a[mx >= np.percentile(mx, 99.5)].mean(0)
        white = float((a.min(-1) > 200).sum() / max(int(lit.sum()), 1) * 100)
        tag = f"software reloaded depth={depth}"
        print(
            f"  {tag}: lit {lit.mean():.3f} hue {hue:.1f} head ({r_:.0f},{g_:.0f},{b_:.0f}) "
            f"near-white {white:.2f}"
        )
        check(150 <= hue <= 160, f"{tag}: hue {hue:.1f}")
        check(
            20 <= r_ <= 80 and 230 <= g_ <= 255 and 150 <= b_ <= 205,
            f"{tag}: head ({r_:.0f},{g_:.0f},{b_:.0f})",
        )
        check(white <= 0.5, f"{tag}: near-white {white:.2f}")


def check_glyph_atlas():
    """The Resurrections atlas decodes to unflipped coverage and glint tiles, and is cached."""
    glyphs._RES_CACHE.clear()
    started = time.perf_counter()
    got = glyphs.resurrection_set()
    decode_ms = (time.perf_counter() - started) * 1000
    check(got is not None, "resurrection_set returned None")
    coverage, glint = got
    check(len(coverage) == len(glint) == 135, "135 tiles each")
    check(all(t.shape == (112, 80) and t.dtype == np.uint8 for t in coverage + glint), "tile shape")
    lit = [float((t > 127).mean()) for t in coverage]
    check(
        all(0.01 <= v <= 0.7 for v in lit) and all(t.max() > 200 for t in coverage),
        f"coverage tiles: lit fraction {min(lit):.3f}..{max(lit):.3f}",
    )
    check(sum(1 for t in glint if t.max() > 0) == 68, "glint atlas has 68 non-blank tiles")
    if PERF:
        # Measured about 150 ms on the development PC.
        gate.within("atlas decode ms", decode_ms, hi=400, fmt="{:.0f}")
    check(glyphs.resurrection_set() is glyphs._RES_CACHE["gpu"], "second call is cached")
    classic = glyphs.glyph_set(1.0, "", None)[0]
    check(
        len(classic) == len(glyphs.glyph_set(1.0, "", None, "classic")[0]),
        "classic glyph_set unchanged",
    )
    tiles, source = glyphs.glyph_set(1.0, "", None, "resurrections", (27, 27))
    check(
        source == "resurrections" and len(tiles) == 135 and tiles[0].get_size() == (27, 27),
        "resurrections soft tiles",
    )


def floor_of(img):
    mx = img.max(axis=2).ravel()
    flat = img.reshape(-1, 3)
    n = max(1, int(len(mx) * 0.02))
    idx = np.argsort(mx, kind="stable")[:n]
    return np.median(flat[idx], axis=0)


def check_software():
    sets = (
        (
            [dict(x=0, y=0, w=800, h=600, dpi=1.0), dict(x=800, y=0, w=640, h=480, dpi=1.5)],
            (1440, 600),
        ),
        ([dict(x=0, y=0, w=152, h=112, dpi=0.3)], (152, 112)),
    )
    run = 0
    for mons, size in sets:
        screen = pygame.display.set_mode(size)
        for preset in settings.PRESET_NAMES:
            for direction in settings.DIRECTIONS:
                pulse = run % 2 == 1
                run += 1
                cfg = dict(
                    settings.DEFAULTS,
                    preset=preset,
                    direction=direction,
                    pulse=pulse,
                    easter_egg=False,
                )
                with fh._seeded():  # the floor of a random frame is flaky
                    r = soft_renderer.SoftRenderer(mons, cfg, (0, 0), size, screen)
                    for frame in range(10):
                        r.render(frame / 30, 1 / 30, frame)
                px = pygame.surfarray.array3d(screen).transpose(1, 0, 2).astype(np.float32)
                tag = f"{preset}/{direction}/pulse={pulse}/{size}"
                for m in mons:
                    rect = px[m["y"] : m["y"] + m["h"], m["x"] : m["x"] + m["w"]]
                    check(rect.max() >= 60, f"{tag}: nothing lit on monitor at {m['x']}")
                    r_, g_, b_ = floor_of(rect)
                    if preset == "film_1999":
                        ok = (
                            0 <= r_ <= 3
                            and 4 <= g_ <= 9
                            and 2 <= b_ <= 7
                            and g_ >= r_ + 4
                            and g_ > b_
                        )
                        check(ok, f"{tag}: film floor {(r_, g_, b_)}")
                    elif preset == "resurrections":
                        check(
                            1 <= r_ <= 6 and 8 <= g_ <= 20 and 1 <= b_ <= 8,
                            f"{tag}: resurrections floor {(r_, g_, b_)}",
                        )
                    elif preset == "reloaded":
                        # the no-gap look keeps faint trail ends, so the floor sits up to g 8
                        check(
                            0 <= r_ <= 1 and 2 <= g_ <= 8 and 0 <= b_ <= 8,
                            f"{tag}: reloaded floor {(r_, g_, b_)}",
                        )
                    else:
                        check(max(r_, g_, b_) <= 6, f"{tag}: black floor {(r_, g_, b_)}")
    check(run == 24, f"expected 24 software runs, did {run}")


def main():
    for fn in (
        check_glyph_atlas,
        check_software,
        check_soft_reloaded,
        check_golden_soft,
        check_soft_run,
    ):
        gate.run(fn)
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
