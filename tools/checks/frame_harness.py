"""Deterministic in-process frames of the saver, for golden-frame and look checks.

    gpu_frames(root, cfg, size, times)  -> [HxWx3 uint8]   (GLRenderer)
    soft_frames(root, cfg, size, times) -> [HxWx3 uint8]   (SoftRenderer)

`root` is the checkout to render (this repository, or a `git worktree` of an
older commit). It goes to the front of sys.path before any project import, and
this module never imports from the repository it lives in, so one harness can
render any revision. Every call:

- patches numpy.random.default_rng to return default_rng(1234) while the
  renderer is built and while it renders (seeds GLRenderer.rng, SoftRenderer.rng
  and every software Rain); soft_frames(..., run=N) skips the patch and seeds
  SoftRenderer with N instead;
- GPU: renders run value RUN (0, the fixed layout) unless `run` is given;
- uses one monitor dict(x=0, y=0, w=W, h=H, dpi=1.0, id="");
- GPU: a hidden pygame.OPENGL window with the GL 3.3 core attributes of
  matrix_saver._make_gl, three consecutive frames render(t, 1/60, round(t*60))
  ending at each listed time, the frame read from ctx.screen and flipped to
  top-down;
- software: a hidden window, 30 frames render(t0 + f/30, 1/30, round(t0*30) + f)
  ending at each listed time, the frame from pygame.surfarray.array3d.

cfg is used as given; `case_cfg(root, preset, **extra)` builds the cfg the
checks use (settings.DEFAULTS, the preset, easter_egg False, live and message
off).

Command line (writes PNG files for GPU frames, prints SHA-256 for software):

    <venv python> tools/checks/frame_harness.py --root <checkout> --out <dir> golden
    <venv python> tools/checks/frame_harness.py --root <checkout> --gpu|--soft
        --preset NAME --size WxH --time T [--upscaling off|quality] --out <dir>

The `golden` command renders the golden cases (GPU 1024x576 with upscaling off and quality,
software 800x600, t = 5 s) into <dir>: the resurrections preset by default, or the presets of
`--presets film_1999,reloaded,custom`, merging soft_hashes.json.

The GL window is kept between calls of the same size, so a gate that renders many frames opens
one window per size. A renderer is built per call because it bakes in its cfg.
"""

import argparse
import contextlib
import hashlib
import inspect
import json
import os
import sys
from unittest import mock

import numpy as np

# The picture layer prepares pictures inline, so frames do not depend on timing.
os.environ.setdefault("MATRIX_IMAGE_SYNC", "1")

SEED = 1234
RUN = 0  # GPU run value of every harness frame (0: the fixed layout)
GOLDEN_PRESETS = ("film_1999", "reloaded", "custom")
GOLDEN_NEW = ("resurrections",)  # a drift guard only: its goldens follow the look on purpose
# The GPU goldens and the film gates were recorded at glyph scale 1.0, not the default.
GPU_GLYPH_SCALE = 1.0
SOFT_GLYPH_SCALE = 0.75  # software goldens and checks were recorded at this glyph size
GOLDEN_GPU_SIZE = (1024, 576)
GOLDEN_SOFT_SIZE = (800, 600)
GOLDEN_TIME = 5.0


def _use_root(root):
    root = os.path.abspath(root)
    if sys.path[:1] != [root]:
        sys.path.insert(0, root)
    return root


def _seeded():
    real = np.random.default_rng
    return mock.patch("numpy.random.default_rng", side_effect=lambda *a, **k: real(SEED))


def _run_kw(cls, run, legacy):
    """{"run": run} for a renderer that takes it. An older checkout (--root) has no
    `run` parameter and only renders `legacy` (GPU 0, soft the seeded rng)."""
    if "run" in inspect.signature(cls.__init__).parameters:
        return {"run": run}
    if run != legacy:
        raise TypeError(f"{cls.__name__} at this root has no run parameter (run {run!r})")
    return {}


def case_cfg(root, preset, **extra):
    _use_root(root)
    from digital_rain import settings

    cfg = dict(settings.DEFAULTS)
    cfg.update(preset=preset, easter_egg=False, live_source="off", message="off")
    cfg.update(extra)
    return cfg


def _monitor(size):
    return [dict(x=0, y=0, w=size[0], h=size[1], dpi=1.0, id="")]


_gl_size = None


