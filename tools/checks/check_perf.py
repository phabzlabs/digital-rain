"""Performance tier: wall-clock limits on settings load/save, the dialog, the saver and the
frozen build. Opt-in (tools/check.py --perf) because a loaded machine can miss any of them.

Every child has its own APPDATA and TEMP below one RunRoot and writes to files, never to a pipe.
The limits are 2 to 25 times the numbers measured when they were set, so only a real regression
fails. The frozen build is skipped when dist/MatrixRain/MatrixRain.scr does not exist.

Usage: <venv python> tools/checks/check_perf.py [--frozen-only]
"""

import ctypes
import json
import os
import re
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TOOLS))
for folder in (ROOT, TOOLS):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import hidden

hidden.setup()

import psutil
from _gate import Checker, LoggedProcess, RunRoot, require_python, run_check, wait_for

SAVER = os.path.join(ROOT, "matrix_saver.py")
SCR = os.path.join(ROOT, "dist", "MatrixRain", "MatrixRain.scr")
TIMEOUT = 60
PERF = re.compile(r"^perf: first_frame_ms=(\S+) render_median_ms=(\S+) render_p95_ms=(\S+)$", re.M)

# Settings file access, milliseconds: measured 1 to 3 ms, limit 50.
MAX_SETTINGS_IO_MS = 50
# Settings dialog: first paint measured 300 to 700 ms, OK until destroyed 20 to 60 ms.
MAX_DIALOG_PAINT_MS = 1500
MAX_DIALOG_OK_MS = 500
# Saver run limits: render median measured 0.5 to 2 ms (GPU) and 8 to 20 ms (software);
# first frame 0.5 to 2 s. CPU is percent of one core, measured 8 to 20.
MAX_FIRST_FRAME_MS = 4000
MAX_GPU_MEDIAN_MS = 5.0
MAX_SOFTWARE_MEDIAN_MS = 40.0
MAX_PREVIEW_MEDIAN_MS = 5.0
MAX_GPU_CPU_PERCENT = 35.0
MIN_GPU_FPS_SHARE = 0.9
MIN_SOFTWARE_FPS_SHARE = 0.75
# Frame rate cap of the software run, like a 60 Hz monitor.
SOFTWARE_FPS_CAP = 60
# CPU sampling window inside a run, seconds after start.
CPU_FROM_S = 1.5
CPU_TO_S = 2.5
# Frozen build wall limits, milliseconds (measured 1 to 2.5 s).
MAX_FROZEN_DIALOG_MS = 4000
MAX_FROZEN_SAVER_MS = 6000
MIN_SHOT_BYTES = 2000

gate = Checker("perf")

LOADSAVE_CODE = """
import json, time
from digital_rain import settings
cfg = settings.load()
t = time.perf_counter(); settings.save(cfg); save_ms = (time.perf_counter() - t) * 1000
t = time.perf_counter(); settings.load(); load_ms = (time.perf_counter() - t) * 1000
print(json.dumps([load_ms, save_ms]))
"""

DIALOG_CODE = """
import json, time, tkinter as tk
from digital_rain.windows import config_dialog
t = time.perf_counter()
root = tk.Tk()
buttons = config_dialog.build(root).buttons
root.update()
paint_ms = (time.perf_counter() - t) * 1000
t = time.perf_counter()
buttons["ok"].invoke()
try:
    while root.winfo_exists():
        root.update()
except tk.TclError:
    pass
ok_ms = (time.perf_counter() - t) * 1000
print(json.dumps([paint_ms, ok_ms]))
"""


def _last_json(result, what):
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except IndexError, ValueError:
        gate.fail(f"{what} exited {result.returncode}: {result.stderr.strip()[-300:]}")
        return None


def check_settings_io(run):
    times = _last_json(
        run_check(run, "loadsave", "-c", LOADSAVE_CODE, timeout=TIMEOUT), "settings load/save"
    )
    if times:
        gate.within("settings.load() ms", times[0], hi=MAX_SETTINGS_IO_MS, fmt="{:.1f}")
        gate.within("settings.save() ms", times[1], hi=MAX_SETTINGS_IO_MS, fmt="{:.1f}")


def check_dialog_timing(run):
    times = _last_json(
        run_check(run, "dialog_timing", "-c", DIALOG_CODE, timeout=TIMEOUT), "dialog timing"
    )
    if times:
        gate.within("dialog first paint ms", times[0], hi=MAX_DIALOG_PAINT_MS, fmt="{:.0f}")
        gate.within("dialog OK ms", times[1], hi=MAX_DIALOG_OK_MS, fmt="{:.0f}")


def _timed_run(run, label, args, cpu=False):
    """Run the saver from source; returns (returncode or None on timeout, output, cpu percent)."""
    child = LoggedProcess(run, label, [SAVER, *args], run.env(label))
    started = time.monotonic()
    percent = None
    if cpu:
        wait_for(lambda: child.poll() is not None, CPU_FROM_S)
        try:
            proc = psutil.Process(child.pid)
            kids = proc.children()
            proc = kids[0] if kids else proc
            proc.cpu_percent()
            wait_for(
                lambda: child.poll() is not None, max(0.0, CPU_TO_S - (time.monotonic() - started))
            )
            percent = proc.cpu_percent()
        except psutil.Error:
            percent = None
    exited = wait_for(lambda: child.poll() is not None, TIMEOUT)
    code, out, err = child.finish(1)
    return (code if exited else None), out + err, percent


