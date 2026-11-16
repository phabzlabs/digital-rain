"""Film look presets (design/film-reference.md) and the helpers both renderers share.

`resolve(cfg)` turns the user's settings into one flat "look" dict. Presets
override the governed keys (color, bloom, scanlines, interlace, vignette,
flicker, trail_falloff); `custom` passes the user's sliders through unchanged.
"""

import json
import math

import numpy as np

from digital_rain import resources
from digital_rain.settings import (
    CELL_H,
    CELL_W,
    COLORS,
    PRESET_NAMES,
    PRESET_TITLES,
    SPEED_ROWS_PER_SEC,
)

PULSE_P = 1.0  # seconds between stammers
PULSE_H = 0.0625  # seconds the pulse clock stands still (one row at 16 rows/s)


def _hex(s):
    s = s.lstrip("#")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))


def _stops(pairs):
    """[[position 0..255, "RRGGBB"], ...] -> [(position 0..1, (r, g, b)), ...]."""
    return [(p / 255, _hex(c)) for p, c in pairs]


def _tuples(val):
    return tuple(_tuples(v) for v in val) if isinstance(val, list) else val


def load_preset(name):
    """assets/presets/<name>.json as a look dict. Lists become tuples, except the
    palette (a list of stops) and the per-look `layers` (a list of dicts); keys
    starting with "_" are notes and are dropped."""
    raw = json.loads(resources.read_text("presets", name + ".json"))
    out = dict(label=PRESET_TITLES[name])
    for key, val in raw.items():
        if key.startswith("_"):
            continue
        if key == "palette":
            val = _stops(val)
        elif key != "layers":
            val = _tuples(val)
        out[key] = val
    return out


# Film presets live in assets/presets (one JSON file each), shared by every build.
PRESETS = {name: load_preset(name) for name in PRESET_NAMES if name != "custom"}

# Keys that later looks added, and the values that skip their code paths.
NEUTRAL = dict(
    step_fps=0.0,
    gamma=1.0,
    crossfade=False,
    defocus=0.0,
    pyramid=False,
    glow_r=(0, 0, 0, 0),
    glow_g=(0, 0, 0, 0),
    grain_ink=0.0,
    lanes=1.0,
    lead_core=1.0,
    glyph_set="classic",
    columns=0,
    glint_gain=0.0,
    layers=None,
    ink_fill=None,
    lead_glow=0.0,
    lead_cap=0.0,
    cluster=None,
    ink_dots=None,
    depth_slices=None,
    depth_jitter=0.0,
    # final palette: brightness below toe eases to black (smoothstep), so faint haze sits at the
    # film's floor
    toe=0.0,
    # grid exit: no churn drops and trails held at top * b^exit_hold while the picture leaves
    exit_hold=0.0,
)
# Preset keys a preset may leave out.
OPTIONAL_KEYS = (
    "ink_fill",
    "lead_glow",
    "lead_cap",
    "cluster",
    "ink_dots",
    "depth_slices",
    "depth_jitter",
    "toe",
    "exit_hold",
)


def cell_px(look, width_px, layer_scale, glyph_scale, dpi_k):
    """(cw, ch) of one cell in the renderer's pixels. Neutral `columns` 0 is the
    classic 20:28 cell; above 0 the cell is square and sized from the monitor
    width (render pixels) so that about `columns` fit across; the DPI
    and `cell_scale` do not enter. The shader computes the same in float32."""
    cols = look.get("columns", 0)
    if cols > 0:
        f32 = np.float32
        c = max(
            4,
            int(
                np.floor(f32(width_px) / f32(cols) * f32(layer_scale) * f32(glyph_scale) + f32(0.5))
            ),
        )
        return c, c
    s = (
        np.float32(layer_scale)
        * np.float32(dpi_k)
        * np.float32(float(glyph_scale) * float(look.get("cell_scale", 1.0)))
    )
    return (
        int(np.floor(np.float32(CELL_W) * s + np.float32(0.5))),
        int(np.floor(np.float32(CELL_H) * s + np.float32(0.5))),
    )


def step_time(t, fps):
    """The clock a 24 fps camera sees. `t` unchanged when fps <= 0; the
    epsilon stops k / fps landing on frame k - 1 through rounding."""
    if fps <= 0:
        return t
    return math.floor(t * fps + 1e-6) / fps


