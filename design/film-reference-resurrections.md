# Film reference: The Matrix Resurrections (2021) digital rain

Evidence pack for the Resurrections look. It extends design/film-reference.md section 4 (F25), which rested on Rezmason's `resurrections` config alone ("no frame of the 2021 film was measured"). This file holds the first measurements of 2021 frames.

## What was and was not sourced

Twelve stills are in `assets/reference/` (`matrix-2021-*`, rows in assets/README.md). Be clear about their independence: ten of the twelve show one shot, the street at night with the code rain painted over the buildings and the road (film-grab frame, trailer 1 at 10.4, 10.9, 11.4 and 11.8 s, trailer 2 at 58.7, 59.1 and 59.4 s; seven trailer frames and one Blu-ray-era frame of the same shot, the trailer frames only 0.3 to 0.5 s apart). The other four frames are the code tunnel (trailer 1, 12.05 s), the glass-glyph logo (trailer 1, 23.1 s) and the two end cards with faint rain behind the credits (trailer 1 at 170.4 s, trailer 2 at 166.5 s). So "confirmed across N stills" below means N crops or frames of at most four distinct compositions, and the facade numbers are one shot in two grades and two trailer cuts.

Not obtainable, with what was tried:

1. movie-screencaps.com: no Resurrections gallery (its sitemap lists only The Matrix 1999 4K and Revolutions 4K; the URLs for the film return 404).
2. screenmusings.org: no Resurrections gallery (index lists only The Matrix; guessed gallery and image URLs return 404).
3. blu-ray.com: the 4K review gallery (10 frames of 1280 x 720, https://www.blu-ray.com/movies/screenshot.php?movieid=300387&position=1 to 10) holds no code rain (green share 0.0 to 0.6 percent, all live action), so none were kept.
4. film-grab.com: 65 frames of the film (https://film-grab.com/2024/05/15/the-matrix-resurrections/), only frame 10 holds code rain. Kept. The page does not say which release the frames come from, so its grade is recorded as "film-grab", not "Blu-ray" or "4K".
5. getyourcomicon.co.uk (trailer stills on imgbox): the originals serve 240 x 240 thumbnails. themoviedb.org image pages and bloody-disgusting.com return 403.
6. Trailers: the official trailers 1 and 2 on YouTube (video ids 9ix7TUGVYIo and nNpvWBuTfrc) were downloaded at 1080p and frames cut with ffmpeg. That is trailer grade (lossy, graded for trailers, letterboxed with picture rows 0.13 to 0.87 of the height), not Blu-ray or 4K grade. The in-world screens and the "rain in depth" Hamilton ad frames were not found.

No motion data exists for 2021 (no gif or clip study like Carl Newton's for 1999). Fall speed, stepping, glyph change rate and trail length are not measured; they stay Rezmason values (F19, F22, F25).

## Method

`tools/dev/measure_reference.py` with one extension: a `STILLS` key may be `file@part`, so one file can be measured on several crops (street shots: left facade, right facade, floor; the tunnel, end cards and logo whole picture area). Crops: left facade x 0 to 0.2, y 0.16 to 0.80 (the Blu-ray-era frame is not letterboxed: y 0 to 0.8); right facade x 0.72 to 1.0, y 0.16 to 0.60; floor x 0.2 to 0.8, y 0.78 to 0.87 (y 0.8 to 1.0 unletterboxed). The crops exclude the lit shopfront, the figure and the lamps, which carry orange and white light that is not rain. Numbers are px at 1915 wide as the script prints them. Run `.venv\Scripts\python.exe -I tools/dev/measure_reference.py` with the `matrix-2021-*` file names as arguments to reproduce them.

Lit means max channel above 40. Because the rain is painted over buildings, every lit-fraction figure includes the stacking of several depth layers; one flat grid of rain cannot be expected to reach it (see the depth target below).

## Measurements

Facade and floor crops, mean (range) over the 16 facade crops (8 frames, 2 crops each) and 8 floor crops:

| Measure | Facade (rain over buildings) | Floor (rain on the road, perspective) |
|---|---|---|
| Lit fraction | 0.38 (0.33 to 0.52) | 0.26 (0.25 to 0.31) |
| Background median, pixels with max channel under 25 | #020F03 (R 2 to 4, G 13 to 18, B 2 to 5) | #030E03 |
| Lit hue median | film-grab 124 to 126, trailer 1 123 to 129, trailer 2 133 to 137 | 125 to 135 |
| Saturation median | 0.65 to 0.79 | 0.72 to 0.83 |
| Tone bucket 40-80 / 80-120 / 120-160 / 160-200 / 200-230 / 230+ (share of lit) | 0.63 / 0.23 / 0.095 / 0.047 / 0.016 / 0.007 (each bucket's range over crops: 0.53 to 0.68, 0.21 to 0.28, 0.07 to 0.12, 0.03 to 0.06, 0.005 to 0.023, 0.002 to 0.011) | 0.78 / 0.20 / 0.04 / 0.01 / 0.002 / about 0 |
| Bucket colour (hue drifts from 129 to 110 going up) | #0F3914, #2B6031, #4D884D, #71AF6A, #9ED590, #C7F3B5 (other crops within 8 per channel) | #0C3712, #225E2B, #498750, #6CAD6A, #9CD299 |
| Near-white share of lit pixels (every channel above 180) | 0.5 percent (0.12 to 1.0) | 0 to 0.1 percent |
| Near-white colour | #D2F0CC to #D6F3CD (a warm green-white, blue lowest) | |
| Halo outside bright ink, 50 / 10 percent | 4 px (4 to 5) / 26 px (18 to 35); 3 percent reached at 36 to 65 px | 5 px / 17 to 46 px |
| 10 to 90 edge rise | 2.9 px (2.6 to 3.3) | 3.8 to 4.6 px |
| Grain, green residual inside ink, relative | 0.11 (0.10 to 0.12; includes trailer compression noise; the film-grab frame alone 0.106 to 0.121) | 0.07 to 0.08 |
| Row pitch / column spacing | row 28 to 37 px on far facade, 47 to 60 px on the near left facade; column spacing 31 to 43 px | row 30 to 50 px, column spacing 31 to 48 px, growing toward the camera |
| Row pitch divided by column spacing | median 0.97 over 13 crops (0.89 to 1.11 in 11 of 13; 0.78 and 1.45 elsewhere) | 0.91 to 1.07 |

Other frames:

| Frame | Lit | Background | Hue | Near-white | Halo 50 / 10 | Edge | Note |
|---|---|---|---|---|---|---|---|
| Code tunnel (`code-tunnel-trailer1080`) | 0.73 | #000E01 | 118 | 2.9 percent, #E3FCDD | 5 / 60 px | 6.4 px | near-camera layer with strong radial motion blur; glyph blocks blown to white cores inside saturated green |
| Glass-glyph logo (`glass-glyph-logo-trailer1080`) | 0.45 | #010C02 | 120 | 0.3 percent | 5 / 53 px | 6.0 px | giant bevelled glyph forms, hue 120 and saturation 0.96 |
| End card, trailer 1 | 0.13 | #060603 | 116 | 0.7 percent | 2 / 6 px | 1.8 px | rain behind credits text; the measure includes the text |
| End card, trailer 2 | 0.09 | #000101 | 130 | 43 percent | 1 / 2 px | 1.5 px | credits text dominates; not a rain measure |

What the stills show that numbers do not (checked at 3x zoom on the film-grab frame and the tunnel frame):

1. Individual glyphs cannot be told apart in the street shot, only vertical streams of tiny glyphs with the brightest cell of many streams a small white dot. White dots are scattered through the facades and are far more frequent than 1999 leaders; they read as leaders or glint sparkles at distance.
2. The colour is pure green at medium brightness (R and B about equal, hue 120 to 129) that lightens toward a warm lime-white, not toward the cool white of 1999. The black between streams is not black: it carries a green floor of about #030F03.
3. The glyph edge is soft (about 3 px at 1915 wide), the halo is a tight core (50 percent at 4 px) plus a skirt about a cell wide.
4. Glint and bevel highlights, the second MSDF atlas of Rezmason's variants, cannot be resolved at this resolution. The glass-glyph logo frame shows bevelled forms at a large scale and the tunnel frame shows white cores, but no still shows thin edge highlights on glyphs of rain size. Glint is therefore Rezmason-only evidence, as before.
5. Depth: in the street shot the rain is on the building faces (vertical streams, cells about 1.6 to 1.8 times larger on the near left facade than on the far one) and on the road, where streams converge toward the vanishing point in perspective with pitch growing from about 30 px at the horizon to about 50 px near the camera. The tunnel frame is a near layer streaming past the camera with motion blur.

## Targets for the resurrections preset

Targets 1 to 10 are the numbers `tools/checks/check_film.py` gates on. "Confirmed" means the count of distinct measurements of the quantity, not of independent shots (see the top of this file).

1. Glyph set: the first 135 tiles of resurrections_msdf.png read unflipped, in atlas order (assets/rezmason/glyph-order.txt); the font is not used, see "Open points". Not measurable from stills (no glyph is legible); Rezmason and the README only (F25). Single-source.
2. Cells: square (row pitch divided by column spacing 1.0; confirmed on 13 crops of one street shot), 70 columns across the long side. The main-layer pitch measures 28 to 37 px at 1915 wide, which is 52 to 68 columns across; 70 columns is 27.4 px, just above the measured range (70 is a Rezmason value, not a film measurement). Confirmed that cells are square, medium confidence on 70 exactly.
3. Background floor: median of pixels more than one cell from lit pixels #030F03 (R 2 to 4, G 13 to 18, B 2 to 5), not black. Confirmed across 24 crops of the street shot.
4. Hue: lit hue median 128, window 120 to 138 (trailer 1 and film-grab 123 to 129, trailer 2 133 to 137). Brightness ramp hue falls from about 129 in the dark buckets to about 110 at the top (yellow-green lightening, R rising faster than B). Confirmed across 24 crops, both trailers and the film-grab frame.
5. Tone buckets of lit pixels (40/80/120/160/200/230): 0.63, 0.23, 0.095, 0.047, 0.016, 0.007 (street facades).
6. Palette stops (position is max channel over 255): 0.0 #030F03, 0.235 #0F3914, 0.392 #2B6031, 0.549 #4D884D, 0.706 #71AF6A, 0.843 #9ED590, 0.951 #C7F3B5, 1.0 #E8FBE8 (top stop from the tunnel frame's saturated overlaps, the nearest thing to a full-brightness area). Confirmed on the street shot in three grades.
7. Leaders: near-white pixels 0.5 percent of lit (window 0.1 to 1.2), colour #D2F0CC (210, 240, 204), far sparser and smaller than 1999's one-in-five strings with white cells. The street facades hold white dots spread through the streams, not one per string. Confirmed on 15 facade crops; the leader frequency per string is not measurable (see Open points).
8. Halo: 50 percent at 4 px (window 3 to 6), 10 percent at 26 px (soft window 12 to 45; the figure belongs to the street shot lit facades and trailer compression, not to the rain) around bright ink, leader halo 50 percent at 5 px and 10 percent at 29 to 54 px.
9. Edge: 10 to 90 rise 2.9 px (window 2.2 to 3.6).
10. Lit fraction: 0.38 on facades (window 0.25 to 0.50) in a stacked-depth picture; 0.26 on the floor. A single flat layer is not comparable.
11. Perspective: floor pitch 30 to 50 px (a 1.6 times growth toward the camera), near facade 1.6 to 1.8 times the far one. Existing `LAYERS` scales 0.65, 1.0 and 1.8 already span a 2.8 times range.
12. Motion, stepping, glyph change rate, trail length: unmeasured; keep Rezmason (15 to 30 rows per second, 0.56 s change, `1.17 b - 0.7`, about 30 lit rows).

## Gap analysis against the code at fdde7fb

The `resurrections` preset (digital_rain/looks.py line 49) runs the film shader with Rezmason numbers but none of the 2021-specific assets, and the renderers ignore them. Baseline from the GPU frame harness, 1920 x 1080, upscaling quality, mean of t = 6, 9, 12 and 15 s, top 10 percent cropped, `pulse` off, measured with the check_film.py `measure` function:

| Measure | Baseline, `depth` false | Baseline, `depth` true | Target |
|---|---|---|---|
| Glyph set | classic Matrix-Code.ttf (source "film", 57 glyphs) | same | Resurrections atlas, 135 tiles |
| Cell size, grid | 20 and 28 times `cell_scale` 1.143 = 23 x 32 display px (15 x 21 render px with FSR quality), 83 to 85 columns | same | square, 69 to 72 columns |
| Lit fraction | 0.038 | 0.063 | 0.25 to 0.50 (depth) |
| Background median | #000000 | #000000 | #030F03 |
| Lit hue median | 134.8 | 134.7 | 128 (120 to 138) |
| Tone buckets | 0.62 / 0.27 / 0.07 / 0.008 / 0.009 / 0.041 | 0.64 / 0.25 / 0.07 / 0.014 / 0.018 / 0.032 | 0.63 / 0.23 / 0.095 / 0.047 / 0.016 / 0.007 |
| Near-white of lit | 4.0 percent | 3.4 percent | 0.5 percent (0.1 to 1.2) |
| Leader columns | 0.44 | 0.33 | not gated (see Open points) |
| Halo bright 50 / 10 percent | 2.0 / 3.2 px | 2.0 / 3.2 px | 4 px / soft (about 26 px) |
| Edge rise | 1.5 px | 1.6 px | 2.9 px |

Findings:

1. The glyphs are wrong. `glyphs.glyph_set` (digital_rain/glyphs.py line 124) only knows the classic font (`FILM_FONT_NAME` line 15, `film_font_path` line 62). `git grep -n "Matrix-Resurrected\|resurrections_msdf\|glint" -- "*.py" build.ps1` finds nothing outside docs and assets: the font and both atlases are never loaded. The preset therefore draws classic glyphs. This is the largest visible gap.
2. The grid is wrong. The cell is 20 by 28 times 1.143 (a 5:7 cell, digital_rain/looks.py `cell_scale` 1.143), so cells are 23 by 32 display px and 83 columns at 1920 (85 at render size with FSR quality), not square and not 70.
3. The palette is wrong. It is Rezmason's 135 degree ramp to #33FF66 at 0.92 and white at 1.0, whose mid-tones are R 51, G 255, B 102 (blue-green). The film's mid-tones are #4D884D-like (R equal to B) with hue falling toward lime, and the dark floor is #030F03.
4. The drop is far too thin. Baseline lit fraction 0.04 to 0.06 against a film figure of 0.26 to 0.52. Part of this is the missing depth stacking, part is that `lanes`, bloom and pyramid are neutral for this preset.
5. The glow is wrong in kind. With `pyramid` False the legacy two-level bloom runs (halo 2 / 3 px against 4 / 26 px) and the edge is sharp (1.5 px against 2.9 px). The `glow_r` and `glow_g` weights and `defocus` that H1 added exist for film_1999 and are neutral here.
6. The leaders are wrong. Every string has a leader (`lead_ratio` 1.0) of cursor colour (178, 255, 153) times 2, which clamps to white, so 3.4 to 4.0 percent of lit pixels are near-white against about 0.5 percent in the film, and their colour is cool-white against the film's #D2F0CC.
7. Glint is absent (no pass, no second atlas). Not measurable in the stills, so only its existence is specified.
8. Depth is two-dimensional. With depth on, the GPU draws six depth slices (`depth_slices`: cells 19 to 110 px at 1920 wide, near slices bigger, sparser and slightly soft, screen blend, per-lane depth jitter); the software renderer keeps the three layers. It is a size spread with no perspective geometry; the street shot's floor streams converge toward a vanishing point.

## Open points

1. Resolved: the glyph source is the two PNG atlases, read unflipped (top-down). resurrections_msdf.png has 135 filled tiles at indices 0 to 134 and 3 extra at 153 to 155, which the preset drops; the glint atlas has 68 non-blank tiles in the same order. The font and its 138 code points are not used.
2. Leader frequency per string (the 1999 figure is one in five): the facades show white dots scattered through the streams, but no still resolves individual strings, so no per-string ratio is measured.
3. Motion and trail length of the 2021 rain, glyph change rate, and thin glint strokes: unmeasured, need clips or higher-resolution stills.
4. A Blu-ray or 4K frame of an in-world screen or a flat full-frame rain shot would give a single-layer lit fraction and tone ramp; none was found.

## Result (measured on the build)

`tools/checks/check_film.py --preset resurrections`, 1920 x 1080 FSR quality, the reference settings (`depth` true), mean of t = 6, 9, 12 and 15 s, top 10 percent cropped. Built values: `bias` -0.58, `gamma` 1.3, `lanes` 1.43, `bloom` 0.6, `defocus` 0.12, `glint_gain` 0.12, near layer dim 0.7, density 0.2, soft 0.15.

| Value | Measured | Gate | Film target |
|---|---|---|---|
| Lit fraction | 0.378 | 0.25 to 0.50 | 0.38 (facades 0.33 to 0.52) |
| Tone buckets 40, 80, 120, 160, 200, 230 | 0.627, 0.222, 0.110, 0.051, 0.015, 0.006 | gated in `tools/checks/check_film.py` | 0.63, 0.23, 0.095, 0.047, 0.016, 0.007 |
| Near-white share of lit | 0.59 percent | 0.1 to 1.2 | 0.5 percent |
| Background median | (4, 17.8, 4) | r 1 to 4, g 10 to 18, b 1 to 6 | (3, 15, 3) |
| Lit hue median | 126.5 | 120 to 138 | 128 |
| Hue drift, 80-120 minus 200-230 bucket | 18.5 degrees | at least 6 | about 19 |
| Halo 50 / 10 percent | 4.0 px / 23.4 px | 3 to 6 / 12 to 45 (soft) | 4 px / 26 px (not a rain property) |
| Edge 10-90 rise | 3.0 px | 2.2 to 3.6 | 2.9 px |
| Cells | square, 71 columns at 1920 | 69 to 72 | square (70 is a Rezmason value; film main layer 52 to 68) |
| Glyph set | 135 tiles, atlas read unflipped | 135 | Resurrections set |
| Flat (depth off) | lit 0.218, edge 2.8 px, 50 percent halo 4.0 px | shape gates only | |

Comparison with the film-grab frame (check_film side-by-side): hue, soft skirt, green floor, square cells, glyph shapes and the dim far layer match in kind. The film maps the rain onto street geometry in perspective (facades, floor streams converging), which this rain cannot show. On the GPU the depth is a six-slice size spread (near glyphs up to 4 times the main cell), with no perspective geometry. Our rain is also more uniformly lit and its glyphs read sharper than the trailer frames, whose compression softens them.

