# Design decisions

The main choices behind Digital Rain, each with what was decided, what else was possible and why. The reasons come from code comments, commit messages, design notes and the documents under `design/`. Where nobody wrote a reason down, the entry says so and describes only what the code shows. For the mechanics, see [[Architecture]] and [[Rendering-pipeline]].

## Rain is a stateless function of time and position

Decision. The shader computes each lane's state from the clock and a hash. Nothing about the rain is stored or stepped on the CPU.

Alternative. A simulation that advances every column each frame, which is what the software renderer's custom model still does.

Reason. The README states the principle ("nothing is simulated per frame on the CPU") and gives no argument for it. The code shows two results. Checks reproduce a frame exactly, because `u_run` 0 fixes the layout. A stalled frame costs nothing, because the next frame reads the clock.

## Per-launch randomness with a fixed run 0

Decision. Each launch mixes a random `u_run` into the hash. Run 0 keeps the layout fixed.

Reason. The design note for this change records that the GPU layout repeated on every launch, while the software path was already random. Checks and goldens need a repeatable layout, so they use run 0.

## pygame-ce and moderngl

Decision. pygame-ce provides the window, the SDL GL context, fonts and software blits. moderngl is a thin wrapper over OpenGL.

Alternatives. Not recorded. The project started from an existing GPL-3.0 screensaver, credited in the README, and the code does not say why these libraries were kept or whether others were tried. What the code shows is that the shaders are GLSL 330 core, so macOS, which serves a 4.1 core profile, compiles them unchanged. The pygame font and surface code also feeds both renderers.

## GLSL 330 core

Decision. Every shader targets `#version 330`.

Reason. The same shaders must run on Windows OpenGL and on the macOS core profile. The macOS view asks for a 3.2 core pixel format and receives 4.1 core. The FSR port uses `texelFetch` instead of `textureGather` for the same reason: `textureGather` is not part of GL 3.3.

## Film glyphs from a TrueType font

Decision. The classic glyph set is rendered from the bundled `assets/rezmason/Matrix-Code.ttf`. Only Resurrections uses the MSDF atlas.

Alternative. Use the MSDF atlas for every look.

Reason. The design note for the film glyphs records that the MSDF route needs a new sampling path and cannot feed the software renderer, while the TrueType font goes through the same pygame path as the other fonts. Both sources hold the same Path of Neo glyphs. The Resurrections atlas is decoded on the CPU into plain coverage tiles, so the shader samples it like any other atlas.

## Film measurements decide the presets

Decision. The presets are tuned against measurements of film stills, not by eye alone. `tools/checks/check_film.py` and its helpers (`tools/checks/film_metrics.py`, `tools/dev/measure_reference.py`, `tools/checks/film_targets.py`) compute lit share, near-white share, hue and similar numbers and compare them with the reference.

Alternative. Judge by eye against the film.

Reason. `design/film-reference.md` records the findings as numbered facts, such as the fixed glyph grid and whole-cell steps, that later design notes cite. The documents never argue for measurement over eyeballing. In practice a change to a preset shows up as a number.

## A software renderer as fallback

Decision. `digital_rain/soft_renderer.py` draws the same looks with numpy and pygame when OpenGL cannot start.

Alternative. Refuse to run, or show a black screen.

Reason. The code comment names the cases: Remote Desktop and some virtual machines have no usable OpenGL. The design note for the film software path keeps the film model stateless there as well, with no per-cell glyph array, and lists the simplifications it accepts: grain, the high-pass and tone-mapped bloom. The macOS saver has no fallback. No reason is recorded for that.

## Parity in model, not in pixels

Decision. The software renderer uses `looks.lane_hash`, not the shader's PCG hash.

Reason. Not recorded. Goldens for software frames are SHA-256 hashes, so any change to the hash would change them. The software and GPU goldens are separate sets.

## A PyInstaller bundle in one-directory mode, renamed to `.scr`

Decision. `build.ps1` builds a `--onedir --noconsole` bundle and renames the executable to `.scr`.

Alternative. A one-file build.

Reason. The start-up performance note records the measurement. A one-file build unpacks itself into the temporary folder on every launch, which costs 1.2 to 1.7 seconds. The settings window screenshot took 2430 ms in one-file mode and 989 ms in one-directory mode. A slimmer one-file build would still unpack.

## Python 3.14 and exact pins

Decision. The build uses Python 3.14 with `==` pins in `requirements/requirements.txt` and `requirements/requirements-build.txt`, without hash lines.

Reason. The design note for the pins records that they reproduce the build from a clean checkout, and that hashes would tie the file to one wheel per platform and Python version, and that the pins already fix the package set.

## Settings: migrate, then clean

Decision. `settings.clean` runs `migrate` first and then overlays validated values on the defaults. Unknown keys are dropped. `save` writes a temporary file and replaces the target.

Alternatives. Fail on bad files, or keep unknown keys.

