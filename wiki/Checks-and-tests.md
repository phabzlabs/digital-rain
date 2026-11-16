# Checks and tests

Digital Rain is checked in two layers. `pytest` runs fast unit tests with no window and no GPU. The gate, `tools/check.py`, runs larger checks that start the saver, the settings window and the renderers. Below is what each one protects. Setting up the tools is in [[Contributing]], and how CI uses them is in [[Build-and-release]].

## Set up

Install the tooling once from the repository root:

```
pip install -r requirements/requirements-dev.txt
```

That file includes `requirements/requirements.txt` and adds pytest, ruff and Pillow. The scripts in `tools/` use Pillow to read and compare images. The gate needs Python 3.14.

## Tiers

| Tier | Command | What it covers |
|---|---|---|
| pytest | `pytest` | The unit tests in `tests/`. Under 10 seconds, no window and no GPU. |
| Fast gate | `python tools/check.py --fast` | Byte-compiling every module plus the windowless checks. No GPU. CI runs this, with `ruff check .` and `pytest`. |
| GPU gate | `python tools/check.py` | The fast gate plus the checks that render on the GPU. |
| Performance | `python tools/check.py --perf` | The GPU gate plus timed runs and the frozen build. Opt-in. |

Each sub-check also runs alone, for example `python tools/checks/check_film.py --preset reloaded`. Never run two copies of the gate at once, and keep GPU runs off a busy machine.

The performance tier is opt-in because a loaded machine can miss the timings on its own. Its limits are 2 to 25 times the numbers measured when they were set, so only a real regression fails.

### Gate behaviour

The gate runs hidden by default, with no visible window, no focus steal and below-normal priority, so you can keep working. `tools/checks/hidden.py` holds the shared helper. Every child process gets its own temporary `APPDATA` and `TEMP` under one run folder, which the gate removes afterwards. The checks therefore never touch your real settings, and two runs never share a file. Pass `--show` to open real full-screen windows instead. Checks that need a visible window print `SKIPPED (needs --show)` in the hidden run.

The saver hides its window only when the check tooling passes the explicit `--check-hidden` flag. The environment never hides a real launch, so a stray variable cannot make the saver invisible for a user. [[Settings-reference]] lists the environment variables for the gate.

## Sub-checks

The sub-checks and their helpers (`_gate.py`, `hidden.py`, `frame_harness.py`, `fake_appkit.py` and the golden frames) are in `tools/checks/`. `tools/check.py` is the gate that runs them. One-off measurement scripts are in `tools/dev/` and the build helpers in `tools/build/`.

| Check | Tier | What it protects |
|---|---|---|
| `check_assets.py` | fast | The film glyph set matches `glyph-order.txt`, every glyph size renders, and an unusable custom font falls back to the film glyphs. The Windows and Mac platform layers both implement the same interface, every shader is `#version 330`, and every preset file loads. A glyph or asset change that breaks a build fails here, before a window opens. |
| `check_looks.py` | fast | Software-renderer output for the three film presets against recorded SHA-256 hashes, the run value, Reloaded colours, the Resurrections glyph atlas, and a matrix of preset, direction and pulse for floors and lit pixels. It keeps a refactor from changing a look by accident. |
| `check_monitors.py` | fast | The monitor ids Windows reports, and the software renderer drawing two monitors with different looks. This guards per-monitor overrides. |
| `check_dialog.py` | fast | Every enable and disable rule of the settings window, using `dialog_model` alone, so no window is needed. The preset effect values in the model are compared with `looks.PRESETS`, since the model copies them to avoid loading numpy. |
| `check_mac_options.py` | fast | The Mac options sheet and saver, run on Windows against fake AppKit (`tools/checks/fake_appkit.py`). It checks the shared tables, the bundle manifest, the settings blob round trip and the sheet's wiring. The fakes check the project's calls against its own reading of the API. No AppKit runs, so the sheet still needs a test on a real Mac (see [[macOS]]). |
| `check_live.py` | GPU | The real CPU and GPU load samplers, then five saver runs whose screenshots are measured. The rain must be brighter inside the message letters than outside them. |
| `check_launch.py` | GPU | Pinned library versions, the settings window (round trip, screenshots, layout settling, preview child process), the full-screen saver smoke runs and the `/p` preview inside a host window. |
| `check_film.py` | GPU | The three film presets measured against numeric windows, plus golden frames. See below. |
| `check_perf.py` | perf | Wall-clock limits on settings load and save, the dialog, the saver and the frozen build. The frozen build is skipped when `dist\MatrixRain\MatrixRain.scr` does not exist. |

