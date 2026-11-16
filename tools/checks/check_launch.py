"""Launch checks: pinned versions, the settings dialog (round trip, screenshots, layout settling,
preview child), the saver smoke runs at full screen and the /p preview inside a host window.

Needs a display (windows are hidden unless --show). Every child runs with its own APPDATA and
TEMP below one RunRoot, so two runs never share a file. The pure parts (argument parsing, the
settings migration table) are in tests/.

Usage: <venv python> tools/checks/check_launch.py [--show]
"""

import colorsys
import contextlib
import importlib.metadata
import json
import os
import re
import sys
import time
import tkinter as tk

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TOOLS))
for folder in (ROOT, TOOLS):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import hidden

hidden.setup()

import numpy as np
import pygame
from _gate import (
    Checker,
    LoggedProcess,
    RunRoot,
    require_python,
    run_check,
    wait_for,
    write_settings,
)
from film_targets import TARGETS

from digital_rain import osapi, settings
from digital_rain.windows import dialog_preview, dialog_widgets

gate = Checker("launch")

SAVER = os.path.join(ROOT, "matrix_saver.py")
PIN = re.compile(r"^[A-Za-z0-9_.-]+==[0-9][^ ]*$")
TIMEOUT = 60
FIXTURE_V110 = os.path.join(ROOT, "tests", "fixtures", "settings_v1_1_0.json")

# Dialog screenshot signals, measured on a 1216 x 1079 shot at scale 1.0: share of pixels within
# 3 levels of each background token (window 0.33, chrome 0.23, panel 0.21, preview 0.13), the
# accent (0.005) and text-coloured pixels (about 2000 in the sidebar, 3100 in the page area).
# A black or blank window has none of these, so each floor is about half the measured value.
MIN_TOKEN_SHARE = {"bg-window": 0.15, "bg-chrome": 0.10, "bg-panel": 0.10, "bg-preview": 0.05}
MIN_ACCENT_SHARE = 0.001
MIN_SIDEBAR_CHROME_SHARE = 0.6
MIN_TEXT_PIXELS = 500
TEXT_TOLERANCE = 40
TOKEN_TOLERANCE = 3
# The window is dark: mean level, share of near-white pixels and title-bar mean stay under these.
MAX_MEAN_LEVEL = 50
MAX_BRIGHT_SHARE = 0.01
MAX_TITLE_MEAN = 80
# The scope shot draws the Override pills and amber page counts: measured about 1000 pixels.
MIN_OVERRIDE_PIXELS = 300
OVERRIDE_TOLERANCE = 12
# Idle Configure events allowed in half a second after layout (a relayout loop fires hundreds).
MAX_IDLE_CONFIGURE = 5
MIN_SHOT_BYTES = 10000
# Lit share a saver frame must reach (max channel > 40); measured 0.2 to 0.6 on every preset.
MIN_LIT_SHARE = 0.05
LIT_LEVEL = 40


def _read_pins(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip() and not line.startswith("#")]


# Versions
def check_versions():
    gate.check(
        sys.version_info[:2] == (3, 14),
        f"Python 3.14 required, found {sys.version_info[0]}.{sys.version_info[1]}",
    )
    for path in (
        "requirements/requirements.txt",
        "requirements/requirements-build.txt",
        "requirements/requirements-dev.txt",
    ):
        for line in _read_pins(path):
            if line.startswith("-r "):
                continue
            if not gate.check(PIN.match(line), f"{path}: not an exact pin: {line}"):
                continue
            name, want = line.split("==")
            try:
                have = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                # build-only tools are not installed in every environment
                if path == "requirements/requirements.txt":
                    gate.fail(f"{path}: {name} is not installed")
                continue
            if path == "requirements/requirements.txt":
                gate.equal(have, want, f"{path}: {name} installed")


# Dialog
def _token_rgb(token):

    colour = dialog_widgets.TOKENS[token]
    return [int(colour[i : i + 2], 16) for i in (1, 3, 5)]


def _near(pixels, rgb, tolerance):

    return (np.abs(pixels - np.array(rgb)) <= tolerance).all(axis=2)


