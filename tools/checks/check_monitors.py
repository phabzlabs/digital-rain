"""Checks for per-monitor looks: the monitor ids Windows reports, and the software renderer
drawing two monitors with different looks (the settings rules are in tests/test_settings.py).

Usage: <venv python> tools/checks/check_monitors.py
Run it from the repository root. It needs no GPU: the software renderer is built on pygame's
dummy video driver. Prints `monitors check OK` on success.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TOOLS))
for folder in (ROOT, TOOLS):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import numpy as np
import pygame
import shot_stats
from _gate import Checker, scratch

from digital_rain import osapi, settings, soft_renderer

pygame.display.init()
pygame.font.init()

gate = Checker("monitors")

# Hue windows (degrees) of the amber colour and the film_1999 green, measured on the software
# renderer: amber sits near 42, the film green near 152.
AMBER_HUE = (35, 50)
FILM_GREEN_HUE = (145, 160)
# Share of pixels lit (max channel >= 60) that proves a monitor drew rain. Measured on the
# software renderer: the dense monitor lights 0.57, the sparse one 0.027, a blank frame 0.
MIN_LIT_SHARE = 0.2
MIN_SPARSE_LIT_SHARE = 0.005


def check_monitor_ids():
    monitors = osapi.list_monitors()
    gate.check(len(monitors) >= 1, "no monitors")
    ids = [m["id"] for m in monitors]
    for m in monitors:
        gate.check(
            isinstance(m["id"], str) and m["id"] and isinstance(m["name"], str) and m["name"],
            f"monitor needs a non-empty id and name: {m}",
        )
    gate.check(len(set(ids)) == len(ids), f"duplicate ids {ids}")
    gate.check(
        osapi.monitor_signature(monitors)[0][-1] == monitors[0]["id"], "signature ends with the id"
    )


def render(monitors, size, cfg):
    screen = pygame.display.set_mode(size)
    renderer = soft_renderer.SoftRenderer(monitors, cfg, (0, 0), size, screen)
    for frame in range(10):
        renderer.render(frame / 30, 1 / 30, frame)
    pixels = pygame.surfarray.array3d(screen).transpose(1, 0, 2).astype(np.float32)
    return renderer, pixels


def rect_of(pixels, m):
    return pixels[m["y"] : m["y"] + m["h"], m["x"] : m["x"] + m["w"]]


def lit_share(pixels):
    return float((pixels.max(axis=2) >= 60).mean())


def check_software():
    a = dict(x=0, y=0, w=800, h=600, dpi=1.0, id="test:a")
    b = dict(x=800, y=0, w=640, h=480, dpi=1.5, id="test:b")
    size = (1440, 600)
    colour = dict(
        settings.DEFAULTS,
        preset="film_1999",
        easter_egg=False,
        monitors={"test:a": {"preset": "custom", "color": "amber"}},
    )
    _, pixels = render([a, b], size, colour)
    hue_a, hue_b = (shot_stats.hue_of(rect_of(pixels, m)) for m in (a, b))
    gate.check(AMBER_HUE[0] <= hue_a <= AMBER_HUE[1], f"monitor a should be amber, hue {hue_a}")
    gate.check(
        FILM_GREEN_HUE[0] <= hue_b <= FILM_GREEN_HUE[1],
        f"monitor b should keep film_1999, hue {hue_b}",
    )

    density = dict(
        settings.DEFAULTS,
        preset="reloaded",
        easter_egg=False,
        monitors={"test:a": {"density": 0.3, "depth": False}, "test:b": {"density": 1.6}},
    )
    _, pixels = render([a, b], size, density)
    lit = [lit_share(rect_of(pixels, m)) for m in (a, b)]
    # The dense monitor must really draw rain, or "a is sparser than b" holds on blank frames.
    gate.within("dense monitor b lit share", lit[1], lo=MIN_LIT_SHARE)
    gate.within("sparse monitor a lit share", lit[0], lo=MIN_SPARSE_LIT_SHARE)
    gate.check(lit[0] < 0.5 * lit[1], f"sparse monitor a should be under half of b: {lit}")

    preview = dict(x=0, y=0, w=152, h=112, dpi=0.3)
    _, pixels = render([preview], (152, 112), colour)
    hue = shot_stats.hue_of(pixels)
    gate.check(
        FILM_GREEN_HUE[0] <= hue <= FILM_GREEN_HUE[1],
        f"preview has no id and uses the global look, hue {hue}",
    )

    b_same_dpi = dict(b, dpi=1.0)
    renderer, _ = render([a, b_same_dpi], size, colour)
    gate.check(
        renderer.fields[0][0][0].atlas is not renderer.fields[1][0][0].atlas,
        "different looks must not share an atlas",
    )
    renderer, _ = render([a, b_same_dpi], size, dict(colour, monitors={}))
    gate.check(
        renderer.fields[0][0][0].atlas is renderer.fields[1][0][0].atlas,
        "equal looks share one atlas",
    )


def main():
    with scratch("matrix_monitors_") as appdata:
        os.environ["APPDATA"] = appdata
        gate.run(check_monitor_ids)
        gate.run(check_software)
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
