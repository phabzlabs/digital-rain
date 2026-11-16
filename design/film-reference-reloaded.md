# Film reference: Reloaded and Revolutions (2003) code rain

Measurements of the 2003 sequels' code rain, written the same way as design/film-reference.md (which covers the 1999 film and keeps the shared findings F1 to F25), so the `reloaded` preset can be brought as close to the film as `film_1999` is to 1999. Measured 10 November 2026 on the base SHA fdde7fb. Stills are in `assets/reference/matrix-2003-*.jpg`, listed with exact source URLs in `assets/README.md`. Numbers come from `tools/dev/measure_reference.py` (run `.venv\Scripts\python.exe -I tools/dev/measure_reference.py $(ls assets/reference | grep matrix-2003)`).

## Evidence and its limits

Fourteen stills: 13 from the Revolutions 4K regrade (movie-screencaps.com; titles, full-frame rain, one monitor) and one Blu-ray-grade Reloaded still (film-grab.com, 1280 wide, a code face from the Reloaded opening). Not found, so not measured: any Reloaded 4K gallery (movie-screencaps.com has only the 1999 and Revolutions 4K pages; screenmusings.org has only the 1999 film), any Revolutions Blu-ray rain still (the film-grab.com Revolutions gallery has none), any Reloaded or Revolutions motion clip. So glyph change rate, fall speed, stepping and stammer for 2003 are unmeasured and the current preset values for them (Rezmason's `classic`: speed 15 to 30 rows per second, `cycle` 0.56 s) stay as they are.

Grade matters. The 4K regrade has hue 147 to 157 degrees; the single Reloaded Blu-ray still has hue 125, close to the yellow-green of the current preset (hue 108). Every hue and palette number below is therefore marked with its grade, and the `reloaded` preset takes the 4K grade; the Blu-ray still is unrepresentative (a face fills the frame: lit 0.77, top bucket 0.013) and is kept only as a colour note.

Title frames carry large spaced letters and rain at several zoom levels, so their pitch and halo numbers describe zoom, not the rain grid; they are measured on a crop that excludes most letters (crop column in `STILLS` of the tool) and used for colour and grain only. The clean rain measurements come from `rain-field`, `rain-field-wide`, `rain-mid` and `rain-close` (frames 39, 151, 37, 36).

## Measurements across stills

Lit means max channel above 40. Hue and saturation are medians over lit pixels. Head is the mean colour of the brightest 0.5 percent of pixels. Near-white is every channel above 180, as a share of lit pixels. Halo and edge are px at 1915 wide (the tool prints halo in native px; converted here by 1915 / image width). Ink grain is the green residual standard deviation inside ink over its mean. Run is the median vertical run of lit pixels along ink columns in rows, gaps under 0.7 row bridged (a lower bound where drops overlap).

| Still (file `matrix-2003-<name>.jpg`) | Frame | Bg | Lit | Hue (IQR) | Sat | Head | Near-white | Col spacing | Halo 50 / 10 | Edge | Ink grain | Run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `revolutions-title-the-matrix-4k` (crop left 38 %) | 2 | #000501 | 0.19 | 150 (147-153) | 0.95 | #29FFB0 | 0 | sparse | 2.0 / 15 | 3.2 | 0.032 | 3.6 |
| `revolutions-title-the-matrix-wide-4k` (crop left 38 %) | 3 | #000201 | 0.04 | 151 (147-155) | 0.94 | #53FFC3 | 1.2 % | 40.4 | 1.5 / 7 | 2.3 | 0.037 | 3.1 |
| `revolutions-title-matrix-4k` (bottom 40 %) | 4 | #000200 | 0.06 | 147 (144-150) | 0.95 | #13EE8D | 0.1 % | sparse | 2.0 / 15.5 | 3.0 | 0.030 | 5.1 |
| `revolutions-title-revolutions-4k` (crop left 35 %) | 5 | #000201 | 0.06 | 148 (145-151) | 0.96 | #12FE9D | 0 | sparse | 2.0 / 9.5 | 2.9 | 0.033 | 2.2 |
| `revolutions-title-revolutions-zoom-4k` (bottom 38 %) | 6 | #000201 | 0.10 | 150 (146-154) | 0.95 | #39FFB8 | 0.6 % | sparse | 4.0 / 24.5 | 5.5 | 0.020 | 8.2 |
| `revolutions-title-letters-4k` (bottom 35 %) | 7 | #000201 | 0.08 | 148 (144-151) | 0.96 | #1CFFA4 | 0 | sparse | 2.0 / 11 | 2.4 | 0.047 | 7.1 |
| `revolutions-title-letter-close-4k` | 8 | #000402 | 0.45 | 148 (146-151) | 0.95 | #25FFA2 | 0.9 % | 41.4 | 3.5 / 23 | 4.6 | 0.029 | 13.8 |
| `revolutions-rain-close-4k` | 36 | #000A05 | 0.30 | 151 (147-154) | 0.96 | #1FFFA8 | 0.07 % | - | 3.0 / 18 | 5.9 | 0.017 | - |
| `revolutions-rain-mid-4k` | 37 | #000D0A | 0.28 | 154 (150-158) | 0.93 | #2DFFAB | 0.2 % | 99.7 | 3.0 / 10.5 | 5.0 | 0.018 | 6.7 |
| `revolutions-rain-field-4k` (crop centre 80 %) | 39 | #000305 | 0.28 | 153 (151-156) | 0.93 | #2CFFB7 | 0.04 % | 40.4 | 2.0 / 5 | 3.0 | 0.029 | 15.7 |
| `revolutions-rain-field-wide-4k` (crop 5 to 90 %) | 151 | #000C0E | 0.32 | 157 (154-160) | 0.88 | #2CFFB8 | 0 | 55.4 | 1.5 / 3.5 | 2.4 | 0.042 | 13.6 |
| `revolutions-rain-pan-4k` | 152 | #040F11 | 0.47 | 156 (154-159) | 0.95 | #28F5A3 | 0 | 70.8 | 16.5 / 41.5 (haze) | 3.1 | 0.026 | 10.3 |
| `revolutions-zion-monitor-4k` (screen crop) | 191 | #001214 | 0.71 | 162 (160-165) | 0.86 | #2DDFA7 | 0 | 20.4 | too small | 3.9 | 0.026 | 9.1 |
| `reloaded-trinity-code-face-bluray` (Blu-ray grade) | Rel. 4 | #051502 | 0.77 | 125 (122-128) | 0.80 | #8FF898 | 0.02 % | 67.3 | face glow | 6.5 | 0.063 | 12.6 |

For comparison the 1999 opening Blu-ray gives lit 0.26, hue 153, head #DCDFE7, near-white 1.6 %, edge 2.9, ink grain 0.081 (design/film-reference.md).

Tone buckets by max channel, share of lit pixels, for the four full-frame rain stills (36, 37, 39, 151), with the bucket mean colour averaged over the four (rounded):

| Bucket | 36 | 37 | 39 | 151 | Mean share | Mean colour |
|---|---|---|---|---|---|---|
| 40-80 | 0.305 | 0.293 | 0.260 | 0.185 | 0.261 | #023A21 |
| 80-120 | 0.199 | 0.236 | 0.185 | 0.117 | 0.184 | #066238 |
| 120-160 | 0.134 | 0.180 | 0.141 | 0.121 | 0.144 | #0D8A52 |
| 160-200 | 0.071 | 0.086 | 0.094 | 0.140 | 0.098 | #14B26B |
| 200-230 | 0.040 | 0.051 | 0.060 | 0.118 | 0.067 | #19D782 |
| 230-256 | 0.263 | 0.164 | 0.268 | 0.328 | 0.256 | #25FCA8 |

Red-to-green ratio rises with level from 0.02 to 0.04 in the darkest bucket to 0.11 to 0.17 in the brightest. The 1999 film puts 6 percent in the top bucket; the 2003 rain puts 16 to 33 percent there, as saturated mint (about #25FCA8), not white. This is the "flat brightness plus bloom" look of Rezmason's classic operator (F10, F13), not the 1999 sawtooth.

Blu-ray grade, one still (Reloaded opening, code over a face, so lit fraction and bucket shares are not representative; only the colour ramp is): 40-80 #093A0B, 80-120 #13611B, 120-160 #268A32, 160-200 #3FB24D, 200-230 #5BD46B, 230 and up #82F28E; hue 122 to 128 at every level, saturation falling from 0.84 to 0.46, red-to-green 0.16 to 0.54, background #051502, head #8FF898.

## Findings

Each finding says how many stills confirm it.

G1. Hue and palette (4K grade). Lit hue 147 to 157, median 153, in 13 of 13 4K stills; saturation 0.86 to 0.96; the ramp above. Confirmed across 13 stills for the 4K grade; one still for the Blu-ray grade (hue 125).

G2. No near-white leader. Near-white pixels are 0 to 0.2 percent of lit pixels in the 9 rain stills (1 percent only where title letters or the digit trace are in the crop). The head is saturated mint, brightest 0.5 percent #1FFFA8 to #2DFFAB (hue 154 to 157) in 10 stills; Blu-ray #8FF898. Confirmed across 10 stills. This differs from 1999 (#DCDFE7 leaders) and from the current preset (cursor 193,255,117 at gain 2, which clips to near-white).

G3. Lit fraction 0.27 to 0.32 in the four upright full-frame rain stills (0.304, 0.281, 0.276, 0.322); 0.47 in the panning haze shot; 0.04 to 0.19 in title frames where the rain is sparse. Confirmed across 4 stills.

G4. Tone distribution: top bucket 16 to 33 percent, darkest bucket 19 to 31 percent (table above). Confirmed across 4 stills; the 9 other stills agree on a heavy top bucket (14 to 28 percent) apart from the pan (2 percent).

G5. Background not pure black: median of dark pixels #000201 to #000D0A (g 2 to 13, r at most 1, b 1 to 10); the haze shots (36, 37, 151, 152) sit at the high end. Confirmed across 13 stills. Floor of the palette (R=0) is the right model; a haze floor above 6 appears only in near-camera shots.

G6. Halo is no wider than 1999. In the 9 stills with clean rain the brightness around bright glyphs falls to 50 percent at 1.5 to 4 px and to 10 percent at 3.5 to 25 px at 1915 wide, median 2.0 and 11; the two upright full-frame stills (39, 151) give 2.0 / 5 and 1.5 / 3.5. The wide tails (16 to 41 px) occur only in hazy or close shots (152, 36, 8). Confirmed across 9 stills.

G7. Edge softness 2.3 to 3.2 px (10 to 90 percent rise at 1915 wide) in 8 stills (2, 3, 4, 5, 7, 39, 151, 152); 3.9 to 5.9 px in the near-camera or zoomed shots (6, 8, 36, 37, 191). So the glyphs are soft but not as soft as a defocused plane. Confirmed across 8 stills.

G8. Ink grain: relative green residual 0.017 to 0.047, mean 0.03, in the 13 4K stills; 0.063 in the Blu-ray still. Background grain (residual std in dark areas far from ink) 0.2 to 0.6 in the upright frames, 2 to 2.7 green in the haze frames 36 and 37. Confirmed across 13 stills for the 4K grade.

G9. Column spacing 40.4 to 41.4 px at 1915 wide (the mean spacing of ink columns, which is a multiple of the grid pitch when columns are skipped) in 3 stills (3, 8, 39); 55 to 100 in layered or zoomed shots. The current preset measures 41.5 to 42.6 at 1920 (depth off) by the same tool, so grid pitch matches and `cell_scale` stays 1.0. The row pitch estimate is noisy (29.7 to 32.8 in the upright stills against 42 for the preset, depth off); the autocorrelation picks different harmonics, so no row pitch gap is claimed. One shot family, 3 stills. The section "Glyph size and clarity (evidence)" at the end of this file revisits it with grid pitch, ink-column count and row pitch on all 14 stills.

G10. Trail length. Median lit run 13.6 to 15.7 rows in the clean upright stills (39, 151) and 13.8 in the letter close-up; 6.7 to 10.3 where drops overlap or haze hides the tail. The same tool gives 6.8 for the 1999 opening and 8.4 (depth off) to 14.7 (default depth) for the current `reloaded`. No change is justified by this measure: the 2003 runs are about twice the 1999 runs, and the preset's `tooth` 75 with `contrast` 1.1 and `bias` -0.5 is already long. Confirmed across 3 stills.

G11. Layering and zoom. The titles zoom through three or more scales at once (row pitch 30 to 48 px in the title stills, up to 58 in the mid-film shots) and the mid-film rain is a drifting camera shot at a different scale from the title. Not reproducible by one preset; the `depth` setting already provides three scales. Observed in all 13 4K stills; no number is targeted.

Unmeasured (no 2003 motion source): glyph change rate, fall speed, whole-row stepping, stammer, leader frequency. One still cannot show leader frequency either: in the rain stills the brightest cells (head) occur on most strings, but no count is made.

## Targets for the `reloaded` preset (4K grade, 1915 px width)

1. Tone ramp. By max channel: 40 to 80 #023A21, 80 to 120 #066238, 120 to 160 #0D8A52, 160 to 200 #14B26B, 200 to 230 #19D782, 230 and up #25FCA8. Hue 150 to 157 (median 153); saturation 0.85 to 0.96; red 2 to 17 percent of green. Alternative, Blu-ray grade (one still): #093A0B, #13611B, #268A32, #3FB24D, #5BD46B, #82F28E, hue 122 to 128.
2. Tone distribution, share of lit: about 0.26, 0.18, 0.14, 0.10, 0.07, 0.26 (the windows `tools/checks/check_film.py` gates on).
3. Background. Dark-pixel median r 0 to 1, g 2 to 8, b 1 to 8 for the upright frames (#000305 target); hazier frames go to g 13.
4. Lit fraction 0.27 to 0.32.
5. Head colour. Brightest 0.5 percent of pixels #1FFFA8 to #2DFFAB (target #2CFFB7); near-white at most 0.3 percent of lit pixels; no white leader.
6. Bloom. Brightness outside bright glyphs falls to 50 percent within 1.5 to 3.5 px and to 10 percent within 3.5 to 18 px.
7. Edge rise 2.3 to 3.2 px.
8. Ink grain 0.02 to 0.045 relative (target 0.03); background grain at most 1.2 on any channel; no scanlines, interlace or flicker (as in `reloaded` now).
9. Column spacing and glyph cell: unchanged (`cell_scale` 1.0).
10. Trail: lit run of at least 10 rows median (current preset passes already; guard against regressions).

## Gap analysis: current `reloaded` and the renderers

Current preset values are `looks.PRESETS['reloaded']` at fdde7fb. Baseline numbers are GPU frames from `tools/checks/frame_harness.py` at 1920x1080, mean of t = 6, 9, 12, 15 s, top 10 percent cropped, seeded renderer, measured with the `check_film.measure` functions (halo and edge in px at 1915). "Default" is `settings.DEFAULTS` with preset reloaded (depth on); "depth off" is the same with depth false.

| # | Film (stills) | `reloaded` today | Size |
|---|---|---|---|
| G1 | Hue 153, 4K ramp | Palette 000000, 176105 at 0.2, 89F76E at 0.7, B0FA9E at 0.8: hue 108.1 both runs | Large |
| G2 | Head mint #2CFFB7, near-white at most 0.3 % | `cursor` (193,255,117) with `cursor_gain` 2.0 gives head #BFEFA5 (default) or #A1E289 (depth off) at the brightest 0.5 %; near-white 1.45 % (default), 2.03 % (depth off); `lead_ratio` 1.0 so 31 to 36 % of lit columns carry the cursor head | Large |
| G3 | Lit 0.27 to 0.32 | 0.151 (default), 0.076 (depth off) | Large |
| G4 | Buckets 0.26/0.18/0.14/0.10/0.07/0.26 | Default 0.404/0.236/0.163/0.125/0.060/0.030; depth off 0.260/0.242/0.237/0.178/0.069/0.024. The top bucket is 0.03 against 0.26 | Large |
| G5 | Bg g 2 to 8 | 0/0/0, palette first stop 000000 | Small |
| G6 | Halo 50 / 10 at 1.5-3.5 / 3.5-18 px | 2.0 / 8.0 (default), 2.0 / 4.5 (depth off): inside, tail slightly short at depth off | None to small |
| G7 | Edge 2.3 to 3.2 px | 1.1 (default), 1.0 (depth off); `defocus` 0.0 | Medium |
| G8 | Ink grain 0.03, bg grain at most 1.2 | `grain_ink` 0.0, `grain` 0.0167 (dither); bg grain g 2.5 (default) and 1.3 (depth off) on this measure, from the bloom skirt | Medium |
| G9 | Pitch equals preset | Column spacing 55.5 (default, depth layers) and 42.6 (depth off); same | None |
| G10 | Run 13.6 to 15.7 rows | 14.7 (default), 8.4 (depth off) | None to small |
| H1 keys | | `pyramid` False, `glow_r`, `glow_g` zero, `lead_core` 1.0, `gamma` 1.0, `lanes` 1.0, `crossfade` False, `step_fps` 0.0: reloaded uses the legacy additive bloom, where the cursor is added after the palette (`min(palette + u_cursor * c.g, 1)`, digital_rain/gl_renderer.py line 413) | Large for G2 to G4 |

### After the preset changes

`check_film.py --preset reloaded` (same measure, depth off, pulse off, upscaling quality), against the film targets.

| # | Film (stills) | After the preset changes | Status |
|---|---|---|---|
| G1 | Hue 153 | 153.1 | Met |
| G2 | Head #2CFFB7, near-white at most 0.3 % | head (38,255,173), near-white 0.00 | Met |
| G3 | Lit 0.27 to 0.32 | 0.308 | Met |
| G4 | Buckets 0.26/0.18/0.14/0.10/0.07/0.26 | 0.440/0.204/0.099/0.065/0.077/0.131 | Dark bucket high and top bucket low (mass sits in the dark and mid buckets); inside the widened windows, the residual gap is the palette ramp shape |
| G5 | Bg g 2 to 8 | (0,4,2) | Met |
| G6 | Halo 1.5-3.5 / 3.5-18 px | 2.99 / 12.5 | Met |
| G7 | Edge 2.3 to 3.2 px | 3.05 | Met |
| G8 | Ink grain 0.03 | 0.042 (1920x1080), 0.038 (960x540); bg grain g 0.49 | Met; with `grain_ink` 0 the residual is 0.0246 (window 0 to 0.03 for reloaded, film_1999 0.0194) |
| G9 | Pitch equals preset | unchanged | Met |
| G10 | Run 13.6 to 15.7 rows | 13.7 | Met |

Renderer parity. The software renderer has no bloom pyramid, halation or `lead_core` (digital_rain/soft_renderer.py header lines 1 to 8), so the software output of `reloaded` follows the same limits as `film_1999`'s: palette, tooth, gamma, lanes, defocus and ink grain are shared, the pyramid look is GPU only.

### Biggest gaps, in order

1. Colour: hue 108 against 153 (4K) or 125 (Blu-ray), and a cursor that clips to near-white where the film has mint heads.
2. Lit fraction 0.08 to 0.15 against 0.28 to 0.32, with a top bucket of 3 percent against 26 percent.
3. Soft edges (1.0 px against 2.3 to 3.2) and ink grain (none against 0.03).
4. Everything about motion is unmeasured for 2003.


## Glyph size and clarity (evidence)

Added to revisit the earlier decision that `cell_scale` stays 1.0, which compared only the ink-column spacing (a multiple of the grid pitch, F7) against a preset whose own row pitch estimate is a harmonic. All 14 `assets/reference/matrix-2003-*.jpg` stills (13 Revolutions, 1 Reloaded) were measured with `tools/dev/measure_reference.py --table`. Definitions are in "Glyph size and clarity (evidence)" of design/film-reference.md. Three stills are not used for the targets: the Reloaded Blu-ray frame (a face fills the frame, lit 0.77, the 4K grade decision), the Zion monitor crop (538 x 593 px) and the camera pan (motion-blurred glyphs). Row pitch estimates are noisy on these frames (several harmonics compete, and the same estimator reads 42.6 px on the saver's true 28 px rows in reloaded frames, so saver numbers below come from `rain_grid`, not from the estimate).

| Still | Used for targets | Lit | Row pitch | Column pitch (strength) | Ink columns per 1915 | Ink spacing | Cell width % of frame | Cell height % of frame | Stroke FWHM | Fill | Edge rise |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2003-reloaded-trinity-code-face-bluray | no: a face fills the frame, lit 0.77 (4K grade decision) | 0.765 | 55.6 | 33.2 (0.14) | 41 | 67.3 | 1.74 | 6.75 | 1.5 | 0.83 | 6.5 |
| 2003-revolutions-rain-close-4k | yes | 0.304 | nan | 34.3 (0.16) | 37 | nan | 1.79 | nan | 1.5 | 0.68 | 5.9 |
| 2003-revolutions-rain-field-4k | yes | 0.276 | 32.8 | 23.0 (0.14) | 45 | 40.4 | 1.20 | 4.11 | 7.5 | 0.43 | 3.0 |
| 2003-revolutions-rain-field-wide-4k | yes | 0.322 | 58.0 | 36.4 (0.12) | 55 | 55.4 | 1.90 | 7.26 | 8.0 | 0.40 | 2.4 |
| 2003-revolutions-rain-mid-4k | yes | 0.281 | 38.3 | nan (0.00) | 34 | 99.7 | nan | 4.80 | 0.5 | 0.61 | 5.0 |
| 2003-revolutions-rain-pan-4k | no: camera pan, motion-blurred glyphs (fill 0.93) | 0.471 | 58.2 | 53.1 (0.19) | 28 | 70.8 | 2.77 | 7.30 | 0.5 | 0.93 | 3.1 |
| 2003-revolutions-title-letter-close-4k | yes | 0.450 | 41.2 | nan (0.00) | 52 | 41.4 | nan | 5.16 | 4.0 | 0.75 | 4.6 |
| 2003-revolutions-title-letters-4k | yes | 0.082 | 29.7 | 39.1 (0.15) | 15 | 156.1 | 2.04 | 3.72 | 6.0 | 0.36 | 2.4 |
| 2003-revolutions-title-matrix-4k | yes | 0.061 | 44.7 | nan (0.00) | 16 | 77.3 | nan | 5.60 | 5.0 | 0.43 | 3.0 |
| 2003-revolutions-title-revolutions-4k | yes | 0.055 | 48.4 | 30.7 (0.16) | 26 | 130.9 | 1.60 | 6.06 | 6.5 | 0.43 | 2.9 |
| 2003-revolutions-title-revolutions-zoom-4k | yes | 0.102 | 36.9 | 27.9 (0.19) | 8 | 429.4 | 1.46 | 4.62 | 3.5 | 0.63 | 5.5 |
| 2003-revolutions-title-the-matrix-4k | yes | 0.192 | 47.1 | 22.0 (0.21) | 26 | 135.1 | 1.15 | 5.91 | 7.0 | 0.52 | 3.2 |
| 2003-revolutions-title-the-matrix-wide-4k | yes | 0.039 | 31.8 | 31.5 (0.28) | 32 | 40.4 | 1.65 | 3.98 | 10.5 | 0.45 | 2.3 |
| 2003-revolutions-zion-monitor-4k | no: in-world monitor crop of 538 x 593 px, 8 ink columns | 0.709 | 32.4 | 18.6 (0.34) | 100 | 20.4 | 0.97 | 4.06 | 7.5 | 0.56 | 3.9 |

Spread over the 11 used stills (counts vary where a column returned no value):

- row_pitch: n 10, median 39.75, min 29.70, max 58.00
- col_pitch: n 8, median 31.10, min 22.00, max 39.10
- ink_cols: n 11, median 32.00, min 8.00, max 55.00
- cell_w_pct: n 8, median 1.62, min 1.15, max 2.04
- cell_h_pct: n 10, median 4.98, min 3.72, max 7.26
- stroke: n 11, median 6.00, min 0.50, max 10.50
- fill: n 11, median 0.45, min 0.36, max 0.75
- edge: n 11, median 3.00, min 2.30, max 5.90
- lit: n 11, median 0.19, min 0.04, max 0.45
- 2003 full-frame rain (field, field-wide, mid, close) ink_cols: n 4, median 41.00, min 34.00, max 55.00
- 2003 full-frame rain (field, field-wide, mid, close) lit: n 4, median 0.29, min 0.28, max 0.32
- 2003 upright cluster (field, title-wide, letters, zoom) row_pitch: n 4, median 32.30, min 29.70, max 36.90

The saver on the base SHA (`reloaded`, gated configuration, 1920x1080, quality): cell 19.5 x 28.5 display px, 98 columns, 37 rows, ink columns 47, fill 0.42, edge 3.05, lit 0.308.

Findings:

T1-G1. The cell is too small. Row pitch is 29.7 to 58.0 px (median 39.75) in 10 measured stills, every one larger than the saver's 28 (ratio 1.06 to 2.07). The spread is camera zoom (the shots differ in scale; F17). The four upright, least zoomed stills (rain field 32.8, title wide 31.8, letters 29.7, title zoom 36.9) cluster at 29.7 to 36.9 (median 32.3), which a cell scale of 1.15 (31.5 px rows) matches. Confirmed across 10 stills that the saver rows are too small; the size 1.15 rests on the 4 upright stills (the other six want it larger, so 1.15 is the conservative end).

T1-G2. Columns. The grid pitch is reliable in no 2003 still (strength 0.12 to 0.28 on all but the Zion monitor); the rain field gives 23.0 px (strength 0.14), consistent with its row pitch over 1.4 (32.8 / 1.4 = 23.4), so the grid pitch rests on 1 still. Ink columns per 1915 px in the 4 full-frame rain stills (field, field wide, mid, close) are 34 to 55 (median 41) against 47 in the saver. After a cell scale of 1.15 the saver gives 39 to 41, which is the median. A density cut is not confirmed: the saver is already inside the range at 47, and a cell scale alone puts it on the median (rests on 0 stills for a density multiplier below 1.0). The old "about 41 px spacing against 20.6 px" compares the ink spacing of skipped columns with the saver's grid pitch; the like-for-like numbers are above.

T1-G3. Lit fraction of the 4 full-frame rain stills is 0.28 to 0.32 (median 0.29); the saver is 0.308 (base) and 0.307 / 0.261 after the cell-size change at 1920x1080 / 2880x1800 at 150 percent scaling. Reducing the lane share lowers lit and takes the 2880x1800 frame under the target window (0.25 to 0.34).

T1-G4. Softness. Edge rise is 2.3 to 5.9 px (median 3.0) over the 11 used stills; fill 0.36 to 0.75 (median 0.45). The saver at the old defocus 0.14 and a 1.15 cell reads 3.45 px (outside the target window 2.0 to 3.4); defocus 0.12 gives 2.99, the median.
