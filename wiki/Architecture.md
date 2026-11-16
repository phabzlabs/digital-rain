# Architecture

How Digital Rain is put together, from the command line to a finished frame. Shader detail is in [[Rendering-pipeline]], multi-monitor and OS behaviour in [[Platform-and-monitors]], and the reasoning behind the main choices in [[Design-decisions]].

## Program shape

Digital Rain is a Python program with GPU shaders. It ships on two platforms from one code base.

| Platform | Entry point | Packaging |
| --- | --- | --- |
| Windows | `matrix_saver.py` (root script, calls `digital_rain/windows/matrix_saver.py`) | PyInstaller bundle, with the executable renamed to `.scr` |
| macOS | `mac_saver.py` (root script, imports `digital_rain/mac/mac_saver.py`) | py2app bundle, loaded by `legacyScreenSaver` |

The code is the `digital_rain` package. `digital_rain/` holds the modules both platforms share, `digital_rain/windows/` the Windows-only modules (the entry point, the Tk settings window and its widgets and preview) and `digital_rain/mac/` the macOS-only ones (the saver view, the options sheet, the settings blob and the Core ML depth estimate). The two root scripts exist only because PyInstaller and py2app each need a top-level file to start from.

Both entry points share the GPU renderer (`digital_rain/gl_renderer.py` and `assets/shaders/`), the settings code (`digital_rain/settings.py`, `digital_rain/looks.py`), the glyph code and the platform layer in `digital_rain/osapi/`. Only the Windows entry point has a software renderer and a Tk settings window.

## Windows entry point

Windows starts a `.scr` file with one of three command-line modes.

| Argument | Mode |
| --- | --- |
| `/s` | Run the saver full screen. |
| `/c` | Open the settings window. |
| `/p <hwnd>` | Draw a small preview inside the window with that handle. |

The `/w` wallpaper flag is accepted, draws nothing and exits at once. Wallpaper mode no longer exists.

`main()` in `digital_rain/windows/matrix_saver.py` calls `parse_args`, which returns the mode, the window handle and a set of developer flags. Mode `c` imports `config_dialog` lazily, so the saver never loads Tk. The other modes run this sequence:

1. `osapi.make_dpi_aware()` turns on per-monitor DPI awareness.
2. `_acquire_instance` takes the single-instance mutex.
3. `_load_config` reads the settings with `settings.load()`. With `--settings-file` it cleans that file instead.
4. `_apply_dev_overrides` applies developer flags on top.
5. `run_session(...)` runs until the user leaves. It returns `"restart"` when the monitor layout changed, and `main()` loops until it returns anything else.

A hidden `--warm-up` run draws for one second and exits. Antivirus and Gatekeeper scan a freshly installed library on first load, and the run pays that cost in advance. `tools/build/install.ps1` runs it.

## Session and main loop

`Session` in `digital_rain/windows/matrix_saver.py` owns the monitor list, the renderer and the loop. One call to `tick()` produces one frame:

1. `FrameLimiter.wait` sleeps until the next frame is due, then spins for the last millisecond.
2. The frame time `dt` is measured and clamped to `MAX_FRAME_DT` (0.1 s), so a stall never makes the rain jump.
3. `_handle_events` reads input and decides whether to exit.
4. `_draw` calls `renderer.render(t, dt, frame)` and then `display.flip()`.
5. `_embed_after_first_frame` attaches a hidden preview window to its parent once there is something to show.
6. `_periodic_checks` looks at the power state and the monitor layout.

A `DevRun` object handles timed runs for the checks: a fixed `--seconds` duration, a `--shot` screenshot and the performance report.

`ExitGate` decides when mouse movement exits. A key press, a click or a window close always exits. Mouse movement exits once the cursor has travelled more than 25 pixels in total, after the first 0.6 s. Timed runs and previews ignore input.

## Renderer choice

`make_renderer` tries `_make_gl` first. If that raises any exception it prints a message and calls `_make_soft`. Both renderer modules are imported lazily, so the GPU path never loads the software renderer and the other way round.

| Renderer | Module | When it runs |
| --- | --- | --- |
| GPU | `digital_rain/gl_renderer.py`, `assets/shaders/` | Default. Needs OpenGL 3.3 core. |
| Software | `digital_rain/soft_renderer.py` | OpenGL is unavailable, for example over Remote Desktop or in some virtual machines. |

`_make_gl` asks for a GL 3.3 core context with vsync. For HDR it also asks for a float16 RGBA framebuffer. pygame-ce rejects that attribute, so the code sets it through the SDL C library with ctypes. If the float format is unavailable, it quits the display and creates the window again, because Windows cannot change the pixel format of an existing window.

The macOS saver has no software fallback. If the GL renderer fails there, the view logs the error and draws black.

## One window, many monitors

On Windows the saver opens one borderless window that covers the whole virtual desktop. The renderer looks up which monitor each pixel belongs to. vsync does not pace a window that spans several monitors (200 fps was measured), so the frame limiter paces the loop at the refresh rate of the fastest display, or lower when the `frame_cap` setting or battery power asks for it. [[Platform-and-monitors]] covers the details.

## Platform layer

`digital_rain/osapi/` hides every operating-system call behind one set of names. `osapi/__init__.py` imports `digital_rain/osapi/windows.py` or `digital_rain/osapi/mac.py` by `sys.platform`. The `INTERFACE` tuple lists the names that each implementation must provide, and `tools/checks/check_assets.py` checks that both do. `digital_rain/osapi/common.py` holds the code that does not depend on the OS, such as `monitor_signature`, `virtual_bounds`, `clamp_dpi` and `valid_refresh_rate`.

