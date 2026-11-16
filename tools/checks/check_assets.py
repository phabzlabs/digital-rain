"""The film glyph set and the platform layer, checked in process (no window, no GPU).

Glyphs: the film set matches assets/rezmason/glyph-order.txt, the fallback set flips the same
glyphs, every size renders, and an unusable custom font falls back to the film glyphs.
Layout: osapi.windows and osapi.mac both implement osapi.INTERFACE, the Mac stubs behave as
documented, every shader is #version 330, every preset file loads and has a looks entry.

Usage: <venv python> tools/checks/check_assets.py
Prints `assets check OK` on success. Needs only the dummy video driver.
"""

import importlib
import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TOOLS))
for folder in (ROOT, TOOLS):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import pygame
from _gate import Checker, RunRoot

import digital_rain.osapi.mac as mac
from digital_rain import glyphs, looks, osapi, resources, settings

gate = Checker("assets")

FILM_GLYPH_COUNT = 57
# Indices in the film glyph order of the blank cell and the long-vowel mark.
SPACE_INDEX, LONG_VOWEL_INDEX = 29, 45
# The glyph scales the renderer asks for (the cell scale of the two film looks).
RENDER_SCALES = (0.195, 0.117)


def check_film_glyphs():
    pygame.font.init()
    order = os.path.join(ROOT, "assets", "rezmason", "glyph-order.txt")
    with open(order, encoding="utf-8") as handle:
        classic = handle.read().split("\n")[1].rstrip("\r")
    gate.equal(glyphs.FILM_GLYPHS, classic, "FILM_GLYPHS against glyph-order.txt")
    gate.equal(len(glyphs.FILM_GLYPHS), FILM_GLYPH_COUNT, "FILM_GLYPHS length")
    film, src = glyphs.glyph_set(4.0)
    gate.equal(src, "film", "glyph_set source with the film font")
    gate.equal(len(film), FILM_GLYPH_COUNT, "film glyph count")
    gate.check(not any(entry[2] or entry[3] for entry in film), "film glyphs must be unflipped")
    gate.equal(film[SPACE_INDEX][0], " ", "film glyph at the space index")
    gate.equal(film[LONG_VOWEL_INDEX][0], "ー", "film glyph at the long-vowel index")
    fallback, src = glyphs.glyph_set(4.0, film_font="")
    gate.equal(src, "fallback", "glyph_set source without the film font")
    gate.equal(len(fallback), FILM_GLYPH_COUNT, "fallback glyph count")
    for i, char in enumerate(glyphs.FILM_GLYPHS):
        kata = "゠" <= char <= "ヿ"
        gate.equal(fallback[i][2], kata or char in "259", f"fallback flip_x at {i}")
        gate.equal(fallback[i][3], char == "3", f"fallback flip_y at {i}")
        if kata:
            gate.check("ｦ" <= fallback[i][0] <= "ﾝ", f"fallback glyph {i} is not half-width")
    gate.equal(fallback[0][0], "ﾓ", "first fallback glyph")
    gate.equal(fallback[34][0], "=", "fallback glyph 34")
    for scale in RENDER_SCALES:
        for kwargs in ({}, {"film_font": ""}):
            entries, _ = glyphs.glyph_set(scale, **kwargs)
            for char, font, flip_x, flip_y in entries:
                glyphs.render_glyph(char, font, flip_x, flip_y, 4, 6)
    entries, src = glyphs.glyph_set(4.0, custom=os.path.join(ROOT, "no-such.ttf"))
    gate.check(
        src == "film" and len(entries) == FILM_GLYPH_COUNT,
        "an unusable custom font must fall back to the film glyphs",
    )


def check_glyph_sheet(run):
    """Both sets drawn onto one sheet and saved (kept in the run root for looking at)."""
    film, _ = glyphs.glyph_set(4.0)
    fallback, _ = glyphs.glyph_set(4.0, film_font="")
    cell_w, cell_h, cols = 96, 128, 10
    rows = (FILM_GLYPH_COUNT + cols - 1) // cols
    sheet = pygame.Surface((cols * cell_w, 2 * rows * cell_h))
    for block, entries in enumerate((film, fallback)):
        for i, (char, font, flip_x, flip_y) in enumerate(entries):
            sheet.blit(
                glyphs.render_glyph(char, font, flip_x, flip_y, cell_w, cell_h),
                ((i % cols) * cell_w, (block * rows + i // cols) * cell_h),
            )
    path = run.file("glyph-sheet.png")
    pygame.image.save(sheet, path)
    gate.check(os.path.getsize(path) > 0, "glyph sheet is empty")


def check_platform_layer():
    gate.equal(osapi.PLATFORM, "windows", "osapi.PLATFORM on this machine")
    for plat in ("windows", "mac"):
        mod = importlib.import_module("digital_rain.osapi." + plat)
        missing = [name for name in osapi.INTERFACE if not hasattr(mod, name)]
        gate.check(not missing, f"osapi.{plat} lacks {missing}")
    # Mac no-ops and stubs (digital_rain/osapi/mac.py docstring); the real calls need AppKit.
    gate.check(
        mac.acquire_single_instance("x") is True and mac.create_event("x") is None,
        "osapi.mac single-instance and event stubs",
    )
    gate.check(
        mac.event_is_set(None) is False and mac.signal_event("x") is False, "osapi.mac event stubs"
    )
    for name, args, exc in (
        ("embed_in_parent", (None, None, 1, 1), NotImplementedError),
        ("work_area", (None,), NotImplementedError),
        ("gpu_load_sampler", (), RuntimeError),
    ):
        try:
            getattr(mac, name)(*args)
        except exc:
            continue
        gate.fail(f"osapi.mac.{name} should raise {exc.__name__}")


def check_shaders_and_presets():
    shaders = [
        n for n in os.listdir(resources.asset_path("shaders")) if n.endswith((".vert", ".frag"))
    ]
    gate.check(bool(shaders), "no shader files found")
    for name in shaders:
        first = resources.read_text("shaders", name).splitlines()[0]
        gate.equal(first, "#version 330", f"first line of {name}")
    for name in settings.PRESET_NAMES:
        if name != "custom":
            json.loads(resources.read_text("presets", name + ".json"))
            gate.check(name in looks.PRESETS, f"preset {name} has no looks entry")


def main():
    with RunRoot("matrix_assets_") as run:
        gate.run(check_film_glyphs)
        gate.run(check_glyph_sheet, run)
        gate.run(check_platform_layer)
        gate.run(check_shaders_and_presets)
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
