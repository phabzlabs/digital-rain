# Film reference: the Matrix digital rain

What the code rain looks like in the films, written down as measurable targets so later rows can match it. Each finding gives a value, a source and a confidence note. The gap analysis at the end compares every finding with what `digital_rain/gl_renderer.py`, `digital_rain/glyphs.py` and `digital_rain/settings.py` do today.

Researched 4 November 2026. Assets mentioned here live in `assets/` and are listed with their origins in `assets/README.md`.

## How to read the sources

There is no official specification. The best quantitative source is Rezmason's open-source WebGL recreation (github.com/Rezmason/matrix, pinned below to commit `5ba9049`, 31 October 2024). Its parameters are tuned by eye against the films, its glyphs were recovered from official promotional material, and Lilly Wachowski called it better than the original (Vice, September 2022). Rezmason ships three film presets, and the names matter:

- `operator`, aliased `1999` and `throwback`: the first film's opening titles and the operators' screens.
- `classic`, aliased `2003`: the Reloaded and Revolutions opening titles. This is the project default.
- `resurrections`, aliased `2021` and `updated`: the 2021 film.

Where the numbers come from Rezmason they are the author's reconstruction, not studio data, so confidence is "high for intent, medium for exact value". Measurements from the film are mine. The first pass used one Blu-ray frame; the evidence pass of 5 November 2026 added 13 more stills from two releases (Blu-ray and the 4K regrade) across five scenes, plus Carl Newton's eight analysis gifs, all measured with `tools/dev/measure_reference.py`. Each finding below that the new evidence touches ends with an evidence note: "confirmed across N stills" or "rests on one still or one sequence". The per-still numbers are in "Measurements across stills" and the resulting targets in "Targets for the film_1999 preset", both after section 4.

Source shorthand used below:

- [RZ-config] https://github.com/Rezmason/matrix/blob/5ba90490453ceceb6812d6b1bc658a99a92411d0/js/config.js
- [RZ-raindrop] https://github.com/Rezmason/matrix/blob/5ba90490453ceceb6812d6b1bc658a99a92411d0/shaders/glsl/rainPass.raindrop.frag.glsl
- [RZ-symbol] https://github.com/Rezmason/matrix/blob/5ba90490453ceceb6812d6b1bc658a99a92411d0/shaders/glsl/rainPass.symbol.frag.glsl
- [RZ-rain] https://github.com/Rezmason/matrix/blob/5ba90490453ceceb6812d6b1bc658a99a92411d0/shaders/glsl/rainPass.frag.glsl
- [RZ-vert] https://github.com/Rezmason/matrix/blob/5ba90490453ceceb6812d6b1bc658a99a92411d0/shaders/glsl/rainPass.vert.glsl
- [RZ-pass] https://github.com/Rezmason/matrix/blob/5ba90490453ceceb6812d6b1bc658a99a92411d0/js/regl/rainPass.js
- [RZ-bloom] https://github.com/Rezmason/matrix/tree/5ba90490453ceceb6812d6b1bc658a99a92411d0/shaders/glsl (bloomPass.highPass, bloomPass.blur, bloomPass.combine) and js/regl/bloomPass.js
- [RZ-palette] https://github.com/Rezmason/matrix/blob/5ba90490453ceceb6812d6b1bc658a99a92411d0/shaders/glsl/palettePass.frag.glsl
- [RZ-readme] https://github.com/Rezmason/matrix/blob/5ba90490453ceceb6812d6b1bc658a99a92411d0/README.md
- [CN] Carl Newton, "An analysis of the behaviour of the digital rain in The Matrix", https://carlnewton.github.io/digital-rain-analysis (frame-by-frame study of the 1999 opening)
- [STILL] `assets/reference/matrix-1999-opening-bluray.jpg`, from https://screenmusings.org/movie/blu-ray/The-Matrix/images/The-Matrix-001.jpg, 1915 x 799, measured with numpy
- [STILLS] the 14 stills in `assets/reference/` named `matrix-1999-*`: Blu-ray frames from screenmusings.org (opening, opening digit trace, Neo's monitor, Nebuchadnezzar operator screens, "system failure" readout, Neo sees the code) and 4K regrade frames from movie-screencaps.com (opening, opening digit trace, the "506" digit close-up, Cypher's code monitors, an operator screen close-up, the operator screens in the finale, Neo sees the code, "system failure"). Exact URLs are in `assets/README.md`. Measured with `tools/dev/measure_reference.py`; pixel distances are quoted at 1915 px frame width so the two releases compare
- [CN-GIF] Carl Newton's eight analysis gifs of the 1999 opening, `assets/reference/carlnewton-0N-*.gif`, 500 x 208: 01 is the opening at 40 ms per frame (42 frames), 02 to 08 are slowed frame steps (500 or 1000 ms per frame) illustrating fixed glyphs, lower starts, invisible strings, changing glyphs, deletion, highlights and the stammer
- [WIKI] https://en.wikipedia.org/wiki/Digital_rain
- [VICE] https://www.vice.com/en/article/88qvn3/coder-makes-matrix-green-rain-simulator-that-lilly-wachowski-says-is-better-than-the-original

## 1. Glyph set

