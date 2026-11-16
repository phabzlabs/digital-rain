"""Measure the film reference stills and frame gifs in assets/reference.

Reference tooling only (not part of the gate). Run with the repo venv:

    .venv\\Scripts\\python.exe -I tools/dev/measure_reference.py

Prints one block per still and per motion gif; design/film-reference.md quotes
the numbers. Crops in STILLS limit each measurement to the code area of the
frame (monitor faces, rain region) so faces and set dressing do not count.
"""

from __future__ import annotations

import colorsys
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # python -I adds no folder
sys.path.insert(0, os.path.join(HERE, "..", "checks"))  # imgmeasure

import numpy as np
from imgmeasure import (
    LIT,
    WHITE,
    box,
    col_pitch,
    dilate,
    distance_rings,
    ink_columns,
    row_pitch_and_columns,
    stroke_width,
)
from PIL import Image, ImageSequence

ROOT = os.path.join(HERE, "..", "..", "assets", "reference")

# file -> (x0, y0, x1, y1) crop as fractions of width/height, label
STILLS = {
    "matrix-1999-opening-bluray.jpg": ((0, 0, 1, 1), "opening rain, Blu-ray"),
    "matrix-1999-opening-4k.jpg": ((0, 0, 1, 1), "opening rain, 4K"),
    "matrix-1999-opening-trace-bluray.jpg": ((0, 0, 1, 1), "opening digit trace, Blu-ray"),
    "matrix-1999-opening-trace-4k.jpg": ((0, 0, 1, 1), "opening digit trace, 4K"),
    "matrix-1999-digit-closeup-4k.jpg": ((0, 0, 1, 1), "opening digit close-up, 4K"),
    "matrix-1999-cypher-monitors-4k.jpg": ((0.0, 0.1, 0.38, 0.7), "Cypher's code monitors, 4K"),
    "matrix-1999-operator-closeup-4k.jpg": ((0, 0, 1, 1), "operator screen close-up, 4K"),
    "matrix-1999-operator-screens-bluray.jpg": (
        (0.32, 0.03, 0.57, 0.30),
        "Nebuchadnezzar operator screens, Blu-ray",
    ),
    "matrix-1999-operator-screens-end-4k.jpg": (
        (0.03, 0.12, 0.58, 0.72),
        "operator screens in the finale, 4K",
    ),
    "matrix-1999-neo-monitor-bluray.jpg": ((0.05, 0.08, 0.95, 0.95), "Neo's monitor, Blu-ray"),
    "matrix-1999-system-failure-bluray.jpg": ((0, 0, 1, 1), "system failure readout, Blu-ray"),
    "matrix-1999-system-failure-4k.jpg": ((0, 0, 1, 1), "system failure readout, 4K"),
    "matrix-1999-neo-sees-code-bluray.jpg": ((0, 0, 1, 1), "Neo sees the code, Blu-ray"),
    "matrix-1999-neo-sees-code-4k.jpg": ((0, 0, 1, 1), "Neo sees the code, 4K"),
    # Reloaded / Revolutions (2003), design/film-reference-reloaded.md. Title frames
    # are cropped to the rain beside or below the title letters.
    "matrix-2003-revolutions-title-the-matrix-4k.jpg": (
        (0, 0, 0.38, 1),
        "Revolutions title, rain beside THE MATRIX, 4K",
    ),
    "matrix-2003-revolutions-title-the-matrix-wide-4k.jpg": (
        (0, 0, 0.38, 1),
        "Revolutions title, THE MATRIX larger, rain at left, 4K",
    ),
    "matrix-2003-revolutions-title-matrix-4k.jpg": (
        (0, 0.6, 1, 1),
        "Revolutions title, MATRIX zoom, rain below letters, 4K",
    ),
    "matrix-2003-revolutions-title-revolutions-4k.jpg": (
        (0, 0, 0.35, 1),
        "Revolutions title, rain beside REVOLUTIONS, 4K",
    ),
    "matrix-2003-revolutions-title-revolutions-zoom-4k.jpg": (
        (0, 0.62, 1, 1),
        "Revolutions title, zoom, rain below letters, 4K",
    ),
    "matrix-2003-revolutions-title-letters-4k.jpg": (
        (0, 0.65, 1, 1),
        "Revolutions title, big letters, rain strip, 4K",
    ),
    "matrix-2003-revolutions-title-letter-close-4k.jpg": (
        (0, 0, 1, 1),
        "Revolutions title, rain texture inside a letter, 4K",
    ),
    "matrix-2003-revolutions-rain-close-4k.jpg": ((0, 0, 1, 1), "full-frame rain, near camera, 4K"),
    "matrix-2003-revolutions-rain-mid-4k.jpg": ((0, 0, 1, 1), "full-frame rain, mid distance, 4K"),
    "matrix-2003-revolutions-rain-field-4k.jpg": ((0.1, 0, 0.9, 1), "full-frame rain field, 4K"),
    "matrix-2003-revolutions-rain-field-wide-4k.jpg": (
        (0.05, 0, 0.9, 1),
        "full-frame rain field, wide, 4K",
    ),
    "matrix-2003-revolutions-rain-pan-4k.jpg": ((0, 0, 1, 1), "rain field in a pan, 4K"),
    "matrix-2003-revolutions-zion-monitor-4k.jpg": (
        (0.81, 0.58, 0.95, 0.95),
        "Zion operator monitor, 4K",
    ),
    "matrix-2003-reloaded-trinity-code-face-bluray.jpg": (
        (0, 0, 1, 1),
        "Reloaded opening, code face, Blu-ray grade",
    ),
    # 2021 film (design/film-reference-resurrections.md). "file@part" measures one crop of a
    # file; the trailer frames are letterboxed (picture rows 0.13 to 0.87 of 1080).
    "matrix-2021-street-rain-filmgrab.jpg@facade-left": (
        (0.0, 0.0, 0.2, 0.8),
        "2021 street rain, left facade, film-grab",
    ),
    "matrix-2021-street-rain-filmgrab.jpg@facade-right": (
        (0.72, 0.0, 1.0, 0.6),
        "2021 street rain, right facade, film-grab",
    ),
    "matrix-2021-street-rain-filmgrab.jpg@floor": (
        (0.2, 0.8, 0.8, 1.0),
        "2021 street rain, floor, film-grab",
    ),
    "matrix-2021-street-rain-a-trailer1080.jpg@facade-left": (
        (0.0, 0.16, 0.2, 0.80),
        "2021 street rain, left facade, trailer 1 a",
    ),
    "matrix-2021-street-rain-a-trailer1080.jpg@facade-right": (
        (0.72, 0.16, 1.0, 0.60),
        "2021 street rain, right facade, trailer 1 a",
    ),
    "matrix-2021-street-rain-a-trailer1080.jpg@floor": (
        (0.2, 0.78, 0.8, 0.87),
        "2021 street rain, floor, trailer 1 a",
    ),
    "matrix-2021-street-rain-b-trailer1080.jpg@facade-left": (
        (0.0, 0.16, 0.2, 0.80),
        "2021 street rain, left facade, trailer 1 b",
    ),
    "matrix-2021-street-rain-b-trailer1080.jpg@facade-right": (
        (0.72, 0.16, 1.0, 0.60),
        "2021 street rain, right facade, trailer 1 b",
    ),
    "matrix-2021-street-rain-b-trailer1080.jpg@floor": (
        (0.2, 0.78, 0.8, 0.87),
        "2021 street rain, floor, trailer 1 b",
    ),
    "matrix-2021-street-rain-c-trailer1080.jpg@facade-left": (
        (0.0, 0.16, 0.2, 0.80),
        "2021 street rain, left facade, trailer 1 c",
    ),
    "matrix-2021-street-rain-c-trailer1080.jpg@facade-right": (
        (0.72, 0.16, 1.0, 0.60),
        "2021 street rain, right facade, trailer 1 c",
    ),
    "matrix-2021-street-rain-c-trailer1080.jpg@floor": (
        (0.2, 0.78, 0.8, 0.87),
        "2021 street rain, floor, trailer 1 c",
    ),
    "matrix-2021-street-rain-d-trailer1080.jpg@facade-left": (
        (0.0, 0.16, 0.2, 0.80),
        "2021 street rain, left facade, trailer 1 d",
    ),
    "matrix-2021-street-rain-d-trailer1080.jpg@facade-right": (
        (0.72, 0.16, 1.0, 0.60),
        "2021 street rain, right facade, trailer 1 d",
    ),
    "matrix-2021-street-rain-d-trailer1080.jpg@floor": (
        (0.2, 0.78, 0.8, 0.87),
        "2021 street rain, floor, trailer 1 d",
    ),
    "matrix-2021-street-rain-e-trailer1080.jpg@facade-left": (
        (0.0, 0.16, 0.2, 0.80),
        "2021 street rain, left facade, trailer 2 e",
    ),
    "matrix-2021-street-rain-e-trailer1080.jpg@facade-right": (
        (0.72, 0.16, 1.0, 0.60),
        "2021 street rain, right facade, trailer 2 e",
    ),
    "matrix-2021-street-rain-e-trailer1080.jpg@floor": (
        (0.2, 0.78, 0.8, 0.87),
        "2021 street rain, floor, trailer 2 e",
    ),
    "matrix-2021-street-rain-f-trailer1080.jpg@facade-left": (
        (0.0, 0.16, 0.2, 0.80),
        "2021 street rain, left facade, trailer 2 f",
    ),
    "matrix-2021-street-rain-f-trailer1080.jpg@facade-right": (
        (0.72, 0.16, 1.0, 0.60),
        "2021 street rain, right facade, trailer 2 f",
    ),
    "matrix-2021-street-rain-f-trailer1080.jpg@floor": (
        (0.2, 0.78, 0.8, 0.87),
        "2021 street rain, floor, trailer 2 f",
    ),
    "matrix-2021-street-rain-g-trailer1080.jpg@facade-left": (
        (0.0, 0.16, 0.2, 0.80),
        "2021 street rain, left facade, trailer 2 g",
    ),
    "matrix-2021-street-rain-g-trailer1080.jpg@facade-right": (
        (0.72, 0.16, 1.0, 0.60),
        "2021 street rain, right facade, trailer 2 g",
    ),
    "matrix-2021-street-rain-g-trailer1080.jpg@floor": (
        (0.2, 0.78, 0.8, 0.87),
        "2021 street rain, floor, trailer 2 g",
    ),
    "matrix-2021-code-tunnel-trailer1080.jpg@all": (
        (0, 0.13, 1, 0.87),
        "2021 code tunnel, trailer 1",
    ),
    "matrix-2021-endcard-rain-a-trailer1080.jpg@all": (
        (0, 0.13, 1, 0.87),
        "2021 end card rain, trailer 1",
    ),
    "matrix-2021-endcard-rain-b-trailer1080.jpg@all": (
        (0, 0.13, 1, 0.87),
        "2021 end card rain, trailer 2",
    ),
    "matrix-2021-glass-glyph-logo-trailer1080.jpg@all": (
        (0, 0.13, 1, 0.87),
        "2021 glass glyph logo, trailer 1",
    ),
}
GIFS = [
    "carlnewton-01-opening.gif",
    "carlnewton-05-changing.gif",
    "carlnewton-07-highlight.gif",
    "carlnewton-08-stammer.gif",
]


