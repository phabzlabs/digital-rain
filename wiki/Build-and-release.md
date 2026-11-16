# Build and release

Building the Windows screensaver from source, publishing a release and numbering versions. The Mac build is on [[macOS]]. Run the checks first, as [[Checks-and-tests]] describes.

## Build output

A `.scr` is a renamed `.exe`. Windows starts it with `/s` (run), `/c` (configure) or `/p HWND` (preview). The build packages `matrix_saver.py` with PyInstaller as a one-folder bundle, renames `MatrixRain.exe` to `MatrixRain.scr` and zips the folder to `MatrixRain.zip`, a local build output that releases do not carry. It then builds the installer, `DigitalRain-Setup.exe`, from the folder. The folder holds `MatrixRain.scr` and an `_internal` folder of libraries and assets.

The screensaver picker shows string 1 of the `.scr`'s string table as its name. `tools/build/scr_name.py` writes a resource that sets it to "Digital Rain" and checks it after the build. The file and folder keep the name `MatrixRain`, so existing installs keep working.

## Local build

You need Windows and Python 3.14. The `py` launcher finds it, or pass `-Python`.

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

The script, in order:

1. Checks that the interpreter is Python 3.14.
2. Creates `build\venv` from scratch and installs the pinned `requirements/requirements-build.txt`, then runs `pip check`.
3. Checks that the film font `assets\rezmason\Matrix-Code.ttf` and the depth model `assets\models\depth_anything_v2_small_q.onnx` exist.
4. Writes the picker-name resource.
5. Runs PyInstaller with the icon, the version resource from `version_info.txt`, the data folders `assets\rezmason`, `assets\shaders` and `assets\presets`, the depth model and the ONNX Runtime binaries. A folder `assets\images` is added too if it holds pictures.
6. Renames the exe to `.scr`, checks the picker name and writes `MatrixRain.zip`.
7. Builds `DigitalRain-Setup.exe` with Inno Setup 6 from `installer/windows/DigitalRain.iss`, passing the version from `version_info.txt` as `/DAppVersion`. It finds `ISCC.exe` from `-Iscc`, then `PATH`, then `%LOCALAPPDATA%\Programs\Inno Setup 6` and the Program Files folders. `-NoInstaller` skips this step.
8. Runs a smoke test from the built `.scr` unless you skip it. The test makes two timed three-second full-screen runs (GPU and software renderer) and takes a timed screenshot of the settings window. All runs share one temporary `APPDATA`. Each run must exit with code 0, write a screenshot above a minimum size and finish inside a time limit.

| Flag | Effect |
|---|---|
| `-Python <path>` | The Python 3.14 interpreter used to create the venv. |
| `-ReuseVenv` | Reuse `build\venv` instead of recreating it. |
| `-NoSmoke` | Skip the smoke test, for machines with no desktop. |

The pins in `requirements/requirements-build.txt` (PyInstaller and its hooks) and `requirements/requirements.txt` (the runtime libraries) are exact versions, so a build is reproducible. `check_launch.py` verifies that the installed versions match the pins (see [[Checks-and-tests]]).

### Install a build

`tools\build\install.ps1` copies a built `dist\MatrixRain` folder or a zip into `%LOCALAPPDATA%\Programs\MatrixRain` and runs the warm-up. [[Installing-and-uninstalling]] describes it.

## Run from source

Create a venv with Python 3.14 and install `requirements/requirements.txt`, then:

```powershell
python matrix_saver.py /s
```

[[Contributing]] lists the developer flags.

## Release workflow

`.github/workflows/release.yml` runs when a release is published, from the Releases page or with `gh release create`. The tag must be `v` plus the version, for example `v1.0.0`. Starting the workflow by hand builds both installers as workflow artifacts without releasing them. Releases carry only `DigitalRain-Setup.exe`, `DigitalRain.dmg` and `SHA256SUMS.txt`. The workflow has read-only permissions by default and every third-party action is pinned to a commit. It has three jobs. On a Windows runner it:

1. Installs Python 3.14 and the check requirements.
2. For a release, checks that the tag (minus the `v`) equals `ProductVersion` in `version_info.txt`, and fails if they differ. This prevents a release whose file properties show the wrong version.
3. Runs `ruff check .`, `pytest` and `python tools/check.py --fast`.
4. Installs Inno Setup with Chocolatey if the runner image lacks it.
5. Runs `build.ps1 -NoSmoke -Iscc <path>`, because the runner has no interactive desktop for the smoke test.
6. Uploads `DigitalRain-Setup.exe` as a workflow artifact.

On an Apple Silicon macOS runner, at the same time, it:

1. Installs the python.org build of Python 3.14, which py2app needs.
2. Runs `tools/build/build_mac.sh`, which builds, signs ad hoc and checks `Digital Rain.saver`, then zips it to `MatrixRain-mac.zip` (local only) and builds `DigitalRain.dmg`, a compressed disk image holding the saver and an `Install.txt`.
3. Uploads `DigitalRain.dmg` and the `mac-build-results` folder as workflow artifacts. The folder is kept even when the build fails.

Once both builds pass, a third job downloads both installers, writes `SHA256SUMS.txt` over them, adds GitHub build provenance attestations (it alone has the `id-token` and `attestations` write permissions, plus `contents: write`) and uploads the two installers and the checksum file to the release, replacing any earlier copies. Anyone can check a download with `gh attestation verify <file> -R phabzlabs/digital-rain`. If the release was published with no notes, the job fills in GitHub's generated notes. If either build fails, the release stays up with no downloads. Fix the build, then delete and publish the release again.

The workflow runs only the fast tier of the checks. The GPU tier needs a GPU, so run `python tools/check.py` locally before publishing a release. A separate workflow, `ci.yml`, runs lint, pytest and the fast checks on every push and pull request.

The Mac job checks the bundle but cannot open it in System Settings. Try a new Mac build by hand before publishing a release, see [[macOS]].

## Version numbers

Releases are tagged `vMAJOR.MINOR.PATCH`. The first public release is 1.0.0, and `CHANGELOG.md` lists each release. The convention is semantic versioning. A patch is for fixes, a minor version for new features that keep existing settings working, and a major version for a change that breaks them.

The version lives in `version_info.txt`, which is the one source. PyInstaller turns it into the file properties of `MatrixRain.scr`, and `setup_mac.py` reads it for the Mac bundle's version fields. To release:

1. Edit `version_info.txt`: the `filevers` and `prodvers` tuples (four numbers, for example `(1, 1, 0, 0)`), and the `FileVersion` and `ProductVersion` strings (for example `'1.1.0'`). The release workflow checks only `ProductVersion`, so keep the other three in step by hand, and set the same version in `pyproject.toml`, which `tests/test_version.py` compares.
2. Merge the change to `main`.
3. Publish a release with the tag `v1.1.0` on `main`, from the Releases page or with `gh release create v1.1.0 --target main`. Leave the notes empty to get GitHub's generated notes, or write your own.
4. Check that the workflow attached `DigitalRain-Setup.exe`, `DigitalRain.dmg` and `SHA256SUMS.txt` to the release.

Settings files carry their own layout number, `version` in `settings.json` (see [[Settings-reference]]). It changes only when the file layout needs a migration.
