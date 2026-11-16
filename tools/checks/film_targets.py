"""Gate configuration of tools/checks/check_film.py: the frame size and times, the per-preset
settings and the per-preset measurement windows. Kept apart so other checks (the software saver
hue gate) read the same numbers.
"""

SIZE = (1920, 1080)
TIMES = (6.0, 9.0, 12.0, 15.0)
SCALE = 1915.0 / 1920.0
# Settings each preset is measured with; everything else is default.
PRESET_CFG = {
    "film_1999": dict(pulse=True, depth=False, upscaling="quality"),
    "reloaded": dict(pulse=False, depth=False, upscaling="quality"),
    "resurrections": dict(pulse=False, depth=True, upscaling="quality"),
}
# Lit-pixel brightness buckets (max channel) the TARGETS "buckets" windows refer to.
BUCKETS = ((40, 80), (80, 120), (120, 160), (160, 200), (200, 230), (230, 256))
# Gate windows per preset, lo to hi. film_1999: stills of design/film-reference.md sections 4 and
# "Glyph size and clarity"; reloaded: design/film-reference-reloaded.md; resurrections:
# design/film-reference-resurrections.md (street-shot crops). Where a window is wider than the
# stills, the saver's own measured value sits inside it.
#   lit      share of lit pixels (max channel > 40) after the 10 percent top crop
#   buckets  share of lit pixels in each BUCKETS bucket
#   white    percent of lit pixels near white (min channel > 200)
#   head     colour of the brightest 0.5 percent (reloaded only)
#   bg       median background colour per channel;  hue  median lit hue in degrees
#   h50/h10  glow radius (px) where a bright glyph falls to 50 and 10 percent
#   edge     10 to 90 percent edge rise in px;  run  brightest column run (reloaded)
#   cols/fill/row  ink columns, stroke fill and row pitch at 1915 px wide
#   clarity/followup  also gate the CLARITY_GATES / FOLLOWUP_GATES below
TARGETS = {
    "film_1999": dict(
        lit=(0.18, 0.33),
        buckets=(
            (0.25, 0.55),
            (0.05, 0.25),
            (0.05, 0.25),
            (0.05, 0.25),
            (0.05, 0.25),
            (0.02, 0.12),
        ),
        white=(1.0, 2.4),
        head=None,
        leader=True,
        clarity=True,
        followup=True,
        bg=dict(r=(1, 4), g=(2, 16), b=(3, 9)),
        hue=(152, 155),
        h50=(1.5, 3.0),
        h10=(4.5, 14.0),
        edge=(1.8, 3.2),
        run=None,
        cols=(40, 60),
        fill=(0.30, 0.45),
        row=(33.0, 38.0),
    ),
    "reloaded": dict(
        lit=(0.25, 0.34),
        buckets=(
            (0.20, 0.50),
            (0.12, 0.28),
            (0.06, 0.20),
            (0.04, 0.14),
            (0.04, 0.14),
            (0.08, 0.38),
        ),
        white=(0.0, 0.5),
        head=dict(r=(20, 80), g=(230, 255), b=(150, 205)),
        leader=False,
        bg=dict(r=(0, 1.5), g=(1, 10), b=(0, 8)),
        hue=(148, 158),
        h50=(1.5, 3.5),
        h10=(3.5, 18.0),
        edge=(2.0, 3.4),
        run=10.0,
        cols=(34, 50),
        fill=(0.35, 0.50),
        row=(29.0, 34.0),
    ),
    # The 10 percent halo is a wide sanity window (the film's 26 px is not a rain property).
    "resurrections": dict(
        lit=(0.25, 0.50),
        buckets=(
            (0.45, 0.75),
            (0.15, 0.30),
            (0.05, 0.14),
            (0.02, 0.08),
            (0.003, 0.03),
            (0.001, 0.015),
        ),
        white=(0.1, 1.2),
        head=None,
        leader=False,
        bg_mode="dark",
        bg=dict(r=(1, 4), g=(10, 18), b=(1, 6)),
        hue=(120, 138),
        h50=(3.0, 6.0),
        h10=(12.0, 45.0),
        edge=(2.2, 3.6),
        run=None,
        grain=(0.0, 0.10),
        grain0=0.10,
        bggrain_info=True,
    ),
}

# Second size for the high-DPI gates (monitor dpi 1.5).
BIG_SIZE = (2880, 1800)
BIG_DPI = 1.5

# Clarity gate windows (film_1999): key, label, lo, hi, format. None is an open side. Measured
# on the Blu-ray opening stills resampled to 1915 px wide (design/film-reference.md) and swept
# over the film_1999 settings; ring r/g and b/g were judged by eye against the stills.
# core_b_r and p200 are guards that keep the clarity look inside the film's range.
CLARITY_GATES = (
    ("dark", "dark share in bright ink boxes", 0.18, 0.45, "{:.3f}"),
    ("aspect", "ink box aspect h/w", 1.35, 1.65, "{:.3f}"),
    ("lt150", "glyph peaks under 150", 0.0, 0.09, "{:.3f}"),
    ("p200", "glyph peaks above 200 (guard)", 0.62, None, "{:.3f}"),
    ("core_mean", "leader core mean", 218.0, None, "{:.1f}"),
    ("core_b_r", "leader core b - r (guard)", 5.0, None, "{:.1f}"),
    ("ring_r_g", "leader ring r/g (by eye)", 0.45, 0.95, "{:.3f}"),
    ("ring_b_g", "leader ring b/g (by eye)", 0.85, 1.2, "{:.3f}"),
    ("band_sat", "band 200-239 saturation", 0.75, None, "{:.3f}"),
    ("bg_gx", "background green excess g - max(r, b)", None, 4.0, "{:.1f}"),
)

# Follow-up gate windows (film_1999 on MONITORS monitors, each with its own rain seed, the gate
# is the mean): leader openness, column clustering index, leader columns on 2.39:1 bands,
# near-white share of lit and the ink dot peak. Measured on the same stills, 2.39:1 bands being
# the shape of the wide stills.
MONITORS = 8
FOLLOWUP_GATES = (
    ("open", "leader openness", 0.30, 0.70, "{:.3f}"),
    ("ci", "clustering index", 1.30, 1.80, "{:.2f}"),
    ("lc239", "leader columns 2.39:1", 0.07, 0.27, "{:.3f}"),
    ("wp", "near-white percent of lit", 1.45, 1.80, "{:.2f}"),
    ("dot_y", "ink dot peak, y prominence", 2.0, None, "{:.2f}"),
)
