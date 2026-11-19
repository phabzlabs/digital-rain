# Digital Rain documentation

Digital Rain is a Matrix-inspired screensaver for Windows 10 and 11 and for macOS. It draws falling green code on the GPU with OpenGL shaders, runs on every monitor at once, follows Windows display scaling and has a settings window with a live preview. Each release carries the Mac saver too (see [[macOS]]).

The Windows screensaver picker lists it as Digital Rain, while the files and the settings folder keep the older name, `MatrixRain`. The project began as a fork of madkoding's matrix-screensaver, and parts of that code remain ([[Licensing-and-credits]] names them). It is an unofficial fan project, not affiliated with Warner Bros., and not an official Matrix product.

## Contents

### Use the screensaver

| Page | What it covers |
|---|---|
| [[Features]] | Everything the screensaver does, and why each feature exists |
| [[Settings-reference]] | Every setting, its values, default and purpose, plus looks and environment variables |
| [[Installing-and-uninstalling]] | Windows install, preview, multiple monitors, troubleshooting |
| [[macOS]] | The Mac saver: install, build and open points |

### How it works

| Page | What it covers |
|---|---|
| [[Architecture]] | The modules and how a frame gets from settings to screen |
| [[Rendering-pipeline]] | The shader passes, bloom, upscaling and the software fallback |
| [[Design-decisions]] | Why the code is built the way it is |
| [[Platform-and-monitors]] | The Windows and macOS platform layers, monitors, DPI and hot-plug |

### Work on the project

| Page | What it covers |
|---|---|
| [[Contributing]] | Setting up, code style and proposing changes |
| [[Build-and-release]] | Building from source, the release workflow and versioning |
| [[Checks-and-tests]] | The check tiers, pytest and golden frames |
| [[Film-research]] | The measurements the film looks are based on |
| [[Licensing-and-credits]] | Licence, the original project, third-party code and assets |

The repository also has a short [contributing guide](https://github.com/phabzlabz/digital-rain/blob/main/CONTRIBUTING.md), a [code of conduct](https://github.com/phabzlabz/digital-rain/blob/main/CODE_OF_CONDUCT.md), a [security policy](https://github.com/phabzlabz/digital-rain/blob/main/SECURITY.md) for reporting vulnerabilities privately and a [changelog](https://github.com/phabzlabz/digital-rain/blob/main/CHANGELOG.md).

## Install

The Windows download is `DigitalRain-Setup.exe` and the Mac one is `DigitalRain.dmg`. Get them from the [latest release](https://github.com/phabzlabz/digital-rain/releases/latest). On Windows, run the installer and tick Set Digital Rain as my screensaver at the end; the installer is not code-signed and the Mac saver is not notarised, so SmartScreen or Gatekeeper asks you to allow them. [[Installing-and-uninstalling]] has the full steps, the multi-monitor notes and troubleshooting. The [project website](https://phabzlabz.github.io/digital-rain/#install) has a shorter install guide.

## Screenshots

![Digital Rain demo, a looping clip](https://github.com/phabzlabz/digital-rain/raw/main/docs/demo.gif)

| The Matrix (1999) | Reloaded (2003) | Resurrections (2021) |
|---|---|---|
| ![The Matrix (1999) look](https://github.com/phabzlabz/digital-rain/raw/main/docs/look-film_1999.png) | ![The Reloaded (2003) look](https://github.com/phabzlabz/digital-rain/raw/main/docs/look-reloaded.png) | ![The Resurrections (2021) look](https://github.com/phabzlabz/digital-rain/raw/main/docs/look-resurrections.png) |

| Picture | Message |
|---|---|
| ![A picture formed by the rain in the Over the rain style, of a cat portrait](https://github.com/phabzlabz/digital-rain/raw/main/docs/picture.png) | ![Wake up, Neo... forming out of rain glyphs, set on the Message and clock page with Your text](https://github.com/phabzlabz/digital-rain/raw/main/docs/message.png) |

![The default look, The Matrix (1999), on one 3440 by 1440 ultrawide monitor](https://github.com/phabzlabz/digital-rain/raw/main/docs/screenshot.png)

![A close view at full resolution: film glyphs, white leading glyphs and bloom](https://github.com/phabzlabz/digital-rain/raw/main/docs/detail.png)

![The Look page of the settings window, with the sidebar pages Look, Motion and layout, Message and clock, React to computer load, Graphics and Pictures](https://github.com/phabzlabz/digital-rain/raw/main/docs/screenshot-settings.png)
