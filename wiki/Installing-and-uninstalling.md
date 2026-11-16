# Installing and uninstalling

How to install, update and remove the Windows screensaver, and what to try when something goes wrong. The Mac build has its own page, [[macOS]], and building from source is covered in [[Build-and-release]].

## Requirements

Windows 10 or 11. `DigitalRain-Setup.exe` is mostly the depth model for pictures and ONNX Runtime. It installs a self-contained PyInstaller bundle, so you do not need Python or administrator rights. The saver uses the Windows fonts `msgothic.ttc` and `courbd.ttf` only if it cannot load the bundled film font.

## Install

1. Download `DigitalRain-Setup.exe` from the [latest release](https://github.com/phabzlabs/digital-rain/releases/latest), under Assets.
2. Run it. It installs for your user only, into `%LOCALAPPDATA%\Programs\MatrixRain`.
3. When it finishes, it runs the saver once hidden (the warm-up, see below) and offers Set Digital Rain as my screensaver, ticked by default. That opens the screensaver picker with Digital Rain already selected, the same as right-click Install on `MatrixRain.scr`. Use Settings there to adjust the look, and Preview to run it full screen.

The installer is not code-signed, because signing needs a paid certificate. Windows SmartScreen may show "Windows protected your PC". Click More info, then Run anyway. You can read the source in the repository and build the installer yourself.

The screensaver runs from the install folder and `MatrixRain.scr` needs the `_internal` folder beside it, so do not move or delete them by hand. Uninstall instead (see below).

### Check the download

Each release has a `SHA256SUMS.txt` and a signed build provenance attestation for each file. Compare the hash of your download with the line in `SHA256SUMS.txt` (`Get-FileHash DigitalRain-Setup.exe` on Windows, `shasum -a 256 DigitalRain.dmg` on a Mac). To check the attestation, with the GitHub CLI:

```powershell
gh attestation verify DigitalRain-Setup.exe -R phabzlabs/digital-rain
```

### Update

Run a newer `DigitalRain-Setup.exe` over the old install. It upgrades in place and asks to close a running saver or preview from the install folder. Your settings stay, because they live in a separate folder (see below).

Developers can instead copy a build over an install with the script `tools\build\install.ps1`, from a built folder or a zip:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build\install.ps1 -Source MatrixRain.zip
```

The script copies to `%LOCALAPPDATA%\Programs\MatrixRain` (or `-Dest <folder>`) and replaces `MatrixRain.scr` and `_internal`. It keeps anything else in the folder. It stops if the saver is running from there. It does not change which screensaver Windows uses, so a first install still needs right-click Install.

The installer runs the same warm-up itself. The script then runs `MatrixRain.scr --warm-up`, a hidden run of about one second that loads every library once. Windows Defender scans freshly written libraries the first time they load. Without the warm-up, the first launch after an install took two to three seconds to show a frame. The `-NoWarmUp` switch skips the warm-up.

## Preview and settings window

The screensaver picker has two entry points. To open it, go to Settings, Personalization, Lock screen, Screen saver, or search for Change screen saver.

The small preview box in the picker is the `/p` mode of the saver. It draws the rain at a small scale inside the picker window.

The Settings button opens the settings window. It has its own live preview strip and a Full screen button, so you can try changes before you press OK. [[Settings-reference]] describes every setting.

## Multiple monitors

One borderless window covers the whole virtual desktop and each monitor draws its own rain, sized to its resolution and Windows scaling. You do not need to configure anything for mixed sizes, portrait displays or different scaling.

Notes for multi-monitor setups:

* Plugging in or removing a display while the saver runs is picked up automatically.
* The frame rate cap is the lowest of the fastest connected display's refresh rate, the Frame rate limit on the Graphics page (default 60, range 15 to 240) and, on battery power, 30 FPS.
* In the settings window, the Editing settings for picker gives one display its own film look, colour, fall speed, rain density or depth. The numbers in that list follow their own order, not the order in Windows Settings.
* Pictures work only when no monitor overrides the look, colour, speed, density or depth.
* A saved monitor that is not connected stays listed as Saved, not connected. Forget this monitor removes its overrides.

## File locations

| What | Where |
|---|---|
| The screensaver | `%LOCALAPPDATA%\Programs\MatrixRain` |
| Settings | `%APPDATA%\MatrixRain\settings.json` |
| Cached picture maps | `%APPDATA%\MatrixRain\surfaces` |
| A custom font | Chosen in the settings window, or placed in a `fonts` folder next to `MatrixRain.scr` |
| Logs | None. On Windows the saver writes diagnostics to standard error and keeps no log file. |

## Troubleshooting

### The first launch is slow

Windows Defender scans new libraries the first time they load. Later launches take under a second. Installing through the picker already runs the small preview, which loads the same libraries.

### Remote Desktop, virtual machines and the software renderer

The GPU renderer fails to start without an OpenGL driver, which Remote Desktop sessions and many virtual machines lack, or when a shader fails to build. The saver then prints a message to standard error and uses a CPU renderer with the same look. The CPU renderer is slower. Upscaling, HDR and pictures need the GPU renderer and do nothing in the CPU renderer.

To test the CPU renderer on any machine, set Draw with to CPU on the Graphics page. To force the GPU, set it to GPU. The saver still falls back if the GPU cannot start.

### The picker preview or the saver shows nothing

Open Settings, set Draw with to CPU on the Graphics page and press Full screen. If the rain shows with CPU but not with Auto, update the graphics driver. The saver build has no console, so it prints no visible output.

### The saver exits on mouse movement

The saver ignores the mouse for the first 0.6 seconds. After that it exits once the pointer has travelled more than 25 pixels in total. Any key press or click exits at once. No setting changes these rules.

### Settings seem to be ignored

The saver reads the settings file when it starts, so press OK and run the saver again. The saver ignores an invalid value in `settings.json` and uses the default. Check that a hand-edited value is in its allowed range ([[Settings-reference]]).

### Reset everything

Close the settings window, then delete `%APPDATA%\MatrixRain\settings.json`. The defaults return on the next launch. The settings window also has a Reset to defaults button. It asks first and saves nothing until you press OK.

## Uninstall

1. Open the screensaver picker and choose a different screensaver, or None.
2. Open Settings, Apps, Installed apps, find Digital Rain and choose Uninstall. This removes the program folder and leaves your settings in `%APPDATA%\MatrixRain`.
3. Optionally delete `%APPDATA%\MatrixRain` to remove the settings and cached picture maps.
