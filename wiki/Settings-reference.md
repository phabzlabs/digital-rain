# Settings reference

Every setting in the settings window: its label, its key in the settings file, the values it takes, its default and what it is for. Keys, defaults and ranges come from `digital_rain/settings.py`, and labels, pages and help text from `digital_rain/dialog_model.py`. For the bigger picture, see [[Features]].

## Where settings live

On Windows the settings window writes `%APPDATA%\MatrixRain\settings.json` and the saver reads it. The window writes a temporary file beside the real one and renames it over the real one, so a crash mid-write never leaves a truncated file. Nothing is saved until you press OK. Cancel, Esc and closing the window discard every change. Reset to defaults asks first and also saves nothing until OK.

A missing or unreadable file gives the defaults. A value of the wrong type or outside its list of choices is ignored and the default stays, except that an unknown `preset` loads as `custom`. A number outside its range is clamped to the nearest end. Unknown keys are dropped. A hand-edited file therefore cannot stop the saver from starting.

Two older layouts are migrated on load. A file with no `preset` key loads as `custom`, so a file from before presets existed looks as it always did. The old `city_dir` key is read as `image_dir`. The file also carries a `version` key, currently 1.

On macOS the options sheet saves one JSON blob to ScreenSaverDefaults and reads `settings.json` only when nothing was saved there. See [[macOS]].

## The settings window pages

| Page | Contents |
|---|---|
| Look | Film look cards, fall direction, stutter, and the effects box |
| Motion and layout | Fall speed, rain density, character size, depth |
| Message and clock | What to form in the rain, clock options, your text, messages from the film |
| React to computer load | CPU or GPU load source, what it changes, strength |
| Graphics | Renderer, HDR, frame rate limit, upscaling, sharpness, font |
| Pictures | Picture folder and how pictures appear |

Each sidebar entry shows a one-line summary of its settings. The strip at the top is a live preview. Full screen runs the saver with the current settings until you press a key or move the mouse.

### Per-monitor edits

The Editing settings for picker at the top of the sidebar sets the scope. In All monitors, every control edits the global values. Choose a display and the film look, colour, fall speed, rain density and depth controls gain an Override button. The box at the bottom of the sidebar lists what that display changes. Forget this monitor removes all its overrides. Saved monitors that are not connected appear under Saved, not connected. Display numbers in the picker follow its own list, not Windows Settings.

Overrides are stored under `monitors`, keyed by the Windows monitor device path, with a `name` and any of `preset`, `color`, `speed`, `density` and `depth`. Entries with bad keys or values are dropped on load. The picture layer is off whenever monitors differ in these five settings.

## Look

| Label | Key | Values | Default | What it does and why |
|---|---|---|---|---|
| Film look | `preset` | `film_1999`, `reloaded`, `resurrections`, `custom` | `film_1999` | Picks a film look, or Custom for hand tuning. The film presets fix glow, scanlines, dark edges, flicker and interlacing. The Customise these button switches to Custom, starting from the preset's values and the Film green colour. |
| Fall direction | `direction` | `down`, `sideways` (left to right), `diagonal` (down and right) | `down` | Which way the rain falls. Pictures need `down`. |
| Stutter | `pulse` | on or off | off | The 1999 stammer: columns pause, drop a row, then catch up. |

### The effects box

The box holds Colour plus the six effects below. Under a film preset the whole box is read-only. The preset fixes five effects and the box shows their values. Colour and Trail length show the stored values.

| Label | Key | Range | Default | What it does |
|---|---|---|---|---|
| Colour | `color` | `film`, `classic`, `amber`, `red`, `blue`, `white` | `film` | Colour of the rain. The leading character of each column is paler. Shown as Film green, Bright green, Amber, Red, Blue and White. Only Custom uses it, because the film presets have their own palettes. |
| Glow | `bloom` | 0 to 1 | 0.5 | Soft glow around bright characters. 0 turns it off. |
| Scanlines | `scanlines` | 0 to 0.9 | 0.45 | Faint horizontal lines like an old monitor. |
| Dark edges | `vignette` | 0 to 1 | 0.35 | Darkens the edges and corners of the screen. |
| Flicker | `flicker` | 0 to 0.2 | 0.03 | A slight, constant flicker in brightness. |
| Trail length | `trail_falloff` | 0.6 to 4 | 1.6 | How far each trail stretches behind its leading character. Higher values give shorter trails, and the slider reads Long to Short. Applies to every look, including the film presets. |
| Interlaced lines | `interlace` | on or off | on | Alternates even and odd scanline fields every frame. |

The values the film presets fix:

| Preset | Glow | Scanlines | Dark edges | Flicker | Interlaced lines |
|---|---|---|---|---|---|
| The Matrix (1999) | 1.0 | 0 | 0.15 | 0 | off |
| Reloaded (2003) | 1.0 | 0 | 0.15 | 0 | off |
| Resurrections (2021) | 0.6 | 0 | 0.15 | 0 | off |