def dialog_signals(path):
    """Region and pixel measurements of a dialog screenshot (see the floors above)."""

    pixels = pygame.surfarray.array3d(pygame.image.load(path)).transpose(1, 0, 2).astype(int)
    height, width = pixels.shape[:2]
    sidebar = pixels[:, : dialog_widgets.SIDEBAR_W]
    page = pixels[:, dialog_widgets.SIDEBAR_W :]
    text_rgb = _token_rgb("text-strong")
    return {
        "size": (width, height),
        "token": {
            name: float(_near(pixels, _token_rgb(name), TOKEN_TOLERANCE).mean())
            for name in MIN_TOKEN_SHARE
        },
        "accent": float(_near(pixels, _token_rgb("accent"), TOKEN_TOLERANCE).mean()),
        "sidebar_chrome": float(_near(sidebar, _token_rgb("bg-chrome"), TOKEN_TOLERANCE).mean()),
        "sidebar_text": int(_near(sidebar, text_rgb, TEXT_TOLERANCE).sum()),
        "page_text": int(_near(page, text_rgb, TEXT_TOLERANCE).sum()),
        "mean": float(pixels.mean()),
        "bright": float((pixels > 200).all(axis=2).mean()),
        "title": float(pixels[:, :20].mean()),
        "override": int(_near(pixels, _token_rgb("override"), OVERRIDE_TOLERANCE).sum()),
    }


def check_dialog_signals(label, path, floor_scale=1.0):
    """The dialog was really drawn: every background region, the accent and the text exist."""
    sig = dialog_signals(path)
    for name, floor in MIN_TOKEN_SHARE.items():
        gate.within(f"{label}: {name} share", sig["token"][name], lo=floor * floor_scale)
    gate.within(f"{label}: accent share", sig["accent"], lo=MIN_ACCENT_SHARE, fmt="{:.4f}")
    gate.within(
        f"{label}: sidebar chrome share", sig["sidebar_chrome"], lo=MIN_SIDEBAR_CHROME_SHARE
    )
    gate.within(
        f"{label}: sidebar text pixels", sig["sidebar_text"], lo=MIN_TEXT_PIXELS, fmt="{:.0f}"
    )
    gate.within(f"{label}: page text pixels", sig["page_text"], lo=MIN_TEXT_PIXELS, fmt="{:.0f}")
    gate.within(f"{label}: mean level", sig["mean"], hi=MAX_MEAN_LEVEL, fmt="{:.1f}")
    gate.within(f"{label}: near-white share", sig["bright"], hi=MAX_BRIGHT_SHARE, fmt="{:.4f}")
    gate.within(f"{label}: title bar mean", sig["title"], hi=MAX_TITLE_MEAN, fmt="{:.1f}")
    return sig


_SCOPE_SHOT_CODE = """
import json, os, sys, tkinter as tk
from digital_rain import osapi
osapi.make_dpi_aware()
mid = osapi.list_monitors()[0]["id"]
d = os.path.join(os.environ["APPDATA"], "MatrixRain")
os.makedirs(d, exist_ok=True)
with open(os.path.join(d, "settings.json"), "w") as fh:
    json.dump(dict(preset="film_1999", monitors={
        mid: dict(name="Display 1", speed=1.4, color="amber"),
        "check-not-connected": dict(name="Old TV", density=0.5)}), fh)
from digital_rain.windows import config_dialog
root = tk.Tk()
root.tk.call("tk", "scaling", 96 / 72)
app = config_dialog.SettingsWindow(root, shot_size=config_dialog.OPEN_SIZE)
app.model.set_scope(mid)
config_dialog.capture(root, sys.argv[1])
root.destroy()
"""

