# Changelog

Notable changes to Digital Rain. Versions follow [semantic versioning](https://semver.org/).

## 1.0.0

First public release.

### Windows

- `DigitalRain-Setup.exe`: a per-user installer that needs no administrator rights, upgrades in place, uninstalls from Settings > Apps and keeps your settings. It warms the saver up and offers to set it as the screensaver.
- A GPU renderer, with a software renderer as the fallback, and frames paced at each display's refresh rate.
- Per-monitor settings, a settings window with a live preview, and the live preview in the screensaver picker.
- HDR output (`hdr`, `hdr_peak`) and optional AMD FSR 1.0 upscaling (`upscaling`, `sharpness`).
- `--warm-up`: a short hidden run after an install so the first real start is quick.

### macOS

- `DigitalRain.dmg`, holding `Digital Rain.saver` with its own options sheet.

### Both

- Film look presets: `film_1999`, `reloaded` and `resurrections`, measured against film stills, with trail directions and the 1999 pulse.
- Live load mode: CPU or GPU load drives the rain's speed and density.
- A clock or text message formed by the rain, with a fixed clock in nine screen positions.
- A Letter font option for the rain message, the clock and the typed film messages.
- Pictures from a folder, formed by the rain from their own characters over it or drawn by the falling characters, with depth on grid-mode pictures.

### Releases

- Each release carries `DigitalRain-Setup.exe`, `DigitalRain.dmg` and `SHA256SUMS.txt`, with build provenance attestations.
- The saver shows as "Digital Rain"; its files and settings folder keep the name `MatrixRain`.
