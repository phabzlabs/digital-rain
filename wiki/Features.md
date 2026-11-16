# Features

What Digital Rain does, and why each part is there. For the exact controls and values, see [[Settings-reference]]. For why the code is built the way it is, see [[Design-decisions]].

## The rain itself

The rain is drawn by a fragment shader on the GPU. Each column's state is a pure function of time and a hash of its position, so the CPU simulates nothing per frame. The shader is cheap, so the saver holds the display refresh rate on ordinary graphics hardware.

Glyphs come from the film's own 57-glyph set, taken from the Matrix Code font in Rezmason's project. The set has blocky katakana, digits and symbols, with the selective mirroring the film used. If the font is missing, the saver falls back to MS Gothic and Courier New Bold with the same selection and mirroring. A stock CJK font looks different from the film (thinner strokes, different shapes), which is why the film font is bundled and used by default. [[Film-research]] has the details.

The leading glyph of each column is almost white, the trail fades through phosphor green, and glyphs mutate at random along the trail.

## Film looks

Three presets recreate the code rain of the three film eras, each from measurements of film frames.

| Preset | Based on | Main traits |
|---|---|---|
| The Matrix (1999) | The first film's opening and operator screens | Classic 57-glyph set, saturated green palette with blue-white leaders, rain stepped at 24 frames per second, clustered lanes, strong bloom |
| Reloaded (2003) | The Reloaded and Revolutions titles and rain | Mint-green heads with no white leaders, a heavy bright tone band, soft glyph edges |
| Resurrections (2021) | The 2021 film | The 135-glyph Resurrections set on square cells, 70 columns, a green floor under the rain, warm lime-white leaders, three depth layers with their own densities and a bevel glint |

A fourth choice, Custom, lets you set colour, glow, scanlines, vignette and the other effects by hand. The film presets fix those effects as part of each measured look. A settings file written before presets existed loads as Custom, so an upgrade does not change how it looks.

The Stutter option reproduces the 1999 stammer: highlighted strings pause together, fall one row behind the others, then catch up. It is off by default. The Fall direction option can send the rain sideways or diagonally.

## Depth and optics

Depth draws the rain in three parallax layers: a dim, slow far layer, a middle layer, and a large out-of-focus near layer. The near layer is the same glyph atlas read at a coarser mip level, so the blur costs almost nothing.

Bloom blurs the whole frame at several scales and adds it back, instead of drawing a halo per glyph. Custom mode also offers scanlines with animated interlacing (the even and odd fields alternate every frame), a vignette and a faint flicker. These effects give a CRT monitor look. The film shows grain, not scanlines, so the film presets turn them off.

## Messages and the clock

The rain can spell out the time or your own text (up to 24 characters). It forms a few seconds after the saver starts and again every 36 seconds. A clock can instead stay on screen all the time, in any of nine screen positions, in 12-hour or 24-hour form. The message needs a grid at least seven rows tall.

The Letter font option opens the system font picker (ChooseFont on Windows, the font panel on macOS) and sets the family, bold, italic and size of the message, the clock and the typed film messages. The default is Courier New Bold at 36 pt. Sizes under 36 pt put the message on its own finer glyph grid, so small letters stay readable. Bold reads best, because thin strokes can break up in the rain.

A separate option types short messages from the film ("Wake up, Neo...", "The Matrix has you...", "Follow the white rabbit.", "Knock, knock, Neo.") over the rain now and then. It applies only while the message option is Off.

## Pictures

The rain can form pictures from a folder of your own (JPG, PNG, WebP or BMP), one after another. Two styles exist. Over the rain, the picture forms from its own characters on top of the rain. In the rain, the falling characters brighten to draw the picture, so the rain keeps a single grid.

In-the-rain mode uses an estimate of each picture's depth and surfaces, so that figures, corridors and floors keep their perspective. The Windows build estimates depth with a bundled ONNX model and the macOS build with a bundled Core ML model. Each picture is analysed once, on a background thread, the first time it is shown, and the depth map is cached. On a first run a picture waits up to 10 seconds for its own map, and the network works on that picture first. The first pictures on a new install or a new folder are then not drawn flat. Later runs find the maps on disk and never wait. A picture whose map is still missing after the wait is drawn by an older vanishing-point path. Pictures need the GPU renderer, a film look, rain falling down and the same look on every monitor.

Subfolders can be included, with limits on depth, picture count, folder count and search time so that pointing the saver at a whole drive cannot stall its start.

## Response to the computer

Live load mode makes the rain faster, denser or both as the CPU or GPU load rises. The load is sampled once a second on a background thread and eased, so the rain never jumps. If the load cannot be read, the rain stays normal and nothing is raised into the render loop.

## Display handling

Every monitor runs its own rain, fitted to its resolution, position and Windows scaling. One borderless window spans the whole virtual desktop and the shader works out which monitor each pixel belongs to, so mixed sizes, orientations and scaling work. Plugging or unplugging a display while the saver runs is picked up automatically. [[Platform-and-monitors]] covers how.

Per-monitor overrides let one display use its own film look, colour, fall speed, density or depth. Monitors that were saved but are not connected stay listed, so their overrides come back when you reconnect them.

A precise limiter caps frames at the fastest connected display's refresh rate. The Frame rate limit slider (15 to 240 FPS, default 60) lowers the cap further to save power. On battery power the cap drops to 30 FPS if that is lower. The macOS saver caps at the refresh rate, or 30 FPS on battery, and does not read the slider.

## Performance options

The GPU renderer is the default. When OpenGL is unavailable (a Remote Desktop session, some virtual machines, a driver or shader failure), a CPU renderer with the same look takes over so the saver still draws something. Pictures, upscaling and HDR work only on the GPU.

Optional AMD FSR 1.0 upscaling renders at 67%, 59% or 50% of the resolution per axis (the Quality, Balanced and Performance modes) and upscales with a GLSL port of AMD's EASU and RCAS passes. It is off by default. The rain shader is cheap, so on a fast GPU FSR costs more than it saves. It is meant for weak or integrated GPUs and very high resolutions. Scanlines, interlacing and flicker are applied after upscaling so they stay one real pixel row thick.

In-the-rain pictures on a display 2000 pixels wide or more render at Quality upscaling at least, whatever the setting says, because their picture passes held the frame rate near 20 FPS at full resolution.

HDR output lets the brightest characters go above SDR white on an HDR display. Windows caps highlights at eight times your SDR content brightness.

## Settings window

The settings window has six pages, a live preview strip, a Full screen button and a scope picker for per-monitor editing. Nothing is saved until you press OK. [[Settings-reference]] describes each page.

## First launch

Windows Defender scans freshly written libraries the first time they load, so the first launch after an install could take two to three seconds to show a frame. The installer script runs a hidden one-second warm-up that loads every library once, so the first real launch is as quick as later ones.