# Every page in every message mode must settle: after the first layout an idle half second may
# not fire more than a few <Configure> events (a wraplength that follows its own label's width
# once looped forever on the Clock page).
_SETTLE_CODE = """
import json, os, sys, time, tkinter as tk
from digital_rain import dialog_model, osapi, settings
osapi.make_dpi_aware()
d = os.path.join(os.environ["APPDATA"], "MatrixRain")
os.makedirs(d, exist_ok=True)
from digital_rain.windows import config_dialog
worst = (0, "")
runs = [(m, config_dialog.OPEN_SIZE, dialog_model.PAGES) for m in settings.MESSAGE_MODES]
runs += [(m, s, ("message",)) for m in ("clock", "both") for s in ((1200, 1200), (1500, 1040))]
for mode, size, pages in runs:
    with open(os.path.join(d, "settings.json"), "w") as fh:
        json.dump(dict(message=mode), fh)
    root = tk.Tk()
    root.tk.call("tk", "scaling", 96 / 72)
    app = config_dialog.SettingsWindow(root, shot_size=size)
    n = [0]
    root.bind_all("<Configure>", lambda e: n.__setitem__(0, n[0] + 1), add="+")
    for page in pages:
        app.show_page(page)
        end = time.monotonic() + 0.3
        while time.monotonic() < end:
            root.update()
        n[0] = 0
        end = time.monotonic() + 0.5
        while time.monotonic() < end:
            root.update()
        if n[0] >= worst[0]:
            worst = (n[0], f"{mode}/{page} {size[0]}x{size[1]}")
    root.destroy()
print(f"{worst[0]} {worst[1]}")
"""


def check_dialog_round_trip(run):
    """An old settings file saved through the dialog's OK keeps its values."""

    env = run.env("dialog_rt")
    with open(FIXTURE_V110, encoding="utf-8") as handle:
        fixture = json.load(handle)
    write_settings(env, fixture)
    code = (
        "import tkinter as tk; from digital_rain.windows import config_dialog; "
        "r = tk.Tk(); "
        "app = config_dialog.build(r); app.buttons['ok'].invoke()"
    )
    result = run_check(
        run, "dialog_rt_run", "-c", code, timeout=TIMEOUT, env_extra={"APPDATA": env["APPDATA"]}
    )
    if not gate.check(
        result.ok, f"dialog round trip exited {result.returncode}: {result.stderr.strip()[-300:]}"
    ):
        return
    previous = os.environ.get("APPDATA")
    os.environ["APPDATA"] = env["APPDATA"]
    try:
        cfg = settings.load()
    finally:
        if previous is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = previous
    for key, value in dict(fixture, upscaling="off", sharpness=0.2).items():
        gate.equal(cfg.get(key), value, f"dialog round trip: {key}")


def check_dialog_shots(run):
    # Fixed scale 1.0, so the check does not depend on the machine's own DPI.
    env = run.env("dialog_shot")
    shot = run.file("dialog_100.png")
    result = run_check(
        run,
        "dialog_100",
        SAVER,
        "/c",
        "--dialog-shot",
        shot,
        "--dialog-scale",
        "1.0",
        timeout=TIMEOUT,
        env_extra={"APPDATA": env["APPDATA"]},
    )
    if not gate.check(
        result.ok and os.path.exists(shot),
        f"dialog shot exited {result.returncode}: {result.stderr.strip()[-300:]}",
    ):
        return
    gate.check(
        not os.path.exists(os.path.join(env["APPDATA"], "MatrixRain", "settings.json")),
        "dialog shot wrote settings.json",
    )
    base = check_dialog_signals("dialog 100%", shot)

    shot15 = run.file("dialog_150.png")
    result = run_check(
        run,
        "dialog_150",
        SAVER,
        "/c",
        "--dialog-shot",
        shot15,
        "--dialog-scale",
        "1.5",
        timeout=TIMEOUT,
    )
    if gate.check(
        result.ok and os.path.exists(shot15),
        f"dialog 150% shot exited {result.returncode}: {result.stderr.strip()[-300:]}",
    ):
        size15 = dialog_signals(shot15)["size"]
        gate.within(
            "dialog 150% width over the 100% width",
            size15[0] / base["size"][0],
            lo=1.3,
            fmt="{:.2f}",
        )
        check_dialog_signals("dialog 150%", shot15)

    small_env = run.env("dialog_small")
    small = run.file("dialog_small.png")
    result = run_check(
        run,
        "dialog_small",
        SAVER,
        "/c",
        "--dialog-shot",
        small,
        "--dialog-scale",
        "1.0",
        "--dialog-size",
        "960x600",
        timeout=TIMEOUT,
        env_extra={"APPDATA": small_env["APPDATA"]},
    )
    if gate.check(
        result.ok and os.path.exists(small),
        f"dialog 960x600 shot exited {result.returncode}: {result.stderr.strip()[-300:]}",
    ):
        gate.check(
            not os.path.exists(os.path.join(small_env["APPDATA"], "MatrixRain", "settings.json")),
            "dialog 960x600 shot wrote settings.json",
        )
        sig = check_dialog_signals("dialog 960x600", small, floor_scale=0.5)
        # The window grows past the requested size to fit its content, never below it.
        gate.within("dialog small width", sig["size"][0], lo=960, fmt="{:.0f}")
        gate.within("dialog small height", sig["size"][1], lo=600, fmt="{:.0f}")