The presets turn scanlines, interlacing and flicker off. [[Film-research]] covers the film measurements.

## Motion and layout

| Label | Key | Range | Default | What it does and why |
|---|---|---|---|---|
| Fall speed | `speed` | 0.4 to 2.5 (times) | 1.0 | Multiplies the look's fall speed. Per-monitor override allowed. |
| Rain density | `density` | 0.3 to 1.6 (times) | 1.0 | How many columns rain at once. Per-monitor override allowed. |
| Character size | `glyph_scale` | 0.25 to 2.0 (times) | 0.5 | Glyph size multiplier. |
| Depth | `depth` | on or off | on | Three parallax layers of different sizes instead of one, so some rain looks farther away. The Resurrections look on the GPU renderer uses six depth slices instead. Per-monitor override allowed. |

## Message and clock

| Label | Key | Values | Default | What it does and why |
|---|---|---|---|---|
| Show in the rain | `message` | `off`, `clock` (shown as Time), `text` (Your text), `both`, `clock_fixed` | `off` | Forms the time or a text out of rain glyphs a few seconds after the saver starts, then every 36 seconds. The message needs a grid at least seven rows tall. |
| Keep clock on screen | not a setting | on or off | off | Shown only while Show in the rain is Time. A view of `message`: on stores `clock_fixed`, which shows the time all the time, and off stores `clock`. |
| Clock position | `clock_position` | `top_left`, `top_center`, `top_right`, `middle_left`, `middle_center`, `middle_right`, `bottom_left`, `bottom_center`, `bottom_right` | `top_right` | Which of nine screen segments holds the clock. Shown with Time and used only when Keep clock on screen is on. |
| 24-hour clock | `clock_24h` | on or off | on | 13:45 rather than 1:45. The 12-hour form has no AM or PM marker. |
| Your text | `message_text` | up to 24 characters | `Wake up, Neo...` | The text for Your text or Both. Characters the rain has no shape for are skipped. Control characters are removed and a blank entry keeps the default. |
| Messages from the film | `easter_egg` | on or off | on | Now and then, messages from Neo's computer in the film type out over the rain. Used only while Show in the rain is Off. |
| Letter font | `message_font`, `message_bold`, `message_italic`, `message_font_size` | a font family name (blank is Courier New), on or off, on or off, 8 to 144 points | blank, on, off, 36 | Opens the system font picker, which sets all four at once, for the message, the clock and the typed film messages. 36 pt is the standard size and 72 is twice that. Long text still shrinks to fit. Bold reads best, because thin strokes can break up in the rain. Used only when something is shown in the rain or Messages from the film is on. |

## React to computer load

| Label | Key | Values | Default | What it does and why |
|---|---|---|---|---|
| React to | `live_source` | `off`, `cpu`, `gpu` | `off` | Which load drives the rain, read once a second. If it cannot be read, the rain stays normal. |
| Changes | `live_target` | `speed`, `density`, `both` | `both` | What the load changes. Used only when React to is CPU or GPU. |
| Effect strength | `live_strength` | 0 to 1 | 0.6 | How far the load moves the rain. Used only when React to is CPU or GPU. |

## Graphics

| Label | Key | Values | Default | What it does and why |
|---|---|---|---|---|
| Draw with | `renderer` | `auto`, `gpu`, `software` (shown as CPU) | `auto` | Auto uses the graphics card and falls back to the processor, which is slower. Forcing one helps when diagnosing. |
| HDR | `hdr` | `auto`, `off` | `auto` | On an HDR display, Auto lets the brightest characters go above SDR white. GPU only. |
| HDR peak brightness | `hdr_peak` | 200 to 2000 nits | 1000 | How bright the brightest characters get. Windows caps highlights at eight times your SDR content brightness, so a high SDR brightness leaves little headroom. Used only when HDR is on. |
| Frame rate limit | `frame_cap` | 15 to 240 fps | 60 | Caps frames per second to save power, never above the display's refresh rate. The slider reads Lower power to Smoother. On battery power the cap drops to 30 fps if that is lower. Windows only: the macOS saver does not read it. |
| Upscaling | `upscaling` | `off`, `quality` (1.5x), `balanced` (1.7x), `performance` (2x) | `off` | Draws at a lower resolution and scales up with AMD FSR 1.0, for a higher frame rate on slower graphics cards. GPU only. |
| Upscaling sharpness | `sharpness` | 0 to 2 stops | 0.2 | FSR sharpening. 0 is sharpest and 2 is softest. 0.2 is AMD's default. Used only when upscaling is on. |
| Font | `font_path` | path to a TTF or OTF, or blank | blank | Draws the rain with your font instead of the built-in film font. Blank uses the film glyphs unless a `fonts` folder holds a font. |