## Film look measurements and golden frames

`check_film.py` holds the looks to their research ([[Film-research]]). For each preset it runs the saver for six seconds with a settings file for that preset. The average frame rate must reach 90 percent of the cap. The check then renders frames in process at 1920 by 1080, with FSR on Quality, at several times, and measures them.

The measurements are the lit share, tone buckets, near-white share, leader columns, background colour and hue, halo width, edge softness, ink columns, stroke fill, row pitch, ink grain and background grain. Each has a window of acceptable values in `tools/checks/film_targets.py`, taken from measurements of film frames. Measurement code is in `tools/checks/film_metrics.py` and `tools/dev/measure_reference.py`.

The Resurrections part adds checks on bucket hue drift, square cells, column and glyph tile counts and the glint strokes. It also checks a classic monitor beside a Resurrections one, depth off and the depth slices.

Golden frames are saved images in `tools/checks/golden/`. There are eight GPU frames: film_1999, reloaded, resurrections and custom, each with upscaling off and on Quality, at 1024 by 576 and t equal to 5 seconds. There are also SHA-256 hashes of four software frames, at 800 by 600 and t equal to 5 seconds. `tools/checks/frame_harness.py` renders them deterministically. It fixes the random seed and the rain layout and uses one monitor. For GPU frames it renders three consecutive frames ending at each time.

The two kinds of golden protect different things.

* `check_looks.py` compares the software hashes exactly, because the software renderer does not depend on the GPU.
* `check_film.py` compares the GPU frames with a tolerance. At most 0.1 percent of pixels may have a channel off by more than 1 unit, and no channel may be off by more than 8 units. The tolerance exists because GPU frames are valid only for the machine's GPU and driver.

Regenerate goldens only when a change to a look is on purpose, using the commands in `tools/checks/golden/README.txt`. After a GPU or driver change, regenerate the GPU frames with the same commands. The Custom goldens prove that neutral values skip the code paths added for the film looks, so they stay recorded at an older commit.

## Picture depth sheets

`python tools/dev/grid_sheet.py` renders every picture of one folder in grid mode with this machine's depth network (Core ML on macOS, ONNX on Windows), one process per picture. It writes the depth maps, the renders, a picture-over-render sheet and a CSV of brightness, legibility and near share. Its `compare` command lines up two runs, so the Windows and macOS depth maps of the same pictures can be checked against each other.

## Unit tests

The files in `tests/` cover logic that needs no window or GPU.

| File | Covers |
|---|---|
| `test_settings.py`, `test_settings_clean.py` | Load, clean, migrate, atomic save and the round trip. `clean()` on a raw dict must equal what `load()` returns for the same file, and saving either gives the same bytes. The dialog relies on that to skip a second disk read. |
| `test_looks.py` | Preset resolution, the 24 frames per second clock, palette and pulse maths. |
| `test_dialog_model.py` | The settings window's editing, overrides, reset and round trip contract. |
| `test_dialog_preview_args.py` | The preview child process's command line and developer flags. |
| `test_saver_args.py` | The Windows screensaver switches and the developer flags. |
| `test_exit_gate.py` | When mouse movement ends the saver, against a reference rule. |
| `test_easter_egg.py` | Timing of the typed messages. |
| `test_rain_message.py` | Masks, the message schedule, the letter front and the head latch. |
| `test_live_load.py` | How a load reading moves the rain, and the fallback when psutil is missing. |
| `test_image_layer.py` | The picture analysis on small synthetic pictures, with a fake GL context. |
| `test_mac_settings.py` | The Mac settings blob and where the saver reads it. |
| `test_version.py` | That the `pyproject.toml` version equals `ProductVersion` in `version_info.txt`. |
| `test_warm_up.py` | The hidden one-second run made once after an install. |

Unit tests hold the pure logic because they are fast and need no machine state. The gate holds only what needs a real display, a GPU or a child process.

## Lint

`ruff check .` runs in CI and in the release workflow. The rule set is in `pyproject.toml`, described in [[Contributing]].
