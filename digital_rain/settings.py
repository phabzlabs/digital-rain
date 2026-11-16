"""User settings (settings.json, see osapi for where) and the look-and-feel
constants shared by both renderers.

The saver only reads settings (load); only the settings dialog writes them (save).
On Windows both use the same file. On Mac the options sheet (mac_options.py)
saves one JSON blob to ScreenSaverDefaults, validated by clean(), and the
settings.json file is only read when nothing was saved there (mac_settings.py).
"""

import contextlib
import json
import os
import tempfile

from digital_rain import osapi

CELL_W, CELL_H = 20, 28  # grid cell in px at scale 1.0 (glyph centred inside)
FONT_SIZE = 26  # px at scale 1.0
FILM_FONT_SIZE = round(CELL_W * 1.05)  # Matrix-Code.ttf px at scale 1.0
SPEED_ROWS_PER_SEC = (9.0, 28.0)
TRAIL_LEN_ROWS = (10.0, 38.0)

# Depth: three parallax layers drawn far -> near and added together.
#   scale   glyph/cell size vs. the middle layer
#   dim     brightness of the layer (distance haze)
#   speed   fall-speed multiplier (rows/s; pixels/s also grows with scale)
#   density fraction of columns that rain at once
#   trail   trail-length multiplier
#   soft    0..1 defocus (the near layer is out of focus)
LAYERS = [
    dict(scale=0.65, dim=0.40, speed=0.9, density=0.6, trail=1.2, soft=0.0),
    dict(scale=1.00, dim=1.00, speed=1.0, density=0.7, trail=1.0, soft=0.0),
    dict(scale=1.80, dim=1.00, speed=0.9, density=0.12, trail=0.5, soft=0.55),
]

# name -> (trail color, head color)
COLORS = {
    "film": ((0, 255, 70), (205, 255, 220)),
    "classic": ((0, 255, 0), (210, 255, 210)),
    "amber": ((255, 176, 0), (255, 235, 190)),
    "red": ((255, 40, 30), (255, 215, 205)),
    "blue": ((40, 150, 255), (210, 235, 255)),
    "white": ((215, 225, 255), (255, 255, 255)),
}

# The film has Neo's screen messages; they type out over the rain now and then.
PHRASES = [
    "Wake up, Neo...",
    "The Matrix has you...",
    "Follow the white rabbit.",
    "Knock, knock, Neo.",
]

# Live load mode and rain message choices (see live_load.py, rain_message.py).
LIVE_SOURCES = ("off", "cpu", "gpu")
LIVE_TARGETS = ("speed", "density", "both")
MESSAGE_MODES = ("off", "clock", "text", "both", "clock_fixed")
# clock_fixed: the clock stays up all the time in one of nine screen segments.
CLOCK_POSITIONS = (
    "top_left",
    "top_center",
    "top_right",
    "middle_left",
    "middle_center",
    "middle_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
)
MESSAGE_TEXT_MAX = 24
MESSAGE_FONT_MAX = 128  # longest font family name kept
MESSAGE_FONT_REF_PT = 36  # message_font_size of the standard size (72 is twice as big)
DEFAULT_MESSAGE_FONT = "Courier New"  # what an empty message_font means

# AMD FSR 1.0 upscaling: name -> how many times fewer pixels per axis are rendered
UPSCALE_RATIO = {"off": 1.0, "quality": 1.5, "balanced": 1.7, "performance": 2.0}

# Look presets (see looks.py) and the direction the rain travels.
PRESET_NAMES = ("custom", "film_1999", "reloaded", "resurrections")
PRESET_TITLES = {
    "film_1999": "The Matrix (1999)",
    "reloaded": "Reloaded (2003)",
    "resurrections": "Resurrections (2021)",
}
DIRECTIONS = ("down", "sideways", "diagonal")
# The settings a single monitor can override (see "monitors" in DEFAULTS).
OVERRIDE_KEYS = ("preset", "color", "speed", "density", "depth")

