"""Grid-mode pictures of one folder on this machine: depth maps, renders, a sheet and numbers.

    <venv python> tools/dev/grid_sheet.py run FOLDER OUT [--preset film_1999] [--size 1440x932]
    <venv python> tools/dev/grid_sheet.py compare OUT_A OUT_B

run: works out each picture's depth with the network this machine has (Core ML on macOS, ONNX on
Windows), renders it in grid mode 20 s in (one process per picture: the picture is prepared in
the background and the frame harness renders only at the times it is given), and writes to OUT:

- depth/<picture>.npz: the disparity map, as cached by surfaces.fill_cache
- renders/NN.png: the grid-mode frame of picture NN (sorted file order)
- sheet.png: each picture over its render, five pairs a row
- results.csv: backend, picture and render brightness (mean 0..1), legibility (correlation of
  32x18 block brightness of the render against the picture; 1 means the picture's light layout
  reads in full), and the depth map's mean and near share (disparity above 0.5)

compare: the same pictures from two runs (say Windows ONNX and macOS Core ML): correlation of
the two depth maps, difference in near share and in render brightness, per picture and overall.

The depth cache goes to OUT/cache (MATRIX_SURFACE_CACHE), so a run never reads another run's maps.
"""

import argparse
import csv
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "checks"))

EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
TIMES = [8.0, 20.0]  # the first frame starts the picture's preparation, the second is kept
BLOCKS = (32, 18)
TILE = (384, 248)
COLUMNS = 5


def _pictures(folder):
    return sorted(n for n in os.listdir(folder) if n.lower().endswith(EXTENSIONS))


