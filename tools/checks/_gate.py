"""Shared plumbing for the check scripts in tools/.

Checker      one pass/fail counter: collect every failure, print a summary, give an exit code.
RunRoot      one temp folder per gate run, removed in `finally`; every child process gets its
             own APPDATA and TEMP below it, so two runs on the same machine never share files.
run_check    run a sub-check script as a child process under a RunRoot.
wait_for     poll a condition until a deadline instead of sleeping a fixed time.
"""

import contextlib
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TOOLS))


class Checker:
    """Collect-all pass/fail recorder. No bare asserts: `-O` would strip them."""

    def __init__(self, name):
        self.name = name
        self.count = 0
        self.failures = []

    def check(self, cond, msg):
        """Record one boolean check. Returns the condition so callers can branch on it."""
        self.count += 1
        if not cond:
            self.failures.append(msg)
            print(f"FAIL: {msg}", flush=True)
        return bool(cond)

    def equal(self, got, want, msg):
        return self.check(got == want, f"{msg}: got {got!r}, wanted {want!r}")

    def within(self, name, value, lo=None, hi=None, fmt="{:.3f}"):
        """One-sided or two-sided limit; pass only the bounds that carry meaning."""
        ok = (lo is None or value >= lo) and (hi is None or value <= hi)
        low = "-" if lo is None else fmt.format(lo)
        high = "-" if hi is None else fmt.format(hi)
        return self.check(ok, f"{name} = {fmt.format(value)} outside [{low}, {high}]")

    def fail(self, msg):
        return self.check(False, msg)

    def run(self, fn, *args, **kwargs):
        """Run one section; an exception counts as a failure and does not stop the rest."""
        label = getattr(fn, "__name__", str(fn))
        before = len(self.failures)
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self.count += 1
            self.failures.append(f"{label} raised: {traceback.format_exc(limit=3).strip()}")
            print(f"FAIL: {self.failures[-1]}", flush=True)
            return None
        if len(self.failures) == before:
            print(f"ok: {label}", flush=True)
        return result

    @property
    def ok(self):
        return not self.failures

    def summary(self):
        if self.ok:
            return f"{self.name} check OK ({self.count} checks)"
        lines = [f"{self.name} check FAILED: {len(self.failures)} of {self.count} checks"]
        lines += [f"  - {msg}" for msg in self.failures]
        return "\n".join(lines)

    def finish(self):
        """Print the summary and return the process exit code."""
        print(self.summary(), flush=True)
        return 0 if self.ok else 1


def require_python():
    if sys.version_info[:2] != (3, 14):
        print(f"Python 3.14 required, found {sys.version_info[0]}.{sys.version_info[1]}")
        return False
    return True


class RunRoot:
    """One temp folder for a whole run; `with RunRoot() as run:` removes it on exit."""

    def __init__(self, prefix="matrix_check_"):
        self.path = tempfile.mkdtemp(prefix=prefix)
        self._counter = itertools.count(1)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        shutil.rmtree(self.path, ignore_errors=True)

    def subdir(self, label):
        path = os.path.join(self.path, f"{label}-{next(self._counter)}")
        os.makedirs(path)
        return path

    def file(self, name):
        """A unique output path (PNG, JSON, log) below the run root."""
        stem, ext = os.path.splitext(name)
        return os.path.join(self.path, f"{stem}-{next(self._counter)}{ext}")

    def env(self, label="run", **extra):
        """Environment for a child: private APPDATA and TEMP, nothing shared."""
        appdata = self.subdir(label + "-appdata")
        temp = self.subdir(label + "-temp")
        env = dict(os.environ, APPDATA=appdata, TEMP=temp, TMP=temp)
        env.update(extra)
        return env


class Result:
    def __init__(self, returncode, stdout, stderr, command):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.command = command

    @property
    def ok(self):
        return self.returncode == 0


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def write_settings(env, data):
    """Write settings.json (a dict, or raw bytes/str) into the APPDATA of a run.env()."""
    folder = os.path.join(env["APPDATA"], "MatrixRain")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "settings.json"), "wb") as handle:
        if isinstance(data, dict | list):
            data = json.dumps(data)
        handle.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def run_check(
    run, label, *args, dummy_video=False, timeout=600, env_extra=None, cwd=ROOT, settings_json=None
):
    """Run `python <args>` with a private environment under `run` and capture the output.

    Output goes to files inside the run root, so a chatty child can never fill a pipe and
    block. `settings_json` is written as the child's settings file first.
    """
    env = run.env(label, **(env_extra or {}))
    if settings_json is not None:
        write_settings(env, settings_json)
    if dummy_video:
        env["SDL_VIDEODRIVER"] = "dummy"
    else:
        env.pop("SDL_VIDEODRIVER", None)
    command = [sys.executable, *[str(a) for a in args]]
    out_path = run.file(f"{label}.out")
    err_path = run.file(f"{label}.err")
    returncode = 0
    with open(out_path, "w", encoding="utf-8") as out, open(err_path, "w", encoding="utf-8") as err:
        try:
            returncode = subprocess.run(
                command, cwd=cwd, env=env, stdout=out, stderr=err, timeout=timeout, check=False
            ).returncode
        except subprocess.TimeoutExpired:
            returncode = 124
            err.write(f"\ntimed out after {timeout} s\n")
    return Result(returncode, _read(out_path), _read(err_path), command)


class LoggedProcess:
    """A child whose stdout and stderr go to files, so the pipe can never fill and block."""

    def __init__(self, run, label, args, env, cwd=ROOT, executable=None):
        self._out_path = run.file(f"{label}.out")
        self._err_path = run.file(f"{label}.err")
        # The child keeps its own copies of the handles, so the parent closes these at once.
        enc = {"mode": "w", "encoding": "utf-8"}
        with open(self._out_path, **enc) as out, open(self._err_path, **enc) as err:
            self.proc = subprocess.Popen(
                [executable or sys.executable, *args], cwd=cwd, env=env, stdout=out, stderr=err
            )

    @property
    def pid(self):
        return self.proc.pid

    def poll(self):
        return self.proc.poll()

    def text(self):
        """(stdout, stderr) written so far."""
        return _read(self._out_path), _read(self._err_path)

    def finish(self, timeout):
        """Wait for exit (kill on timeout); returns (returncode, stdout, stderr)."""
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        return (self.proc.returncode, *self.text())


def wait_for(condition, deadline_s, poll_s=0.02):
    """Poll `condition()` until it is truthy or the deadline passes; returns its last value."""
    end = time.monotonic() + deadline_s
    value = condition()
    while not value and time.monotonic() < end:
        time.sleep(poll_s)
        value = condition()
    return value



@contextlib.contextmanager
def scratch(prefix="matrix_check_"):
    """A private temp folder for an in-process check, removed afterwards."""
    folder = tempfile.mkdtemp(prefix=prefix)
    try:
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)
