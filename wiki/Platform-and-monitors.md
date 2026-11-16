# Platform and monitors

How Digital Rain handles displays, power and the operating system. Every platform call sits behind `digital_rain/osapi/`, described in [[Architecture]]. For macOS packaging and install steps, see [[macOS]].

## Monitor list

`osapi.list_monitors()` returns one dictionary per display with `x`, `y`, `w`, `h`, `dpi`, `id` and `name`. Positions are in pixels, the origin is the top left of the primary display, and the primary display comes first. Both platforms use this layout.

On Windows, `dpi` is the scale factor: the effective DPI from `GetDpiForMonitor` divided by 96, clamped to 0.75 to 3.0 by `clamp_dpi` in `digital_rain/osapi/common.py`. The `id` is the lower-cased device interface path, or `gdi:<device>` when that is unavailable. If two monitors produce the same id, the second gets a `|2` suffix.

On macOS, `dpi` is the backing scale factor, 2.0 on a Retina display. macOS works in points from the bottom left, so the code flips the y axis and multiplies by each display's scale. With displays of mixed scale the pixel layout is approximate, and nothing in the saver depends on it being exact. The `id` is built from the display's vendor, model and serial numbers (`cg:<vendor>-<model>-<serial>`), which survives replugging and restarts.

## One window across monitors

The Windows saver opens a single borderless window over the virtual desktop. The scene shader finds each pixel's monitor through up to eight rectangles (`u_mon`). Each monitor's cell size follows that monitor's DPI scale.

Per-monitor settings (preset, colour, speed, density and depth) are stored under the monitor's id. When every monitor shares one look, one full-screen pass draws everything. When they differ, the renderer draws one scissored rectangle per monitor. A monitor with no override uses the global look. By default there are no overrides.

With `--split-sim` the saver simulates two monitors on a single display, which the check scripts use to exercise this path.

## Per-monitor DPI

`osapi.make_dpi_aware()` calls `SetProcessDpiAwareness(2)` on Windows, so the window and the monitor rectangles are in real pixels. Each monitor's cell size then follows its DPI scale. On macOS the function does nothing, because the view's backing store already handles Retina.

## Hot-plug

The session stores a monitor signature, built by `osapi.common.monitor_signature`, and compares it every `MONITOR_CHECK_SECS` (3 seconds). When the signature changes, `run_session` returns `"restart"` and `main()` builds a new session. The new session lists the monitors again, makes a new window and creates a new renderer. It reuses the loaded settings.

Previews, timed runs and `--split-sim` runs do not watch the monitors.

On macOS, `legacyScreenSaver` creates and destroys one view per display itself, so the saver has no hot-plug code. A size change on a view rebuilds that view's renderer.

## Single instance

On Windows, a named mutex stops two saver processes from drawing at once. The name is `Local\MatrixRainScreensaver_Run` for a full-screen run and `Local\MatrixRainScreensaver_Preview` for a preview. The saver skips the lock for timed runs and for the settings window's own preview, which starts with `--settings-file`.

On macOS, `acquire_single_instance` always returns true. `legacyScreenSaver` runs one process and makes the views itself.

## Preview embedding

Windows asks for a preview with `/p <hwnd>`, where the handle is the small window in the Screen Saver Settings window. The saver reads that window's client size with `osapi.client_size`, lays out one monitor to fit and draws at a DPI scale of 0.3 by default (`preview_scale`). A preview has no HDR and no monitor watch. It exits if the parent window disappears.

`embed_in_parent` turns the saver window into a child of the preview window with `SetParent` and the `WS_CHILD` style. The saver creates the window as a top-level window and embeds it straight away.

The settings window's preview strip runs the saver as a child process with more flags:

```
/p <strip hwnd> --settings-file <temp json> --fps 18 --preview-scale 0.5 --ready-event <name> --run <seed>
```

The child starts hidden, embeds after its first frame and then sets the named event. The dialog keeps the old child drawing until the event is set or three seconds pass, so a change of setting swaps previews without a blank frame. This live preview is Windows only (`dialog_preview.live_allowed`). On other systems the dialog shows a static sample.

