# Rendering pipeline

One frame's path through the GPU renderer (`digital_rain/gl_renderer.py`, `GLRenderer`) and its shaders in `assets/shaders/`, followed by the software renderer and how closely it matches. For the program around it, see [[Architecture]].

## Passes in order

Each frame runs these passes.

| Step | What it does | Shader |
| --- | --- | --- |
| 1. Reveal cache | Optional, with the picture layer. Writes the picture's reveal per main-layer cell into a float texture. | `scene.frag` with `u_rev_pass` set |
| 2. Scene | Draws the rain into an RGBA8 texture at render resolution. | `scene.frag` with `STAGE 1` |
| 3. Picture passes | Optional, grid picture mode. Screen-blends the picture glyphs onto the scene texture. | `scene.frag` with `STAGE 2` |
| 4. Bloom | Builds blurred copies of the scene. | `down.frag`, `blur.frag` |
| 5. Final | Adds scene and bloom, applies colour and the CRT finish. | `final.frag` |
| 6. Upscale | Optional. Raises the image from render to screen resolution. | FSR passes, `scan_post.glsl` |
| 7. HDR | Optional. Converts the frame to linear light with extra headroom. | `hdr.frag` |

The scene texture holds brightness in R and a leader flag in G. When the picture layer is on, B and A carry the picture reveal. Colour does not exist yet at that point. The palette is applied in the final pass. The easter egg draws into the scene texture after the rain, through `overlay.vert` and `overlay.frag`.

## Stateless rain

The GPU renderer keeps no rain state between frames. For any pixel, the scene shader works out which cell it sits in and which lane that cell is in. It then computes the brightness from the clock and a hash of the lane. The README puts it this way: each column's state is a pure function of time and a hash of its position.

The hash is `h1(a, b, c)`, built from three rounds of the PCG function `pcg`. The seed for a lane is `L*64 + mi*8 + 1`, where `L` is the layer index and `mi` the monitor index. For a non-zero `u_run`, the seed is mixed with `u_run`. With `u_run` 0 the layout is fixed, and the checks and golden frames use it. The `--run N` flag sets the value.

### Film model

The film presets use the saw model. Each lane has one endless phase that advances with the rain clock:

```
w     = wobble(((rain_time + o) * speed + drift - a) / T)
k     = floor(w)
b     = 1 - fract(w)
base  = clamp(b * contrast + bias, 0, 1)
```

Here `o` is a per-lane offset, `a` is the cell's row and `T` is the tooth length (`u_saw.x`). `contrast` and `bias` come from the preset, and `wobble(x) = x + 0.3 sin(sqrt(2) x) + 0.2 sin(sqrt(5) x)`. The fractional part `b` is the brightness ramp behind a head. The integer part `k` counts teeth. With `u_run` 0, a lane is lit when a hash of the lane is below the density. With any other `u_run`, every lane is lit and each tooth `k` survives when a hash of the lane and `k` is below the density. A noise over the lane index (`cluster`) scales the density, so lit lanes group together. An optional gamma shapes the ramp.

A tooth is highlighted when a hash of the lane and `k` is below `lead_ratio`. The G channel marks the head of a highlighted string, and the final pass mixes the cursor colour into those pixels. Highlighted strings follow the pulse clock `u_ptime`. When `u_run` is not 0, each lane also gets a slow sinusoidal drift added to its phase.

The `film_1999` preset steps its rain at 24 frames per second (`step_fps`), and `looks.step_time` quantises the clock. The other film presets set `step_fps` to 0 and run continuously. `digital_rain/looks.py` holds the same arithmetic as the shader, so the software renderer and the checks agree with it.

### Custom model

The `custom` preset keeps the older drop model. It is also stateless in the shader: `pos = ptime * speed + d * period`, with a hash giving the length and shift for each cycle. The `custom` golden frames guard that neutral look values keep the film code paths off.

### Glyph choice

A cell's glyph is a hash of the cell and a slot number. Strings that change glyphs use a global slot (`looks.glyph_phase`). With `crossfade` on, the first frame of each slot shows a 50 percent mix of the new and previous glyph.

## Parallax layers

`settings.LAYERS` defines three layers. Each has its own cell scale (0.65, 1.0 and 1.8), dimming, speed, density, trail length and softness. The shader adds the layers together.

The Resurrections preset has its own `layers` table and six `depth_slices`. The shader screen-blends the slices. Each lane in every slice except the main one gets a depth jitter (`depth_jitter`) that scales its dim and speed.

Softness needs no blur pass. The glyph atlas is mipmapped, and the shader samples it with `textureGrad`, scaling the derivative by `blur = 1 + soft*5`. A soft layer therefore reads a coarser mip level. `u_defocus` sets a minimum blur in cell widths.

