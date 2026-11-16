# Rain motion inside the picture (grid mode): diagnosis and plans

Status, 14 Nov 2026: Plan 1 is built, Plan 2 is partly built (the reveal latch is not done), and Plan 3 was built and then dropped (see below).

Plan 3 (flow-field bent lanes, `grid_flow`) was built and then dropped in favour of the existing perspective pass. Its code is not part of the repository.

## Problem (14 Nov 2026)

Once the picture is shown the rain stops moving; only glyphs change in place. Wanted: the rain keeps
falling, contained to the picture's visible areas, following the perspective and angles of what is shown.

## Diagnosis (scene.frag, `layer_color`, current defaults)

The rain is suppressed inside the picture and the picture is drawn as a near-static brightness map.

1. Main layer rain in revealed cells is 5 per cent: `col_r = base * ldf * (preg ? u_img_gfloor : 1)`,
   `grid_rain` 0.05. With `grid_scale` 0.45 (< 1) the main cells carry no picture either.
2. The fine and perspective passes, which draw the picture, have no rain at all: `fine ? 0.0`.
3. Other rain layers are dimmed to 4 per cent over the picture (`grid_back` 0.04, `main()`).
4. Picture level is mostly static: `plv * mix(1, pstr * lanef * boost, grid_string)` with `grid_string`
   0.3, so 70 per cent of the level ignores the string. With `grid_boost` 4 the string part clips at 1
   on most lit cells, so even that 30 per cent barely moves.
5. Churn-dropped strings (`rdrop`) get a constant `pstr` 0.5: those lanes are fully static.
6. White heads only on the arrival head (`phead` from `image_reveal_cell`), never afterwards.
7. Glyph change in "changing" lanes uses the global slot `u_gslot`, so glyphs flip in place on a clock,
   unrelated to any falling string. Static brightness plus clocked flips is the "rotating" look.
8. Fine passes count rows in fine cells, so the same rows-per-second runs at `csm` (0.45 to 0.9) of the
   surrounding rain's pixel speed.

Why it got this way: earlier tuning rounds aimed at recognisability (the 7/7 quiz on stills). Every step that
made a still read better (low `grid_rain`, low `grid_string`, high boost) removed motion. Stills could not
show the loss; an earlier check had already noted motion "could not be confirmed by eye" on stills.

The perspective geometry is partly there already: the perspective pass has fan lanes on floors, lanes
along perspective lines on walls (`grid_wall_dir`), and cells grow toward the viewer. None of it is
visible while nothing moves.

## Plan 1: the rain carries the picture (prerequisite, small)

Cell brightness = picture level x string envelope, so the picture is seen through falling strings.

- `L = plv * (hold + (1 - hold) * b^falloff)`, `b` the sawtooth already computed. New `grid_hold`
  (0.2 to 0.35) is the level a cell keeps between strings, the readability floor. Drop `grid_boost`
  clipping: normalise so the head of a string over the brightest cell is 1.
- Every lane inside the picture carries a string (no `rdrop` static lanes); density shows as trail
  length instead.
- White heads on every passage over a lit cell (`plv` > 0.3), in fine and perspective passes too.
- Glyph change tied to the string: a cell takes a new glyph when a head passes (slot from `ku`), plus the
  slow trail mutation; no `u_gslot` clock flips in picture cells.
- Fine-pass speed scaled by `1 / csm.y`, so pixel speed matches the rain around the picture.
- Keep `grid_back` (other layers stay dim over the picture), so the motion seen is the picture's own.
- Retire or repurpose: `grid_string`, `grid_boost`, `grid_lane` (lane share can stay as a mild variation).

Trade-off: a still reads less well than now (part of each column is between strings). `grid_hold` and
trail length are the dials. Judge by moving clips, not stills.

Scope: shader only, plus TUNING fields and one test.

## Plan 2: flow that follows the surfaces (builds on Plan 1)

- Floors: strings run from the horizon toward the viewer along the fan columns. Constant rows per second
  in the perspective grid already gives perspective-correct acceleration, because cells grow toward the
  viewer. Check `a` increases toward the viewer in every region (an earlier check found floor rows running both ways
  from the vanishing point).
- Walls: along the perspective lines toward the viewer (`grid_wall_dir` 1, already in), same direction
  rule. Ceiling: toward the viewer.
- Frontal objects and far walls: vertical, cell size and speed from disparity (near larger and faster,
  far smaller and slower), which gives parallax between the object and the wall behind it.
- Reveal latch on the same lanes the strings use (now the main grid's vertical lanes), so the picture
  forms from the horizon outward on floors and walls, so the picture stays rain-driven.
- Pictures with only an estimated vanishing point (cat, phone box, up-view, cafe): use the plane class
  from `digital_rain/surfaces.py` per region; where no plane is confident, vertical lanes.

Most risk is in the reveal-latch change (it touches the transition that is
has already tuned).

## Plan 3: per-region flow field (built, then dropped)

Store a flow direction per pixel (from plane gradients, or the disparity gradient for curved objects)
in the label texture's spare channel and run strings along it, so rain bends over a car bonnet or a
face. Locally rotated cell lattices would break the one-grid model and show seams at region boundaries;
the research compares that with a baked lane and distance-along-streamline map.

## Verification (all plans)

- Moving output, not stills: 3 to 5 s clips (frame sequence to GIF or MP4) at 1280 and 2560, picture
  settled and during arrival, film still beside.
- A number for "it moves": inside the revealed area, mean absolute frame-to-frame difference and the
  vertical shift found by phase correlation between frames 1/15 s apart, compared with the rain outside
  the picture. Today's code should score near zero shift inside; Plan 1 passes when the shift matches
  the rain outside (or the perspective speed for Plan 2).
- Re-run the recognition quiz on clips to see what readability Plan 1 costs.

## Built (14 Nov 2026)

Plan 1, in `layer_color`: picture level = `min(1, plv * lanef * grid_boost)` x `mix(1, b^grid_string_gamma, grid_string)`,
`b` the sawtooth; a churn-dropped string leaves the cell at `1 - grid_string`; white heads on every pass
over a cell with level > 0.3; picture cells change glyph per string (`ku`), not on `u_gslot`; fine and
perspective passes divide speed and trail length by `csm.y`. Defaults `grid_string` 0.75,
`grid_string_gamma` 2.5, `grid_boost` 3 (variant c). Variant b (0.9, 3, 3) is more film-like, picture weaker.

Plan 2: left wall streams reversed so both walls flow toward the viewer (`pleft`); flat depth passes get
parallax `speed *= 1 + grid_parallax * (depth - 0.5)`, `grid_parallax` 0.8. Floors already flowed toward the
viewer with perspective speed-up. Not done: reveal latch on the same lanes (touches the tuned arrival).

Measured (street photo, 1280, settled, envelope shift between frames 3 apart): plain rain 0.7 px/frame,
45 per cent of column bands falling; old picture 0.0, 4 to 6 per cent; variant b 0.7, 45 per cent; c 0.0 median,
28 per cent. Walls (sideways): left wall 46 per cent of strips flowing left against 12 right, right wall 37
right against 16 left; old: none.