def load(name, crop=(0, 0, 1, 1)):
    im = Image.open(os.path.join(ROOT, name)).convert("RGB")
    w, h = im.size
    x0, y0, x1, y1 = crop
    im = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
    return np.asarray(im).astype(np.float32)


def hsv_of(rgb):
    h, s, v = colorsys.rgb_to_hsv(*(np.asarray(rgb) / 255.0))
    return h * 360, s, v


def hexc(rgb):
    return "#%02X%02X%02X" % tuple(min(255, int(round(c))) for c in rgb)


def geometry(a, full_w, full_h):
    """Per-frame numbers for design/film-reference.md "Glyph size and clarity":
    column grid pitch, columns across 1915 px, row pitch, cell as a share of the
    frame, stroke width, lit fraction. `a` is the cropped RGB array, `full_w` and
    `full_h` the whole frame in px; lengths are returned at 1915 px frame width."""
    mx = a.max(-1)
    scale = 1915.0 / full_w
    cpx, strength = col_pitch(mx, scale)
    rp, _n, sp = row_pitch_and_columns(mx, max(4, int(8 / scale)), int(60 / scale))
    sw, fill, longs = stroke_width(mx, scale)
    return dict(
        col_pitch=cpx * scale,
        strength=strength,
        cols_1915=1915.0 / (cpx * scale),
        row_pitch=rp * scale,
        cell_w_frac=cpx / full_w,
        cell_h_frac=rp / full_h,
        stroke=sw * scale,
        fill=fill,
        long=longs,
        lit=float((mx > LIT).mean()),
        ink_spacing=sp * scale,
        ink_cols=ink_columns(mx, scale),
    )


