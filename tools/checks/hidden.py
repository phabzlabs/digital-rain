"""Run the check tools without disturbing the person at the keyboard.

Every tool in tools/ that opens a window or launches the saver does
`import hidden` and calls `hidden.setup()` (check.py and the sub-checks do).
Default (hidden) behaviour:
  * Every saver launch gets the explicit --check-hidden argument (added in the
    Popen patch). matrix_saver.py then opens its window with pygame.HIDDEN and
    skips set_topmost and the desktop attach. The environment alone never hides
    a real launch (MATRIX_CHECK_HIDDEN=1 only enables the tools' own tkinter
    patch).
  * tkinter windows (the settings dialog, the /p host) are made fully
    transparent and non-activating, in this process and in every child
    (tools/checks/hidden_site/sitecustomize.py, added to PYTHONPATH).
  * Child processes get CREATE_NO_WINDOW and SW_HIDE, so nothing flashes or
    takes focus. The tools run at BELOW_NORMAL priority; the timed saver
    subprocesses stay at normal priority because a low-priority saver misses
    its fps gate under load (MATRIX_CHECK_PRIORITY=below lowers them too,
    =normal lowers nothing).
Visible behaviour: pass --show to any tool, or set MATRIX_CHECK_SHOW=1.
Checks that only prove something with a real visible window call
`hidden.skip(name)` and print SKIPPED (needs --show) in the default run.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "hidden_site")
CREATE_NO_WINDOW = 0x08000000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
NORMAL_PRIORITY_CLASS = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
GWL_EXSTYLE = -20
_done = False


def show():
    """True when windows should be visible (--show or MATRIX_CHECK_SHOW=1)."""
    return "--show" in sys.argv or os.environ.get("MATRIX_CHECK_SHOW") == "1"


def skip(name):
    """In the hidden run print the SKIPPED line and return True."""
    if show():
        return False
    print(f"SKIPPED (needs --show): {name}")
    return True


def patch_tk(tkinter):
    """Make every new Tk root transparent and non-activating (still mapped, so
    geometry and PrintWindow captures are unchanged)."""
    import ctypes

    orig = tkinter.Tk.__init__
    if getattr(orig, "_matrix_hidden", False):
        return

    def init(self, *a, **k):
        orig(self, *a, **k)
        try:
            self.attributes("-alpha", 0.0)
            self.update_idletasks()
            u32 = ctypes.windll.user32
            u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            u32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            u32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
            hwnd = int(self.wm_frame(), 16)
            u32.SetWindowLongPtrW(
                hwnd, GWL_EXSTYLE, u32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) | WS_EX_NOACTIVATE
            )
        except Exception:
            pass

    init._matrix_hidden = True
    tkinter.Tk.__init__ = init


def setup():
    """Idempotent. --show (or MATRIX_CHECK_SHOW=1) leaves everything visible."""
    global _done
    if _done:
        return
    _done = True
    if show():
        os.environ["MATRIX_CHECK_SHOW"] = "1"
        os.environ.pop("MATRIX_CHECK_HIDDEN", None)
        return
    if sys.platform != "win32":
        return
    import ctypes

    os.environ["MATRIX_CHECK_HIDDEN"] = "1"
    prev = os.environ.get("PYTHONPATH")
    if SITE not in (prev or "").split(os.pathsep):
        os.environ["PYTHONPATH"] = SITE + (os.pathsep + prev if prev else "")
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    if os.environ.get("MATRIX_CHECK_PRIORITY") != "normal":
        k32.SetPriorityClass(k32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS)
    # Saver runs are timed (fps gate), so children go back to normal priority
    # (measured: BELOW_NORMAL starves them under load); the tools stay low.
    low_children = os.environ.get("MATRIX_CHECK_PRIORITY") == "below"
    orig = subprocess.Popen.__init__

    def init(self, *a, **k):
        args = a[0] if a else k.get("args")
        if (
            isinstance(args, (list, tuple))
            and "--check-hidden" not in args
            and any(str(x).lower().endswith(("matrix_saver.py", ".scr")) for x in args)
        ):
            if a:
                a = (list(args) + ["--check-hidden"],) + a[1:]
            else:
                k["args"] = list(args) + ["--check-hidden"]
        k["creationflags"] = (
            (k.get("creationflags") or 0)
            | CREATE_NO_WINDOW
            | (0 if low_children else NORMAL_PRIORITY_CLASS)
        )
        if k.get("startupinfo") is None:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE
            k["startupinfo"] = si
        orig(self, *a, **k)

    subprocess.Popen.__init__ = init
    try:
        import tkinter

        patch_tk(tkinter)
    except ImportError:
        pass
