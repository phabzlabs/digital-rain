# Contributing

How to set up the project, run it, check it and propose a change. The repository's [CONTRIBUTING.md](https://github.com/phabzlabs/digital-rain/blob/main/CONTRIBUTING.md) is the short version of this page. For how the code is structured, see [[Architecture]], and for why, [[Design-decisions]].

## Set up

You need Windows and Python 3.14. The code uses Python 3.14 syntax, for example `except OSError, ValueError:` without parentheses, so an older interpreter fails on import.

```powershell
git clone https://github.com/phabzlabs/digital-rain.git
cd digital-rain
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements/requirements-dev.txt
```

`requirements/requirements-dev.txt` includes `requirements/requirements.txt` (pygame-ce, numpy, moderngl, glcontext and psutil, all pinned) and adds Pillow, ruff and pytest. The Mac-only requirements are in `requirements/requirements-mac.txt` and `requirements/requirements-mac-build.txt` ([[macOS]]).

Run the saver from source:

```powershell
.venv\Scripts\python.exe matrix_saver.py /s
```

Use `/c` for the settings window and `/p` for the preview mode.

## Developer flags

These flags of `matrix_saver.py` exist for development and for the checks. Launch the program from a shell to pass them. Windows drops the arguments when it starts a `.scr` through a double-click or Start-Process.

| Flag | Effect |
|---|---|
| `--seconds N` | Exit after N seconds and ignore input. |
| `--shot FILE` | Save a screenshot right before exiting. |
| `--renderer gpu` or `software` | Force a renderer. |
| `--preset NAME` | Look preset: `custom`, `film_1999`, `reloaded` or `resurrections`. |
| `--direction NAME` | Trail direction: `down`, `sideways` or `diagonal`. |
| `--pulse` | Turn the 1999 stammer on. |
| `--preview-sim` | Draw at the `/p` preview size and scale, with no parent window. |
| `--split-sim` | Split the primary monitor into two simulated monitors to test per-monitor settings. |
| `--dialog-shot FILE` | With `/c`: save a PNG of the settings window and exit. |
| `--dialog-scale F` | With `--dialog-shot`: draw the window as if on a monitor at F times 96 DPI. |
| `--dialog-size WxH` | With `--dialog-shot`: the window size in 96 DPI units (default 1200x1040). |
| `--settings-file PATH` | Load settings from this JSON file instead of the saved ones. |
| `--fps N` | Cap the frame rate at N. |
| `--run N` | Fix the rain layout to run value N (0 to 2^32 - 1). 0 is the fixed layout the checks use. Without it every launch draws a new layout. |
| `--preview-scale K` | With `/p`: draw the glyphs at K times 96 DPI (default 0.3). |
| `--ready-event NAME` | With `/p` and `--settings-file`: start hidden, show the window in its parent after the first frame, then set this named event. |
| `--warm-up` | A hidden run of about one second that loads every library, made once after an install. |

Example:

```powershell
python matrix_saver.py /s --seconds 8 --shot capture.png
```

Environment variables for diagnosis are listed in [[Settings-reference]].

## Run the checks

Run all three before opening a pull request:

```powershell
ruff check .
pytest
python tools/check.py --fast
```

CI runs exactly these on every push and pull request, with `SDL_VIDEODRIVER=dummy` so no window opens. If your change touches rendering, shaders, the settings window or a film look, also run the GPU gate, `python tools/check.py`, on a machine with a GPU. It takes longer, and the machine must be otherwise idle. [[Checks-and-tests]] describes every tier and what it protects.

If you change a look on purpose, record the golden frames again. Follow `tools/checks/golden/README.txt` and say so in the pull request.

## Code style

Linting uses ruff, configured in `pyproject.toml`:

| Setting | Value |
|---|---|
| Line length | 100 |
| Target version | Python 3.14 |
| Rules | `E`, `W` (pycodestyle), `F` (pyflakes), `B` (bugbear), `N` (pep8-naming), `SIM` (simplify), `I` (import sorting) |
| Formatter quotes | preserved, so both quote styles are accepted and existing quotes are not rewritten |
| Excluded | `.claude`, `build`, `dist`, `docs` |

A few files have per-file exceptions, with a comment in `pyproject.toml` giving the reason. Objective-C selector names such as `controlChanged_` in the `digital_rain/mac/` files break the naming rule. Local names that are imported modules (`objc`, `AppKit`) keep the module's spelling. The scripts in `tools/` and `tests/` put the repository root on `sys.path` before importing project modules, so they ignore the import-position rule.

Habits the code follows, which a new change should keep:

* Each module starts with a docstring that says what it does and what it leaves to others. Comments explain why, not what.
* `digital_rain/dialog_model.py` imports neither Tk nor numpy, so the dialog rules can be checked without a window. Keep new rules in the model, and keep the drawing code in `digital_rain/windows/config_dialog.py` and `digital_rain/windows/dialog_widgets.py`.
* Settings go through `settings.clean()`. A new setting needs an entry in `DEFAULTS`, a range or an enum, a label and help text in `digital_rain/dialog_model.py`, and a place on a page. `tools/checks/check_mac_options.py` fails in the fast gate when a settings key is on no page and not in `NON_UI_KEYS`.
* Checks never touch the real `APPDATA`. They use a temporary one, which `tools/checks/_gate.py` provides.
* Shaders are GLSL `#version 330` core, and `check_assets.py` enforces it.
* Wording in the settings window is plain: short labels, help lines that say what the control does.
* British English in documentation and in the settings window.

## Propose a change

1. Open an issue first for anything large, so the direction can be agreed before you spend time on it. A small fix can go straight to a pull request.
2. Work on a branch from `main`.
3. Keep a pull request to one purpose, with the checks above passing.
4. In the description, say what changed, why, and how you tested it. For a visual change, attach a screenshot or the output of `--shot`.
5. If you changed a setting, a look or the install steps, update the README and the documentation pages in `wiki/` that describe it. The documentation site is built from those files, so there is no separate copy to edit. Update the project website page `docs/index.html` too if it mentions the change.

Notable changes per release are listed in [CHANGELOG.md](https://github.com/phabzlabs/digital-rain/blob/main/CHANGELOG.md). Report a security problem privately, as [SECURITY.md](https://github.com/phabzlabs/digital-rain/blob/main/SECURITY.md) describes, not in a public issue. Please follow the [code of conduct](https://github.com/phabzlabs/digital-rain/blob/main/CODE_OF_CONDUCT.md).

The project is released under the GPL-3.0 ([[Licensing-and-credits]]), and contributions go in under the same licence.