DEFAULTS = {
    "preset": "film_1999",  # custom | film_1999 | reloaded | resurrections
    "direction": "down",  # down | sideways | diagonal
    "pulse": False,  # the 1999 "stammer": rain pauses together, then catches up
    "color": "film",
    "bloom": 0.5,  # 0..1 glow strength
    "scanlines": 0.45,  # 0..0.9 darkness of the scanlines
    "interlace": True,  # alternate even/odd scanline fields every frame
    "vignette": 0.35,  # 0..1 darkening toward the monitor corners
    "flicker": 0.03,  # 0..0.2 subtle global brightness jitter
    "speed": 1.0,  # 0.4..2.5 fall speed multiplier
    "density": 1.0,  # 0.3..1.6 how many columns rain at once
    "glyph_scale": 0.5,  # 0.25..2.0 glyph size multiplier
    "trail_falloff": 1.6,  # 0.6..4 trail fade curve (higher = shorter glow)
    "depth": True,  # three parallax layers instead of one
    "easter_egg": True,  # occasional typed "Wake up, Neo..." messages
    "renderer": "auto",  # auto | gpu | software
    # auto | off: HDR output (bright heads) when the display has HDR on, GPU full screen only
    "hdr": "auto",
    # 200..2000 nits: how bright the HDR highlights get (Windows: at most 8x the SDR white
    # level; Mac: nits at about 100 nits SDR white, within the display's EDR limit)
    "hdr_peak": 1000.0,
    # 15..240 fps ceiling on the frame rate (Windows); never above the display's refresh rate
    "frame_cap": 60.0,
    "font_path": "",  # optional TTF/OTF replacing the glyph font
    # optional folder of images the rain fades in and out (GPU, film presets, travel down)
    "image_dir": "",
    # also read the pictures in every subfolder of image_dir (hidden and system folders skipped)
    "image_subfolders": False,
    "image_order": "sequence",  # sequence | shuffle: the order the folder's images form
    # grid: the picture is drawn inside the rain's own cells; classic: its own glyph grid over
    # the rain
    "image_mode": "classic",
    "image_period": 30.0,  # 5..300 s each image is shown
    # 0..30 s of plain rain between images (0: the next sweeps straight over)
    "image_gap": 0.0,
    # 0..1 image glyph detail: 0 the standard sizes, 1 tiny far glyphs for fine detail
    "image_detail": 0.0,
    "upscaling": "off",  # off | quality (1.5x) | balanced (1.7x) | performance (2x), AMD FSR 1.0
    # (grid picture mode on a canvas 2000 px wide or more renders at quality at least)
    "sharpness": 0.2,  # 0..2 FSR sharpening in stops (0 = sharpest, AMD default 0.2)
    "live_source": "off",  # off | cpu | gpu: machine load that drives the rain
    "live_target": "both",  # speed | density | both
    "live_strength": 0.6,  # 0..1 how far the load moves speed and density
    "message": "off",  # off | clock | text | both: a message formed in the rain
    "message_text": PHRASES[0],  # custom message text (cleaned, 24 characters at most)
    "clock_position": "top_right",  # segment of the 3 x 3 screen grid for message clock_fixed
    "clock_24h": True,  # clock message as HH:MM (False: 12-hour, no AM/PM)
    # point size of the message letters, from the OS font picker (36 pt: the standard size)
    "message_font_size": 36.0,
    # font family of the message letters, from the OS font picker ("": Courier New)
    "message_font": "",
    "message_bold": True,  # bold letters (thin strokes can break up in the rain)
    "message_italic": False,
    "monitors": {},  # monitor id -> {name, and any of OVERRIDE_KEYS}
}
RANGES = {
    "bloom": (0.0, 1.0),
    "scanlines": (0.0, 0.9),
    "vignette": (0.0, 1.0),
    "flicker": (0.0, 0.2),
    "speed": (0.4, 2.5),
    "density": (0.3, 1.6),
    "glyph_scale": (0.25, 2.0),
    "trail_falloff": (0.6, 4.0),
    "sharpness": (0.0, 2.0),
    "live_strength": (0.0, 1.0),
    "hdr_peak": (200.0, 2000.0),
    "frame_cap": (15.0, 240.0),
    "image_period": (5.0, 300.0),
    "image_gap": (0.0, 30.0),
    "image_detail": (0.0, 1.0),
    "message_font_size": (8.0, 144.0),
}

# The string settings that accept only a fixed set of values.
ENUMS = {
    "direction": DIRECTIONS,
    "color": tuple(COLORS),
    "renderer": ("auto", "gpu", "software"),
    "hdr": ("auto", "off"),
    "image_order": ("sequence", "shuffle"),
    "image_mode": ("grid", "classic"),
    "upscaling": tuple(UPSCALE_RATIO),
    "live_source": LIVE_SOURCES,
    "live_target": LIVE_TARGETS,
    "message": MESSAGE_MODES,
    "clock_position": CLOCK_POSITIONS,
}

# Version of the settings file layout; save() writes it and migrate() reads older files.
SETTINGS_VERSION = 1


def settings_path():
    """The settings file the saver reads and the dialog writes."""
    return osapi.settings_read_path()


def _is_number(val):
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def _clamp(key, val):
    lo, hi = RANGES[key]
    return min(hi, max(lo, float(val)))


