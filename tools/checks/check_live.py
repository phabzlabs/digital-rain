"""Live load samplers and the on-screen rain message, on the real display.

The mapping from load to rain, the message schedule and masks are unit tests in tests/.
This check runs the real CPU and GPU load samplers, then five saver runs whose screenshots
are measured: the rain must be brighter inside the message letters than outside them.

Usage: <venv python> tools/checks/check_live.py
Run it from the repository root. Prints `live check OK` on success.
"""

import os
import re
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"  # this process never opens a window

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TOOLS))
for folder in (ROOT, TOOLS):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import hidden

hidden.setup()

import pygame
from _gate import Checker, RunRoot, run_check, wait_for

from digital_rain import live_load, looks, osapi, rain_message, settings

gate = Checker("live")

# Samplers need a few one-second periods to produce a first value.
SAMPLER_WAIT_S = 6.0
# Inside the letters the rain is at least this many times brighter than outside. Measured: the
# software clock reads 1.95, the GPU runs 2.9 to 24; a message that never formed reads about 1.
MIN_INSIDE_OUTSIDE_RATIO = 1.8
# Green channel level that counts as lit rain.
LIT_GREEN = 80
SAVER_SECONDS = 3
SAVER_TIMEOUT_S = 120
MIN_SHOT_BYTES = 10000
MIN_PREVIEW_SHOT_BYTES = 1000


def check_samplers():
    samplers = [live_load.LoadSampler("cpu"), live_load.LoadSampler("gpu")]
    wait_for(lambda: all(s.value() is not None or not s.alive() for s in samplers), SAMPLER_WAIT_S)
    for sampler in samplers:
        value = sampler.value()
        gate.check(value is None or 0.0 <= value <= 1.0, f"{sampler.source} sampler gave {value}")
        shown = value if value is None else round(value, 3)
        print(f"  sampler {sampler.source}: {shown}")
        sampler.stop()


def run_saver(run, name, cfg, extra):
    """One /s run with the given settings; returns (shot path, start time, end time)."""
    shot = run.file(name)
    started = time.localtime()
    result = run_check(
        run,
        name,
        os.path.join(ROOT, "matrix_saver.py"),
        "/s",
        "--seconds",
        SAVER_SECONDS,
        "--shot",
        shot,
        *extra,
        settings_json=cfg,
        timeout=SAVER_TIMEOUT_S,
    )
    finished = time.localtime()
    gate.check(result.ok, f"{name} exit {result.returncode}: {result.stdout}{result.stderr}")
    exists = os.path.exists(shot)
    gate.check(exists, f"{name} wrote no screenshot")
    if exists:
        need = MIN_PREVIEW_SHOT_BYTES if "preview" in name else MIN_SHOT_BYTES
        gate.within(f"{name} screenshot bytes", os.path.getsize(shot), lo=need, fmt="{:.0f}")
    match = re.search(r"^live: .*$", result.stdout, re.M)
    gate.check(match, f"{name} printed no live line: {result.stdout}")
    if match:
        print(f"  {name}: {match.group(0)}")
    return shot, started, finished


def clock_minutes(start, end):
    """The HH:MM strings the clock may have shown between two local times."""
    out = []
    for moment in (start, end):
        text = f"{moment.tm_hour:02d}:{moment.tm_min:02d}"
        if text not in out:
            out.append(text)
    return out


