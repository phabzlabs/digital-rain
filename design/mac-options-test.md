# Mac options sheet: manual test

None of this has been run on a Mac: the build machine is Windows, and the AppKit side was only checked against fakes (tools/checks/check_mac_options.py). This test settles what the fakes cannot: that the controls look right and take input, that ScreenSaverDefaults saves inside the legacyScreenSaver sandbox, and how macOS picks up new settings.

## 1. Build and install

```
bash tools/build/build_mac.sh --install
```

The build fails if `dialog_model`, `mac_settings` or `mac_options` is missing from the bundle, or if a Tk dialog module (`config_dialog`, `dialog_widgets`, `dialog_preview`) got in.

## 2. Harness first

```
python tools/dev/mac_host.py --options
```

1. The options sheet opens in an ordinary window.
2. Click through all 6 tabs (Look, Motion, Message, Live, Render, Images) and change a value on each.
3. Press Save. The terminal prints `options: source=...` and the blob.
4. Run `defaults -currentHost read net.phabzlabs.matrixrain` and check `settings_json` is there.
5. Rerun with `python tools/dev/mac_host.py --seconds 5` and check the saver log line `settings source=defaults`. This host run is not sandboxed, so its log is the real-home `saver.log`, not the container log in section 8.

## 3. System Settings

1. System Settings > Screen Saver > Digital Rain > Options: the sheet opens (not "settings app not installed").
2. Change the preset to Reloaded and press Save. The thumbnail changes within a second or two.
3. Press Options again: it shows Reloaded.

## 3b. Tab titles and wrapped text

1. In System Settings, open Options. All 7 tab titles show in full, with no "...": Look, Motion, Message, Input, Live, Render, Images.
2. Open the Live tab. The help under Source reads to the end ("...the rain stays normal.") on two lines, nothing is cut off, and there is no large empty area under Strength: the sheet gets shorter on the Live tab and taller again on Look.
3. Check the notes on every other tab the same way (Input, Live and Render have an extra Mac note under the description; Render has the font help and Images the folder help). Report any line that is cut off, and any tab whose sheet height jumps oddly.

## 3c. Colours against the PC

The colour fix is unverified: it was written on Windows without a Mac. The saver now tags its window (and the GL layer, when there is one) as sRGB so macOS converts the colours for the display.

1. Set the same preset on the Mac and the PC (film_1999).
2. Compare the System Settings thumbnail and the full-screen saver with the PC by eye. The Mac rain should no longer be clearly more saturated (strong green and cyan) than the PC.
3. In the saver log (section 8), find the line `colour space sRGB set on ...` for each view and copy it into the report. It says what was tagged (window, GL view layer, view layer, or neither) and the screen's own colour space, for example `screen colour space Adobe RGB (1998)`. There should be one such line per view.
4. If the colours are unchanged, say so: the window colour space may not reach an NSOpenGLView surface, and a different fix is needed.

Open question behind this section: the rain looked far more saturated on a MacBook whose display reports Adobe RGB, and the likely cause is that nothing on the Mac path set a colour space. `apply_srgb` in mac_saver.py tags the window and, when the GL view is layer-backed, its layer. Whether a window colour space reaches an NSOpenGLView surface is not known; the layer colour space is the other half. The log line is the evidence.

## 4. Cancel

Change the colour, press Cancel, open Options again: the colour is unchanged.

## 5. Reset

Press Reset to defaults, then Save, then open Options again: every value is the default.

## 6. Persistence

Log out and back in (or restart) and open Options: the values are kept. Start the saver with a hot corner: it shows the saved look.

## 7. Old settings file

1. Remove the blob: `defaults -currentHost delete net.phabzlabs.matrixrain` for the harness, or use a fresh user.
2. Put a settings.json with `"preset": "resurrections"` at `~/Library/Application Support/MatrixRain/settings.json`.
3. Open the sheet: it opens on Resurrections and the log says `source=file`.
4. Press Save: the log now says `source=defaults`.

## 7b. Font chooser

On the Look page, use the font chooser button. It opens an NSOpenPanel, which may hang inside the sandboxed saver the same way a modal alert can. Report whether it opens, and whether the sheet still responds afterwards.

## 8. Logs

- Sandbox log: `~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Application Support/MatrixRain/logs/saver.log`.
- `bash tools/build/build_mac.sh --collect` (needs Full Disk Access for Terminal) copies the logs and the ScreenSaverDefaults plist (`defaults-<name>.txt`), or notes "no ScreenSaverDefaults file found".
- Look for `mac_options: saved`, `settings source=`, and no `WARNING` about the module name.

## 9. What to report back

- macOS version.
- Whether the thumbnail updated without a restart.
- Whether a restart was needed for the full-screen saver.
- Whether the tab titles and the Live notes show in full (3b).
- The `colour space sRGB set on ...` log lines, and whether the colours now match the PC (3c).