The names cover files and logging, fonts, monitor enumeration, DPI, refresh rate, battery state, GPU load, HDR information, single-instance locks, named events, preview embedding and settings-dialog helpers. On macOS some are no-ops, because `legacyScreenSaver` already does the work, and the Windows-only window helpers raise `NotImplementedError`.

## Settings

`digital_rain/settings.py` defines `DEFAULTS`, `RANGES` and `ENUMS`. `clean(raw)` calls `migrate` and then lays validated values over the defaults. It clamps numbers, checks enums, limits message text to 24 characters and cleans the per-monitor overrides. Bad input never raises. `load()` returns the defaults on any read error.

`save()` writes a temporary file and then calls `os.replace`, so a crash cannot leave a half-written file. The saver only reads settings. Only the dialog writes them.

`looks.resolve(cfg)` turns the cleaned settings into one flat dictionary of look values for the renderers. The film presets (`film_1999`, `reloaded`, `resurrections`) are JSON files in `assets/presets`. The `custom` preset passes the user's own sliders through unchanged. See [[Settings-reference]] for what each setting does.

## Settings dialog model

The dialog is split into a model and two views.

| Part | File | Role |
| --- | --- | --- |
| Model | `digital_rain/dialog_model.py` | Editing state and rules: scope, per-monitor overrides, which controls are enabled, help text, page layout. No Tk and no numpy. |
| Windows view | `digital_rain/windows/config_dialog.py`, `digital_rain/windows/dialog_widgets.py`, `digital_rain/windows/dialog_preview.py` | The Tk window and its live preview strip. |
| macOS view | `digital_rain/mac/mac_options.py` | The options sheet. |

The macOS bundle excludes `tkinter`, so the model cannot depend on it. `tools/checks/check_dialog.py` checks every rule without opening a window.

## Frame production

On the GPU path, `GLRenderer.render` runs a fixed series of passes: an optional reveal cache, the scene pass, optional picture passes, bloom, a final pass, then optional upscaling and HDR conversion. The scene shader computes the rain from the clock and a hash of each lane, so the GPU path stores no rain state between frames. [[Rendering-pipeline]] walks through each pass.

On the software path, `digital_rain/soft_renderer.py` builds the same look with numpy and pygame surfaces. It draws pre-rendered glyph brightness levels and one bloom at quarter resolution. It shares the message code and the easter egg with the GPU path.

## Side features

| Feature | Module | Notes |
| --- | --- | --- |
| Typed messages and the clock | `digital_rain/rain_message.py` | A glyph mask that cells latch onto. Shared by both renderers. |
| Easter egg | `digital_rain/easter_egg.py` | A typed overlay, drawn on the GPU path with `overlay.vert` and `overlay.frag`. |
| Live load | `digital_rain/live_load.py` | CPU or GPU load changes the rain speed and density. |
| Picture in rain | `digital_rain/image_layer.py`, `digital_rain/surfaces.py`, `digital_rain/mac/depth_coreml.py` | A picture drawn only as rain glyphs. GPU only. |
| Upscaling | `digital_rain/fsr.py` | AMD FSR 1.0 ported to GL 3.3. |

## Module overview

| File | Purpose |
| --- | --- |
| `matrix_saver.py` | Root script that starts the Windows entry point (PyInstaller freezes it). |
| `digital_rain/windows/matrix_saver.py` | Windows entry point, argument parsing, session, frame loop. |
| `digital_rain/exit_gate.py` | Mouse-movement exit rule. |
| `mac_saver.py` | Root script that imports the macOS saver module (py2app bundles it as the plugin script). |
| `digital_rain/mac/mac_saver.py` | macOS `ScreenSaverView` subclass, one view per display. |
| `digital_rain/mac/mac_settings.py` | macOS settings storage in `ScreenSaverDefaults`. |
| `digital_rain/mac/mac_options.py` | macOS options sheet. |
| `digital_rain/gl_renderer.py` | GPU renderer and pass orchestration. |
| `digital_rain/soft_renderer.py` | Software renderer. |
| `assets/shaders/` | GLSL for scene, bloom, final, FSR post, HDR and overlay passes. |
| `digital_rain/glyphs.py` | Glyph tiles for the classic and Resurrections sets. |
| `digital_rain/looks.py` | Preset resolution and the time and glyph helpers shared with the shader. |
| `digital_rain/settings.py` | Defaults, ranges, migration, validation, load and save. |
| `digital_rain/dialog_model.py` | Settings dialog rules without any GUI. |
| `digital_rain/windows/config_dialog.py` | Windows Tk settings window. |
| `digital_rain/osapi/` | Platform layer with one Windows and one macOS implementation. |
| `digital_rain/resources.py` | Finds bundled files and fills shader templates. |
| `digital_rain/rain_message.py` | Message and clock masks and their latching rules. |
| `digital_rain/live_load.py` | Load sampling and the speed and density mapping. |
| `digital_rain/fsr.py` | FSR upscaler: an EASU resample pass and an RCAS sharpen pass. |
| `digital_rain/image_layer.py` | Picture folder scanning, worker thread and GPU upload. |
| `tools/` | `check.py` (the gate), `checks/` (the sub-checks, their helpers and the golden frames), `dev/` (one-off measurement and Mac host scripts) and `build/` (the Mac build, the installer and the icon and picker-name helpers). See [[Checks-and-tests]]. |

## Bundled files

`digital_rain/resources.py` resolves the base folder in three cases: the source tree, the PyInstaller temporary folder (`sys._MEIPASS`) and the py2app `RESOURCEPATH`. Its `shader(name, **subs)` function treats a shader file as a `%(NAME)s` template. The scene shader is compiled twice with different `STAGE` values, once for the rain and once for the picture passes.

## Build and test

[[Build-and-release]] covers the PyInstaller and py2app builds. [[Checks-and-tests]] covers the check tiers and the golden frames that guard the renderers.