def check_dialog_scope(run):
    """A monitor scope with an override and a stale Colour override."""
    env = run.env("dialog_scope")
    scope = run.file("dialog_scope.png")
    result = run_check(
        run,
        "dialog_scope",
        "-c",
        _SCOPE_SHOT_CODE,
        scope,
        timeout=TIMEOUT,
        env_extra={"APPDATA": env["APPDATA"]},
    )
    if not gate.check(
        result.ok and os.path.exists(scope),
        f"dialog scope shot exited {result.returncode}: {result.stderr.strip()[-300:]}",
    ):
        return
    with open(
        os.path.join(env["APPDATA"], "MatrixRain", "settings.json"), encoding="utf-8"
    ) as handle:
        saved = json.load(handle)
    sig = check_dialog_signals("dialog scope", scope)
    gate.within(
        "dialog scope: override-coloured pixels",
        sig["override"],
        lo=MIN_OVERRIDE_PIXELS,
        fmt="{:.0f}",
    )
    gate.check(
        "check-not-connected" in saved.get("monitors", {}),
        "dialog scope shot changed settings.json",
    )


def check_dialog_settles(run):
    result = run_check(run, "dialog_settle", "-c", _SETTLE_CODE, timeout=TIMEOUT)
    if not gate.check(
        result.ok, f"dialog settle exited {result.returncode}: {result.stderr.strip()[-300:]}"
    ):
        return
    count, where = result.stdout.strip().splitlines()[-1].split(" ", 1)
    gate.within(
        f"idle Configure events on {where}", int(count), hi=MAX_IDLE_CONFIGURE, fmt="{:.0f}"
    )


# Dialog preview
def _preview_child(run, renderer, number):
    """One dialog-preview child inside a host frame; returns (ready seconds, shot path)."""

    cfg = settings.clean({"preset": "film_1999"})
    label = renderer or "default"
    shot = run.file(f"dialog_preview_{label}.png")
    host = tk.Tk()
    frame = tk.Frame(host, width=880, height=180, bg="black")
    frame.pack()
    host.update()
    path = dialog_preview.write_temp(cfg)
    event = f"Local\\MatrixRainCheckReady-{os.getpid()}-{number}"
    handle = osapi.create_event(event)
    args = [
        SAVER,
        *dialog_preview.child_args(frame.winfo_id(), path, event)[1:],
        "--seconds",
        "3",
        "--shot",
        shot,
    ]
    if renderer:
        args += ["--renderer", renderer]
    child = LoggedProcess(run, f"dialog_preview_{label}", args, run.env(f"preview_{label}"))
    started = time.monotonic()
    ready = None
    while child.poll() is None and time.monotonic() - started < TIMEOUT:
        host.update()
        if ready is None and osapi.event_is_set(handle):
            ready = time.monotonic() - started
        time.sleep(0.02)
    code, _out, err = child.finish(1)
    if ready is None and osapi.event_is_set(handle):
        ready = time.monotonic() - started
    dialog_preview._close_handle(handle)
    os.remove(path)
    host.destroy()
    gate.check(code == 0, f"dialog preview {label} exited {code}: {err.strip()[-300:]}")
    gate.check(ready is not None, f"dialog preview {label}: ready event never set")
    size = os.path.getsize(shot) if os.path.exists(shot) else 0
    gate.within(f"dialog preview {label} screenshot bytes", size, lo=MIN_SHOT_BYTES, fmt="{:.0f}")
    return ready, shot