def _blocks(lum):

    bw, bh = BLOCKS
    h, w = lum.shape
    lum = lum[: h // bh * bh, : w // bw * bw]
    return lum.reshape(bh, lum.shape[0] // bh, bw, lum.shape[1] // bw).mean(axis=(1, 3))


def _cover(rgb, width, height):
    """Centre crop of rgb to the width:height aspect (the saver fills the screen)."""
    h, w = rgb.shape[:2]
    if w / h > width / height:
        cw = int(h * width / height)
        return rgb[:, (w - cw) // 2 : (w - cw) // 2 + cw]
    ch = int(w * height / width)
    return rgb[(h - ch) // 2 : (h - ch) // 2 + ch]


def _save_png(arr, path):
    import pygame

    pygame.image.save(pygame.surfarray.make_surface(arr.swapaxes(0, 1).copy()), path)


def _load_png(path):
    import pygame

    return pygame.surfarray.array3d(pygame.image.load(path)).swapaxes(0, 1)


def one(folder, out, preset, size):
    """Child process: render the single picture in `folder` and print one result line."""
    import frame_harness
    import numpy as np

    width, height = size
    cfg = frame_harness.case_cfg(
        ROOT, preset, image_dir=folder, image_mode="grid", image_period=60.0, image_gap=0.0
    )
    from digital_rain import image_layer

    name = _pictures(folder)[0]
    rgb = image_layer.load_rgb(os.path.join(folder, name), 1024)
    frame = frame_harness.gpu_frames(ROOT, cfg, (width, height), TIMES)[-1]
    _save_png(frame, out)
    a = _blocks(_cover(rgb, width, height).astype(np.float32).mean(axis=2)).ravel()
    b = _blocks(frame.astype(np.float32).mean(axis=2)).ravel()
    legible = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0
    print("RESULT %.4f %.4f %.4f" % (rgb.mean() / 255, frame.mean() / 255, legible))


def run(folder, out, preset, size):
    os.makedirs(out, exist_ok=True)
    cache = os.path.join(out, "cache")
    os.environ["MATRIX_SURFACE_CACHE"] = cache
    import numpy as np

    from digital_rain import image_layer, surfaces

    backend = surfaces._backend()
    print("depth backend:", backend)
    names = _pictures(folder)
    for sub in ("depth", "renders", "single"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    rows = []
    for i, name in enumerate(names):
        # a folder of its own per picture, so the show holds just this one
        single = os.path.join(out, "single", "%02d" % i)
        os.makedirs(single, exist_ok=True)
        picture = os.path.join(single, name)
        if not os.path.exists(picture):
            shutil.copy2(os.path.join(folder, name), picture)
        mean_d = near = float("nan")
        if backend and surfaces.fill_cache(picture, image_layer.load_rgb):
            shutil.copy(surfaces._cached_file(picture), os.path.join(out, "depth", name + ".npz"))
            d = surfaces._load_cached(picture)
            mean_d, near = float(d.mean()), float((d > 0.5).mean())
        render = os.path.join(out, "renders", "%02d.png" % i)
        child = subprocess.run(
            [
                sys.executable,
                __file__,
                "one",
                single,
                render,
                "--preset",
                preset,
                "--size",
                "%dx%d" % size,
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
        )
        line = [x for x in child.stdout.splitlines() if x.startswith("RESULT")]
        if not line:
            print("%02d %s: render failed\n%s" % (i, name, child.stderr[-2000:]))
            continue
        orig, rendered, legible = (float(x) for x in line[0].split()[1:])
        rows.append([i, name, backend, orig, rendered, legible, mean_d, near])
        print(
            "%02d %-28s picture %.3f  render %.3f  legible %.2f  near %.2f"
            % (i, name, orig, rendered, legible, near)
        )
    with open(os.path.join(out, "results.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "n",
                "picture",
                "backend",
                "picture_mean",
                "render_mean",
                "legible",
                "depth_mean",
                "near_share",
            ]
        )
        w.writerows(rows)
    renders = [r[4] for r in rows]
    if renders:
        print(
            "render brightness %.3f..%.3f (mean %.3f), legible mean %.2f"
            % (min(renders), max(renders), np.mean(renders), np.mean([r[5] for r in rows]))
        )
    _sheet(folder, names, out)


def _sheet(folder, names, out):
    import numpy as np
    import pygame

    from digital_rain import image_layer

    tw, th = TILE

    def fit(arr):
        arr = _cover(arr, tw, th)
        surf = pygame.surfarray.make_surface(np.ascontiguousarray(arr.swapaxes(0, 1)))
        return pygame.surfarray.array3d(pygame.transform.smoothscale(surf, (tw, th))).swapaxes(0, 1)

    rows = (len(names) + COLUMNS - 1) // COLUMNS
    sheet = np.full((rows * (2 * th + 12), COLUMNS * (tw + 6), 3), 40, np.uint8)
    for i, name in enumerate(names):
        r, c = divmod(i, COLUMNS)
        y, x = r * (2 * th + 12), c * (tw + 6)
        sheet[y : y + th, x : x + tw] = fit(image_layer.load_rgb(os.path.join(folder, name), 1024))
        render = os.path.join(out, "renders", "%02d.png" % i)
        if os.path.exists(render):
            sheet[y + th : y + 2 * th, x : x + tw] = fit(_load_png(render))
    _save_png(sheet, os.path.join(out, "sheet.png"))
    print("sheet:", os.path.join(out, "sheet.png"))


def _read(out):
    with open(os.path.join(out, "results.csv"), newline="") as fh:
        return {r["picture"]: r for r in csv.DictReader(fh)}


def compare(out_a, out_b):
    import numpy as np

    a, b = _read(out_a), _read(out_b)
    names = [n for n in a if n in b]
    print(
        "A: %s (%s)   B: %s (%s)" % (out_a, a[names[0]]["backend"], out_b, b[names[0]]["backend"])
    )
    corrs, near_diffs, render_diffs = [], [], []
    for name in names:
        da = np.load(os.path.join(out_a, "depth", name + ".npz"))["disparity"].astype(np.float32)
        db = np.load(os.path.join(out_b, "depth", name + ".npz"))["disparity"].astype(np.float32)
        if da.shape != db.shape:
            h, w = min(da.shape[0], db.shape[0]), min(da.shape[1], db.shape[1])
            da, db = da[:h, :w], db[:h, :w]
        corr = float(np.corrcoef(da.ravel(), db.ravel())[0, 1])
        near_diff = float(a[name]["near_share"]) - float(b[name]["near_share"])
        render_diff = float(a[name]["render_mean"]) - float(b[name]["render_mean"])
        corrs.append(corr)
        near_diffs.append(near_diff)
        render_diffs.append(render_diff)
        print(
            "%-28s depth corr %.2f  near A-B %+.2f  render A-B %+.3f"
            % (name, corr, near_diff, render_diff)
        )
    print(
        "overall: depth corr mean %.2f (min %.2f), near A-B mean %+.2f, render A-B mean %+.3f"
        % (np.mean(corrs), np.min(corrs), np.mean(near_diffs), np.mean(render_diffs))
    )


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("run", "one"):
        s = sub.add_parser(name)
        s.add_argument("folder")
        s.add_argument("out")
        s.add_argument("--preset", default="film_1999")
        s.add_argument("--size", default="1440x932")
    c = sub.add_parser("compare")
    c.add_argument("out_a")
    c.add_argument("out_b")
    args = p.parse_args()
    if args.cmd == "compare":
        compare(args.out_a, args.out_b)
        return
    size = tuple(int(x) for x in args.size.lower().split("x"))
    (run if args.cmd == "run" else one)(args.folder, args.out, args.preset, size)


if __name__ == "__main__":
    main()