F1. Origin and designer. The code was designed at Animal Logic (Sydney) for the 1999 film; the typeface is credited to Simon Whiteley. In a 2017 CNET interview Whiteley said the code was made from Japanese sushi recipes, scanned from his wife's cookbooks. Fact-checkers could not read any recipe in the rain, so treat it as the inspiration for the glyph shapes, not as content to reproduce. Lana Wachowski's brief was "rain on a window pane", and the effect went "back to the drawing board many times". Sources: [WIKI] (citing the Powerhouse Museum object 422513 and CNET, https://www.cnet.com/news/lego-ninjago-movie-simon-whiteley-matrix-code-creator/), [VICE], Mimikama fact check https://www.mimikama.org/die-matrix/. Confidence: high for designer and studio, low for the recipe story as literal content.

F2. Character families. Mirrored half-width katakana, plus Latin numerals and a few Latin letters and symbols. The Revisited DVD featurette ("Look of the Matrix", 2001) is the cited source. Sources: [WIKI]. Confidence: high.

F3. The film's exact glyph inventory (classic set): 57 entries in a repeating order, recovered by Rezmason from vectors in the 2007 Path of Neo promotional SWF. They are 33 katakana (モエヤキオカケサスヨタワネヌナヒホアウセミラリツテニハソコシマムメ), the digits 0 1 2 3 4 5 7 8 9 (0 appears twice, there is no 6), a lowercase z, one blank cell, and ¦ : " ꞊ ╌ ▪ — < > | + *. Order (index 0 first): `モエヤキオカ7ケサスz152ヨタワ4ネヌナ98ヒ0ホア3ウ セ¦:"꞊ミラリ╌ツテニハソ▪—<>0|+*コシマムメ`. Carl Newton's independent catalogue of the 1999 opening counts 53: 30 katakana including the long-vowel mark, 10 numerals, 1 Latin letter (Z), 1 Kangxi radical and 11 symbols. Sources: `assets/rezmason/glyph-order.txt`, [RZ-config] (`glyphSequenceLength: 57`, `glyphTextureGridSize: [8, 8]`), [RZ-readme], [CN]. Confidence: high (two independent counts agree within a few glyphs).

F4. Mirroring is selective, not global. All katakana are mirrored horizontally. Numerals 2, 5 and 9 are mirrored horizontally, 3 and 6 are flipped vertically, and 0, 1, 4, 7, 8 are untransformed. In Rezmason's atlas and TTF the shapes are stored already mirrored and `glyphFlip` defaults to false. Sources: [CN], [RZ-config]. Confidence: high.

F5. The glyphs are not a stock Japanese font. They are a custom blocky face: heavy uniform strokes (roughly a fifth of the glyph width), square terminals, flat tops, several katakana redrawn into composite shapes (for example ヨ drawn like 日), and a few Chicago-style symbols from Susan Kare's typeface. A stock CJK font such as MS Gothic mirrored is recognisably different: thin strokes, slanted terminals and calligraphic hooks. Sources: [RZ-readme] ("they also include a few characters from Susan Kare's Chicago typeface"), my side-by-side render of `Matrix-Code.ttf` against mirrored MS Gothic. Confidence: high.

F6. Glyph assets now in the repo. `assets/rezmason/matrixcode_msdf.png` (512 x 512 MSDF, 8 x 8 grid, `msdfgen -size 512 512 -pxrange 4`, index 0 at the bottom-left because the texture is stored bottom-up), `megacity_msdf.png` (64 glyphs, adds the Revolutions Megacity glyph), `resurrections_msdf.png` and `resurrections_glint_msdf.png` (832 x 768, 13 x 12 grid, 135 glyphs), `Matrix-Code.ttf` (classic set on full-width katakana code points U+30A2 to U+30FC, digits, symbols), `Matrix-Resurrected.ttf` (U+E900 to U+E989), and the fan font Matrix Code NFI (Thomas W. Otto, Norfok, 2003; no longer bundled, its licence is private use only). Rezmason samples the MSDF with `msdfPxRange 4.0`, median of three channels, screen-space anti-aliasing via `fwidth`. Sources: `assets/README.md`, [RZ-pass], [RZ-rain], https://github.com/Rezmason/matrix/blob/5ba90490453ceceb6812d6b1bc658a99a92411d0/assets/msdf_command.txt, https://www.fontspace.com/matrix-code-nfi-font-f11467. Confidence: high. Recommendation: `Matrix-Code.ttf` drops straight into the existing pygame atlas path; the NFI font is a weaker match (unmirrored katakana, full Latin alphabet).

F7. Glyph cell proportions. Rezmason uses a square grid: `numRows = numColumns` and the grid is scaled to the screen's long side, so cells are square and the short side is cropped (`screenSize = [1, aspect]`). Glyph height to width is 1.0 for classic and Resurrections and 1.35 for the 1999 operator preset, with `glyphEdgeCrop` 0.15 (operator) and 0.1 (Resurrections) trimming the atlas border. The film stills do not show square cells; they side with the 1999 preset's taller glyph. Column pitch in the opening is 24.5 to 25 px on a 1915 px wide frame (about 77 to 78 columns across), but the row pitch is 34 to 43 px: 36.5 (opening, Blu-ray), 42.6 (opening, 4K), 34.7 and 38.5 (digit trace, Blu-ray and 4K), 34.1 and 33.6 (Neo sees the code, Blu-ray and 4K), by vertical autocorrelation inside lit columns and checked against a pixel ruler on a 4x zoom. Glyph ink is about 20 px wide by 30 to 32 px tall, so the cell is about 1.4 to 1.7 times taller than wide and the ink about 1.5 times taller than wide. Earlier text here said rows were about 25 px; that was wrong. The opening mixes layers at different scales (F17): in Carl Newton's opening gif the far layer has ink about 6 by 8 px, rows about 10 px and columns about 20 px apart, so its columns are spread wider than the foreground's. The operator screens use smaller glyphs (row pitch about 25 px at 1915 in the finale shot, ink about 10 px in the Blu-ray operator frame). Sources: [RZ-pass] line 40 and 299, [RZ-config], [STILL], [STILLS], [CN-GIF]. Confidence: high that 1999 glyphs are taller than wide (confirmed across 6 stills, two releases, three scenes); medium for the exact ratio. The earlier "near square" reading is withdrawn for 1999 and still holds for Rezmason's classic and Resurrections presets.

F8. Column count. Classic 80 columns across the long side, operator (1999) 108, Resurrections 70, Megacity 40. At 1920 px wide that is a 24 px cell (classic), 17.8 x 24 px (1999), 27.4 px (Resurrections). The 1999 film still measures about 78 columns. Sources: [RZ-config] `numColumns`, [STILL]. Confidence: high. Evidence: the 78-column foreground pitch is confirmed on the Blu-ray and 4K opening frames; other scenes use other scales (F7).

## 2. Brightness, colour and optics

F9. Rain is illumination of fixed glyphs, not moving glyphs. Every cell keeps its own glyph in place; a "drop" is a wave of brightness passing down a column. Sources: [RZ-readme] ("The 2D glyphs are in a fixed grid and don't move"), [CN] ("each one stays in place, and different glyphs appear beneath it"). Confidence: high.

F10. Trail brightness shape (classic). Per column, brightness is a sawtooth: `b = 1 - fract(rainTime)`, linear from 1 at the leading cell to 0 at the far end of a tooth, then the next drop starts. It is then remapped `base = b * baseContrast + baseBrightness = 1.1 b - 0.5`, so cells with b below 0.4545 are black. One tooth spans `raindropLength / 0.01 = 75` rows on average, so a drop is lit for about 41 rows and the gap to the next drop in the same column is about 34 rows. The linear ramp then goes through the colour palette (F13) and bloom, which makes the visible fade read as roughly exponential. Resurrections: `1.17 b - 0.7`, lit for b above 0.598, about 30 of 75 rows. 1999 operator: `raindropLength 1.5`, so 150-row teeth, about 82 lit rows, and `brightnessOverride 0.22` makes every lit non-leading cell the same flat brightness ("flatter, crowded, without a gradient"). Sources: [RZ-raindrop] `getRainBrightness`, [RZ-rain] `getBrightness`, [RZ-config], [RZ-readme]. Confidence: high for intent, medium for exact lengths.

F11. Several drops share a column and never collide. Because the column is one continuous sawtooth, drops follow each other at a fixed spacing and cannot overtake. Sources: [RZ-readme] ("Multiple raindrops often occupy a column at the same time... but they can never collide"). Confidence: high.

F12. The leading glyph ("cursor"). The leader is the cell where the sawtooth wraps (`brightness > brightnessBelow`), drawn in its own colour at boosted intensity and clamped: classic `hsl(0.242, 1, 0.73)` = #C1FF75 times 2, displayed about #FFFFEB (white with a faint yellow-green cast); 1999 `hsl(0.375, 1, 0.66)` = #52FF7D times 3, displayed about #F5FFFF; Resurrections `hsl(0.292, 1, 0.8)` = #B2FF99 times 2, displayed white. In the 1999 film itself the leaders measure #DCDFE7 (mean of all pixels with every channel above 180), a white with a slight blue or lavender cast, and Carl Newton finds that only about 1 in 5 strings has a highlighted leader at all; only the leading glyph is ever highlighted. Sources: [RZ-config] `cursorColor`, `cursorIntensity`, [RZ-palette], [STILL], [CN]. Confidence: high that leaders are near-white; medium on the tint; medium on the 1 in 5 ratio (one sequence analysed). Evidence: near-white leaders are confirmed across 9 stills and two gifs. Near-white pixels make up 1.5 to 1.6 percent of lit pixels in the opening on both releases (1.6 percent in the Blu-ray digit trace, 0.06 percent in the 4K one). The leader tint is confirmed slightly cool: #DCDFE7 (opening, Blu-ray), #E6F2F8 (opening, 4K), #D7F2ED and #D9F1F0 (system failure, both releases), with the in-world monitors greener (#BBE8D2 to #D1F9E0). The frequency rests on one sequence in two views: in [CN-GIF] 07 (highlight) 21.5 percent of lit columns carry a near-white cell at any time, in 01 (the opening as shown) 7 percent; the stills cannot count strings.

F13. Colour ramp: brightness is tone-mapped to a palette after bloom. Rezmason sums scene plus bloom into one brightness value, subtracts dither, then looks the colour up in a 1D palette, so dim cells are dark green and overlapping bright areas move toward pale green. Classic palette (HSL, hue 0.3 = 108 degrees): 0.0 #000000, 0.2 #176105, 0.7 #89F76E, 0.8 and above #B0FA9E. 1999 operator (hue 144 degrees, saturation 0.8): 0.0 #000000, 0.5 #19E66B, 1.0 #FFFFFF; with the 0.22 override the trail sits at about #0B652F. Resurrections (hue 135 degrees): 0.0 #000000, 0.92 #33FF66, 1.0 #FFFFFF, a long saturated green ramp that only whitens at the very top. Sources: [RZ-config] `palette`, [RZ-palette]. Confidence: high for structure, medium for hue.

F14. The 1999 film's green, measured. On the Blu-ray still, lit pixels have hue 152 to 154 degrees (blue-green, not yellow-green) at every brightness, saturation 0.55 to 0.8: by max-channel bucket, 40 to 80 #0F3625, 80 to 120 #125F3C, 120 to 160 #1B8857, 160 to 200 #27B174, 200 to 230 #3DD693, 230 and up #53EEAB. The red channel never reaches zero in lit glyphs (about 15 to 35 percent of green), so the green is not a pure primary. The black floor is not neutral: median (3, 14, 7), #030E07. Home video releases differ (the 2008 era Blu-ray and Netflix masters are much greener than the theatrical and the Bill Pope supervised 4K regrade), so treat the hue as a range of about 108 to 155 degrees, with film prints at the teal end and Rezmason's sequel palette at the yellow end. Sources: [STILL], ResetEra thread on the UHD regrade https://www.resetera.com/threads/the-matrix-no-longer-looks-like-puke-green-in-its-uhd-release.43451/, Rezmason README credit to Alexi Garcia's release comparison https://bit.ly/MatrixVersions. Confidence: medium (one frame, one release). Evidence: the hue is now confirmed across 8 stills and both releases. Title-sequence rain (opening, digit trace, system failure) has a lit-pixel hue median of 153 to 155 degrees on both the Blu-ray and the 4K regrade; the bucket colours of the Blu-ray opening repeat to within 2 hex units on the Blu-ray digit trace. The 4K regrade keeps the hue but is more saturated (median 0.94 to 1.0 against 0.73 to 0.82) with less red (R/G about 0.08 against 0.2 to 0.35), and its black floor is darker (#000904 against #010203 to #030E07). Neo seeing the code in the corridor is greener (hue 124 Blu-ray, 134 4K), and the in-world operator monitors are cyan-shifted (hue 160 to 166, and up to 198 on the defocused Cypher monitors). The ramp shape (share of lit pixels per bucket, falling from about 40 percent in the darkest bucket to about 6 percent in the brightest) repeats on the Blu-ray and 4K openings.

F15. Bloom. Rezmason: high-pass threshold 0.1 (classic; 0 for 1999 and Resurrections), five-level pyramid starting at `bloomSize` 0.4 of screen resolution (0.6 for 1999) and halving each level, separable 3-tap blur per level (centre 0.442, neighbours 0.279), levels summed with weights 0.96549, 0.92832, 0.88790, 0.84343, 0.79370, times `bloomStrength` 0.7 (0.75 for 1999). Bloom is added before the palette lookup (F13), so the glow is green and its overlap whitens. The film still shows a soft halo about one glyph wide around bright glyphs and stronger halation around leaders. Sources: [RZ-bloom], [RZ-config], [STILL]. Confidence: high for Rezmason values, medium for the film match. Evidence: confirmed across 7 stills. Measured as the mean brightness in rings outside the ink, relative to the ink edge, at 1915 px width: around bright glyphs the light falls to 50 percent within 1.5 to 3 px and to 10 percent within 4.5 to 14 px, then leaves a low tail of 5 to 10 percent that reaches about one cell width (25 px) on the Blu-ray opening. Around leaders the halo is about twice as wide: 50 percent at 2.5 to 8 px, 10 percent at 10 to 38 px. So the film has a tight core glow plus a faint, wide halation skirt, not one medium blur. Glyph edges are soft: the 10 to 90 percent edge rise is 2.1 to 2.9 px at 1915 width on the title rain.

F16. Grain, not scanlines. Rezmason subtracts per-pixel, per-frame noise of magnitude `ditherMagnitude / 3 = 0.0167` before the palette lookup. The 1999 still shows heavy film grain on every glyph and soft defocus on some columns. Neither the films nor Rezmason have scanlines, interlace or a CRT vignette: the rain is a 35 mm film-out and the scanline look belongs to other screensavers. A mild lens falloff toward the frame edges is visible in some shots. Sources: [RZ-palette], [STILL]. Confidence: high that scanlines are not in the film; medium on vignette strength (not measurable from one frame). Evidence: no scanlines in the title rain is confirmed across 6 stills; the in-world screens are different. The 4K operator close-up shows horizontal raster lines inside the glyphs, a cyan tint and strong blur, so raster lines belong only to the monitors inside the story, never to the title rain. Grain is measured as the residual standard deviation after a box blur (5 px inside the ink, 7 px in the background): inside lit glyph ink it is 8 percent of the green level on the Blu-ray (16 to 17 units of 255 on the opening and digit trace) and 3 to 4 percent on the 4K regrade, which is visibly denoised; in the black background it is 0.6 to 1.1 units (Blu-ray) and 0.1 to 0.4 (4K). Grain is multiplicative: it sits on the ink, the background stays almost clean.

F17. Depth and layers. The 1999 opening superimposes columns that are not on one grid: some columns overlap neighbours, some are softer or dimmer, giving a double exposure look. Rezmason keeps 2D rain on a single flat grid ("depth effects... can obscure the details") and offers a separate `volumetric` mode: each column becomes a quad at a random depth that moves toward the camera at `forwardSpeed` (0.25 default, 0.2 Trinity, 0.1 Morpheus, 0.4 Bugs) with wrap-around, 90 degree field of view perspective, brightness times depth so far columns are dim, a random vertical offset per column, and `density` 0.75 columns per grid column. Sources: [STILL], [RZ-readme], [RZ-vert], [RZ-pass] line 287, [RZ-config]. Confidence: medium (layering in the film is visible but not quantified).

F18. Stripe and colour variants. Rezmason's stripe pass multiplies brightness by a horizontal colour stripe texture (pride and custom stripe effects); this is not in any film. Nightmare, Paradise, Palimpsest, Twilight, Megacity and the Trinity, Morpheus and Bugs presets are fan or game variants, not film looks. Sources: [RZ-config], https://github.com/Rezmason/matrix/blob/5ba90490453ceceb6812d6b1bc658a99a92411d0/js/regl/stripePass.js. Confidence: high.

## 3. Motion

F19. Fall speed. Rezmason: `rows per second = fallSpeed * columnSpeedOffset / 0.01`, with `columnSpeedOffset` uniform in 0.5 to 1.0 per column. Classic and Resurrections (`fallSpeed 0.3`): 15 to 30 rows per second, crossing a 1080p screen (45 square rows at 80 columns) in 1.5 to 3 s. 1999 operator (`fallSpeed 0.6`): 30 to 60 rows per second. Carl Newton's frame table of the 1999 opening shows a new string growing by about one row per film frame (lengths 1, 2, 2, 3 over frames 0 to 3), so roughly 16 to 24 rows per second at 24 fps. Sources: [RZ-raindrop], [RZ-config], [CN]. Confidence: medium; the two sources agree on the order of 20 rows per second. Evidence: rests on one sequence. Tracking string heads frame to frame in [CN-GIF] 01 gives 1 row per frame in 72 percent of steps, a stall in 18 percent and 2 rows or more in 9 percent, a mean of about 0.95 rows per frame (the script's autocorrelation pitch on this gif, 19 px, is two rows; the ruler shows rows about 10 px apart, and the numbers here are in true rows), which is about 22 rows per second at 24 fps.

