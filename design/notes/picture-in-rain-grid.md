# Picture in the rain's own grid

Status: design note. The grid mode described under "As built" and in the update at the end is implemented. Scope: the GPU renderer (`assets/shaders/scene.frag`, `digital_rain/image_layer.py`, `digital_rain/gl_renderer.py`, the Mac and Windows GPU paths). The software renderer is out of scope until the GPU version is accepted.

## Why

The image layer draws the picture as its own glyph grid (`img_glyphs`), on a different cell size from the rain, and the rain steps back where the picture lands. Two grids disagree about three things at once: where a cell is revealed, how much rain is dimmed, and which glyph is on top. Every artefact reported on the Mac comes from that:

- big rain glyphs cut off part-way down where the dimming follows picture-cell edges
- black boxes and dark lanes where rain is zeroed but the picture draws nothing (sky, shadow)
- lanes that wait many seconds for a rain head while their neighbours are revealed
- the picture "settling" as larger tilted glyphs that read as a second layer

Patches since 13 Nov (pixel-lane reveal, screen blend, sky floor, fallback front, real-head removal) reduce these but leave the structure. A film reference (the Neo corridor shot, hard cut at about 38 s) shows the target.

## Target look (from the film frames)

1. One grid. The picture is carried by ordinary rain columns of a single width across the frame. Brightness per glyph shows the figures, corridor edges and the perspective floor.
2. Dark areas keep rain. Walls and sky have dim glyph columns running through them. No black rectangles and no bare patches.
3. A few large soft white particles drift over the top, sparse, never clipped or boxed.
4. Detail comes from brightness changing along each column, not from a finer second grid.
5. Arrival and removal are carried by the rain heads themselves. No wall that wipes the old picture without rain behind it.

## Precedent already in the shader

The rain message uses a head-latched cell (`mlat` in `layer_color`): a cell lights when the first head of its own lane lands on it after the reveal time, stays lit until the first head after the deletion time, and the rain is otherwise untouched. That is the arrival and removal behaviour wanted for the picture. The proposal generalises that latch from a boolean letter mask to a per-cell picture level, inside `layer_color`, on the rain layers' own grids.

## Design

### 1. Per-cell picture level in layer_color

For a cell of layer L, sample the picture once at the cell centre, mip-filtered to the cell size, and compute a level with the existing tone, edge, open-region and surface functions (`img_surface`, `img_level`), evaluated per cell instead of per pixel. A lit picture cell shows a glyph at that level. The glyph change rate and the head glow follow the existing rain rules, so picture glyphs look like rain glyphs. Final brightness of a cell is `max(rain, picture)`.

### 2. Depth picks the layer

The three layers are scale 0.65 (far, dim), 1.0 (main) and 1.8 (near, soft). The picture's depth value (vanishing-point model, depth field, or the fake depth from roughness) assigns each picture cell to one layer, so a region is drawn at one size only and coverage is not tripled. Near surfaces use the big layer, far surfaces the fine one. The perspective rows of the floor come from the depth field's row coordinate; whether the per-layer grid can carry that, or the floor stays on the main grid with a gentle row warp, is open decision 2.

### 3. Rain is not dimmed

No `keep` or zeroing. In dark and open picture areas the rain stays at a reduced level (a tunable, starting near 0.35), so the sky and shadow match the film. The big soft particles are layer 3's own sparse rain and stay as they are.

### 4. Arrival and removal

Each layer's lanes latch on their own first head, as the message does.

As built (TUNING `grid_hold`, on by default). No fades, cross-fades or hard cuts anywhere: the rain itself forms and removes the picture.