def glyph_phase(t, period, fps, crossfade):
    """(slot, prev_slot, mix) of the synchronised changing glyphs. With a
    frame rate the slot advances every round(period * fps) frames and, with
    crossfade, the first frame of each slot shows a 50 percent mix with the
    previous glyph. Integer frame arithmetic (a float test misfires)."""
    if fps > 0:
        frames = max(1, round(period * fps))
        n = math.floor(t * fps + 1e-6)
        slot = n // frames
        mix = 0.5 if crossfade and n % frames == 0 else 0.0
        return int(slot), int(slot) - 1, mix
    slot = math.floor(t / period)
    return int(slot), int(slot) - 1, 0.0


def palette_rgb(stops, x):
    """Piecewise-linear colour lookup, in the units of `stops` ([(position,
    (r, g, b))] sorted by position). Scalars or numpy arrays."""
    pos = np.array([s[0] for s in stops], float)
    cols = np.array([s[1] for s in stops], float)
    xa = np.asarray(x, float)
    out = np.stack([np.interp(xa, pos, cols[:, i]) for i in range(3)], axis=-1)
    return out


def wobble(x):
    """Speed wobble inside a column, in sawtooth-tooth units."""
    return x + 0.3 * np.sin(math.sqrt(2) * x) + 0.2 * np.sin(math.sqrt(5) * x)


def pulse_time(t, on):
    """The 1999 'stammer': the clock stands still for H at the start of every
    period P, then runs fast until it meets real time again. Lag is 0..H."""
    if not on:
        return t
    n = math.floor(t / PULSE_P)
    u = t - n * PULSE_P
    if u < PULSE_H:
        return n * PULSE_P
    return n * PULSE_P + (u - PULSE_H) * PULSE_P / (PULSE_P - PULSE_H)


def lane_hash(a, b):
    """Software-renderer hash in 0..1 on int64 arrays. The XOR of two products
    is the core; the finaliser avalanches it so that different salts `b` give
    independent values for the same lane."""
    x = (np.asarray(a, np.int64) * 73856093) ^ (np.asarray(b, np.int64) * 19349663)
    x &= 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13
    x = (x * 3266489917) & 0xFFFFFFFF
    x ^= x >> 16
    return (x & 0xFFFFFF) / float(2**24)


def cluster_gain(lanes, seed, period, amount):
    """Normalised lane gain (scene.frag u_clus): 1 + A (2 n - 1) over its mean on `lanes`."""
    xc = np.asarray(lanes, np.float64) / period
    i0 = np.floor(xc)
    fr = xc - i0
    n0 = lane_hash(i0.astype(np.int64) + seed, 9)
    n1 = lane_hash(i0.astype(np.int64) + 1 + seed, 9)
    g = 1.0 + amount * (2 * (n0 + (n1 - n0) * fr * fr * (3 - 2 * fr)) - 1)
    return g / g.mean()


def resolve(cfg):
    """settings dict -> flat look dict. Does not change `cfg`."""
    name = cfg.get("preset", "custom")
    look = dict(direction=cfg.get("direction", "down"), pulse=bool(cfg.get("pulse", False)))
    if name not in PRESETS:
        base, head = COLORS[cfg["color"]]
        look.update(
            name="custom",
            film=False,
            model="drop",
            label="Custom",
            speed=SPEED_ROWS_PER_SEC,
            tooth=75.0,
            contrast=1.1,
            bias=-0.5,
            flat=-1.0,
            lead_ratio=1.0,
            cursor=tuple(c / 255 for c in head),
            cursor_gain=1.0,
            palette=[],
            cycle=(0.56, 0, 0.0),
            cell_scale=1.0,
            hipass=0.0,
            grain=0.0,
            bloom=cfg["bloom"],
            scanlines=cfg["scanlines"],
            interlace=cfg["interlace"],
            vignette=cfg["vignette"],
            flicker=cfg["flicker"],
            falloff=cfg["trail_falloff"],
            base=base,
            head=head,
            **NEUTRAL,
        )
        return look
    preset = PRESETS[name]
    look.update(preset)
    for key in OPTIONAL_KEYS:
        look.setdefault(key, NEUTRAL[key])
    look.update(name=name, film=True, model="saw")
    stops = [(pos, tuple(c / 255 for c in rgb)) for pos, rgb in preset["palette"]]
    look["palette"] = stops
    look["cursor"] = tuple(c / 255 * preset["cursor_gain"] for c in preset["cursor"])
    look["falloff"] = cfg["trail_falloff"]
    look["base"] = tuple(float(c) * 255 for c in palette_rgb(stops, 0.706))
    look["head"] = tuple(c * 255 for c in stops[-1][1])
    return look
