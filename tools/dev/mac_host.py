"""Runs the Mac saver view (mac_saver.MatrixRainView) in ordinary windows,
outside legacyScreenSaver, so it can be tested before the .saver bundle exists.
Errors print to the terminal, and the saver's own log lines
land in ~/Library/Application Support/MatrixRain/logs/saver.log (unsandboxed,
state_dir() is the real folder).

    python tools/dev/mac_host.py [--mode window|preview|fullscreen|covered]
                             [--seconds N] [--preset NAME] [--settings-file PATH]
                             [--sheet] [--options] [--out DIR]

    window        one 1280 x 720 point window, drawn as a full-screen view
    preview       a thumbnail-sized window (isPreview), as in System Settings
    fullscreen    a borderless window over every display at screen-saver level;
                  it closes itself after --seconds (nothing else dismisses it)
    covered       what legacyScreenSaver does on macOS 14 and later: a second
                  full-screen view opens over a first one that keeps animating.
                  Passes when the older view goes idle and the newer one draws
    --sheet       also open the configure sheet (the options sheet) for 3 seconds
    --options     open the options sheet in an ordinary window, run until you
                  press Save or Cancel (no timeout, --seconds is ignored while
                  it is open), then print the saved blob and where settings
                  were read from: python tools/dev/mac_host.py --options
    --out DIR     save a PNG per view, a copy of saver.log and a report there

Exit code 0 when every view drew frames without an error. tools/dev/mac_host.sh
sets up a venv and runs the whole test set. macOS only.
"""

import argparse
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def parse():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--mode", default="window", choices=("window", "preview", "fullscreen", "covered")
    )
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--preset")
    ap.add_argument("--settings-file")
    ap.add_argument("--size", help="window size in points, WxH")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--options", action="store_true")
    ap.add_argument("--out")
    return ap.parse_args()


def run_loop(seconds):
    from Foundation import NSDate, NSRunLoop

    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(1 / 240))


def main():
    if sys.platform != "darwin":
        print("mac_host.py runs on macOS only")
        return 2
    args = parse()
    from digital_rain import osapi
    from digital_rain.mac import mac_saver

    if args.settings_file:
        mac_saver.settings_file = args.settings_file
    if args.preset:
        mac_saver.cfg_overrides["preset"] = args.preset
    from AppKit import (
        NSApplication,
        NSApplicationActivationPolicyRegular,
        NSBackingStoreBuffered,
        NSMakeRect,
        NSScreen,
        NSScreenSaverWindowLevel,
        NSWindow,
        NSWindowStyleMaskBorderless,
        NSWindowStyleMaskTitled,
    )

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    app.finishLaunching()
    log_start = os.path.getsize(osapi.log_path()) if os.path.exists(osapi.log_path()) else 0
    print(
        f"host: mode={args.mode} seconds={args.seconds} preset={args.preset or '(settings)'}"
        f" log={osapi.log_path()}"
    )

    if args.mode == "covered":
        return run_covered(args, mac_saver)

    pairs = []
    if args.mode == "fullscreen":
        for scr in NSScreen.screens():
            f = scr.frame()
            win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_screen_(
                NSMakeRect(0, 0, f.size.width, f.size.height),
                NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False,
                scr,
            )
            win.setFrame_display_(f, True)
            win.setLevel_(NSScreenSaverWindowLevel)
            view = mac_saver.MatrixRainView.alloc().initWithFrame_isPreview_(
                NSMakeRect(0, 0, f.size.width, f.size.height), False
            )
            pairs.append((win, view))
    else:
        preview = args.mode == "preview"
        w, h = (300, 188) if preview else (1280, 720)
        if args.size:
            w, h = (int(v) for v in args.size.lower().split("x"))
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(120, 120, w, h), NSWindowStyleMaskTitled, NSBackingStoreBuffered, False
        )
        win.setTitle_(f"Digital Rain host ({args.mode})")
        view = mac_saver.MatrixRainView.alloc().initWithFrame_isPreview_(
            NSMakeRect(0, 0, w, h), preview
        )
        pairs.append((win, view))
    if not pairs or any(v is None for _w, v in pairs):
        print("host: initWithFrame:isPreview: returned nil")
        return 1
    for win, view in pairs:
        win.setContentView_(view)
        win.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)
    for _win, view in pairs:
        view.startAnimation()

    # The ScreenSaverView timer normally calls animateOneFrame. If it does not
    # fire in a plain app, drive the views by hand.
    t0 = time.perf_counter()
    run_loop(min(1.5, args.seconds))
    driver = "ScreenSaverView timer"
    manual = all(v.mr.frame == 0 for _w, v in pairs) and not all(v.mr.failed for _w, v in pairs)
    if manual:
        driver = "manual (the timer did not fire)"
    shot_at = t0 + args.seconds * 0.6
    shots = []
    while time.perf_counter() < t0 + args.seconds:
        if args.out and not shots and time.perf_counter() >= shot_at:
            os.makedirs(args.out, exist_ok=True)
            for i, (_w, v) in enumerate(pairs, 1):
                name = f"{args.mode}{'-' + args.preset if args.preset else ''}-view{i}.png"
                v.mr.shot_path = os.path.join(args.out, name)
                shots.append(v.mr.shot_path)
        if manual:
            for _w, v in pairs:
                v.animateOneFrame()
            run_loop(1 / 60)
        else:
            run_loop(0.05)

    if args.sheet:
        _w, v = pairs[0]
        sheet = v.configureSheet()
        if sheet is None:
            print("host: configureSheet returned nil")
        else:
            pairs[0][0].beginSheet_completionHandler_(sheet, None)
            run_loop(3.0)
            pairs[0][0].endSheet_(sheet)
            print("host: options sheet shown for 3 s")

    if args.options:
        run_options(pairs[0])

    elapsed = time.perf_counter() - t0
    ok = True
    lines = [f"driver: {driver}"]
    for i, (_win, view) in enumerate(pairs, 1):
        view.stopAnimation()
        mr = view.mr
        r = mr.renderer
        good = mr.frame > 0 and not mr.failed
        ok = ok and good
        lines.append(
            f"view {i}: {'OK' if good else 'FAILED'} frames={mr.frame} "
            f"avg_fps={mr.frame / max(elapsed, 1e-6):.1f} cap={mr.fps} "
            f"size={mr.size} preview={mr.preview} "
            f"glyphs={getattr(r, 'glyph_source', None)} "
            f"preset={(mr.cfg or {}).get('preset')}"
        )
    lines.append(f"shots: {[s for s in shots if os.path.exists(s)]}")
    for ln in lines:
        print("host: " + ln)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "report.txt"), "a", encoding="utf-8") as fh:
            fh.write(f"== {time.strftime('%H:%M:%S')} mode={args.mode} preset={args.preset}\n")
            fh.write("\n".join(lines) + "\n")
        if os.path.exists(osapi.log_path()):
            with open(osapi.log_path(), encoding="utf-8", errors="replace") as src:
                src.seek(log_start if os.path.getsize(osapi.log_path()) >= log_start else 0)
                with open(os.path.join(args.out, "saver.log"), "a", encoding="utf-8") as dst:
                    shutil.copyfileobj(src, dst)
    return 0 if ok else 1