- Arrival: a cell takes the picture when the first lit head after the picture's start reaches it. Strings already on the cell at the start do not count. Behind that head the bringing string lights the picture and hands over to the picture's own streams (the lane opens out from the main cell to the fine cells). A lane with no head after 6 to 9 s gets a backstop with the same latch.
- Removal: after the exit front passes a cell, it keeps the picture until a lit main-lane string covers it (base at least half the head's level, gamma-aware), so rain replaces the picture glyph by glyph and gaps between strings keep it. Backstop 6 to 9 s per lane.
- Exit hold (preset key `exit_hold`, 0 off): for a per-lane window from the end time to 5 to 9 s after it, no main-layer string is dropped by churn, and every string keeps its trail at `top * b^exit_hold`. Without it, lanes that drop strings (film_1999's clustered lanes, Reloaded's density 0.8) leave picture waiting for the backstop, which then clears it into black. film_1999 uses 1.5 (also fills its gaps while the picture leaves); Reloaded uses 2.8, its own gamma, so only the churn part changes anything. Resurrections drops no strings and leaves it off. Whole strings only: gaps and churn come back with the first head after the window.
- Timing semantics are kept: `image_period` is how long a picture is held from its start, `image_gap` is added on top of it.

### 5. What goes

`img_glyphs`, `image_reveal` dimming, the settle growth and tilt, the per-pixel `img_orient` taps, and the `image_layer.glsl` fine-detail underlay (a dim second picture under the glyphs, absent from the film). That also removes the heaviest per-pixel work in the scene pass.

## Open decisions

1. Detail slider. With three layers the finest glyph is 0.65 of the main cell. High Detail could add a fourth, finer layer (about 0.4) used only for far regions, or map Detail to how much of the picture goes to the far layer. Recommendation: fourth layer, enabled by Detail above 0.5.
2. Perspective rows. Recommendation: keep rows and columns on each layer's grid and accept less exact floor perspective at first. Revisit if the floor reads flat.
3. Fallback to the current renderer. Recommendation: keep it behind an `image_mode` setting (`grid` or `classic`) until the new one is accepted, then remove classic and its tests.
4. Software renderer. Out of scope now. Needs its own plan once the look is agreed.

## Phases

Each phase ends with rendered frames at the reference settings (resurrections preset, 20 s per image, 15 s between, Detail 1.00, 2560x1440 and 1280x720) shared for review before the next starts.

1. Main layer only: per-cell picture level and head latch in the main layer, no rain dimming, classic path untouched behind `image_mode`. Compare the settled frame with the film stills.
2. Depth assignment across the three layers.
3. Detail (fourth layer) and the dark/open rain floor tuning on all seven test photos.
4. Arrival and removal tuning, including the fallback latch and the slow release. Check the 37 s style cut look and a full 20/15 cycle.
5. Remove classic, update dialog text, README, the image-layer tests and the golden frames.

## Acceptance

- Settled frame: no 24 px blocks darker than the surrounding rain in sky or shadow, uniform lane brightness (no lanes under 70 % of the median), picture readable at thumbnail size.
- Arrival: picture fully formed within about 5 s of its start at the reference settings. No plain rain lanes left beside revealed ones.
- Removal: no black lanes while the old picture goes. Rain returns on the heads.
- Frame cost on the Mac no worse than the current renderer at 2560x1440 (the last log showed 59.9 fps at that size).
- Tests: image-layer unit tests updated, golden frames regenerated for the image cases, full suite green.

## Risks

- A level per cell is coarser than the per-pixel sampling used now. Mitigation: mip-filtered sampling and the fourth layer.
- Moving the latch into `layer_color` touches the message code that shares it. Mitigation: share the latch helper, keep the message tests.
- The look is judged by eye. Mitigation: the phase review points above, with the film stills as the reference.

## Update, 15 Nov 2026 (legibility work)

The reference images (`picture-targets.md`) now decide the look, and some of the target rules above have changed:

- Rule 1 (one grid) and rule 4: outlines are drawn by a pass of their own in finer glyphs (`grid_outline`), and the default glyph size is now 0.5.
- Rule 2: sky, space and plain backdrops are black, with only sparse rain (`surfaces.grow_open`, `sky_mask`, `space_mask`).
- Brightness comes from the photo's own light, not depth (`surfaces.own_light_tone`, `grid_own`).
- Streams follow the camera position (`surfaces.CAMERA_UP`, `grid_wall_dir` 0).

The details are in `picture-targets.md`, under "How it is drawn".