F20. Speed wobble within a column. Rezmason does not move drops at a constant speed: `rainTime = wobble(rainTime)` with `wobble(x) = x + 0.3 sin(sqrt(2) x) + 0.2 sin(sqrt(5) x)`. Its derivative swings between about 0.13 and 1.87, so each column surges and stalls, and the tooth length varies along the column ("modulating the width of the teeth"). In the 1999 film Carl Newton sees a periodic "stammer": all highlighted strings pause together and fall one row behind the others. Sources: [RZ-raindrop], [RZ-readme], [CN]. Confidence: high that speed is not constant; medium on the shape.

F21. Discrete steps. The film advances illumination one whole cell at a time; there is no sub-row motion or smooth head interpolation. Rezmason computes brightness per cell, so the leader also jumps cell to cell. The film itself runs at 24 fps. Sources: [CN], [RZ-raindrop], [RZ-rain]. Confidence: high. Evidence: rests on one sequence, now measured: in [CN-GIF] 01 heads move by whole rows, mostly one per frame, with occasional stalls (F19).

F22. Glyph change (mutation). 1999 film: changing glyphs hold for 3 frames, then change, with one crossfade frame where old and new glyph each show at 50 percent; at 24 fps that is a change every 125 ms (8 per second). All changing glyphs switch on the same frame, and some strings change entirely while others hold still. Rezmason classic and Resurrections: per-cell age advances `cycleSpeed 0.03` per frame at 60 fps, so each cell picks a new random glyph every 33 frames (0.56 s, about 1.8 changes per second), with a random starting phase per cell. 1999 operator: `cycleSpeed 0.01` with `cycleFrameSkip 8`, a change every 100 frames (1.67 s) with updates only every 8th frame (7.5 Hz). The Reloaded and Revolutions titles step through the fixed sequence in F3 rather than random picks. Sources: [CN], [RZ-symbol], [RZ-config], [RZ-readme]. Confidence: high for the 1999 frame counts (direct frame study), medium for the Rezmason rates (tuned by eye). Evidence: rests on one sequence, measured two ways. In [CN-GIF] 05 (changing) the share of ink pixels that change between frames spikes on a 3-frame period (autocorrelation peak at lag 3, 0.51). In the opening as shown ([CN-GIF] 01) about 9 percent of lit ink pixels change from one frame to the next, including the motion of the heads; the period there is less clean (peak at lag 2, 0.27).