## Glyph atlases

`digital_rain/glyphs.py` supplies the glyph tiles and `digital_rain/gl_renderer.py` lays them into atlas textures. The classic atlas keeps only the R channel (coverage).

The classic set takes the user's own font (`font_path`) first. Without one it renders the film's 57 glyphs from `assets/rezmason/Matrix-Code.ttf`. If that file is missing it falls back to Courier New Bold plus a Japanese font with selective mirroring (`_flips`). Each atlas cell is 96 by 128 pixels with an 8 pixel margin, laid out in 10 columns. Glyphs render at scale 4.0, then the atlas gets mipmaps and anisotropic filtering of 4.

For Resurrections it decodes the project's MSDF PNGs (a 13 by 12 grid of 64 pixel cells holding 135 glyphs) on the CPU. It takes the median of the three channels, maps the distance with `clip((d - 0.5) * 4 + 0.5)` and crops 6 pixels per side. That gives a coverage tile in R and a glint tile in G of a second atlas. For classic looks that set `ink_fill`, `ink_stretch` scales the ink and a third atlas holds the result.

Cells are 20 by 28 pixels at scale 1.0, multiplied by the layer scale, the DPI scale, `glyph_scale` and `cell_scale`. When `columns` is above 0, cells are square and sized from the monitor width, which is how Resurrections gets its 70 columns. The shader and `looks.cell_px` do the same float32 arithmetic so both agree on the grid.

## Split looks

The renderer supports up to `MAX_MON` (8) monitors. The shaders find a pixel's monitor through `u_mon` rectangles. Per-monitor settings (`monitor_cfg`) can override preset, colour, speed, density and depth. When the monitors do not all share the same values, the renderer enters split mode and draws one scissored rectangle per monitor.

## Bloom

The film presets build a pyramid of four levels at 1/2, 1/4, 1/8 and 1/16 of the render size. `down.frag` is a 4-tap bilinear box filter with an optional high-pass threshold. The final pass weights and sums the levels.

The `custom` preset keeps the older chain: a quarter-size and a sixteenth-size copy, each blurred with the 5-tap separable `blur.frag`.

## Final pass

`final.frag` does the following in one pass:

1. Adds scene and bloom into one brightness value.
2. Subtracts a hash-based film grain and maps the brightness through the palette, with an optional smoothstep toe.
3. Mixes the cursor colour into leader pixels.
4. Applies ink grain and ink dots (`ink_grain.glsl`) when the look sets them.
5. Applies the vignette, the flicker gain and the scanlines.

A scanline row is dark when `mod(floor(y) + field, 2)` is below 1. With `interlace` on, `field` is the frame number modulo 2. When upscaling is on, scanlines, flicker, ink grain and ink dots move to the upscale pass, so scanlines stay one real pixel row thick.

## FSR upscaling

`digital_rain/fsr.py` ports AMD FSR 1.0 to GL 3.3. `FSR.resample` runs EASU (edge-adaptive spatial upsampling), then `begin_sharpen` and `sharpen` run RCAS, AMD's contrast-adaptive sharpening pass. The port uses `texelFetch` where the reference uses `textureGather`, which GL 3.3 lacks. The finish from `scan_post.glsl` runs inside the RCAS pass.

| Setting | Render scale divisor |
| --- | --- |
| Off | 1.0 |
| Quality | 1.5 |
| Balanced | 1.7 |
| Performance | 2.0 |

The `sharpness` setting defaults to 0.2. Upscaling is skipped when the canvas is under 1000 pixels wide. Grid picture mode with a picture folder on a canvas at least 2000 pixels wide forces at least Quality (`grid_upscaled`, `GRID_UPSCALE_WIDTH`). Picture passes cost about twice plain rain per pixel, and at full resolution they held the frame rate near 20 fps.

## HDR

`hdr.frag` runs last. The display-referred frame is drawn into a float16 texture, and the shader converts it to linear light. With `m` the largest linear channel, it takes `k = smoothstep(0.12, 0.8, m)` and multiplies the colour by `1 + (headroom - 1) * k^1.3`, then by `u_white`. Bright parts of the rain gain headroom and dim parts stay near SDR white.

On Windows the output is scRGB, where 1.0 is 80 nits, and `u_white` is the SDR white level divided by 80. On macOS the output is extended linear sRGB, where 1.0 is SDR white. The headroom is `hdr_peak` divided by the SDR white level in nits, limited to the display's `max_headroom` and to 8. Windows reports no peak brightness, so only the limit of 8 applies there. The `hdr_peak` setting defaults to 1000 and accepts 200 to 2000. HDR works only on the GPU renderer at full screen.