In-the-rain pictures on a canvas 2000 pixels wide or more render at Quality upscaling at least, whatever `upscaling` says. When `font_path` is blank or missing, the first `.ttf` or `.otf` in a `fonts` folder next to the `.scr`, in name order, takes priority over the film font.

## Pictures

| Label | Key | Values | Default | What it does and why |
|---|---|---|---|---|
| Picture folder | `image_dir` | folder path, or blank | blank | Any folder of JPG, PNG, WebP or BMP pictures. Blank turns pictures off. |
| Include subfolders | `image_subfolders` | on or off | off | Also reads every folder inside it, each folder's pictures before its subfolders', in name order. Hidden and system folders, links and macOS packages such as a Photos library are skipped. The search stops 8 levels down, at 5,000 pictures, 2,000 folders or 2 seconds. |
| How pictures appear | `image_mode` | `classic` (Over the rain), `grid` (In the rain) | `classic` | Over the rain forms the picture from its own characters on top of the rain. In the rain brightens the falling characters to draw the picture. |
| Order | `image_order` | `sequence` (Name order), `shuffle` (Shuffled) | `sequence` | The order the folder's pictures form. |
| Time per picture | `image_period` | 5 to 300 s | 30 | How long each picture is shown. |
| Rain between pictures | `image_gap` | 0 to 30 s | 0 | Plain rain between pictures. 0 means the next picture sweeps straight over. |
| Picture detail | `image_detail` | 0 to 1 | 0 | Higher draws distant parts of a picture with smaller characters, for finer detail. |

Pictures work only with the GPU renderer, a film look, rain falling down, and no per-monitor differences in the five override settings.

## Settings without a control

| Key | Values | Default | Purpose |
|---|---|---|---|
| `monitors` | map of monitor id to overrides | empty | The per-monitor overrides described above. Edited through the scope picker. |
| `version` | integer | 1 | Version of the file layout, written on save. |

## Looks and presets

A look is the flat set of values the renderers read. `looks.resolve` builds it from the settings. For Custom it uses your sliders and the chosen colour with the classic cell size. A film preset loads a JSON file from `assets/presets/` (`film_1999.json`, `reloaded.json`, `resurrections.json`). Each file holds the palette stops, the fall speed range in rows per second, glyph cell scale, bloom, grain, defocus, the glow radii and other shape parameters. The loader ignores keys that start with `_`.

| Preset | Fall speed (rows per second) | Palette top stop | Glyph set | Cell |
|---|---|---|---|---|
| film_1999 | 16 to 24 | `28F5A0` | classic | classic cell at scale 1.3, rain stepped at 24 frames per second |
| reloaded | 15 to 30 | `25FCA8` | classic | classic cell at scale 1.15 |
| resurrections | 15 to 30 | `E8FBE8` | resurrections | square cells, 70 columns across the display width |

[[Film-research]] summarises the measurements behind the numbers.

## Environment variables

These are for development and diagnosis. None changes a normal install.

| Variable | Effect |
|---|---|
| `MATRIX_TIMING=1` | The saver prints wall-clock stamps to stderr, for startup measurements. |
| `MATRIX_IMAGE_SYNC=1` | Prepares background pictures inline instead of on a worker thread, so frames do not depend on timing. The frame renderer for the checks sets it by default. |
| `MATRIX_IMAGE_DIR` | Picture folder used when `image_dir` is blank. |
| `MATRIX_IMAGE_PERIOD`, `MATRIX_IMAGE_DETAIL` | Override `image_period` and the picture detail. |
| `MATRIX_IMAGE_<NAME>` | Every tuning field of the picture layer (`ImageTuning` in `digital_rain/image_layer.py`) can be overridden this way, for example `MATRIX_IMAGE_BLACK` and `MATRIX_IMAGE_EDGE`. |
| `MATRIX_DEPTH_MODEL` | Path to an ONNX depth model instead of the bundled `assets/models/depth_anything_v2_small_q.onnx`. The Windows build runs it on a background thread and caches each picture's depth map. |
| `MATRIX_SURFACE_CACHE` | Folder for the cached surface and depth maps of pictures. Default is a `surfaces` folder inside the settings folder. |
| `MATRIX_COREML_MODEL` | macOS only: path to a Core ML depth model folder instead of the bundled one. |
| `MATRIX_CHECK_SHOW=1` | The checks open real windows instead of hidden ones. Same as `--show`. |
| `MATRIX_CHECK_PRIORITY` | `normal` keeps everything at normal priority. `below` also lowers the timed saver runs. The default lowers the checks only. |
| `MATRIX_CHECK_HIDDEN` | Set by the check tooling. The settings window then starts no preview child process. |

See [[Checks-and-tests]] for how the check variables are used, and [[Contributing]] for the command-line flags of the saver.
