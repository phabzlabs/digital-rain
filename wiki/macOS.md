# macOS

Each release carries the Mac saver as `DigitalRain.dmg`, signed ad hoc only and not notarised. It needs macOS 12 or later (`LSMinimumSystemVersion` in `setup_mac.py`) and has been tested on macOS 27.2 on Apple Silicon. This page records what exists, how to build it and what is untested.

## Status

The Mac build is a `.saver` plugin made with py2app. Its plugin script is the root `mac_saver.py`, which imports `digital_rain/mac/mac_saver.py`, whose `MatrixRainView` is a `ScreenSaverView` with an OpenGL view per display. The renderer, looks, settings rules and shaders are the same code the Windows build uses. The platform layer for monitors, power status, fonts, settings paths and logging is in `digital_rain/osapi/mac.py` ([[Platform-and-monitors]]). The settings window is not the Tk window of Windows. The Options button in System Settings opens a native sheet (`digital_rain/mac/mac_options.py`) with the same six pages. The sheet uses the same `digital_rain/dialog_model.py` as Windows ([[Settings-reference]]).

The repository records this about testing:

* On 16 November 2026 the 1.0.0 dmg was built with Python 3.14 on macOS 27.2 and Apple Silicon, and tested by hand. The build checks passed, and install, Preview, the options sheet and depth on grid-mode pictures worked. The bundle's signature stayed valid after the saver had run.
* The fast gate checks the options sheet on Windows against fake AppKit (`tools/checks/check_mac_options.py`). The fakes test the project's calls against the project's own reading of the API. No real AppKit runs in the gate.
* `design/mac-options-test.md` is a manual test for a Mac. Its opening says nobody had run the sheet on a Mac when it was written. It lists what the fakes cannot settle. Do the controls look right and take input? Does ScreenSaverDefaults save inside the sandbox? How does macOS pick up new settings?
* The release workflow builds the Mac saver on a macOS runner. Nothing notarises it.

## Open points

The repository leaves these points unproven.

* The colour fix. The rain looked far more saturated on a MacBook whose display reports Adobe RGB, and the likely cause was that no colour space was set. The saver now tags its window as sRGB, and its layer too when the GL view is layer-backed. Nobody knows yet whether a window colour space reaches an OpenGL view surface. The manual test marks the fix as unverified.
* The font chooser. It opens a system file panel, which may hang inside the sandboxed saver as a modal alert can.
* Tab titles and wrapped help text in the options sheet, and the height of the sheet on each tab.
* The thumbnail in System Settings. The bundle ships its own tile image (`assets/mac/thumbnail.png` and `thumbnail@2x.png`), but macOS 27.2 shows the generic swirl for third-party savers anyway. Apple has the report as FB21094920.
* Gatekeeper behaviour on other Macs. The bundle is only ad-hoc signed.

## Build

Build on a Mac with Python from python.org. `build_mac.sh` looks for Python 3.14. Set `PYTHON=/path/to/python3.x` to use another version.

```bash
bash tools/build/build_mac.sh --install
```

The script:

1. Creates `build/mac-venv` from scratch and installs the pinned `requirements/requirements-mac-build.txt`.
2. Compiles the Core ML depth model with `tools/build/compile_coreml.py`.
3. Runs `python setup_mac.py py2app`.
4. Signs the bundle ad hoc with `codesign -s -`.
5. Checks the bundle: the Info.plist, the bundled `assets/`, the math, moderngl and glcontext binaries and the signature. It also checks that `dialog_model`, `mac_settings` and `mac_options` are present and no Tk dialog module is.
6. Writes `dist/Digital Rain.saver` and `MatrixRain-mac.zip` (local only), then `DigitalRain.dmg` with `hdiutil create` (compressed UDZO, volume name Digital Rain). The image holds the saver and an `Install.txt` that says to double-click the saver and, if macOS blocks it, to click Open Anyway in System Settings, Privacy & Security, or run `xattr -dr com.apple.quarantine "Digital Rain.saver"` first. The build output and `checks.txt` go to `mac-build-results/`. The disk image step has not been run on a Mac yet.

With `--install` the script also copies the bundle to `~/Library/Screen Savers` and warms it up. The warm-up loads the installed bundle and the renderer's libraries once. macOS then runs its first-load checks on the new files at that point, not at the first screensaver start. `--reuse-venv` keeps the existing venv. The version number comes from `version_info.txt`, the same file the Windows build uses ([[Build-and-release]]).

## Manual install and test

1. Double-click `dist/Digital Rain.saver`, or skip this step after `--install`. macOS asks whether to install it for this user only. Either answer works.
2. Open System Settings, then Screen Saver, choose Digital Rain and check that the thumbnail shows rain. Click Preview for the full-screen saver. Any key or mouse movement ends it.
3. Run `bash tools/build/build_mac.sh --collect` to copy the saver's log and its system log lines into `mac-build-results/`.

To update, open a newer `DigitalRain.dmg` and install its saver the same way. It replaces the installed copy. Then run `killall legacyScreenSaver` in Terminal, or log out and back in, so macOS loads the new one.

To uninstall, delete `Digital Rain.saver` from `~/Library/Screen Savers`.

After you replace the bundle by hand, run `killall legacyScreenSaver` so macOS loads the new one. The `--install` option does this for you.

`tools/dev/mac_host.sh` runs the saver view in ordinary windows, outside the sandbox, without building the bundle. `python tools/dev/mac_host.py --options` opens the options sheet in an ordinary window.

## Settings and logs

Settings are saved in ScreenSaverDefaults under `net.phabzlabs.matrixrain`, key `settings_json`. The saver still reads the old `~/Library/Application Support/MatrixRain/settings.json` when nothing was saved in ScreenSaverDefaults. The saver cannot write to that file, so only the options sheet saves settings.

The saver runs inside the `legacyScreenSaver` sandbox, so its log is in that process's container and not in your own Library:

```
~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Application Support/MatrixRain/logs/saver.log
```

Terminal can read that folder only after you allow it to access other apps' data. macOS asks, or you can turn on Full Disk Access for Terminal. Every line also goes to the system log, but macOS shows the text as `<private>`, so that log shows mainly whether the saver loaded:

```bash
log show --last 10m --predicate 'process BEGINSWITH "legacyScreenSaver"'
```

## Mac-only parts

Pictures in the rain use depth. The Mac build estimates it in process with Apple's Core ML conversion of Depth Anything V2 Small (`digital_rain/mac/depth_coreml.py`, model in `assets/models`). Loading takes several seconds the first time, so the work runs on a background thread. On a first run a picture waits up to 10 seconds for its map, as on Windows. Without the model or pyobjc Core ML, the code falls back. The Windows build runs the same model as ONNX ([[Settings-reference]]). The model's licence is in [[Licensing-and-credits]].

HDR on the Mac assumes SDR white is 100 nits. The HDR peak setting cannot exceed the headroom that the screen reports for extended dynamic range.