def clean_monitors(raw):
    """Validated copy of the per-monitor overrides; bad entries and keys are dropped."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for mon_id, ent in raw.items():
        if not (isinstance(mon_id, str) and mon_id and isinstance(ent, dict)):
            continue
        new = {}
        name = ent.get("name")
        if isinstance(name, str):
            new["name"] = name[:128]
        val = ent.get("preset")
        if isinstance(val, str) and val in PRESET_NAMES:
            new["preset"] = val
        val = ent.get("color")
        if isinstance(val, str) and val in COLORS:
            new["color"] = val
        for key in ("speed", "density"):
            val = ent.get(key)
            if _is_number(val):
                new[key] = _clamp(key, val)
        val = ent.get("depth")
        if isinstance(val, bool):
            new["depth"] = val
        if any(k in new for k in OVERRIDE_KEYS):
            out[mon_id] = new
    return out


def monitor_cfg(cfg, mon_id):
    """cfg with one monitor's overrides applied; unknown or empty id: cfg as is."""
    out = dict(cfg)
    ent = cfg.get("monitors", {}).get(mon_id) if mon_id else None
    if ent:
        for key in OVERRIDE_KEYS:
            if key in ent:
                out[key] = ent[key]
    return out


def load():
    """Defaults overlaid with whatever valid values the JSON file contains."""
    try:
        with open(settings_path(), encoding="utf-8") as fh:
            raw = json.load(fh)
    except OSError, ValueError:
        return clean(None)
    return clean(raw)


def migrate(raw):
    """A copy of the parsed settings dict `raw` with older layouts brought up to date.

    Both rules are safe to apply to any file, whatever its "version", so they are
    not gated on it. Later layout changes should test `raw.get("version", 0)`."""
    raw = dict(raw)
    # Files written before presets existed keep their sliders: "custom".
    raw.setdefault("preset", "custom")
    # The image folder was saved as "city_dir" before the image layer was renamed.
    if "city_dir" in raw and "image_dir" not in raw:
        raw["image_dir"] = raw["city_dir"]
    return raw


_REJECT = object()  # _clean_value result for a value that must be ignored


def _clean_message_text(val):
    if not isinstance(val, str):
        return _REJECT
    text = "".join(ch for ch in val if ch >= " ").strip()[:MESSAGE_TEXT_MAX]
    return text or _REJECT


def _clean_value(key, default, val):
    """The valid form of `val` for setting `key`, or _REJECT to keep the default."""
    if key == "monitors":
        return clean_monitors(val)
    if isinstance(default, bool):
        return val if isinstance(val, bool) else _REJECT
    if isinstance(default, (int, float)):
        return _clamp(key, val) if _is_number(val) else _REJECT
    if key == "preset":
        return val if isinstance(val, str) and val in PRESET_NAMES else "custom"
    if key in ENUMS:
        return val if isinstance(val, str) and val in ENUMS[key] else _REJECT
    if key == "message_text":
        return _clean_message_text(val)
    if key == "message_font":
        if not isinstance(val, str):
            return _REJECT
        return clean_message_font(val)
    return val if isinstance(val, str) else _REJECT


def clean_message_font(val):
    """A font family name: no control characters, 128 characters at most."""
    return "".join(ch for ch in str(val) if ch >= " ").strip()[:MESSAGE_FONT_MAX]


def clean(raw):
    """Defaults overlaid with the valid values of `raw` (parsed JSON, any type)."""
    cfg = dict(DEFAULTS)
    cfg["monitors"] = {}  # never hand out DEFAULTS' own dict
    if not isinstance(raw, dict):
        return cfg
    raw = migrate(raw)
    for key, default in DEFAULTS.items():
        if key in raw:
            val = _clean_value(key, default, raw[key])
            if val is not _REJECT:
                cfg[key] = val
    return cfg


def save(cfg):
    """Write cfg; for the settings dialog only (the Mac saver cannot write here).

    The file is written beside the real one and renamed over it, so a crash
    mid-write never leaves a truncated settings.json."""
    path = settings_path()
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    data = cfg
    if isinstance(cfg, dict):  # the checks also save malformed values, written as given
        data = {"version": SETTINGS_VERSION, **{k: v for k, v in cfg.items() if k != "version"}}
    fd, tmp_path = tempfile.mkstemp(dir=folder, prefix="settings-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp_path)
        raise


def main_layer_index(cfg):
    """Index into active_layers(cfg) of the layer that carries the rain."""
    return 1 if cfg["depth"] else 0


def active_layers(cfg, look=None, slices=False):
    """LAYERS adjusted by the user's speed/density; one layer if depth is off.
    A look with its own `layers` supplies them instead; its middle layer is
    the single layer when depth is off. With `slices` (GPU only), depth on
    and a look with `depth_slices`, those slices are the list instead."""
    own = look.get("layers") if look else None
    if slices and cfg["depth"] and look and look.get("depth_slices"):
        layers = look["depth_slices"]
    elif own:
        layers = own if cfg["depth"] else [own[min(1, len(own) - 1)]]
    else:
        layers = LAYERS if cfg["depth"] else [LAYERS[1]]
    out = []
    for lay in layers:
        lay = dict(lay)
        lay["speed"] *= cfg["speed"]
        lay["density"] = min(1.0, lay["density"] * cfg["density"])
        out.append(lay)
    return out
