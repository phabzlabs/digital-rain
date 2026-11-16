"""Measure a saver screenshot.

Usage: <venv python> tools/checks/shot_stats.py <png> [--cell 20x28] [--crop X,Y,W,H]
--crop measures only that pixel rectangle (top-left origin).
Prints: floor=(r,g,b) lit=<f> hue=<deg> parity=<f> corr_v=<f> corr_h=<f> corr_d=<f>

floor  per-channel median of the darkest 2 percent of pixels (by max channel)
lit    fraction of pixels with max channel >= 60
hue    median HSV hue (degrees) of pixels with max channel >= 60 and saturation >= 0.25
parity mean luminance of even pixel rows / odd pixel rows
corr_* Pearson correlation of the cell-block grid of bright pixels (max channel
       >= 120, block mean > 0.15) with itself shifted down (v), right (h), down-right (d)
"""

import os
import sys

import numpy as np
import pygame
from imgmeasure import scanline_parity


def load(path):
    surf = pygame.image.load(path)
    return pygame.surfarray.array3d(surf).transpose(1, 0, 2).astype(np.float32)  # h, w, 3


def floor_of(img):
    mx = img.max(axis=2).ravel()
    flat = img.reshape(-1, 3)
    n = max(1, int(len(mx) * 0.02))
    idx = np.argsort(mx, kind="stable")[:n]
    return tuple(int(round(v)) for v in np.median(flat[idx], axis=0))


def hue_of(img):
    mx = img.max(axis=2)
    mn = img.min(axis=2)
    sel = (mx >= 60) & ((mx - mn) / np.maximum(mx, 1) >= 0.25)
    if not sel.any():
        return float("nan")
    r, g, b = (img[..., i][sel] for i in range(3))
    mxs, d = mx[sel], (mx[sel] - mn[sel])
    h = (
        np.where(mxs == r, ((g - b) / d) % 6, np.where(mxs == g, (b - r) / d + 2, (r - g) / d + 4))
        * 60.0
    )
    return float(np.median(h))


def corr(a, b):
    a, b = a.ravel(), b.ravel()
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def measure(img, cell=(20, 28)):
    h, w = img.shape[:2]
    mx = img.max(axis=2)
    cw, ch = cell
    gw, gh = w // cw, h // ch
    mask = (mx[: gh * ch, : gw * cw] >= 120).astype(np.float32)
    grid = mask.reshape(gh, ch, gw, cw).mean(axis=(1, 3)) > 0.15
    g = grid.astype(np.float32)
    return dict(
        floor=floor_of(img),
        lit=float((mx >= 60).mean()),
        hue=hue_of(img),
        parity=scanline_parity(img),
        corr_v=corr(g[:-1, :], g[1:, :]),
        corr_h=corr(g[:, :-1], g[:, 1:]),
        corr_d=corr(g[:-1, :-1], g[1:, 1:]),
    )


def main(argv):
    cell = (20, 28)
    if "--cell" in argv:
        i = argv.index("--cell")
        cell = tuple(int(v) for v in argv[i + 1].lower().split("x"))
        del argv[i : i + 2]
    crop = None
    if "--crop" in argv:
        i = argv.index("--crop")
        crop = tuple(int(v) for v in argv[i + 1].split(","))
        del argv[i : i + 2]
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.display.init()
    img = load(argv[0])
    if crop:
        x, y, w, h = crop
        img = img[y : y + h, x : x + w]
    m = measure(img, cell)
    print(
        "floor=({},{},{}) lit={:.4f} hue={:.1f} parity={:.3f} corr_v={:.3f} "
        "corr_h={:.3f} corr_d={:.3f}".format(
            *m["floor"], m["lit"], m["hue"], m["parity"], m["corr_v"], m["corr_h"], m["corr_d"]
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