def still(name, crop, label):
    a = load(name, crop)
    height, width = a.shape[:2]
    scale = 1915.0 / Image.open(os.path.join(ROOT, name)).size[0]  # px at Blu-ray width
    mx = a.max(-1)
    lit = mx > LIT
    print(f"\n== {name}  ({label})  crop {width}x{height}")
    bg = a[mx < 25]
    bg_median = hexc(np.median(bg, 0)) if len(bg) else "-"
    bg_mean = np.round(bg.mean(0), 1) if len(bg) else "-"
    print(f"background median {bg_median}  mean {bg_mean}")
    print(f"lit fraction (max>{LIT}) {lit.mean():.3f}")
    lit_px = a[lit]
    if len(lit_px) == 0:
        return
    hs = np.array([hsv_of(c) for c in lit_px[:: max(1, len(lit_px) // 20000)]])
    print(
        f"lit hue median {np.median(hs[:, 0]):.0f} "
        f"(IQR {np.percentile(hs[:, 0], 25):.0f}-{np.percentile(hs[:, 0], 75):.0f})"
        f"  sat median {np.median(hs[:, 1]):.2f}"
    )
    print("tone ramp by max channel:")
    for lo, hi in [(40, 80), (80, 120), (120, 160), (160, 200), (200, 230), (230, 256)]:
        m = (mx >= lo) & (mx < hi)
        if m.sum() < 20:
            continue
        c = a[m].mean(0)
        h, s, v = hsv_of(c)
        print(
            f"  {lo:3d}-{hi:3d}: {hexc(c)}  hue {h:4.0f} sat {s:.2f}  "
            f"share {m.sum() / lit.sum():.3f}  R/G {c[0] / max(c[1], 1):.2f}"
        )
    white = a.min(-1) > WHITE
    print(
        f"near-white pixels / lit pixels {white.sum() / lit.sum():.4f}"
        + (f"  white mean {hexc(a[white].mean(0))}" if white.sum() > 20 else "")
    )
    # cell pitch from autocorrelation of lit columns and rows
    lo_px = max(4, int(8 / scale))
    hi_px = int(60 / scale)
    rp, ncols, cp = row_pitch_and_columns(mx, lo_px, hi_px)
    print(
        f"row pitch (vertical autocorrelation inside ink columns) {rp:.1f} px = "
        f"{rp * scale:.1f} px at 1915 wide; {ncols} ink columns across the crop, mean column "
        f"spacing {cp:.1f} px = {cp * scale:.1f} px "
        f"({ncols / (width * scale) * 1915:.0f} per 1915 px)"
    )
    if not np.isfinite(cp):
        cp = 24.5 / scale
    full_w, full_h = Image.open(os.path.join(ROOT, name)).size
    g = geometry(a, full_w, full_h)
    print(
        f"geometry: column pitch {g['col_pitch']:.1f} px (strength {g['strength']:.2f}) = "
        f"{g['cols_1915']:.0f} columns per 1915 px, row pitch {g['row_pitch']:.1f} px, "
        f"cell {g['cell_w_frac'] * 100:.2f}% of width x {g['cell_h_frac'] * 100:.2f}% of "
        f"height, horizontal stroke FWHM {g['stroke']:.1f} px at 1915 wide, "
        f"fill {g['fill']:.2f}, long-run share {g['long']:.2f}"
    )
    top = a[mx >= np.percentile(mx, 99.5)]
    print(
        f"brightest 0.5% of pixels, mean colour {hexc(top.mean(0))} "
        "(the head colour when leaders are not white)"
    )
    if np.isfinite(rp) and rp > 0:
        # trail length: vertical runs of lit pixels in a strip around each ink column, gaps under
        # 0.7 row bridged (glyph strokes leave gaps inside a lit cell), in rows
        prof = mx.mean(0)
        w = max(1, int(cp * 0.15)) if np.isfinite(cp) else 2
        br = max(1, int(rp * 0.35))
        runs = []
        step = max(1, int(cp) if np.isfinite(cp) else 6)
        for x in np.where(prof > np.percentile(prof, 70))[0][::step]:
            col = lit[:, max(0, x - w) : x + w + 1].any(-1).astype(np.float32)
            col = box(col[:, None], br)[:, 0] > 0.0
            n = 0
            for v in list(col) + [False]:
                if v:
                    n += 1
                elif n:
                    runs.append(n / rp)
                    n = 0
        runs = [r for r in runs if r > 1.5]
        if runs:
            print(
                "lit run length along ink columns (rows, runs over 1.5 rows): "
                f"median {np.median(runs):.1f}, p25 {np.percentile(runs, 25):.1f}, "
                f"p75 {np.percentile(runs, 75):.1f}, n {len(runs)}"
            )
    # halation: profile of max channel outside bright ink, by distance in px
    for nm, ink in (("leader", white), ("bright glyph", mx > 200)):
        if ink.sum() < 50:
            continue
        nmax = int(max(cp, 10) * 1.5)
        dist = distance_rings(ink, nmax)
        prof = [float(np.median(mx[dist == d])) for d in range(0, nmax + 1)]
        floor = float(np.median(mx[mx < 25])) if (mx < 25).any() else 0.0
        peak = prof[0]
        norm = [(v - floor) / max(peak - floor, 1) for v in prof]
        d50 = next((d for d, v in enumerate(norm) if v < 0.5), nmax)
        d10 = next((d for d, v in enumerate(norm) if v < 0.1), nmax)
        d03 = next((d for d, v in enumerate(norm) if v < 0.03), nmax)
        print(
            f"halo outside {nm} ink: 50% at {d50} px, 10% at {d10} px, 3% at {d03} px"
            f" (= {d10 / cp:.2f}, {d03 / cp:.2f} cell widths); profile "
            + " ".join(f"{v:.2f}" for v in norm[: min(len(norm), 16)])
        )
    # edge softness: contrast over max gradient around bright ink
    g = mx
    gx = np.abs(np.diff(g, axis=1))[:-1, :]
    gy = np.abs(np.diff(g, axis=0))[:, :-1]
    grad = np.maximum(gx, gy)
    edge = dilate(mx > 120, 2)[:-1, :-1] & ~(mx > 120)[:-1, :-1] | (mx > 120)[:-1, :-1]
    local_max = np.maximum.reduce(
        [np.roll(np.roll(g, i, 0), j, 1) for i in (-3, 0, 3) for j in (-3, 0, 3)]
    )[:-1, :-1]
    sel = edge & (local_max > 150)
    if sel.sum() > 100:
        width = (local_max[sel] - 20) / np.maximum(np.percentile(grad[sel], 90), 1)
        print(
            f"edge 10-90 width estimate {np.median(width) * 0.8 * scale:.1f} px at 1915 wide "
            f"(max gradient {np.percentile(grad[sel], 90):.0f}/px native)"
        )
    # grain: residual std in dark background far from ink, and on flat bright ink
    far = ~dilate(lit, int(max(cp, 6)))
    if far.sum() > 1000:
        res = [a[..., c] - box(a[..., c], 3) for c in range(3)]
        print(
            "grain in background (residual std R G B): "
            + " ".join(f"{r[far].std():.2f}" for r in res)
        )
    inner = (mx > 120) & ~dilate(mx <= 120, 1)
    if inner.sum() > 500:
        g2 = a[..., 1] - box(a[..., 1], 2)
        relative = g2[inner].std() / a[..., 1][inner].mean()
        print(
            f"grain inside glyph ink (green residual std) {g2[inner].std():.2f}  "
            f"relative {relative:.3f}"
        )


def frames(name):
    im = Image.open(os.path.join(ROOT, name))
    return [np.asarray(f.convert("RGB")).astype(np.float32) for f in ImageSequence.Iterator(im)]


def motion(name):
    """Pixel-based motion measures; the gifs are downscaled film frames."""
    fr = frames(name)
    height, width = fr[0].shape[:2]
    maxch = np.array([f.max(-1) for f in fr])
    print(f"\n== {name}  {len(fr)} frames {width}x{height}")
    mean = maxch.mean(0)
    rp, ncols, cp = row_pitch_and_columns(mean, 4, 24)
    print(f"row pitch {rp:.1f} px, {ncols} ink columns, column spacing {cp:.1f} px")
    lit = maxch > 70
    # glyph change: inside cells lit in both frames, share of ink pixels that change strongly
    cell = max(3, int(rp / 2)) if np.isfinite(rp) else 4
    ch = []
    for t in range(1, len(fr)):
        both = (box(lit[t].astype(np.float32), cell) > 0.15) & (
            box(lit[t - 1].astype(np.float32), cell) > 0.15
        )
        ink = both & (lit[t] | lit[t - 1])
        if ink.sum() < 50:
            ch.append(float("nan"))
            continue
        ch.append(float((np.abs(maxch[t] - maxch[t - 1])[ink] > 60).mean()))
    ch = np.array(ch)
    ok = np.isfinite(ch)
    if ok.any():
        print(
            "ink change share per frame: "
            + " ".join("-" if not np.isfinite(c) else f"{c:.2f}" for c in ch)
        )
        c = ch[ok] - ch[ok].mean()
        if len(c) > 8:
            ac = np.correlate(c, c, "full")[len(c) - 1 :]
            ac /= ac[0] + 1e-9
            per = 2 + int(np.argmax(ac[2:8]))
            print(
                f"  mean {ch[ok].mean():.2f}; autocorrelation peak at lag {per} frames "
                f"(value {ac[per]:.2f})"
            )
    # heads: lowest lit pixel in each column strip, frame to frame
    if np.isfinite(cp):
        prof = mean.mean(0)
        sm = np.convolve(prof, np.ones(3) / 3, "same")
        floor = np.percentile(sm, 60)
        xs = [
            x
            for x in range(1, width - 1)
            if sm[x] >= sm[x - 1] and sm[x] >= sm[x + 1] and sm[x] > floor
        ]
        steps = []
        for x in xs:
            strip = lit[:, :, max(0, x - 1) : x + 2].any(-1)
            prev = None
            for t in range(len(fr)):
                ys = np.where(strip[t])[0]
                y = ys.max() if len(ys) else None
                if prev is not None and y is not None and y < height - 2:
                    d = y - prev
                    if 0 <= d <= 3 * rp:
                        steps.append(d / rp)
                prev = y
        if steps:
            s = np.round(np.array(steps) * 2) / 2
            vals, cnt = np.unique(s, return_counts=True)
            advance = ", ".join(f"{v:g}: {n / len(s):.2f}" for v, n in zip(vals, cnt, strict=True))
            print(
                f"head advance per frame in rows: {advance}; mean {np.mean(steps):.2f} "
                f"rows/frame = {np.mean(steps) * 24:.0f} rows/s at 24 fps"
            )
    white = np.array([f.min(-1) > 150 for f in fr])
    print(f"near-white pixels / lit pixels {white.sum() / max(lit.sum(), 1):.3f}")
    wl = [white[t].any(0) for t in range(len(fr))]
    ll = [lit[t].any(0) for t in range(len(fr))]
    print(
        "share of lit x positions that also hold near-white ink "
        f"{np.sum(wl) / max(np.sum(ll), 1):.3f}"
    )


def table(names):
    """One tab-separated row per still: the geometry (design/film-reference.md "Glyph size and
    clarity"). Lengths in px at 1915 wide."""
    print(
        "\t".join(
            [
                "still",
                "col_pitch",
                "strength",
                "cols_1915",
                "ink_spacing",
                "row_pitch",
                "cell_w_pct",
                "cell_h_pct",
                "stroke",
                "fill",
                "long",
                "ink_cols",
                "lit",
            ]
        )
    )
    for n, (crop, _label) in STILLS.items():
        fn = n.split("@")[0]
        missing = not os.path.exists(os.path.join(ROOT, fn))
        if (names and n not in names and fn not in names) or missing:
            continue
        a = load(fn, crop)
        fw, fh_ = Image.open(os.path.join(ROOT, fn)).size
        g = geometry(a, fw, fh_)
        print(
            "\t".join(
                [
                    fn,
                    f"{g['col_pitch']:.1f}",
                    f"{g['strength']:.2f}",
                    f"{g['cols_1915']:.0f}",
                    f"{g['ink_spacing']:.1f}",
                    f"{g['row_pitch']:.1f}",
                    f"{g['cell_w_frac'] * 100:.2f}",
                    f"{g['cell_h_frac'] * 100:.2f}",
                    f"{g['stroke']:.1f}",
                    f"{g['fill']:.2f}",
                    f"{g['long']:.2f}",
                    f"{g['ink_cols']:.0f}",
                    f"{g['lit']:.3f}",
                ]
            )
        )


def main():
    names = [n for n in sys.argv[1:] if n != "--table"]
    if "--table" in sys.argv:
        table(names)
        return
    for n, (crop, label) in STILLS.items():
        fn = n.split("@")[0]
        if (not names or n in names or fn in names) and os.path.exists(os.path.join(ROOT, fn)):
            still(fn, crop, label)
    for n in GIFS:
        if (not names or n in names) and os.path.exists(os.path.join(ROOT, n)):
            motion(n)


if __name__ == "__main__":
    main()
