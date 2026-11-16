# Picture targets: reference images (15 Nov 2026)

Every change to how the rain forms pictures is judged against these three images, side by side, not by a
score alone. The files are in `film-reference-stills/picture-targets/` (git-ignored, so not part of the repository).

| File | What it is |
|---|---|
| `1-city-lit-windows.webp` | A city of dark towers in green haze, lit windows, thin rain falling through |
| `2-film-corridor.webp` | The film's code corridor with three figures at the far end |
| `3-objects-of-code.webp` | Nine single objects (cat, wolf, lips, couple, laptop, bottle, dog, face, car) made of code on black |

## What each one shows

1. City. Building bodies stay dark; detail is the lit windows, small bright points in a regular grid, plus
   faint edge lines. Rain is thin vertical lines over everything. Haze is lighter green, behind, never on
   top of the buildings.
2. Corridor. Walls are vertical columns of falling code: perspective shows in column spacing and glyph size
   shrinking toward the far end, never in the direction of fall. Floor and ceiling streams run toward the
   vanishing point. The figures are the brightest thing, dense and glowing, against a dark gap. Sparse large
   soft white glyphs drift over the top.
3. Objects. Black background. The object is made of fine code following its form, shaded by its own light
   (highlights, rim light on the silhouette, darker shadow side that still carries code). Rain falls
   vertically through it and drips on below it. The object is drawn finer and brighter than the rain.

## Shared rules

- Background is black: sky, space and plain backdrops carry only sparse rain.
- The subject is the brightest thing and is shaded by the photo's own light, not by depth.
- Streams follow the trajectory that suits the surface, not always straight down: down the
  faces of subjects and walls (converging on the sky in a view looking up between buildings), along floors
  and ceilings toward the vanishing point.
- Gravity follows the camera: level camera, rain runs straight down the faces; looking up
  between buildings, it comes from the sky toward the camera (outward from the sky); looking down, it falls
  away from the camera toward the point below.
- Detail is bright points and lines (windows, edges, rims) on a darker body that still has code.
- Rain passes through the subject and continues below it.
- The subject's code is denser than the background rain (references 1 and 3); in the corridor the whole
  frame is dense.

## How it is drawn (15 Nov 2026)

These settings are `image_layer.TUNING` fields; the shader reads them as uniforms.

- Own light. `surfaces.own_light_tone` sets the picture's tone at the label map's size, replacing the depth-led `coarse_tone` when `grid_own` is on:
  - open background is black;
  - the subject keeps at least `grid_body`, so a dark side still carries code;
  - light and shade above that come from the photo's luminance, blurred by `grid_own_blur` and shaped by `grid_own_gamma`;
  - small points brighter than their surroundings add highlights (`grid_highlight`).

  Depth no longer sets brightness (`grid_layer` 0, `grid_tone_far` 0).
- Open background. `surfaces.grow_open` grows the sky, space and backdrop masks over the black pixels they touch, up to the subject's edge. Without it a strip of false ground is left round a ship on black, and the outline pass draws it.
- Steady highlights. `grid_glow` is the share of the falling string's modulation that the brightest cells lose, so lit windows stay lit between strings.
- Outlines. Depth jumps, including the subject against open background, are drawn by an extra picture pass (`dcl` 3 in `scene.frag`). Its cells are `grid_outline` times the mid class's size, and it draws only cells whose outline strength is at least `grid_outline_min`. The other passes leave the outline out.
- Camera position. `surfaces.detect` flags a view looking up between buildings (`CAMERA_UP`): side walls, no floor or ceiling, and a tall strip of sky. The rain then streams radially out of a point just above the sky, toward the camera, and every non-sky pixel counts as a wall. A level camera streams straight down the faces (`grid_wall_dir` 0).
- Glyph size. The `glyph_scale` default is 0.5, finer than the film's column count (0.75), because the finer code read better at 2560x1440.
