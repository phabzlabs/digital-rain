# Film research

The three film looks, The Matrix (1999), Reloaded (2003) and Resurrections (2021), are built from measurements of film frames. This page summarises that research and links to the full documents in the repository. The settings that result are in [[Settings-reference]], and the checks that hold each look to its targets are in [[Checks-and-tests]].

## Reason for the research

There is no official specification of the digital rain, and a stock Japanese font, a plain green and CRT effects look different from the film. The research asked what the film frames show and recorded each answer as a number with a source and a confidence note. Presets are tuned against those numbers, and the checks catch a later change that drifts from them.

## Sources

The research used four kinds of source, all outside this repository.

| Source | Used for |
|---|---|
| Rezmason's open-source WebGL recreation of the rain | Parameters, glyph atlases and the font. Its numbers are the author's reconstruction tuned by eye against the films, so confidence is high for intent and medium for exact values. |
| Carl Newton's frame-by-frame analysis of the 1999 opening | Behaviour: fixed glyphs, how strings start and end, deletion, glyph changes and the stammer. |
| Film stills from public screenshot galleries (Blu-ray and 4K regrades) | Colour, grain, glow, edge softness, row and column pitch, tone distribution. |
| Trailer frames for the 2021 film | Colour and layering where no better frames could be found. |

The reference stills and fan GIFs are third-party film material. They are not distributed with the project, and they are not part of the repository. The measurement tools and checks use them when they are present locally and skip them otherwise. The sources of each file are listed in `assets/README.md`.

## Measurements

`tools/dev/measure_reference.py` measures each still. A pixel counts as lit when its brightest channel is above 40. The tool reports:

* the share of lit pixels
* median hue and saturation of lit pixels
* the tone distribution in six brightness buckets
* the share of near-white pixels, and the colour of the brightest ones (the leaders)
* row pitch and column spacing, which give the glyph cell size
* halo width, as the distance at which brightness falls to 50 and 10 percent outside bright glyphs
* edge rise, the width of a glyph edge from 10 to 90 percent
* ink grain and background grain

Distances are scaled to a 1915 pixel wide frame. Each finding records how many stills confirm it and their grade, because a Blu-ray grade and a 4K regrade show different hues.

## Findings

### The Matrix (1999)

Full document: [film-reference.md](https://github.com/phabzlabs/digital-rain/blob/main/design/film-reference.md), with 25 numbered findings.

* The rain is brightness moving through glyphs that stay in place. Each cell keeps its glyph, and a drop is a wave of light down a column. Several drops share a column and never collide.
* The glyph set has 57 entries (33 katakana, the digits except 6, a lowercase z, a blank and a few symbols). The shapes are a custom blocky face, not a stock Japanese font. Mirroring is selective: all katakana are mirrored, the digits 2, 5 and 9 are mirrored horizontally, and 3 is flipped vertically.
* The green is blue-green, not yellow-green. Lit pixels measure hue 152 to 154 degrees on the Blu-ray still.
* Leaders are near white with a faint cool cast.
* The film advances light one whole cell at a time. It runs at 24 frames per second, and changing glyphs switch together about eight times a second.
* The film shows heavy grain and soft defocus, with no scanlines, interlacing or CRT vignette. The scanline look belongs to other screensavers, which is why the film presets turn those effects off and Custom keeps them.
* The 1999 opening has about 78 columns across the frame.

### Reloaded and Revolutions (2003)

Full document: [film-reference-reloaded.md](https://github.com/phabzlabs/digital-rain/blob/main/design/film-reference-reloaded.md).

* Fourteen stills were measured: 13 from the Revolutions 4K regrade and one Blu-ray-grade Reloaded still. The Blu-ray still has a different hue (125 degrees), so the preset follows the 4K grade and the document records the choice.
* Lit hue is 147 to 157 degrees in all 13 4K stills.
* There is no near-white leader. The head is saturated mint.
* The lit fraction is 0.27 to 0.32 in upright full-frame rain, and the tone distribution has a heavy bright bucket.
* The titles zoom through several scales at once, which one preset cannot reproduce. The existing Depth setting gives three scales instead.
* No 2003 motion source was found, so fall speed, glyph change rate and stepping are not measured for this look.

### Resurrections (2021)

Full document: [film-reference-resurrections.md](https://github.com/phabzlabs/digital-rain/blob/main/design/film-reference-resurrections.md).

* The research found no Blu-ray or 4K screenshot gallery with code rain, so the stills are one film frame and trailer frames. Ten of the twelve show the same street shot, and the document says so. It records the grade of each still and keeps the lossy trailer frames for measurement only.
* Cells are square. The 70 columns across the long side come from Rezmason's configuration, not from a measurement, and the measured pitch is close to it.
* The background is a green floor of about `#030F03`, not black.
* Median hue is 128 degrees, and leaders are sparse, small and pale lime (near-white pixels about 0.5 percent of lit pixels).
* The look uses the 135-glyph Resurrections set. The stills show stacked depth. The floor pitch grows about 1.6 times toward the camera, and near facades are 1.6 to 1.8 times the size of far ones. The preset has three depth layers for this reason.
* Motion, stepping, glyph change rate and trail length are not measured and use Rezmason's values.

## Pictures in the rain

Three design notes in `design/notes/` record the work on pictures that the rain draws (the In the rain mode):

* [picture-in-rain-grid.md](https://github.com/phabzlabs/digital-rain/blob/main/design/notes/picture-in-rain-grid.md) explains why the picture should live in the rain's own grid. Two grids that disagreed about what is revealed, how much rain is dimmed and which glyph is on top caused visible artefacts such as cut-off glyphs and black boxes.
* [rain-motion-in-picture.md](https://github.com/phabzlabs/digital-rain/blob/main/design/notes/rain-motion-in-picture.md) diagnoses why the rain stopped moving once a picture was shown. It lays out plans to keep the rain falling inside the picture, following perspective. A flow-field variant was built from one of those plans and rejected in favour of the existing perspective pass.
* [picture-targets.md](https://github.com/phabzlabs/digital-rain/blob/main/design/notes/picture-targets.md) describes three reference images for judging the result side by side, not by a score alone. They show a city of dark towers with lit windows, the film's code corridor with figures at the far end and an object of fine code shaded by its own light. The images are third-party material and are not distributed.

The notes share three rules: the subject is the brightest thing, the background keeps sparse rain, and streams follow the surface instead of always falling straight down. [[Design-decisions]] covers how they shaped the code.

## Credit for the research sources

The glyph atlases and the film font come from Rezmason's matrix project under the MIT licence. The analysis of the 1999 behaviour draws on Carl Newton's study. [[Licensing-and-credits]] has the details. Warner Bros. owns the film, and this project is unofficial.