Reason. No comment states the motive. The effect is that any input produces a valid configuration, so a bad file cannot stop the saver. Migration sets the preset to `custom` for older files, so their sliders keep working, and renames `city_dir` to `image_dir`. The design note for the settings layout records that stored settings keep their keys, ranges and meaning. `tests/fixtures/settings_v1_1_0.json` is an older file that the tests load. The temporary-file write protects against a crash leaving a truncated file.

## The saver reads, the dialog writes

Decision. Only the dialog writes settings.

Reason. Not stated as a rule in one place. The code follows it everywhere, and on macOS it is enforced, because the sandboxed saver cannot write the real home folder. Settings live in `ScreenSaverDefaults` as one JSON blob, validated by `clean`.

## A dialog model with no Tk

Decision. `digital_rain/dialog_model.py` holds all the editing rules and imports neither Tk nor numpy.

Alternative. Put the rules in the Tk window.

Reason. The macOS bundle excludes `tkinter`, and the macOS options sheet is generated from the same tables, so one rule set feeds both. The start-up performance note adds that numpy cost 120 to 190 ms of dialog start-up. A side effect is that `tools/checks/check_dialog.py` can test every rule without a window. The preset effect values are copied into `PRESET_EFFECTS`, because `digital_rain/looks.py` imports numpy. A check compares the copy with the real values.

## Per-monitor overrides keyed by device identity

Decision. Per-monitor looks are stored by a stable monitor id, and there are none by default.

Reason. The per-monitor design note records that the Windows device interface path survives layout, resolution, scaling and restart changes. It sets the default to no overrides because the film applies one look to every screen, and monitors it does not know use the global look. The same note keeps the glow, scanline, interlace, vignette, flicker and trail settings global, because only five override keys were requested.

## Wallpaper mode removed

Decision. The `/w` argument exits with code 0 and draws nothing.

Reason. Commit `b335105` removed the mode. No reason is recorded. The saver still accepts the flag and exits at once.

## Pictures are drawn only as rain

Decision. The picture layer never shows the picture. It decides which cells carry glyphs and how bright.

Reason. `design/notes/picture-in-rain-grid.md` records that the first design had two glyph grids that disagreed about reveal, dimming and which glyph sat on top, so grid mode draws the picture in the rain's own cells. The Over the rain style still uses its own grid. The targets in `picture-targets.md` are black backgrounds, a subject shaded by its own light, and streams that follow surfaces and camera. Depth comes from a depth network or a cached depth map. No document compares that network with others.

## HDR through SDL directly

Decision. The float16 framebuffer is requested with `SDL_GL_SetAttribute` through ctypes.

Reason. Commit #33 notes that pygame-ce rejects the attribute, so the float format was never requested and HDR fell back to SDR silently. The code now recreates the window when the first one has no float format.

## Frame pacing on a multi-monitor window

Decision. The loop paces itself with `FrameLimiter` at the fastest display's refresh rate, lowered by the `frame_cap` setting and to 30 fps on battery.

Reason. A comment records that vsync is ignored when the window spans several monitors, and 200 fps or more was measured. The limiter sleeps, then spins for the last millisecond.

## Eight timer ticks per frame on macOS

Decision. The macOS view fires its timer 8 times per frame and draws once a frame's time has passed (`TIMER_SUBSTEPS`).

Reason. The comment in `digital_rain/mac/mac_saver.py` says `flushBuffer` waits for the GPU, so a plain timer at 1/fps skipped ticks and settled at half rate.

## A warm-up run at install

Decision. `--warm-up` draws for one second so the first real launch is fast.

Reason. Defender and Gatekeeper scan freshly installed libraries on first load. The measurement in the commit is 0.75 s for the first frame after warm-up and 2.08 s without.

## Checks, goldens and hidden runs

Decision. Checks come in tiers (`fast`, `gpu`, `perf`). Golden frames guard the renderers. A `--check-hidden` flag runs checks without disturbing the user.

Reason. The custom-preset golden comes from the commit before the film work (`2575ea6`), as proof that neutral values skip the new code. The film goldens guard against drift afterwards. The hidden-run flag came from PR #12, which runs the checks hidden by default (`--show` for visible windows) so the person at the keyboard can keep working. CI runs only the fast tier, with `SDL_VIDEODRIVER=dummy`. GPU goldens are valid only for one machine's GPU and driver (`tools/checks/golden/README.txt`). Each check run gets its own `APPDATA` and `TEMP` through `RunRoot` in `tools/checks/_gate.py`, so a run never touches the real settings. See [[Checks-and-tests]].

## Not recorded

The project history does not explain these choices. The code shows what was done and nothing more.

1. Why pygame-ce and moderngl were chosen over other libraries.
2. Why the software renderer's PCG hash differs from the GPU hash.
3. Why the macOS saver has no software fallback.
4. Why the bloom pyramid has four levels.
5. Why the seed layout is `L*64 + mi*8 + 1`.