def check_dialog_preview(run):

    for number, renderer in enumerate((None, "software"), 1):
        _preview_child(run, renderer, number)

    # Two children for the same frame in sequence: the first goes after the second is ready.
    cfg = settings.clean({"preset": "film_1999"})
    host = tk.Tk()
    frame = tk.Frame(host, width=880, height=180, bg="black")
    frame.pack(fill="both", expand=True)
    canvas = tk.Canvas(frame, width=880, height=180, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    host.update()
    dialog_widgets.set_scale(host, 1.0)  # the static sample draws with the dialog's fonts
    preview = dialog_preview.Preview(
        host,
        frame,
        canvas,
        lambda: (cfg, cfg, "#53EEAB"),
        force=True,
        extra_args=["--seconds", "15"],
    )
    kills = []
    original_kill = preview._kill

    def kill(child):
        if child is not None:
            kills.append((time.monotonic(), child, child.proc.poll()))
        original_kill(child)

    preview._kill = kill
    preview.start()
    started = time.monotonic()
    restarted = False
    while time.monotonic() - started < 30:
        host.update()
        if not restarted and len(preview.ready_times) >= 1:
            preview.restart_now()
            restarted = True
        if len(preview.ready_times) >= 2 and kills:
            break
        time.sleep(0.02)
    other = dialog_preview.Preview(host, frame, canvas, lambda: (cfg, cfg, "#53EEAB"), force=True)
    preview.close()
    host.destroy()

    gate.check(1 <= preview.run < 2**32, f"dialog preview run value {preview.run} out of range")
    want = ["--run", str(preview.run)]
    for index, command in enumerate(preview.child_cmds):
        gate.check(
            any(command[j : j + 2] == want for j in range(len(command) - 1)),
            f"dialog preview child {index + 1} lacks --run {preview.run}: {command}",
        )
    gate.equal(len(preview.child_cmds), 2, "dialog preview child commands recorded")
    gate.check(other.run != preview.run, f"a second Preview drew the same run value {preview.run}")
    if not gate.check(
        len(preview.ready_times) >= 2,
        f"dialog preview swap: {len(preview.ready_times)} of 2 children got ready "
        f"(unavailable={preview.unavailable})",
    ):
        return
    first, second = preview.ready_times[0][1], preview.ready_times[1]
    mine = [k for k in kills if k[1] is first]
    if gate.check(mine, "dialog preview swap: the first child was never terminated"):
        gate.check(
            mine[0][0] >= second[0],
            "dialog preview swap: the first child went before the second was ready",
        )
        gate.check(mine[0][2] is None, "dialog preview swap: the first child had already exited")


# Saver
def _lit_share_and_hue(path):
    """(lit share, median hue in degrees) of the pixels above LIT_LEVEL in a screenshot."""

    pixels = pygame.surfarray.array3d(pygame.image.load(path)).reshape(-1, 3)
    lit = pixels[pixels.max(axis=1) > LIT_LEVEL]
    if len(lit) == 0:
        return 0.0, float("nan")
    share = len(lit) / max(1, pixels.shape[0])
    sample = lit[:: max(1, len(lit) // 5000)]
    hues = [colorsys.rgb_to_hsv(*(c / 255.0))[0] * 360 for c in sample]
    return share, float(np.median(hues))


def _saver_run(run, label, *extra):
    shot = run.file(f"saver_{label}.png")
    result = run_check(
        run,
        f"saver_{label}",
        SAVER,
        "/s",
        "--seconds",
        "3",
        "--shot",
        shot,
        *extra,
        timeout=TIMEOUT,
    )
    gate.check(result.ok, f"{label} run exited {result.returncode}: {result.stderr.strip()[-300:]}")
    exists = os.path.exists(shot)
    gate.check(
        exists and os.path.getsize(shot) >= MIN_SHOT_BYTES,
        f"{label} screenshot missing or under {MIN_SHOT_BYTES} bytes",
    )
    return result, shot if exists else None


def check_saver_smoke(run):
    """One default GPU run and two software runs, each with its own screenshot."""

    osapi.make_dpi_aware()
    _x, _y, width, height = osapi.virtual_bounds(osapi.list_monitors())

    result, shot = _saver_run(run, "default")
    for needle in (
        "look: film_1999/down/off",
        "overrides: 0",
        "glyphs: film",
        "live: source=off load=unavailable speed_k=1.00 density_k=1.00",
    ):
        gate.check(needle in result.stdout, f"default run did not report {needle!r}")
    if shot:
        gate.equal(
            pygame.image.load(shot).get_size(),
            (width, height),
            "default screenshot size is the virtual desktop",
        )

    result, shot = _saver_run(run, "software", "--renderer", "software")
    gate.check("renderer: software" in result.stdout, "software run did not report its renderer")
    if shot:
        gate.equal(
            pygame.image.load(shot).get_size(),
            (width, height),
            "software screenshot size is the virtual desktop",
        )

    result, shot = _saver_run(
        run, "software_resurrections", "--renderer", "software", "--preset", "resurrections"
    )
    if shot:
        share, hue = _lit_share_and_hue(shot)
        low, high = TARGETS["resurrections"]["hue"]
        gate.within("software resurrections lit share", share, lo=MIN_LIT_SHARE)
        gate.within("software resurrections lit hue", hue, lo=low, hi=high, fmt="{:.1f}")


# Preview
def _host_run(host, args, run, label, close_after=None):
    """Run the saver in /p mode inside `host`, pumping its messages.

    Returns (returncode or None when it did not exit in time, stderr, seconds after close).
    """
    child = LoggedProcess(run, label, args, run.env(label))
    started = time.monotonic()
    closed_at = None
    while child.poll() is None and time.monotonic() - started < TIMEOUT:
        host.update()
        if close_after is not None and time.monotonic() - started >= close_after:
            closed_at = time.monotonic()
            host.destroy()
            break
        time.sleep(0.02)
    if closed_at is not None:
        exited = wait_for(lambda: child.poll() is not None, 5)
        code, _out, err = child.finish(0.1)
        return (code if exited else None), err, time.monotonic() - closed_at
    code, _out, err = child.finish(0.1)
    return code, err, 0.0


def _new_host():

    host = tk.Tk()
    frame = tk.Frame(host, width=152, height=112, bg="black")
    frame.pack()
    host.update()
    return host, frame


def check_preview(run, preset=None):

    tag = f"_{preset}" if preset else ""
    for renderer in (None, "software"):
        label = f"preview{'_soft' if renderer else ''}{tag}"
        path = run.file(label + ".png")
        host, frame = _new_host()
        hwnd = frame.winfo_id()
        if not gate.equal(osapi.client_size(hwnd), (152, 112), f"{label}: host client size"):
            host.destroy()
            continue
        args = [SAVER, "/p", str(hwnd), "--seconds", "3", "--shot", path]
        if renderer:
            args += ["--renderer", renderer]
        if preset:
            args += ["--preset", preset]
        code, err, _ = _host_run(host, args, run, label)
        with contextlib.suppress(tk.TclError):
            host.destroy()
        if not gate.check(code == 0, f"{label} exited {code}: {err.strip()[-300:]}"):
            continue
        if not gate.check(os.path.exists(path), f"{label} screenshot missing"):
            continue
        image = pygame.image.load(path)
        gate.equal(image.get_size(), (152, 112), f"{label} screenshot size")
        share, hue = _lit_share_and_hue(path)
        gate.within(f"{label} lit share", share, lo=MIN_LIT_SHARE)
        if preset:
            low, high = TARGETS[preset]["hue"]
            gate.within(f"{label} lit hue", hue, lo=low, hi=high, fmt="{:.1f}")

    if preset:
        return
    # Closing the host ends the saver.
    host, frame = _new_host()
    code, err, _took = _host_run(
        host, [SAVER, "/p", str(frame.winfo_id())], run, "preview_close", close_after=2.5
    )
    gate.check(code is not None, "preview saver did not exit within 5 s of the host closing")
    if code is not None:
        gate.check(
            code == 0, f"preview saver exited {code} after the host closed: {err.strip()[-300:]}"
        )


def main():
    if not require_python():
        return 1
    gate.run(check_versions)
    with RunRoot("matrix_launch_") as run:
        for fn in (
            check_dialog_round_trip,
            check_dialog_shots,
            check_dialog_scope,
            check_dialog_settles,
            check_dialog_preview,
            check_saver_smoke,
            check_preview,
        ):
            gate.run(fn, run)
        gate.run(check_preview, run, "resurrections")
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