def _gl_window(size):
    """A hidden GL 3.3 core window of `size`; reused when the last call had the same size."""
    global _gl_size
    import pygame

    if _gl_size == size and pygame.display.get_surface() is not None:
        return
    pygame.display.init()
    pygame.font.init()
    for attr, val in (
        (pygame.GL_CONTEXT_MAJOR_VERSION, 3),
        (pygame.GL_CONTEXT_MINOR_VERSION, 3),
        (pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE),
    ):
        pygame.display.gl_set_attribute(attr, val)
    pygame.display.set_mode(size, pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
    _gl_size = size


def gpu_frames(root, cfg, size, times, frames=None, info=None, mons=None, run=RUN):
    """GPU frames at each time in `times`. `frames` optionally overrides the
    frame number of the last render call per time (the grain check uses it).
    `info` (a dict) receives the renderer's rain_grid(0) and glyph source; `mons`
    replaces the single monitor."""
    _use_root(root)
    width, height = size
    _gl_window(size)
    from digital_rain.gl_renderer import GLRenderer

    out = []
    with _seeded():
        r = GLRenderer(
            mons or _monitor(size), cfg, (0, 0), (width, height), **_run_kw(GLRenderer, run, 0)
        )
        try:
            for n, t in enumerate(times):
                for j in (2, 1, 0):
                    tt = t - j / 60
                    fr = round(tt * 60)
                    if j == 0 and frames is not None:
                        fr = frames[n]
                    r.render(tt, 1 / 60, fr)
                data = r.ctx.screen.read(viewport=(0, 0, width, height), components=3)
                img = np.frombuffer(data, np.uint8).reshape(height, width, 3)[::-1].copy()
                out.append(img)
            if info is not None:
                info.update(
                    grid=r.rain_grid(0),
                    glyph_source=r.glyph_source,
                    set_tiles=(r.atlas2_info[4] if r.atlas2_info else r.atlas_info[4]),
                    classic_tiles=r.atlas_info[4],
                )
        finally:
            r.close()
    return out


def soft_frames(root, cfg, size, times, run=None):
    _use_root(root)
    import pygame

    pygame.display.init()
    pygame.font.init()
    width, height = size
    screen = pygame.display.set_mode((width, height), pygame.HIDDEN)
    from digital_rain.soft_renderer import SoftRenderer

    out = []
    with _seeded() if run is None else contextlib.nullcontext():
        r = SoftRenderer(
            _monitor(size),
            cfg,
            (0, 0),
            (width, height),
            screen,
            **_run_kw(SoftRenderer, run, None),
            **(
                {"churn": False}
                if "churn" in inspect.signature(SoftRenderer.__init__).parameters
                else {}
            ),
        )
        try:
            for t in times:
                for f in range(30):
                    t0 = t - 29 / 30
                    r.render(t0 + f / 30, 1 / 30, round(t0 * 30) + f)
                out.append(pygame.surfarray.array3d(screen).transpose(1, 0, 2).copy())
        finally:
            r.close()
    return out


def sha(img):
    return hashlib.sha256(np.ascontiguousarray(img, np.uint8).tobytes()).hexdigest()


def gpu_name(preset, upscaling):
    return f"gpu_{preset}_{upscaling}.png"


def save_png(path, img):
    from PIL import Image

    Image.fromarray(img).save(path)


def load_png(path):
    from PIL import Image

    return np.asarray(Image.open(path).convert("RGB"))


def gpu_compare(a, b):
    """(share of pixels with any channel off by more than 1, max channel diff)."""
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return float((d.max(-1) > 1).mean()), int(d.max())


def first_difference(a, b):
    """Text for a failed comparison: where the frames first differ and by how much."""
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(-1)
    ys, xs = np.nonzero(d > 1)
    if len(ys) == 0:
        return "no pixel differs by more than 1"
    y, x = int(ys[0]), int(xs[0])
    return f"first differing pixel at x={x} y={y}: {a[y, x].tolist()} against {b[y, x].tolist()}"


def _golden(root, out, presets=GOLDEN_NEW):
    """GPU PNGs only for `presets`; soft hashes merged into <out>/soft_hashes.json
    (only the `soft_<preset>` keys of `presets` change)."""
    os.makedirs(out, exist_ok=True)
    for preset in presets:
        for up in ("off", "quality"):
            cfg = case_cfg(root, preset, upscaling=up, glyph_scale=GPU_GLYPH_SCALE)
            img = gpu_frames(root, cfg, GOLDEN_GPU_SIZE, [GOLDEN_TIME])[0]
            save_png(os.path.join(out, gpu_name(preset, up)), img)
            print("wrote", gpu_name(preset, up))
    path = os.path.join(out, "soft_hashes.json")
    hashes = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            hashes = json.load(f)
    for preset in presets:
        cfg = case_cfg(root, preset)
        img = soft_frames(root, cfg, GOLDEN_SOFT_SIZE, [GOLDEN_TIME])[0]
        hashes[f"soft_{preset}"] = sha(img)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=1, sort_keys=True)
    print(json.dumps(hashes, indent=1, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="one")
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default=".")
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--soft", action="store_true")
    ap.add_argument("--preset", default="film_1999")
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--time", type=float, default=5.0)
    ap.add_argument("--upscaling", default=None)
    ap.add_argument("--presets", default=",".join(GOLDEN_NEW))
    a = ap.parse_args()
    if a.cmd == "golden":
        _golden(a.root, a.out, tuple(a.presets.split(",")))
        return 0
    size = tuple(int(v) for v in a.size.lower().split("x"))
    extra = {} if a.upscaling is None else dict(upscaling=a.upscaling)
    cfg = case_cfg(a.root, a.preset, **extra)
    os.makedirs(a.out, exist_ok=True)
    if a.soft:
        img = soft_frames(a.root, cfg, size, [a.time])[0]
        print(sha(img))
        save_png(os.path.join(a.out, f"soft_{a.preset}.png"), img)
    else:
        img = gpu_frames(a.root, cfg, size, [a.time])[0]
        p = os.path.join(a.out, f"gpu_{a.preset}.png")
        save_png(p, img)
        print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
