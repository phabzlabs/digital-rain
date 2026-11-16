"""Preview strip and Full screen of the settings window.

In normal use the strip hosts the saver itself as a child process:
    /p <strip hwnd> --settings-file <temp json> --fps 18 --preview-scale K
       --ready-event Local\\MatrixRainDialogReady-<dialog pid>-<n> --run <dialog value>
The child starts hidden, embeds itself in the strip after its first frame and
then sets the named event (the frozen build has no console, so stdout can't
carry the signal). The old child keeps drawing until the new child's event is
set, or 3 s pass, so there is no blank frame between changes.

With a dialog shot, or when MATRIX_CHECK_HIDDEN is set, no child starts: the
strip shows a still sample drawn on a canvas, and nothing outside the dialog
window appears on screen.
"""

import base64
import contextlib
import json
import os
import random
import subprocess
import sys
import tempfile
import time
import tkinter as tk

from digital_rain import osapi
from digital_rain.windows import dialog_widgets as dw
from digital_rain.windows.dialog_widgets import sc

FPS = 18
PREVIEW_SCALE = 0.5
TEMP_PREFIX = "MatrixRain-dialog-"
READY_POLL_MS = 50
IDLE_POLL_MS = 500
DEBOUNCE_MS = 500
HOLD_S = 3.0  # the old child draws at most this long after a restart
READY_TIMEOUT_S = 5.0
KILL_AFTER_S = 2.0  # a terminated child still running after this is killed
REAP_POLL_MS = 100
FULL_POLL_MS = 500
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def saver_command():
    """The saver: the frozen executable itself, or the root matrix_saver.py from source."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [
        sys.executable,
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "matrix_saver.py",
        ),
    ]


def child_args(hwnd, settings_file, event_name, scale=PREVIEW_SCALE, fps=FPS, run=None):
    """Command line of one preview child drawing into window `hwnd`."""
    args = saver_command() + [
        "/p",
        str(hwnd),
        "--settings-file",
        settings_file,
        "--fps",
        f"{fps:g}",
        "--preview-scale",
        f"{scale:g}",
        "--ready-event",
        event_name,
    ]
    if run is not None:
        args += ["--run", str(run)]
    return args


def event_name(n):
    return f"Local\\MatrixRainDialogReady-{os.getpid()}-{n}"


def write_temp(cfg, path=None):
    """cfg as JSON in `path`, or in a new temp file under the MatrixRain-dialog- prefix."""
    if path is None:
        fd, path = tempfile.mkstemp(prefix=TEMP_PREFIX, suffix=".json")
    else:
        fd = os.open(path, os.O_WRONLY | os.O_TRUNC)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    return path


def live_allowed():
    """Check runs (MATRIX_CHECK_HIDDEN) never start a child, and only Windows can
    reparent the child into the strip (elsewhere the static sample shows)."""
    return sys.platform == "win32" and not os.environ.get("MATRIX_CHECK_HIDDEN")


def _remove(path):
    with contextlib.suppress(OSError):
        os.remove(path)


def _close_handle(handle):
    if handle:
        osapi.close_event(handle)


class _Child:
    def __init__(self, proc, handle, path):
        self.proc, self.handle, self.path = proc, handle, path
        self.started = time.monotonic()


def draw_static(cv, w, h, colour, dim=False, note=None, seed=7):
    """The still sample: a few columns of glyphs in the preset's colour."""
    cv.delete("static")
    rnd = random.Random(seed)
    font = dw.FONTS["glyph"]
    cw = max(4, font.measure("0") + sc(6))
    ch = max(6, font.metrics("linespace"))
    bg = dw.BG_PREVIEW
    cols = max(1, w // cw)
    for c in range(cols):
        if rnd.random() < 0.35:
            continue
        top = rnd.randint(-6, max(0, h // ch - 2))
        length = rnd.randint(3, max(4, h // ch))
        for k in range(length):
            y = (top + k) * ch + ch // 2
            if y < 0 or y > h:
                continue
            fade = 0.15 + 0.75 * (1 - k / length)
            if dim:
                fade *= 0.4
            col = dw.blend(colour, bg, 1 - fade)
            cv.create_text(
                c * cw + cw // 2, y, text=rnd.choice(dw.GLYPHS), fill=col, font=font, tags="static"
            )
    if note:
        cv.create_text(
            w / 2, h / 2, text=note, fill=dw.TEXT, font=dw.FONTS["body_semi"], tags="static"
        )


def draw_paused(cv, w, h):
    """Centred "Paused" pill with a pause icon."""
    cv.delete("pause")
    font = dw.FONTS["body_semi"]
    tw = font.measure("Paused") + sc(46)
    ph = sc(dw.MIN_H["pill"])
    x0, y0 = (w - tw) / 2, (h - ph) / 2
    dw.rrect(
        cv, x0, y0, x0 + tw, y0 + ph, ph / 2, fill=dw.BG_PANEL, outline=dw.BORDER, tags="pause"
    )
    bx, by, bh = x0 + sc(14), h / 2 - sc(6), sc(12)
    for dx in (0, sc(6)):
        cv.create_rectangle(
            bx + dx, by, bx + dx + sc(3), by + bh, fill=dw.TEXT, outline="", tags="pause"
        )
    cv.create_text(
        x0 + sc(30), h / 2, text="Paused", anchor="w", fill=dw.TEXT, font=font, tags="pause"
    )


class Preview:
    """Runs the preview children for the strip and the Full screen process.

    host: the tk.Frame the children draw into (its canvas shows the stills).
    get_cfg() -> (cfg for the strip, full cfg for Full screen, sample colour).
    on_full(running) is told when Full screen starts and ends."""

    def __init__(
        self,
        root,
        host,
        canvas,
        get_cfg,
        on_full=None,
        force=False,
        extra_args=(),
        scale=PREVIEW_SCALE,
    ):
        self.root, self.host, self.canvas = root, host, canvas
        self.get_cfg, self.on_full = get_cfg, on_full
        self.allowed = force or live_allowed()
        self.extra_args = list(extra_args)
        self.scale = scale
        self.live = False
        self.paused = False
        self.unavailable = False
        self.current = None
        self.starting = None
        self.queued = False
        self.failures = 0
        self.n = 0
        self.temps = set()
        self.strip_file = None  # settings file shared by every strip child
        self.full_file = None
        self.dying = []  # [(process, kill deadline)] terminated, not yet exited
        self.jobs = {}
        self.full = None
        self.still = None
        self.closed = False
        self.ready_times = []  # (monotonic time the event was seen, child) for checks
        self.terminated = []  # children terminated, in order (for checks)
        self.child_cmds = []  # argument list of every child started, in order (for checks)
        # One rain layout for the life of the dialog, kept across setting changes.
        self.run = random.SystemRandom().randrange(1, 2**32)

    def _after(self, name, ms, fn):
        self._cancel(name)
        self.jobs[name] = self.root.after(ms, fn)

    def _cancel(self, name):
        job = self.jobs.pop(name, None)
        if job:
            with contextlib.suppress(tk.TclError):
                self.root.after_cancel(job)

    def _terminate(self, proc):
        """Ask `proc` to exit without waiting: _reap collects it, or kills it if it hangs."""
        if proc.poll() is None:
            self.dying.append((proc, time.monotonic() + KILL_AFTER_S))
            proc.terminate()
            if not self.closed:
                self._after("reap", REAP_POLL_MS, self._reap)

    def _reap(self):
        self.jobs.pop("reap", None)
        now = time.monotonic()
        waiting = []
        for proc, deadline in self.dying:
            if proc.poll() is not None:
                continue
            if now > deadline:
                proc.kill()
            waiting.append((proc, deadline))
        self.dying = waiting
        if waiting:
            self._after("reap", REAP_POLL_MS, self._reap)

    def _kill(self, child):
        if child is None:
            return
        self._terminate(child.proc)
        _close_handle(child.handle)
        child.handle = None
        self.terminated.append(child)

    def size(self):
        return max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())

    def draw(self):
        """Redraw the canvas under the child (the still sample, paused frame or note)."""
        w, h = self.size()
        cv = self.canvas
        cv.delete("all")
        _cfg, _full, colour = self.get_cfg()
        if self.paused:
            if self.still is not None:
                cv.create_image(0, 0, image=self.still, anchor="nw", tags="static")
            else:
                draw_static(cv, w, h, colour, dim=True)
            draw_paused(cv, w, h)
            return
        note = "Preview unavailable" if self.unavailable else None
        draw_static(cv, w, h, colour, dim=self.unavailable, note=note)

    def start(self):
        """Start the live preview (after first paint). Does nothing in check runs."""
        self.draw()
        if not self.allowed or self.closed:
            return
        self.live = True
        self.restart_now()

    def changed(self):
        """A setting or the strip size changed: restart about 500 ms after the last change."""
        if not self.live or self.paused or self.unavailable:
            self.draw()
            return
        self._after("debounce", DEBOUNCE_MS, self.restart_now)

    def restart_now(self):
        self._cancel("debounce")
        if not self.live or self.paused or self.unavailable or self.closed:
            return
        if self.starting is not None:
            self.queued = True
            return
        cfg, _full, _colour = self.get_cfg()
        self.strip_file = write_temp(cfg, self.strip_file)
        path = self.strip_file
        self.temps.add(path)
        self.n += 1
        name = event_name(self.n)
        handle = osapi.create_event(name)
        try:
            if handle is None:
                raise OSError("ready event unavailable")
            cmd = (
                child_args(self.host.winfo_id(), path, name, self.scale, run=self.run)
                + self.extra_args
            )
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
        except OSError:
            _close_handle(handle)
            self._failed()
            return
        self.child_cmds.append(cmd)
        self.starting = _Child(proc, handle, path)
        self._after("tick", READY_POLL_MS, self._tick)

    def _failed(self):
        self.failures += 1
        if self.failures >= 2:
            self.unavailable = True
            self._kill(self.current)
            self.current = None
            self.draw()
            return
        self.root.after_idle(self.restart_now)

    def _tick(self):
        self.jobs.pop("tick", None)
        if self.closed:
            return
        s = self.starting
        if s is not None:
            age = time.monotonic() - s.started
            if osapi.event_is_set(s.handle):
                self.ready_times.append((time.monotonic(), s))
                old, self.current, self.starting = self.current, s, None
                self.failures = 0
                self._kill(old)
                if self.queued:
                    self.queued = False
                    self.restart_now()
            elif s.proc.poll() is not None or age > READY_TIMEOUT_S:
                self.starting = None
                self._kill(s)
                self.queued = False
                self._failed()
            elif age > HOLD_S and self.current is not None:
                self._kill(self.current)
                self.current = None
        c = self.current
        if c is not None and c.proc.poll() is not None and self.starting is None:
            # the drawing child died: count it and start another
            self.current = None
            _close_handle(c.handle)
            if c.proc.returncode != 0:
                self._failed()
            else:
                self.restart_now()
        if self.starting is not None:
            self._after("tick", READY_POLL_MS, self._tick)
        elif self.current is not None:
            self._after("tick", IDLE_POLL_MS, self._tick)

    def pause(self):
        """Window lost focus or was minimised: keep a dimmed still, stop the child."""
        if not self.live or self.paused:
            return
        self.paused = True
        self._cancel("debounce")
        self.still = None
        if self.current is not None:
            try:
                w, h, rgb = osapi.capture_client_rgb(self.host.winfo_id())
                if w > 0 and h > 0 and rgb.strip(b"\x00"):
                    ppm = b"P6 %d %d 255\n" % (w, h) + rgb
                    self.still = tk.PhotoImage(
                        master=self.root, data=base64.b64encode(ppm), format="ppm"
                    )
            except RuntimeError, OSError, tk.TclError:
                self.still = None
        self._kill(self.starting)
        self.starting = None
        self.queued = False
        self._kill(self.current)
        self.current = None
        self.draw()

    def resume(self):
        if not self.paused:
            return
        self.paused = False
        self.still = None
        self.draw()
        self.restart_now()

    def full_screen(self):
        """Run the saver full screen with the unsaved settings (input exits it)."""
        if self.full is not None or self.closed:
            return
        _cfg, full, _colour = self.get_cfg()
        self.full_file = write_temp(full, self.full_file)
        path = self.full_file
        self.temps.add(path)
        try:
            self.full = subprocess.Popen(
                saver_command() + ["/s", "--settings-file", path, "--run", str(self.run)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
        except OSError:
            self.full = None
            return
        if self.on_full:
            self.on_full(True)
        self._after("full", FULL_POLL_MS, self._full_poll)

    def _full_poll(self):
        self.jobs.pop("full", None)
        if self.full is None:
            return
        if self.full.poll() is None:
            self._after("full", FULL_POLL_MS, self._full_poll)
            return
        self.full = None
        if self.on_full and not self.closed:
            self.on_full(False)

    def close(self):
        """Terminate every child, close every event and delete every temp file."""
        if self.closed:
            return
        self.closed = True
        for name in list(self.jobs):
            self._cancel(name)
        self._kill(self.starting)
        self._kill(self.current)
        self.starting = self.current = None
        if self.full is not None:
            self._terminate(self.full)
            self.full = None
        # The dialog is going away, so nothing will poll: kill whatever is left now.
        for proc, _deadline in self.dying:
            if proc.poll() is None:
                proc.kill()
        self.dying = []
        for path in list(self.temps):
            _remove(path)
        self.temps.clear()
