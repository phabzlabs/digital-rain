# Contributing

Thanks for taking an interest. This page is the short version; the [Contributing page in the documentation](https://phabzlabz.github.io/digital-rain/contributing.html) has the full developer flags, code style and the reasons behind them.

## Set up

You need Windows and Python 3.14 (the code uses 3.14 syntax, so older interpreters fail on import). macOS development is possible too; see the [macOS page](https://phabzlabz.github.io/digital-rain/macos.html).

```powershell
git clone https://github.com/phabzlabz/digital-rain.git
cd digital-rain
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements/requirements-dev.txt
.venv\Scripts\python.exe matrix_saver.py /s
```

Every requirement is pinned. `requirements/requirements.txt` is what the saver needs at run time, `requirements/requirements-dev.txt` adds ruff, pytest and Pillow, and `requirements/requirements-build.txt` adds PyInstaller for `build.ps1`.

## Where things are

- `digital_rain/` is the code. The modules both platforms share are at its top level, `windows/` holds the Windows-only ones and `mac/` the macOS-only ones, and `osapi/` is the platform layer.
- `matrix_saver.py` and `mac_saver.py` at the root are thin entry scripts for PyInstaller (`build.ps1`) and py2app (`setup_mac.py`). Run the saver from a checkout with `python matrix_saver.py`.
- `assets/` holds the shaders, presets and fonts; `tests/` holds the pytest tests.
- `tools/check.py` is the gate. The sub-checks, their helpers and the golden frames are in `tools/checks/`, one-off measurement scripts in `tools/dev/`, and the Mac build, the dev install script and the icon helpers in `tools/build/`.
- `installer/windows/` holds the Inno Setup script for `DigitalRain-Setup.exe`, which `build.ps1` builds.
- `requirements/` holds the pinned requirements files.
- `design/` holds the design notes and the film research. `docs/` is only the GitHub Pages site.

## Run the checks

```powershell
ruff check .
pytest
$env:SDL_VIDEODRIVER = "dummy"; python tools/check.py --fast
```

CI runs exactly these on every push and pull request. None of them needs a GPU. If you touch rendering, shaders, the settings window or a look, also run `python tools/check.py` on an idle machine with a GPU, and say in the pull request whether you did.

## Common changes

To add a look, add `assets/presets/<name>.json` (copy an existing preset), add the name to `PRESET_NAMES` and `PRESET_TITLES` in `digital_rain/settings.py`, then record its golden frames as described in `tools/checks/golden/README.txt`. `tools/checks/check_assets.py` and `tests/test_looks.py` load every preset.

To add a setting, give it a default in `settings.DEFAULTS` and a range in `RANGES` or a value list in `ENUMS`, then a label, help text and a place on a page in `digital_rain/dialog_model.py`. The fast gate fails when a settings key is on no page and not listed as a non-UI key. If you rename a key, add a rule to `settings.migrate()` so older settings files still load. Document it in the settings table of `README.md`.

To change a shader, edit the GLSL in `assets/shaders/` (`#version 330` core, enforced by `tools/checks/check_assets.py`). Shaders run only in the GPU gate, so run `python tools/check.py`. A change that moves pixels on purpose needs new golden frames.

## Pull requests

1. Open an issue first for anything large, so the direction is agreed before you spend time on it. Small fixes can go straight to a pull request.
2. Branch from `main` and keep each pull request to one purpose.
3. Say what changed, why, and how you tested it. Attach a screenshot (or `--shot` output) for visual changes.
4. Update `README.md` and the documentation pages in `wiki/` when you change a setting, a look or the install steps. The documentation site is built from those files. Update the project website page (`docs/index.html`) too if it mentions the change.

By contributing you agree that your work is released under the project's licence, the [GNU GPL v3](LICENSE). Please follow the [code of conduct](CODE_OF_CONDUCT.md).