def check_saver_runs(run, preset=None):
    """GPU, software, --preview-sim and --split-sim runs; with a preset only gpu and preview-sim."""
    # name, args, median limit, min fps share of the cap, cpu limit, text the output must hold
    runs = [
        (
            "gpu",
            ["/s", "--seconds", "3"],
            MAX_GPU_MEDIAN_MS,
            MIN_GPU_FPS_SHARE,
            MAX_GPU_CPU_PERCENT,
            None,
        ),
        # --fps caps the run at a 60 Hz monitor: the CPU renderer manages about 50 fps at
        # 3440x1440, so a share of a 240 Hz cap would be unreachable.
        (
            "software",
            ["/s", "--seconds", "3", "--renderer", "software", "--fps", str(SOFTWARE_FPS_CAP)],
            MAX_SOFTWARE_MEDIAN_MS,
            MIN_SOFTWARE_FPS_SHARE,
            None,
            None,
        ),
        (
            "preview-sim",
            ["--preview-sim", "--seconds", "3"],
            MAX_PREVIEW_MEDIAN_MS,
            None,
            None,
            None,
        ),
        (
            "split-sim",
            ["--split-sim", "--seconds", "3"],
            MAX_PREVIEW_MEDIAN_MS,
            None,
            None,
            "mons: 2",
        ),
    ]
    if preset:
        runs = [
            (n, [*a, "--preset", preset], lim, share, cpu_lim, f"look: {preset}")
            for n, a, lim, share, cpu_lim, _m in runs
            if n in ("gpu", "preview-sim")
        ]
    for name, args, median_limit, fps_share, cpu_limit, must in runs:
        label = f"{name}{'/' + preset if preset else ''}"
        code, out, percent = _timed_run(
            run, label.replace("/", "_"), args, cpu=cpu_limit is not None
        )
        if not gate.check(code is not None, f"{label} run did not exit within {TIMEOUT} s"):
            continue
        if not gate.check(code == 0, f"{label} run exited {code}: {out.strip()[-300:]}"):
            continue
        match = PERF.search(out)
        fields = None if not match else [None if v == "none" else float(v) for v in match.groups()]
        full = name in ("gpu", "software")
        if not gate.check(
            fields and fields[1] is not None and (not full or fields[0] is not None),
            f"no timing for {label}",
        ):
            continue
        first_ms, median, _p95 = fields
        gate.within(f"{label} render median ms", median, hi=median_limit, fmt="{:.2f}")
        if full:
            gate.within(f"{label} first frame ms", first_ms, hi=MAX_FIRST_FRAME_MS, fmt="{:.0f}")
        if fps_share is not None:
            cap = re.search(r"cap: ([\d.]+) Hz", out)
            fps = re.search(r"avg fps at exit: ([\d.]+)", out)
            if gate.check(cap and fps, f"{label} printed no cap or avg fps"):
                gate.within(
                    f"{label} avg fps",
                    float(fps.group(1)),
                    lo=fps_share * float(cap.group(1)),
                    fmt="{:.1f}",
                )
        if cpu_limit is not None and gate.check(
            percent is not None, f"{label} CPU could not be measured"
        ):
            gate.within(f"{label} CPU percent of one core", percent, hi=cpu_limit, fmt="{:.0f}")
        if must:
            gate.check(must in out, f"{label} output lacks {must!r}")


def _short_path(path):
    buf = ctypes.create_unicode_buffer(32768)
    size = ctypes.windll.kernel32.GetShortPathNameW(path, buf, len(buf))
    return buf.value if 0 < size < len(buf) else path


def check_frozen(run):
    """Launch times of the onedir MatrixRain.scr, also reached by its 8.3 short path."""
    if not os.path.exists(SCR):
        print("perf: frozen build not found, skipped")
        return
    shot_long = run.file("frozen_dialog.png")
    shot_short = run.file("frozen_dialog_short.png")
    short = _short_path(SCR)
    runs = [  # name, argv, wall limit ms, png that must exist
        (
            "dialog",
            [SCR, "/c", "--dialog-shot", shot_long, "--dialog-scale", "1.0"],
            MAX_FROZEN_DIALOG_MS,
            shot_long,
        ),
        ("saver", [SCR, "/s", "--seconds", "1"], MAX_FROZEN_SAVER_MS, None),
        (
            "dialog short path",
            [short, "/c", "--dialog-shot", shot_short, "--dialog-scale", "1.0"],
            MAX_FROZEN_DIALOG_MS,
            shot_short,
        ),
    ]
    for name, argv, limit, png in runs:
        label = "frozen_" + name.replace(" ", "_")
        env = run.env(label)
        started = time.monotonic()
        child = LoggedProcess(run, label, argv[1:], env, executable=argv[0])
        exited = wait_for(lambda child=child: child.poll() is not None, TIMEOUT)
        elapsed_ms = (time.monotonic() - started) * 1000
        code, _out, err = child.finish(1)
        if not gate.check(exited, f"frozen {name} did not exit within {TIMEOUT} s"):
            continue
        gate.check(code == 0, f"frozen {name} exited {code}: {err.strip()[-300:]}")
        gate.within(f"frozen {name} ms", elapsed_ms, hi=limit, fmt="{:.0f}")
        if png:
            gate.check(
                os.path.exists(png) and os.path.getsize(png) >= MIN_SHOT_BYTES,
                f"frozen {name} wrote no screenshot of at least {MIN_SHOT_BYTES} bytes",
            )


def main():
    if not require_python():
        return 1
    frozen_only = "--frozen-only" in sys.argv[1:]
    with RunRoot("matrix_perf_") as run:
        if not frozen_only:
            gate.run(check_settings_io, run)
            gate.run(check_dialog_timing, run)
            gate.run(check_saver_runs, run)
            gate.run(check_saver_runs, run, "reloaded")
            gate.run(check_saver_runs, run, "resurrections")
        gate.run(check_frozen, run)
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