On macOS a preview view draws at 30 fps (`PREVIEW_FPS`). On macOS 27 the host's `isPreview` views stay 0 by 0 and draw nothing, and the System Settings thumbnail is a full-size view that the host scales down. The Windows embedding helpers (`embed_in_parent`, `set_topmost`) raise `NotImplementedError` on macOS, because macOS places the views itself.

## Frame cap and power source

The session checks the power state every `POWER_CHECK_SECS` (5 seconds) and picks the frame cap. On battery the starting cap is `FPS_BATTERY` (30). On mains power it is the fastest display's refresh rate from `osapi.max_refresh_rate`, which accepts values from 24 to 500 and falls back to 60. The Windows saver then lowers the cap to the `frame_cap` setting, shown in the dialog as Frame rate limit. The setting runs from 15 to 240 fps and defaults to 60. The `--fps` developer flag lowers it further.

Windows reads `GetSystemPowerStatus` and refresh rates with `EnumDisplaySettings`. macOS reads the battery through psutil and the refresh rate from `maximumFramesPerSecond`, so a 120 Hz ProMotion display reports 120. The macOS view caps at 30 fps (`BATTERY_FPS`) on battery and ignores `frame_cap`.

## Live load

`digital_rain/live_load.py` can speed up or thicken the rain as the machine gets busier. A background thread samples every second, and the `live_source` setting picks CPU, GPU or off. CPU load comes from psutil on both platforms. GPU load comes from the Windows performance counters, and the macOS sampler raises, so it reports unavailable and the rain stays at its normal speed. Three failed samples in a row have the same effect. See [[Rendering-pipeline]] for the mapping.

## Exit gate

On Windows, any key press, click or window close ends the saver. `ExitGate` ends the saver when the cursor has travelled more than 25 pixels in total (`MOUSE_THRESHOLD_PX`, summed over x and y), ignoring the first 0.6 s. Previews and timed runs ignore input.

macOS dismisses a saver on input by itself, so the view has no exit gate.

## macOS differences

| Area | Windows | macOS |
| --- | --- | --- |
| Entry point | `matrix_saver.py`, a `.scr` file | `mac_saver.py`, a `.saver` bundle loaded by `legacyScreenSaver` |
| Window | One window over all monitors | One `NSOpenGLView` per display, each with its own renderer |
| OpenGL | 3.3 core | A 3.2 core pixel format, served as 4.1 core |
| Software fallback | Yes | No. A GL failure draws black and the process stays up. |
| Settings storage | `%APPDATA%\MatrixRain\settings.json` | One JSON blob in `ScreenSaverDefaults` under `net.phabzlabs.matrixrain` |
| Settings window | Tk window with live preview | Options sheet from `digital_rain/mac/mac_options.py` |
| Settings change signal | The dialog writes the file | A distributed notification (`CHANGED_NOTE`) reloads the views in other processes |
| HDR | scRGB, 1.0 is 80 nits | Extended linear sRGB, headroom from the EDR limit |
| GPU load | Performance counters | Unavailable |
| Logging | Standard error | syslog plus `saver.log` in the state folder |
| Frame limit setting | `frame_cap` | Not applied |
| Exit | `ExitGate` | Handled by macOS |

Frame pacing on macOS differs too. The timer ticks eight times per frame (`TIMER_SUBSTEPS`) and the view draws once a frame's time has passed. `flushBuffer` waits for the GPU, so a plain timer at 1/fps skipped ticks and settled at half rate.

On macOS 27 the host keeps older views animating after a new one starts. Only the newest live view per display draws. Older views tick at `IDLE_FPS` (4) and release their renderer after 30 seconds.

The saver cannot write the real home folder, because `legacyScreenSaver` runs it in a sandbox. `osapi.settings_read_path` finds the real home from the password database, and `mac_settings.resolve` reads the old settings file only when no blob was saved. Logging goes to syslog because `NSLog` output never reaches the system log from inside `legacyScreenSaver`, and to `<state_dir>/logs/saver.log`, which is cut back to empty beyond 1 MB.

Some `osapi` names are no-ops on macOS: `make_dpi_aware`, `acquire_single_instance` and the named-event helpers. The Tk settings-window helpers (`set_dark_title_bar`, `capture_window`, `capture_client_rgb`, `work_area`) raise `NotImplementedError`, like the embedding helpers, because the options sheet does not use them.