## Picture in rain

The picture layer shows a photograph made of rain glyphs. The picture itself is never drawn, apart from a debug switch.

`digital_rain/image_layer.py` scans the `image_dir` folder, with optional subfolders. The limits are 8 levels of subfolders, 5000 pictures, 2000 folders and a 2 second listing budget. Decoding and analysis run on a worker thread, and uploads to the GPU happen on the main thread, one step per frame, so a large folder never blocks the first frame.

Analysis produces luminance, an open-background mask, a surface tone, a depth field and a vanishing point. Grid mode adds surface labels. The depth network Depth Anything V2 Small provides disparity. The saver fills a cache of `.npz` files on a background thread the first time each picture is wanted. On Windows `digital_rain/surfaces.py` runs the bundled ONNX model with ONNX Runtime. On macOS `digital_rain/mac/depth_coreml.py` runs it through Core ML. A picture waits up to `depth_wait` (10 seconds) for its own map before it falls back to the vanishing-point path. `tools/dev/surface_cache.py` fills the cache ahead of time. `digital_rain/surfaces.py` fits planes with sequential RANSAC and labels them front, wall left, wall right, floor or ceiling.

There are two modes.

| Mode | Behaviour |
| --- | --- |
| `classic` | A separate glyph grid (`img_glyphs`) shows the picture. This is the default. |
| `grid` | The picture is drawn in the rain's own cells (`image_mode`). |

In grid mode a cell takes the picture when the first lit head after the picture's start reaches it. A backstop of 6 to 9 seconds per lane covers lanes with no head. The `image_period` setting sets how long each picture shows, from 5 to 300 seconds.

The layer needs the GPU renderer, a film preset, downward direction and a single shared look (no split mode). A picture that fails to load is skipped, and the layer turns itself off if none are usable.

The design notes in `design/notes/` (`picture-in-rain-grid.md`, `picture-targets.md` and `rain-motion-in-picture.md`) record why grid mode exists. In classic mode two grids disagreed about reveal, dimming and which glyph was on top. The notes judge the look against the film's corridor shot and three reference images.

## Rain messages

`digital_rain/rain_message.py` builds a glyph mask from the Latin font. `display_text` upper-cases the text and keeps Latin characters only. A cell latches to the mask on the first rain head in its own lane after the reveal, and unlatches on the first head after the deletion. The default schedule reveals at 0.5 s, starts the deletion eight seconds later and repeats every 36 s.

The clock variant (`clock_fixed`) stays on screen. When the minute changes it uses change codes (stable, appear, vanish) and a glitch of 1.6 s. Both renderers share the mask code.

`digital_rain/easter_egg.py` times a typed overlay that shows one of four film phrases, such as "Wake up, Neo...". The first appears 12 to 25 seconds in, and later ones follow 45 to 90 seconds apart. The overlay is off when a message is set.

## Live load

`digital_rain/live_load.py` runs a daemon thread that samples once a second and smooths the result with an exponential moving average (time constant 3 s). The `live_source` setting picks CPU, GPU or off. CPU load comes from psutil, with the saver's own process subtracted. GPU load comes from the Windows performance counter `\GPU Engine(*engtype_3D)\Utilization Percentage`. Three failed samples in a row mark the sampler unavailable, and the rain stays normal.

`LiveControl` maps the load to a speed factor `1 + s*(2*load - 1)*0.5` and a density factor `1 - s*0.75*(1 - load)`, where `s` is the `live_strength` setting. The `live_target` setting chooses which factors apply. Both ease towards their targets with a 3 s time constant. The renderer warps the rain clock with `rain_off += dt * (speed_k - 1)`. On macOS the GPU sampler raises, so it reports unavailable.

## Software renderer parity

`digital_rain/soft_renderer.py` draws with numpy and pygame when OpenGL fails. The film looks use the same stateless idea, through `looks.lane_hash`. That hash is not the shader's PCG, so the two renderers share a model but differ pixel by pixel.

The software renderer pre-renders glyph brightness levels (20 of them), tints them and applies the palette per level. `design/film-reference.md` lists the differences in its "Software renderer differences" section:

1. No flicker.
2. No film grain on ink, though the static ink dots remain.
3. One quarter-resolution bloom, rebuilt every other frame, with no high-pass and no pyramid.
4. The palette applies per glyph level instead of per pixel.
5. No `lead_core` and no glint.

It has no FSR, HDR or picture layer. It does have messages, live load and the easter egg.

## Golden frames

Eight GPU frames (four presets, upscaling off and Quality) are compared with a small tolerance, and four software frames by SHA-256. GPU goldens hold for one machine's GPU and driver. [[Checks-and-tests]] has the sizes and tolerances.