F23. How trails start, end and reset. Strings do not always start at the top; some begin part way down, as if preceded by invisible cells. Trails are not erased by a separate fade; in the 1999 film they disappear when an invisible "deletion" string passes over them. In Rezmason the next sawtooth tooth follows, so the tail end of each drop is where brightness falls below the threshold, and a column is never reset: it is one endless phase offset by a random `columnTimeOffset` (0 to 1000 s). `brightnessDecay 1.0` means cells change instantly; lower values (0.75 Nightmare, 0.05 Paradise) blend with the previous frame for a slow wink. Sources: [CN], [RZ-raindrop]. Confidence: medium.

F24. Ripples and effects. The 1999 operator preset adds an occasional square ripple (`rippleTypeName "box"`, scale 30, speed 0.2, thickness 0.2, adds 0.75 brightness inside the ring). The effects shader calls these "non-canon"; Rezmason links them to the operator screens. Thunder flashes belong to Nightmare only. Sources: https://github.com/Rezmason/matrix/blob/5ba90490453ceceb6812d6b1bc658a99a92411d0/shaders/glsl/rainPass.effect.frag.glsl, [RZ-config]. Confidence: low as a film feature.

## 4. Resurrections

F25. The 2021 look in one paragraph. New 135-glyph set (the classic 57 plus many new katakana-like and geometric shapes), recovered from trailers, a Hamilton watch ad and BUF's VFX breakdown. 70 columns, square cells, `glyphEdgeCrop 0.1`. Brightness `1.17 b - 0.7` (shorter, punchier drops, about 30 lit rows), same 15 to 30 rows per second fall and 0.56 s glyph change as classic. Colour hue 135 degrees: black to #33FF66 at 0.92, then quickly to white, so drops are saturated pure green with whitened leaders (#B2FF99 times 2) and a hot top end. Bloom 0.7 with no high-pass threshold, so even dim glyphs glow. The glyphs carry bevel highlights ("glint", a second MSDF atlas) that Rezmason uses in its Trinity, Morpheus and Bugs variants with metal and pixel-grid textures; the TODO notes that "even completely dark glyphs can have glint on their edges". In the film the rain is frequently shown in depth, which the volumetric mode approximates. The digital rain was handled by BUF Paris (72 shots) and was off limits to the screen-graphics vendor. Sources: [RZ-config] `resurrections`, [RZ-readme], https://github.com/Rezmason/matrix/blob/5ba90490453ceceb6812d6b1bc658a99a92411d0/TODO.txt, https://buf.com/films/the-matrix-resurrections, Creative Review search summary https://www.creativereview.co.uk/the-matrix-resurrections-on-screen-graphics/. Confidence: medium (no frame of the 2021 film was measured; values are Rezmason's).

## Measurements across stills

All values from `tools/dev/measure_reference.py` (run it with `.venv\Scripts\python.exe -I tools/dev/measure_reference.py`). Lit means max channel above 40. Hue and saturation are medians over lit pixels. Near-white is every channel above 180, as a share of lit pixels. Row pitch, halo distances and edge width are in px at 1915 frame width. Halo is the distance at which ring brightness outside bright glyph ink falls to 50 and 10 percent. Grain is the green residual standard deviation inside lit ink, relative to the ink level. A dash means not measurable in that frame (too few pixels, or a defocused or cropped screen).

| Still | Release | Background | Lit fraction | Hue (IQR) | Sat | Near-white | Leader colour | Row pitch | Halo 50 / 10 | Edge | Grain |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Opening (`opening-bluray`) | Blu-ray | #010203 | 0.26 | 153 (147-159) | 0.82 | 1.6 % | #DCDFE7 | 36.5 | 3 / 13 | 2.9 | 0.081 |
| Opening (`opening-4k`) | 4K | #000904 | 0.32 | 153 (149-156) | 0.98 | 1.5 % | #E6F2F8 | 42.6 | 2.5 / 8 | 2.3 | 0.043 |
| Opening digit trace (`opening-trace-bluray`) | Blu-ray | #0D1014 | 0.33 | 155 (152-160) | 0.73 | 1.6 % | #D1F9E0 | 34.7 | 3 / 7 | 2.6 | 0.083 |
| Opening digit trace (`opening-trace-4k`) | 4K | #040B0B | 0.18 | 155 (152-158) | 1.00 | 0.06 % | #C7FCE4 | 38.5 | 1.5 / 4.5 | 2.1 | 0.040 |
| "506" digit close-up (`digit-closeup-4k`) | 4K | #000303 | 0.38 | 159 (102-175) | 0.63 | 13 % | #E5FFDF | - | - | 3.9 | 0.027 |
| Neo's monitor (`neo-monitor-bluray`) | Blu-ray | #080C01 | 0.02 | 98 (90-146) | 0.42 | 1.5 % | #BBE8D2 | - | 2 / 5 | 2.6 | 0.075 |
| Cypher's monitors (`cypher-monitors-4k`) | 4K | #000706 | 0.15 | 156 (154-157) | 1.00 | 0 | - | - | - | 11.6 | 0.009 |
| Operator screens (`operator-screens-bluray`) | Blu-ray | #080C10 | 0.30 | 160 (156-168) | 0.86 | 0.4 % | #C8DEEA | about 10 | 2 / 7 | 1.9 | 0.149 |
| Operator close-up (`operator-closeup-4k`) | 4K | #000A09 | 0.15 | 147 (144-150) | 0.99 | 0 | - | - | 1.5 / 5.5 | 1.9 | 0.080 |
| Operator screens, finale (`operator-screens-end-4k`) | 4K | #000B0E | 0.06 | 162 (156-168) | 0.98 | 0 | - | 24.6 | - | - | - |
| System failure (`system-failure-bluray`) | Blu-ray | #0B0E0F | 0.24 | 162 (158-168) | 0.77 | 10 % | #D7F2ED | - | 2 / 5 | 2.9 | 0.056 |
| System failure (`system-failure-4k`) | 4K | #040706 | 0.19 | 155 (151-160) | 0.94 | 5.4 % | #D9F1F0 | - | 1.5 / 4.5 | 2.5 | 0.030 |
| Neo sees the code (`neo-sees-code-bluray`) | Blu-ray | #021105 | 0.54 | 124 (119-135) | 0.91 | 0.3 % | #DBF6F3 | 34.1 | 2 / 14 | 2.6 | 0.118 |
| Neo sees the code (`neo-sees-code-4k`) | 4K | #000D00 | 0.32 | 134 (125-141) | 1.00 | 0.15 % | #C1FFEC | 33.6 | 1 / 5.5 | 1.5 | 0.088 |