def run_options(pair):
    """Open the options sheet on the first window and run until it closes
    (Save or Cancel). No timeout: the user clicks through it."""
    win, view = pair
    sheet = view.mr.configure_sheet()
    if sheet is None:
        print("host: configure_sheet returned nil")
        return
    closed = []
    win.beginSheet_completionHandler_(sheet, lambda _code: closed.append(1))
    print("host: options sheet open, press Save or Cancel")
    while not closed and view.mr.sheet_target is not None:
        run_loop(0.05)
    from digital_rain import osapi
    from digital_rain.mac import mac_settings

    blob = mac_settings.read_blob(mac_settings.open_defaults())
    cfg, source, problems = mac_settings.resolve(blob, osapi.settings_read_path())
    print(f"options: source={source} problems={problems}")
    print(f"options: blob={blob}")


def run_covered(args, mac_saver):
    """The legacyScreenSaver behaviour seen in the first bundle runs, in plain windows:
    a newer full-screen view shown over an older one that keeps animating."""
    from AppKit import (
        NSApplication,
        NSBackingStoreBuffered,
        NSMakeRect,
        NSWindow,
        NSWindowStyleMaskTitled,
    )

    app = NSApplication.sharedApplication()

    def window(title, w, h):
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(120, 120, w, h), NSWindowStyleMaskTitled, NSBackingStoreBuffered, False
        )
        win.setTitle_(title)
        return win

    lines = []
    w1 = window("Digital Rain host (covered: old view)", 1280, 720)
    v1 = mac_saver.MatrixRainView.alloc().initWithFrame_isPreview_(
        NSMakeRect(0, 0, 1280, 720), False
    )
    w1.setContentView_(v1)
    w1.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)
    v1.startAnimation()
    run_loop(2.0)
    f1_before = v1.mr.frame
    # The host makes a second view for the same display and shows it over
    # the first, which it leaves animating (and re-sends startAnimation).
    w2 = window("Digital Rain host (covered: new view)", 1280, 720)
    v2 = mac_saver.MatrixRainView.alloc().initWithFrame_isPreview_(
        NSMakeRect(0, 0, 1280, 720), False
    )
    w2.setContentView_(v2)
    w2.makeKeyAndOrderFront_(None)
    v1.startAnimation()
    v2.startAnimation()
    run_loop(max(3.0, args.seconds - 2.0))
    f1_after, f2 = v1.mr.frame, v2.mr.frame
    ok = (
        f1_before > 0
        and f2 > 0
        and v1.mr.idle
        and not v2.mr.idle
        and not v1.mr.failed
        and not v2.mr.failed
    )
    lines.append(
        f"covered: {'OK' if ok else 'FAILED'} old view frames {f1_before} before "
        f"the cover, {f1_after - f1_before} after (idle={v1.mr.idle}); new view "
        f"frames {f2} (idle={v2.mr.idle}, cap {v2.mr.fps})"
    )
    for v in (v1, v2):
        v.stopAnimation()
    keep = (w1, w2)
    for ln in lines:
        print("host: " + ln)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "report.txt"), "a", encoding="utf-8") as fh:
            fh.write(f"== {time.strftime('%H:%M:%S')} mode={args.mode}\n" + "\n".join(lines) + "\n")
    for win in keep:
        win.orderOut_(None)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
