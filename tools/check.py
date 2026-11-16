"""The local gate: runs the sub-checks in tiers and prints one line per check.

Usage: <venv python> tools/check.py [--fast] [--perf] [--show]
The sub-checks and their helpers are in tools/checks/; one-off scripts are in tools/dev/ and
the build helpers in tools/build/.
Run it from the repository root with Python 3.14. Never run two copies at once.

Tiers (a tier includes the ones above it):
  fast  windowless, dummy video driver, no GPU: byte-compile, check_assets, check_looks,
        check_monitors, check_dialog, check_mac_options. This is what CI runs.
  gpu   the default: adds the checks that open hidden windows and render on the GPU:
        check_live, check_launch, check_film.
  perf  --perf adds check_perf (timed runs and the frozen build), which a loaded machine can
        fail on its own.
--fast stops after the fast tier. --show opens real windows in the checks that take it
(MATRIX_CHECK_SHOW=1 does the same). pytest (tests/) is separate: run `pytest`.
"""

import os
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
CHECKS = os.path.join(TOOLS, "checks")
ROOT = os.path.dirname(TOOLS)
if CHECKS not in sys.path:
    sys.path.insert(0, CHECKS)

from _gate import RunRoot, require_python, run_check

# (name, script, tier, needs the dummy video driver, extra arguments)
SUBCHECKS = (
    ("assets", "check_assets.py", "fast", True, ()),
    ("looks", "check_looks.py", "fast", True, ()),
    ("monitors", "check_monitors.py", "fast", True, ()),
    ("dialog", "check_dialog.py", "fast", True, ()),
    ("mac options", "check_mac_options.py", "fast", False, ()),
    ("live", "check_live.py", "gpu", False, ()),
    ("launch", "check_launch.py", "gpu", False, ()),
    ("film", "check_film.py", "gpu", False, ()),
    ("perf", "check_perf.py", "perf", False, ()),
)
SHOW_AWARE = ("check_launch.py", "check_film.py")
SUBCHECK_TIMEOUT_S = 1800


def tiers_to_run(argv):
    if "--fast" in argv:
        return ("fast",)
    return ("fast", "gpu", "perf") if "--perf" in argv else ("fast", "gpu")


def compile_all():
    """Byte-compile every module (a syntax error anywhere fails the gate). Returns the count."""
    mods = [f for f in os.listdir(ROOT) if f.endswith(".py")]
    for sub in ("digital_rain", "tools", "tests"):
        for folder, dirs, names in os.walk(os.path.join(ROOT, sub)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            mods += [
                os.path.relpath(os.path.join(folder, f), ROOT) for f in names if f.endswith(".py")
            ]
    for mod in sorted(mods):
        with open(os.path.join(ROOT, mod), "rb") as handle:
            compile(handle.read(), mod, "exec")
    return len(mods)


def run_subchecks(run, tiers, argv):
    """Run the selected sub-checks; return a list of (name, passed, seconds, output)."""
    results = []
    for name, script, tier, dummy, extra in SUBCHECKS:
        if tier not in tiers:
            continue
        args = [os.path.join(CHECKS, script), *extra]
        if "--show" in argv and script in SHOW_AWARE:
            args.append("--show")
        started = time.monotonic()
        result = run_check(
            run, name.replace(" ", "_"), *args, dummy_video=dummy, timeout=SUBCHECK_TIMEOUT_S
        )
        seconds = time.monotonic() - started
        results.append((name, result.ok, seconds, result.stdout + result.stderr))
        print(f"{'ok  ' if result.ok else 'FAIL'} {name:12s} {seconds:6.1f} s", flush=True)
        if not result.ok:
            print(result.stdout.strip()[-3000:])
            print(result.stderr.strip()[-1500:], flush=True)
    return results


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not require_python():
        return 1
    started = time.monotonic()
    try:
        print(f"compiled {compile_all()} modules")
    except SyntaxError as exc:
        print(f"FAIL compile: {exc}")
        return 1
    with RunRoot("matrix_gate_") as run:
        results = run_subchecks(run, tiers_to_run(argv), argv)
    failed = [name for name, passed, _, _ in results if not passed]
    total = time.monotonic() - started
    if failed:
        print(f"gate FAILED ({', '.join(failed)}) in {total:.0f} s")
        return 1
    print(f"gate OK in {total:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