File names are short forms of `assets/reference/matrix-1999-<name>.jpg`. The close-ups, system failure frames and Neo's monitor hold too few glyph rows for a reliable row pitch. The near-white share on the digit close-up and system failure frames is the white digits and readout text, not leaders.

Motion, from [CN-GIF]:

| Gif | Frames | Measure | Value |
|---|---|---|---|
| 01 opening | 42 at 40 ms | Head advance per frame | 1 row 72 %, stall 18 %, 2 or more rows 9 %; mean about 0.95 rows, about 22 rows/s at 24 fps |
| 01 opening | | Ink pixels changed per frame | mean 0.09 (autocorrelation peak at lag 2, 0.27) |
| 01 opening | | Lit columns holding a near-white cell | 7 % |
| 05 changing | 22 at 500 ms | Ink change period | 3 frames (autocorrelation 0.51 at lag 3); mean change share 0.08 |
| 07 highlight | 10 at 500 ms | Lit columns holding a near-white cell | 21.5 % |
| 08 stammer | 5 at 1000 ms | | too few frames to measure |

End credits were not collected: no still or clip of the 1999 end credits rain could be found from a source that allows direct download (the 4K gallery ends at frame 13403, before the credits). Their numbers stay open.

### Evidence status

Confirmed across several stills: F7 (taller-than-wide glyphs, 6 stills), F8 (78-column foreground pitch, 2 stills), F12 (near-white, cool leader colour, 9 stills), F14 (hue 153 to 155 degrees in title rain, 8 stills, both releases), F15 (tight glow plus wide halation, 7 stills), F16 (no scanlines in the title rain, grain on the ink, 6 stills). Still resting on one sequence: F12 leader frequency, F19 fall speed, F20 stammer, F21 whole-row steps, F22 three-frame glyph change (all from Carl Newton's study of the opening), and F17 layering. Resting on Rezmason only: F10, F11, F13 structure, F23, F24, F25.

## Targets for the film_1999 preset

Concrete numbers a `film_1999` preset should hit, measured at 1915 px width unless stated. Cell width means one column pitch (about 25 px at 1915, so 1/77 of the screen width).

1. Tone ramp. Map brightness to these colours (by max channel): 40 to 80 #103725, 80 to 120 #13603C, 120 to 160 #1B8858, 160 to 200 #27B274, 200 to 230 #3ED694, 230 and up #53EEAB. Hue 153 degrees (range 152 to 155) at every level, saturation 0.7 to 0.8, red at 20 to 35 percent of green. A 4K-grade option uses the same hue at saturation about 0.92 with red at about 8 percent of green (#04361E, #086137, #0B8B50, #0CB66C, #11D581, #4AF1AE).
2. Tone distribution. Of lit pixels, about 40 percent in the darkest bucket, 15 percent in the next, then 11 to 18 percent each in the middle three and 6 percent in the brightest.
3. Background. Not pure black: #010203 to #030E07 (Blu-ray), #000904 (4K).
4. Lit fraction. 0.25 to 0.32 of the frame lit (max channel above 40) in the full-screen title rain.
5. Leaders. Colour #DCDFE7 (Blu-ray) to #E6F2F8 (4K), a cool near-white, never green-tinted white. About 1 in 5 drops (target 20 percent, acceptable 7 to 22 percent of lit columns at any moment) carries a leader; the others end in a plain green cell. Near-white pixels should be about 1.5 percent of lit pixels.
6. Bloom. A tight core: brightness outside a bright glyph falls to 50 percent within 2 to 3 px (0.1 cell width) and to 10 percent within 8 to 13 px (0.3 to 0.5 cell width).
7. Halation. A faint wide skirt under the core: 5 to 10 percent of the ink level reaching about one cell width (25 px). Around leaders the glow is about twice as wide: 50 percent at 5 to 8 px, 10 percent at 10 to 38 px.
8. Edge softness. The 10 to 90 percent edge rise of glyph ink is 2 to 3 px at 1915 width; glyphs should never look pixel-sharp.
9. Grain. Multiplicative noise on the ink with a standard deviation of 8 percent of the ink level (Blu-ray look) or 4 percent (4K look), refreshed every frame; the black background carries at most about 1 unit of 255. No scanlines, no interlace.
10. Glyph cell. Column pitch 1/77 of the screen width; glyph ink about 1.5 times taller than wide; row pitch 1.4 to 1.7 times the column pitch for the foreground layer.
11. Glyph change rate. Changing glyphs switch on a fixed 3-frame period at 24 fps (8 changes per second), all together, with one 50 percent crossfade frame. About 9 percent of lit ink changes per film frame in the opening, counting motion.
12. Speed and stepping. Heads advance one whole row per 24 fps frame, about 22 rows per second, with stalls in about 1 frame in 5 and occasional 2-row jumps; no sub-row motion.

## Gap analysis

What the repository does today (main at `3510ece`) against each finding. "Size" is how visible the difference is on screen: large, medium or small.

| # | Film or reference | This repo today | Size |
|---|---|---|---|
| F3, F5 | 57 custom blocky glyphs: 33 selected katakana, digits without 6, z, blank, ¦ : " ꞊ ╌ ▪ — < > \| + * | `digital_rain/glyphs.py` `GLYPHS`: all 56 half-width katakana U+FF66 to U+FF9D (includes small ｧｨｩｪｫｬｭｮｯ and ｰ), digits 0 to 9, `:.="*+-<>\|`, drawn with MS Gothic (synthetic bold) and Courier New Bold | Large |
| F4 | Selective mirroring: katakana and 2 5 9 mirrored, 3 6 flipped vertically, 0 1 4 7 8 untouched | `render_mirrored` flips every glyph horizontally, including all digits and symbols | Medium |
| F6 | Film glyph TTF and MSDF atlases available in `assets/` | Fonts come from `C:\Windows\Fonts`; a `font_path` or `fonts/` override exists but nothing ships | Large (easy fix) |
| F7, F8 | About 78 columns across the long side (25 px at 1920); 1999 glyphs about 1.5 times taller than wide, row pitch 1.4 to 1.7 times the column pitch | `CELL_W, CELL_H = 20, 28` (1.4 tall), so about 96 columns on the main layer at 1920 px; glyph rendered at `FONT_SIZE 26` in a 20 px wide cell | Medium (measured on 6 stills, see "Glyph size and clarity (evidence)" below) |
| F9 | Glyphs fixed, illumination moves | Same: glyphs fixed per cell, a brightness window moves | None |
| F10 | Linear sawtooth remapped `1.1 b - 0.5`, about 41 lit rows of a 75-row period, then palette and bloom; 1999 flat brightness | `br = pow(1 - dist/len, 1.6)`, length 10 to 38 rows, gap `rows * 0.6 / density`; no flat 1999 mode | Medium |
| F11 | Several drops per column, evenly following, never colliding | One drop per period per column (period = rows + max length + gap), so at most about one drop per column on screen | Medium |
| F12 | Leader near-white (#FFFFEB Rezmason, #DCDFE7 measured, slightly blue); only about 1 in 5 strings highlighted in 1999 | Every drop has a leader, colour #CDFFDC (`COLORS["film"]` head) blended over one row by `headness`; leader glyph re-randomised at 12 Hz | Medium |
| F13 | Brightness (scene plus bloom) tone-mapped through a black, dark green, bright green, pale green palette | Single colour times brightness (`mix(u_base * br, u_head, headness)`); bloom added after colouring, so dim cells stay fully saturated and overlaps do not whiten | Large |
| F14 | 1999 green hue about 153 degrees (#27B174 mid, #53EEAB bright) with red above zero and a green black floor #030E07; Rezmason 108 to 144 degrees | `film` trail #00FF46, hue 136 degrees, pure saturated primary with red 0; black background 0,0,0 | Large |
| F15 | Five-level bloom from 0.4 resolution, weights 0.97 to 0.79, strength 0.7, high-pass 0.1, before palette | Two levels (1/4 and 1/16), gains `bloom * 0.55` and `bloom * 0.9` with default 0.5 (0.275 and 0.45), no high-pass, after colouring | Small to medium |
| F16 | Film grain, no scanlines, no interlace | Scanlines 0.45 with interlace on by default, global flicker 0.03, vignette 0.35; no grain or dither | Large |
| F17 | Overlapping, partly defocused columns in 1999; volumetric depth mode in Rezmason and Resurrections | Three parallax grids (`LAYERS`: scale 0.65 dim 0.4, scale 1.0, scale 1.8 soft 0.55 density 0.12), all 2D, no perspective motion. Resurrections with depth on (GPU): six depth slices (`depth_slices`, cells 0.71 to 4.0 times the main one, screen blend, per-lane depth jitter); still a size spread, no perspective geometry | Small (already approximates the 1999 layering) |
| F18 | Stripe and fan variants are not film | Colour presets classic, amber, red, blue, white; fine as options | None |
| F19 | 15 to 30 rows per second (classic), about 20 at 24 fps (1999) | `SPEED_ROWS_PER_SEC = (9, 28)` times layer speed 0.9 to 1.0 | Small |
| F20 | Speed wobbles within a column (derivative 0.13 to 1.87); 1999 stammer | Constant speed per column for its lifetime | Medium |
| F21 | Whole-cell steps at 24 fps | Continuous position; the leader cross-fades over one row (`headness = clamp(1 - dist)`), so the head slides smoothly | Small to medium |
| F22 | 1999: change every 3 frames (8 Hz) with a 50 percent crossfade frame, synchronous; Rezmason 0.56 s per cell random | Trail cells change every about 2.9 s (`u_time * 0.35`), random phase; leader flickers at 12 Hz; no crossfade | Medium |
| F23 | Strings may start mid-screen; erased by deletion strings; columns never reset | Drop starts at a random `shift` within the gap, which can be mid-screen; trail fades to nothing at its length; column phase recycles every period with new random length | Small |
| F24 | Box ripple only in 1999 operator screens, non-canon | None | None (optional) |
| F25 | Resurrections: 135 glyphs, 70 columns, #33FF66 ramp to white, glint bevels, depth | Resurrections preset; depth on draws six depth slices on the GPU, three layers in software | Done |

### Five biggest gaps

1. Glyphs. Stock MS Gothic and Courier, globally mirrored, with the full half-width katakana range and a 6, against the film's 57 custom blocky glyphs with selective mirroring. `assets/rezmason/Matrix-Code.ttf` fixes this through the existing atlas code.
2. Colour model. One saturated #00FF46 multiplied by brightness, against a brightness-to-palette tone map applied after bloom with a blue-green hue (about 153 degrees in the 1999 film, #27B174 to #53EEAB), red above zero and a green-tinted black.
3. Screen treatment. Scanlines, interlace and global flicker are on by default but are not in any film; the film has grain and halation instead.
4. Drop rhythm. One drop per column period at constant speed, against several drops per column on an endless sawtooth with wobbling speed and about 41 lit rows out of 75.
5. Leaders and glyph change. Every drop has a smoothly sliding leader that flickers at 12 Hz, and trail glyphs change every 2.9 s; the film steps whole cells, highlights only some strings with a near-white slightly blue leader, and changes glyphs much faster (8 Hz with a crossfade frame in 1999, about 0.56 s per cell in the sequels).


## Glyph size and clarity (evidence)

The question for this section: are the `film_1999` glyphs too small and too many, and are the strokes too filled in, across several independent stills and not one. All 14 `assets/reference/matrix-1999-*.jpg` stills were measured with `tools/dev/measure_reference.py --table` (one row per still) and `tools/dev/measure_reference.py <file>` (full block with a "geometry" line). Run: `.venv\Scripts\python.exe -I tools/dev/measure_reference.py --table matrix-1999-opening-bluray.jpg ...` (no names: every still of the 1999, 2003 and 2021 sets).

Definitions (px at 1915 frame width unless a percent). Row pitch: vertical autocorrelation inside ink columns, the estimate of F7 (checked there against a pixel ruler). Column pitch: the first autocorrelation peak above 0.1 of the column ink profile after removing blobs wider than a column (`col_pitch`); the strength in brackets is that peak (below 0.25 the pitch is a weak estimate, and sparse shots can return a multiple of the true pitch). Ink columns: peaks of the column ink profile at least 12 px apart (`ink_columns`; unlike the older "ink columns" count it does not depend on the row pitch estimate, so adjacent columns are not merged). Ink spacing: the older count's mean spacing (a multiple of the grid pitch when columns are skipped, F7). Cell width and height as a percent of the whole frame. Stroke FWHM: median width of the horizontal runs above half of the local maximum, runs up to 14 px (`stroke_width`). Fill: share of pixels, among those whose local maximum exceeds 120, that are above half of it (0.25 open strokes, near 1 for blobs). Edge rise: the 10 to 90 percent estimate that `still()` prints. The same functions measure the saver frames (check_film uses them), so the comparison is like for like.

Stills used for the targets are the six that show the title rain or the Neo code field at full-frame scale (opening, opening trace, Neo sees the code, Blu-ray and 4K). The other eight are in-world monitors, close-ups or readout text and are listed with their reason; they are not averaged.

| Still | Used for targets | Lit | Row pitch | Column pitch (strength) | Ink columns per 1915 | Ink spacing | Cell width % of frame | Cell height % of frame | Stroke FWHM | Fill | Edge rise |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1999-cypher-monitors-4k | no: in-world monitor, blurred, strokes not resolved | 0.153 | 58.2 | 60.0 (0.30) | 29 | 65.3 | 3.13 | 7.29 | nan | nan | 11.6 |
| 1999-digit-closeup-4k | no: zoomed on a few digits, rows not resolved (the pitch is glyph-internal) | 0.378 | 8.8 | 16.2 (0.75) | 72 | 16.5 | 0.85 | 1.11 | 6.5 | 0.70 | 3.9 |
| 1999-neo-monitor-bluray | no: in-world monitor, lit 0.018 (a handful of glyph rows) | 0.018 | 49.4 | nan (0.00) | 20 | 53.5 | nan | 6.19 | 8.0 | 0.55 | 2.6 |
| 1999-neo-sees-code-4k | yes | 0.322 | 33.6 | 16.2 (0.14) | 47 | 36.4 | 0.85 | 4.21 | 2.5 | 0.29 | 1.5 |
| 1999-neo-sees-code-bluray | yes | 0.541 | 34.1 | 24.6 (0.11) | 57 | 40.5 | 1.28 | 4.26 | 3.0 | 0.40 | 2.6 |
| 1999-opening-4k | yes | 0.318 | 42.6 | 15.0 (0.17) | 66 | 53.4 | 0.78 | 5.34 | 7.5 | 0.37 | 2.3 |
| 1999-opening-bluray | yes | 0.263 | 36.5 | 25.5 (0.31) | 45 | 30.5 | 1.33 | 4.57 | 7.0 | 0.39 | 2.9 |
| 1999-opening-trace-4k | yes | 0.177 | 38.5 | 39.5 (0.72) | 38 | 39.4 | 2.06 | 4.83 | 5.0 | 0.25 | 2.1 |
| 1999-opening-trace-bluray | yes | 0.325 | 34.7 | 35.7 (0.92) | 53 | 36.0 | 1.86 | 4.35 | 6.0 | 0.29 | 2.6 |
| 1999-operator-closeup-4k | no: in-world monitor with raster lines and heavy blur (F16) | 0.154 | 49.1 | 34.5 (0.48) | 36 | 37.2 | 1.80 | 6.15 | 1.0 | 0.40 | 1.9 |
| 1999-operator-screens-bluray | no: in-world operator screens, small separate layer scale | 0.295 | 10.0 | 17.8 (0.14) | 88 | 10.0 | 0.93 | 1.25 | 3.0 | 0.33 | 1.9 |
| 1999-operator-screens-end-4k | no: in-world finale screens, small glyphs, lit 0.06 | 0.063 | 24.6 | 23.1 (0.24) | 76 | 24.9 | 1.21 | 3.09 | nan | nan | - |
| 1999-system-failure-4k | no: readout text, not rain | 0.186 | 56.8 | 31.8 (0.32) | 40 | 114.7 | 1.66 | 7.12 | 10.0 | 0.41 | 2.5 |
| 1999-system-failure-bluray | no: readout text, not rain | 0.236 | 49.1 | 28.7 (0.35) | 36 | 105.0 | 1.50 | 6.14 | 10.0 | 0.42 | 2.9 |

Spread over the 6 rain stills:

- row_pitch: n 6, median 35.60, min 33.60, max 42.60
- col_pitch: n 6, median 25.05, min 15.00, max 39.50
- ink_cols: n 6, median 50.00, min 38.00, max 66.00
- cell_w_pct: n 6, median 1.31, min 0.78, max 2.06
- cell_h_pct: n 6, median 4.46, min 4.21, max 5.34
- stroke: n 6, median 5.50, min 2.50, max 7.50
- fill: n 6, median 0.33, min 0.25, max 0.40
- edge: n 6, median 2.45, min 1.50, max 2.90
- lit: n 6, median 0.32, min 0.18, max 0.54

The saver on the base SHA (`film_1999`, gated configuration, 1920x1080, upscaling quality, `check_film` frames, mean of t = 6, 9, 12, 15 s): cell 19.5 x 28.5 display px (20 x 28 with upscaling off), 98 columns (96), 37 rows, row pitch 28.5, ink columns 66, fill 0.39, edge 2.69, lit 0.242.

Findings (each with the number of stills that carry it):

T1-F1. The cell is too small. Row pitch is 33.6 to 42.6 px (median 35.6) in all 6 rain stills against 28 in the saver: every still is larger, by 1.20 to 1.52 times (median 1.27). Cell height is 4.21 to 5.34 percent of the frame height (median 4.46) against 2.6 percent (28 of 1080). Confirmed across 6 stills, both releases, three scenes. A cell scale of about 1.3 gives 36 px rows, the median.

T1-F2. There are too many columns. The grid pitch is 25.5 px (opening, Blu-ray, strength 0.31) and 24.6 px (Neo sees the code, Blu-ray, strength 0.11), that is 75 to 78 columns; the 4K opening and trace stills return 15 to 39 px with strengths of 0.17 and 0.72, because each is a different layer scale (F17). So the column pitch rests on 2 stills, one of them weak (F8's 78 columns was read the same way). The count of ink columns is more reliable: 38 to 66 across 6 stills (median 50), against 66 in the saver at 98 grid columns. Confirmed across 6 stills that the saver is at or above the top of the range (5 of 6 below it, 1 equal). A cell scale of 1.3 gives 75 grid columns and 48 ink columns.

T1-F3. Stroke width and fill. Stroke FWHM is 7.0, 7.5, 6.0, 5.0 px in four stills and 3.0 and 2.5 px in the two Neo stills (dense, overlapping glyph trails, lit 0.32 and 0.54); median 5.5. Fill is 0.25 to 0.40 (median 0.33) in all 6. The saver at the base size is already inside both ranges (stroke 5.7, fill 0.39 at defocus 0.14; stroke 5.0, fill 0.35 at defocus 0). The "filled in" reading is therefore confirmed only for the enlarged cell: with `cell_scale` 1.3 and the old defocus 0.14 the fill is 0.45 (above all 6 stills, whose maximum is 0.40) and the edge rise 3.20 (above all 6, whose maximum is 2.9). Edge rise is 1.5 to 2.9 px (median 2.45) in the 6 rain stills (1.5 to 3.9 over 12 of the 14 stills; the blurred Cypher monitor reads 11.6 and one still gave no value); the earlier diagnosis (defocus 0 gives a 5 px stroke against the film's 5 to 8) is confirmed on 4 of 6 stills and is not contradicted by the two dense ones. Defocus below `1 / cell width in render px` has no effect on the GPU (the blur is `max(1.0, defocus * cell.x)`, digital_rain/gl_renderer.py line 262), so 0.04 and 0 give the same frame at 1920x1080 with upscaling quality (render cell 17 px, threshold 0.059).

T1-F4. Not measurable from stills: leader frequency, leader tint and the film's near-white share of about 1.5 percent (F12) against 0.5 percent in the saver. Out of scope for this section; listed as a follow-up.


## Clarity (evidence)

The question for this section: after the size work, is `film_1999` still unlike the film in glyph clarity (counters, ink shape, string tone), the leader and the palette. Measured with the clarity metric (`tools/checks/check_film.py` `t2_measure`) on the frame resampled to 1915 px wide. Per-still values were measured with that function; the 1999 stills carrying a gate are listed (the two neo-sees-code stills are another scene and are excluded from the tone windows).

| Still | Dark share in ink boxes | Ink box aspect h/w | Peaks under 150 | Peaks above 200 | Near-white % of lit | Leader core mean | Core b - r | Ring r/g / b/g | Band saturation | Background r, g, b |
|---|---|---|---|---|---|---|---|---|---|---|
| 1999-neo-sees-code-4k | 0.429 | 1.608 | 0.456 | 0.406 | 0.14 | 228.3 | 44 | 0.10 / 0.65 | 0.95 | 0, 12, 0 |
| 1999-neo-sees-code-bluray | 0.319 | 1.487 | 0.432 | 0.418 | 0.31 | 237.3 | 22 | 0.10 / 0.69 | 0.88 | 2, 17, 5 |
| 1999-opening-4k | 0.415 | 1.400 | 0.003 | 0.984 | 1.50 | 245.7 | 19 | 0.69 / 1.12 | 0.97 | 0, 2, 0 |
| 1999-opening-bluray | 0.296 | 1.405 | 0.048 | 0.920 | 1.63 | 227.3 | 10 | 0.56 / 0.96 | 0.83 | 1, 1, 2 |
| 1999-opening-trace-4k | 0.278 | 1.600 | 0.074 | 0.636 | 0.06 | 226.7 | 31 | 0.15 / 0.63 | 0.99 | 4, 6, 7 |
| 1999-opening-trace-bluray | 0.196 | 1.571 | 0.019 | 0.804 | 1.64 | 227.0 | 16 | 0.23 / 0.65 | 0.77 | 12, 13, 17 |
| 1999-operator-screens-bluray | 0.000 | 1.250 | 0.607 | 0.160 | 0.39 | 220.7 | 36 | 0.88 / 1.08 | 0.83 | 9, 11, 16 |
| saver after the clarity changes, 1920x1080 gated | 0.259 | 1.518 | 0.043 | 0.873 | 1.21 | 225.7 | 11.5 | 0.83 / 0.97 | 0.84 | 1, 6, 4 |
| saver after the clarity changes, 2880x1800 dpi 1.5 gated | 0.239 | 1.494 | 0.051 | 0.854 | 1.37 | 227.3 | 10.5 | 0.83 / 0.97 | 0.84 | 1, 6, 4 |
| saver after the size change, 1920x1080 gated | 0.110 | 1.098 | 0.177 | 0.747 | 0.54 | 212.5 | 10.0 | 0.18 / 0.63 | 0.66 | 3, 14, 7 |

The ring colour rests on the opening Blu-ray and 4K and the operator screens; trace Blu-ray contradicts it (a green ring), so the two ring gates are a judgement call. Near-white stays under the film's 1.5 percent because of the leader-columns cap (0.22, read from the gifs); the three leader stills have 0.231 to 0.251, so re-reading the cap is a follow-up. Column clustering and grain texture are not covered in this section.


## Follow-ups (evidence)

The questions for this section: do the leader cores show the glyph, is the leader-columns cap right for the film's frame shape, and do lit columns cluster as in the film. Metrics: `tools/checks/check_film.py` `t3_measure`, on the frame resampled to 1915 px wide.

| Still | Leaders | Leader openness | Box fill | lc239 | Near-white % of lit | Clustering index |
|---|---|---|---|---|---|---|
| 1999-opening-4k | 13 | 0.384 | 0.55 | 0.231 | 1.50 | 1.44 |
| 1999-opening-bluray | 11 | 0.438 | 0.52 | 0.251 | 1.63 | 1.73 |
| 1999-opening-trace-4k | 0 | | | 0.027 | 0.06 | 1.22 |
| 1999-opening-trace-bluray | 53 | 0.586 | 0.41 | 0.234 | 1.64 | |
| 1999-digit-closeup-4k | 100 | 0.535 | 0.36 | 0.521 | 13.4 | |
| 1999-system-failure-4k | 11 | 0.657 | 0.26 | 0.819 | 5.38 | 1.25 |
| 1999-system-failure-bluray | 82 | 0.791 | 0.24 | 0.710 | 10.5 | 1.29 |
| 1999-neo-sees-code-4k | 4 | 0.697 | 0.24 | 0.041 | 0.14 | |
| 1999-neo-sees-code-bluray | 7 | 0.669 | 0.32 | 0.093 | 0.31 | |
| carlnewton-03 and -04 (one rain) | | | | | | 1.30 |
| saver before the leader changes, 8-seed mean, 1920 / 2880 | | 0.110 / 0.077 | 0.74 | 0.141 / 0.145 | 1.14 / 1.25 | 1.14 / 1.17 |
| saver after the leader changes, 8-seed mean, 1920 / 2880 | | 0.370 / 0.368 | 0.56 | 0.226 / 0.231 | 1.35 / 1.40 | 1.54 / 1.59 |

Findings:

T3-F1. The leader core was a solid box. At the leader the halo term is well above 1, so every pixel in and around the glyph clipped to near-white (openness 0.110 at 1920 and 0.077 at 2880, box fill 0.74). The opening stills read 0.384 and 0.438 (11 to 13 leaders); every other still with leaders is more open (0.535 to 0.791). `lead_cap` 0.5 caps the cursor light of the halo and `lead_core` 1.5 narrows the cursor mix, which gives 0.37 at both sizes: the closed end of the film, about 0.015 under the lowest still. The ring stays blue-white where lowering `lead_glow` turned it green.

T3-F2. Leader columns depend on the number of rows per column. A 16:9 crop holds about 969 rows at 1915 px wide and a 16:10 crop about 1077, against 799 to 801 in the 2.39:1 stills, so the whole-frame ratio is not comparable. `lc239` measures the same ratio on 1915 x 801 bands and equals the whole-frame value on the three leader stills (0.231 to 0.251). With the shape accounted for, `lead_ratio` 0.42 gives lc239 0.23 and near-white 1.35 to 1.40 (8-seed mean), under the film's 1.50 to 1.64.

T3-F3. Lit columns cluster in the film. The clustering index (mean empty gap in 25.5 px bins, about one film column, times the lit-bin share) is 1.22 to 1.73 over 6 single realisations (mean 1.37); independent lanes give about 1 at any density. The saver's lanes were independent (earlier 8-seed mean 1.14, per seed 0.91 to 1.48). A normalised value-noise gain over the lane index (`cluster` [6, 0.8]) takes the 8-seed mean to 1.54 and 1.59 at the same mean density (lit 0.259 and 0.252 against 0.258 and 0.249). Per-seed values run 1.22 to 2.13, so one monitor in eight can look more clustered than any still.

T3-F4. Grain dot mask: not supported by the stills. The 1D spectra of the ink residual show a prominent periodic peak only in opening-4k (5.33 px native, prominence 11.4 on y and 3.5 on x; one still, possibly a transfer artefact). The digit close-up, neo-sees-code and system-failure 4K stills have none (prominence 1.0 to 1.4); operator-closeup shows an in-world monitor raster. The saver's grain is flat white noise and the changes in this section do not move the grain gates. It was added as a static mask anyway (see the addendum below).

### Addendum: near-white and ink dots

Near-white: `lead_ratio` 0.46 and `lead_cap` 0.55 take the 8-seed near-white to 1.55 (1920) and 1.63 (2880) against the film's 1.50 to 1.64 (gate 1.45 to 1.80), with openness 0.350 and 0.356 and lc239 0.247 and 0.253. Over the time windows near-white reaches 1.69 at 2880, above the film's top still and inside the gate.

Ink dots (rests on one still). The 1D ink-residual spectrum (green minus a 5 x 5 box mean, runs of max channel above 120, 64 px along y, 16 px along x; prominence is the bin power over the mean of the bins two either side) shows a peak at the pitch only in 1999-opening-4k: 5.33 px on a 3840 wide frame (720 periods per width), y prominence 11.37, x 1.40. The Blu-ray of the same shot has none (1.46, 14 runs), nor do the digit-rain stills (0.83, 0.79), neo-sees-code-4k (0.89) or system-failure-4k (0.86, 0.46). It may be a 4K transfer or scan artefact, so the mask is a taste call backed by one still, not a measured film property. `ink_dots` [2.6667, 0.1, 0.3] (pitch in display px at dpi 1, times the monitor dpi; strength; x share) multiplies the ink by a static cosine product on unseeded `gl_FragCoord`, sparing near-white so the leaders keep their values, and leaves the palette floor alone. The saver's y prominence goes from 1.03 to 2.75 (1920) and 2.79 (2880), about a quarter of the still's. The pitch is looked up per monitor in both shader paths, so mixed-dpi monitors each read their own bin.

## Software renderer differences

The software renderer (digital_rain/soft_renderer.py) draws the same rain model, directions, pulse, 24 fps stepping, lane share, tooth gamma, glyph crossfade and defocus as the GPU path. It leaves out the following. There is no flicker. There is no film grain on the ink, but a static dot mask (ink_dots) is drawn. There is no bloom pyramid or halation: one bloom is composed at a quarter of the resolution instead, with no high-pass. The palette is applied per glyph level rather than to the bloom overlaps, so the crossfade and defocus are tinted per level. There is no lead_core, so the leader is drawn at the cursor level. There is no glint (look key glint_gain). Resurrections tiles are drawn from the 52 px cropped coverage at the square cell of looks.cell_px.