def message_ratios(shot, monitors, cfg, gpu, texts):
    """Best inside / outside share of lit green over the candidate texts, per monitor."""
    pixels = pygame.surfarray.array3d(pygame.image.load(shot)).transpose(1, 0, 2)
    left, top, _w, _h = osapi.virtual_bounds(monitors)
    results = []
    for monitor in monitors:
        monitor_cfg = settings.monitor_cfg(cfg, monitor.get("id"))
        look = looks.resolve(monitor_cfg)
        cols, rows, cell_w, cell_h, pad_x = rain_message.main_grid(
            monitor["w"],
            monitor["h"],
            monitor["dpi"],
            monitor_cfg["glyph_scale"],
            look["cell_scale"],
            1,
            gpu,
            look["columns"],
        )
        best = None
        for text in texts:
            found = rain_message.message_mask(text, cols, rows)
            if found is None:
                continue
            mask, col0, row0 = found
            mask_rows, mask_cols = mask.shape
            x0 = monitor["x"] - left + pad_x + col0 * cell_w
            y0 = monitor["y"] - top + row0 * cell_h
            box = pixels[y0 : y0 + mask_rows * cell_h, x0 : x0 + mask_cols * cell_w, 1] >= LIT_GREEN
            if box.shape != (mask_rows * cell_h, mask_cols * cell_w):
                continue
            cell = box.reshape(mask_rows, cell_h, mask_cols, cell_w).mean(axis=(1, 3))
            inside, outside = cell[mask].mean(), cell[~mask].mean()
            ratio = inside / max(outside, 1e-6)
            if best is None or ratio > best[0]:
                best = (ratio, inside, outside, text)
        gate.check(best is not None, f"no message mask for {monitor.get('id')}")
        results.append(best)
    return results


def check_message_runs(run):
    osapi.make_dpi_aware()
    monitors = osapi.list_monitors()
    primary = monitors[:1]
    first = monitors[0]
    half = first["w"] // 2
    split = [
        dict(x=first["x"], y=first["y"], w=half, h=first["h"], dpi=first["dpi"], id="sim:left"),
        dict(
            x=first["x"] + half,
            y=first["y"],
            w=first["w"] - half,
            h=first["h"],
            dpi=first["dpi"],
            id="sim:right",
        ),
    ]
    clock = {"preset": "film_1999", "upscaling": "off", "message": "clock", "live_source": "cpu"}
    text = {
        "preset": "custom",
        "upscaling": "off",
        "message": "text",
        "live_source": "gpu",
        "live_target": "density",
        "live_strength": 1.0,
    }
    split_clock = {
        "preset": "film_1999",
        "upscaling": "off",
        "message": "clock",
        "monitors": {"sim:right": {"depth": False}},
    }
    # Resurrections with depth on draws six slices with screen blend; the message sits on slice 1.
    sliced_text = {"preset": "resurrections", "depth": True, "upscaling": "off", "message": "text"}
    phrase = rain_message.display_text(settings.DEFAULTS["message_text"])

    runs = [
        ("clock_gpu.png", clock, [], primary, True, None),
        ("clock_soft.png", clock, ["--renderer", "software"], primary, False, None),
        ("text_gpu.png", text, [], primary, True, [phrase]),
        ("text_resurrections_gpu.png", sliced_text, [], primary, True, [phrase]),
        ("split_gpu.png", split_clock, ["--split-sim"], split, True, None),
    ]
    for name, cfg, extra, shown, gpu, texts in runs:
        shot, started, finished = run_saver(run, name, cfg, extra)
        if not os.path.exists(shot):
            continue
        full = dict(settings.DEFAULTS, **cfg)
        candidates = texts or clock_minutes(started, finished)
        for monitor, found in zip(
            shown, message_ratios(shot, shown, full, gpu, candidates), strict=True
        ):
            if found is None:
                continue
            ratio, inside, outside, used = found
            print(
                f"  {name} {monitor.get('id', 'primary')}: ratio {ratio:.2f} "
                f"(inside {inside * 100:.1f}%, outside {outside * 100:.1f}%, text {used!r})"
            )
            gate.within(
                f"{name} {monitor.get('id', 'primary')} inside/outside ratio",
                ratio,
                lo=MIN_INSIDE_OUTSIDE_RATIO,
                fmt="{:.2f}",
            )

    preview = {"preset": "film_1999", "message": "clock"}
    run_saver(run, "preview.png", preview, ["--preview-sim"])
    look = looks.resolve(dict(settings.DEFAULTS, **preview))
    cols, rows = rain_message.main_grid(
        152,
        112,
        0.3,
        settings.DEFAULTS["glyph_scale"],
        look["cell_scale"],
        1,
        True,
        look["columns"],
    )[:2]
    gate.check(
        rain_message.message_mask("12:34", cols, rows) is None,
        "the preview grid must be too small for a message",
    )


def main():
    gate.run(check_samplers)
    with RunRoot("matrix_live_") as run:
        gate.run(check_message_runs, run)
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
