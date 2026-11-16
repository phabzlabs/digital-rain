"""Editing state and rules of the settings window.

No Tk and no numpy: tools/checks/check_dialog.py checks every rule here without a
window. config_dialog.py draws what this model says and sends edits back.

The model holds the global values and the per-monitor overrides being edited,
the monitor in scope, and derives everything else on demand (enable rules, help
lines, scope pills, sidebar summaries, override chips), so every derived state
is recomputed on every change.
"""

from typing import NamedTuple

from digital_rain import settings

# Values a film preset fixes for the effects box (looks.PRESETS, which imports
# numpy, so they are copied here; tools/checks/check_dialog.py compares them).
PRESET_EFFECTS = {
    "film_1999": {
        "bloom": 1.0,
        "scanlines": 0.0,
        "vignette": 0.15,
        "flicker": 0.0,
        "interlace": False,
    },
    "reloaded": {
        "bloom": 1.0,
        "scanlines": 0.0,
        "vignette": 0.15,
        "flicker": 0.0,
        "interlace": False,
    },
    "resurrections": {
        "bloom": 0.6,
        "scanlines": 0.0,
        "vignette": 0.15,
        "flicker": 0.0,
        "interlace": False,
    },
}
FIXED_EFFECTS = ("bloom", "scanlines", "vignette", "flicker", "interlace")
# Sample colour of each film preset card: its last palette stop (looks.PRESETS).
PRESET_SAMPLE = {"film_1999": "#28F5A0", "reloaded": "#25FCA8", "resurrections": "#E8FBE8"}
# The effects box: Colour plus the six effects every monitor shares.
SHARED_EFFECTS = ("bloom", "scanlines", "vignette", "flicker", "trail_falloff", "interlace")
BOX_KEYS = ("color",) + SHARED_EFFECTS
FILM_PRESETS = ("film_1999", "reloaded", "resurrections")
CARD_ORDER = ("film_1999", "reloaded", "resurrections", "custom")

PAGES = ("look", "motion", "message", "live", "rendering", "images")
PAGE_TITLES = {
    "look": "Look",
    "motion": "Motion and layout",
    "message": "Message and clock",
    "live": "React to computer load",
    "rendering": "Graphics",
    "images": "Pictures",
}
# Look and Message and clock were worded first; the other pages copy their style.
PAGE_DESCRIPTIONS = {
    "look": "How the rain looks on {scope}. Pick a preset, or Custom to tune every effect.",
    "motion": "How fast and how thickly the rain falls, and how big the characters are.",
    "message": "Spell out the time or your own text in the rain.",
    "live": "The harder the computer works, the faster or thicker the rain.",
    "rendering": "How the rain is drawn: graphics card, HDR, upscaling and font.",
    "images": "Pictures from a folder of yours, formed by the rain one after another.",
}
# Rows of each page: (key, control).
PAGE_ROWS = {
    "look": [
        ("preset", "cards"),
        ("direction", "segmented"),
        ("pulse", "switch"),
        ("effects", "box"),
    ],
    "motion": [
        ("speed", "slider"),
        ("density", "slider"),
        ("glyph_scale", "slider"),
        ("depth", "switch"),
    ],
    "message": [
        ("message", "segmented"),
        ("keep_clock", "switch"),
        ("clock_position", "grid"),
        ("clock_24h", "switch"),
        ("message_text", "text"),
        ("message_font", "fontpick"),
        ("easter_egg", "switch"),
    ],
    "live": [
        ("live_source", "segmented"),
        ("live_target", "segmented"),
        ("live_strength", "slider"),
    ],
    "rendering": [
        ("renderer", "segmented"),
        ("hdr", "segmented"),
        ("hdr_peak", "slider"),
        ("frame_cap", "slider"),
        ("upscaling", "dropdown"),
        ("sharpness", "slider"),
        ("font_path", "font"),
    ],
    "images": [
        ("image_dir", "folder"),
        ("image_subfolders", "switch"),
        ("image_mode", "segmented"),
        ("image_order", "segmented"),
        ("image_period", "slider"),
        ("image_gap", "slider"),
        ("image_detail", "slider"),
    ],
}
# Control kind of each effects-box key.
BOX_ROWS = tuple(
    (k, "dropdown" if k == "color" else "switch" if k == "interlace" else "slider")
    for k in BOX_KEYS
)
# Setting keys each page edits: its rows, with the effects box standing for BOX_KEYS.
# keep_clock is a view of the message setting, not a setting of its own.
# The message_font row edits the three settings in FONT_KEYS together.
FONT_KEYS = ("message_font", "message_bold", "message_italic", "message_font_size")
PAGE_KEYS = {
    page: tuple(
        k
        for key, kind in rows
        if kind != "box" and key != "keep_clock"
        for k in (FONT_KEYS if kind == "fontpick" else (key,))
    )
    + (BOX_KEYS if any(kind == "box" for _key, kind in rows) else ())
    for page, rows in PAGE_ROWS.items()
}
# settings.DEFAULTS keys no page edits directly.
NON_UI_KEYS = ("monitors",)

LABELS = {
    "preset": "Film look",
    "direction": "Fall direction",
    "pulse": "Stutter",
    "color": "Colour",
    "bloom": "Glow",
    "scanlines": "Scanlines",
    "vignette": "Dark edges",
    "flicker": "Flicker",
    "trail_falloff": "Trail length",
    "interlace": "Interlaced lines",
    "speed": "Fall speed",
    "density": "Rain density",
    "glyph_scale": "Character size",
    "depth": "Depth",
    "message": "Show in the rain",
    "keep_clock": "Keep clock on screen",
    "clock_position": "Clock position",
    "clock_24h": "24-hour clock",
    "message_text": "Your text",
    "message_font": "Letter font",
    "easter_egg": "Messages from the film",
    "live_source": "React to",
    "live_target": "Changes",
    "live_strength": "Effect strength",
    "renderer": "Draw with",
    "hdr": "HDR",
    "hdr_peak": "HDR peak brightness",
    "frame_cap": "Frame rate limit",
    "upscaling": "Upscaling",
    "sharpness": "Upscaling sharpness",
    "font_path": "Font",
    "image_dir": "Picture folder",
    "image_subfolders": "Include subfolders",
    "image_mode": "How pictures appear",
    "image_order": "Order",
    "image_period": "Time per picture",
    "image_gap": "Rain between pictures",
    "image_detail": "Picture detail",
}
HELP = {
    "direction": "Which way the rain falls.",
    "pulse": "Columns pause, drop a row, then catch up, as in the 1999 film.",
    "depth": "Draws the rain in three layers of different sizes, so some looks farther away.",
    "message": "Formed out of the rain a few seconds after it starts, then every 36 seconds.",
    "keep_clock": "Shows the time all the time instead of every 36 seconds.",
    "clock_position": "Where the clock stays on screen.",
    "clock_24h": "13:45 rather than 1:45.",
    "message_text": "Up to 24 characters. Characters the rain has no shape for are skipped.",
    "message_font": "Opens your system's font picker. Its size sets how big the letters are; "
    "36 pt is the standard size. Bold letters read best in the rain; thin strokes can break up.",
    "easter_egg": "Now and then, the messages from Neo's computer in the film type out "
    "over the rain.",
    "live_source": "The processor (CPU) or graphics card (GPU) load, read once a second. "
    "If it can't be read, the rain stays normal.",
    "renderer": "Auto uses the graphics card (GPU) and falls back to the processor (CPU), "
    "which is slower.",
    "sharpness": "AMD's default is 0.2.",
    "upscaling": "Draws at a lower resolution and scales it up with AMD FSR 1.0, for a "
    "higher frame rate on slower graphics cards.",
    "hdr_peak": "How bright the brightest characters get. Windows caps highlights at 8x "
    "your SDR content brightness, so a high SDR brightness leaves little headroom.",
    "frame_cap": "Caps frames per second to save power. Never above your display's refresh "
    "rate. 60 is plenty for the rain.",
    "font_path": "A TTF or OTF font to draw the rain with instead of the built-in one.",
    "image_dir": "Any folder of JPG, PNG, WebP or BMP pictures. With no folder, there are "
    "no pictures.",
    "image_subfolders": "Also shows the pictures in every folder inside it. "
    "Hidden and system folders are skipped.",
    "image_gap": "0 means the next picture sweeps straight over.",
    "image_mode": "In the rain: the falling characters brighten to draw the picture. "
    "Over the rain: the picture forms from its own characters on top of the rain.",
    "image_detail": "Higher draws distant parts of a picture with smaller characters, for "
    "finer detail.",
}
DISABLED_HELP = {
    "clock_position": "Only used when Keep clock on screen is on.",
    "clock_24h": "Only used when the clock is shown.",
    "message_text": "Only used for Your text or Both.",
    **dict.fromkeys(
        ("message_font",),
        "Only used when something is shown in the rain or Messages from the film is on.",
    ),
    "easter_egg": "Only used while Show in the rain is Off.",
    "live_target": "Only used when React to is CPU or GPU.",
    "live_strength": "Only used when React to is CPU or GPU.",
    "upscaling": "Only used when drawing with the GPU.",
    "hdr": "Only used when drawing with the GPU.",
    "hdr_peak": "Only used when HDR is on.",
    "sharpness": "Only used when upscaling is on.",
    "image_subfolders": "Only used when a picture folder is chosen.",
}
# Hover text of the effects box rows, which have no room for a help line.
EFFECT_TIPS = {
    "color": "The colour of the rain. The leading character of each column is paler.",
    "bloom": "A soft glow around bright characters.",
    "scanlines": "Faint horizontal lines, like an old monitor.",
    "vignette": "Darkens the edges and corners of the screen.",
    "flicker": "A slight, constant flicker in brightness.",
    "trail_falloff": "How far each column's trail stretches behind its leading character.",
    "interlace": "Moving alternate lines, like an interlaced video picture.",
}
FOLLOWING_HELP = "Following All monitors."
TOOLTIP_PICKER = "Display numbers follow this list, not Windows Settings."

# Slider rows: (key, decimals, unit, end labels). Ranges come from settings.RANGES.
SLIDERS = {
    "bloom": (2, "", None),
    "scanlines": (2, "", None),
    "vignette": (2, "", None),
    "flicker": (2, "", None),
    "trail_falloff": (2, "", ("Long", "Short")),
    "speed": (2, "×", ("Slow", "Fast")),
    "density": (2, "×", ("Sparse", "Dense")),
    "glyph_scale": (2, "×", ("Small", "Large")),
    "live_strength": (2, "", None),
    "sharpness": (2, "", ("Sharper", "Softer")),
    "hdr_peak": (0, " nits", ("Dimmer", "Brighter")),
    "frame_cap": (0, " fps", ("Lower power", "Smoother")),
    "image_period": (0, " s", None),
    "image_gap": (0, " s", None),
    "image_detail": (2, "", ("Low", "Maximum")),
}
SEGMENTS = {
    "direction": (("down", "Down"), ("sideways", "Sideways"), ("diagonal", "Diagonal")),
    "message": (("off", "Off"), ("clock", "Time"), ("text", "Your text"), ("both", "Both")),
    "live_source": (("off", "Off"), ("cpu", "CPU"), ("gpu", "GPU")),
    "live_target": (("speed", "Speed"), ("density", "Density"), ("both", "Both")),
    "renderer": (("auto", "Auto"), ("gpu", "GPU"), ("software", "CPU")),
    "hdr": (("auto", "Auto"), ("off", "Off")),
    "image_mode": (("grid", "In the rain"), ("classic", "Over the rain")),
    "image_order": (("sequence", "Name order"), ("shuffle", "Shuffled")),
}
COLOR_LABELS = {name: name.capitalize() for name in settings.COLORS}
COLOR_LABELS.update(film="Film green", classic="Bright green")
UPSCALE_LABELS = {"off": "Off"}
UPSCALE_LABELS.update(
    {k: f"{k.capitalize()} ({v:g}×)" for k, v in settings.UPSCALE_RATIO.items() if k != "off"}
)
POSITION_NAMES = {
    p: p.replace("_", " ").replace("center", "centre").capitalize()
    for p in settings.CLOCK_POSITIONS
}
FILM_GLYPHS_LABEL = "Built-in film font"
NO_FOLDER_LABEL = "No folder chosen"


class Picker(NamedTuple):
    """A file or folder row: the setting it edits and the texts of its buttons."""

    key: str
    directory: bool
    file_label: str  # file type group shown in the file dialog
    extensions: tuple  # allowed file extensions, no dot
    browse_name: str  # accessible name of the browse button
    clear_label: str
    clear_name: str
    empty_label: str  # what the box shows while the setting is empty


# Picker of each "font" and "folder" row, by the setting it edits.
PICKERS = {
    "font_path": Picker(
        "font_path",
        False,
        "Fonts",
        ("ttf", "otf"),
        "Browse for a custom font",
        "Use built-in font",
        "Use the built-in font",
        FILM_GLYPHS_LABEL,
    ),
    "image_dir": Picker(
        "image_dir",
        True,
        "",
        (),
        "Choose a picture folder",
        "Turn off",
        "Turn pictures off",
        NO_FOLDER_LABEL,
    ),
}
RESET_QUESTION = (
    "Reset every setting and forget all monitor overrides? Nothing is saved until you press OK."
)


def preset_title(name):
    return settings.PRESET_TITLES.get(name, "Custom")


def clean_text(text):
    """What the message text box accepts: no characters below a space, 24 at most."""
    return "".join(ch for ch in str(text) if ch >= " ")[: settings.MESSAGE_TEXT_MAX]


USE_DEFAULT_FONT = "Use default"
CHOOSE_FONT = "Choose font…"


def font_text(family, bold, italic, size):
    """The font row's text: family (Courier New when empty), style and size."""
    style = " ".join(w for w, on in (("Bold", bold), ("Italic", italic)) if on)
    name = f"{family or settings.DEFAULT_MESSAGE_FONT} {style}".strip()
    return f"{name}, {float(size):g} pt"


def fmt(key, value):
    """A value as the dialog writes it in help lines, chips and summaries."""
    if key == "preset":
        return preset_title(value)
    if key == "color":
        return COLOR_LABELS.get(value, str(value))
    if key in ("speed", "density", "glyph_scale"):
        return f"{float(value):.2f}×"
    if isinstance(value, bool):
        return "on" if value else "off"
    if key in SLIDERS:
        dec, unit, _ends = SLIDERS[key]
        return f"{float(value):.{dec}f}{unit}"
    return str(value)


class Row:
    """Derived state of one setting row."""

    __slots__ = (
        "key",
        "visible",
        "enabled",
        "pill",
        "pill_enabled",
        "help",
        "global_text",
        "reset_enabled",
    )

    def __init__(self, key, **kw):
        self.key = key
        self.visible = kw.get("visible", True)
        self.enabled = kw.get("enabled", True)
        self.pill = kw.get("pill")  # None | "override" | "overridden" | "all"
        self.pill_enabled = kw.get("pill_enabled", True)
        self.help = kw.get("help", "")
        self.global_text = kw.get("global_text")  # "Global value X" when overridden
        self.reset_enabled = kw.get("reset_enabled", False)

    def __repr__(self):
        return (
            f"Row({self.key}, visible={self.visible}, enabled={self.enabled}, "
            f"pill={self.pill}, pill_enabled={self.pill_enabled}, help={self.help!r}, "
            f"global_text={self.global_text!r})"
        )


class Model:
    """cfg: a settings.clean() dict. connected: osapi.list_monitors() order, each
    a dict with at least "id" and "name"."""

    def __init__(self, cfg, connected=()):
        self.connected = [dict(id=m["id"], name=m.get("name", "")) for m in connected]
        self._load(cfg)
        self.scope = None
        self.listeners = []

    def _load(self, cfg):
        self.g = {k: v for k, v in cfg.items() if k != "monitors"}
        self.over = {i: dict(e) for i, e in cfg.get("monitors", {}).items()}

    def _changed(self):
        for fn in list(self.listeners):
            fn()

    def _connected_ids(self):
        return [m["id"] for m in self.connected]

    def _saved_ids(self):
        conn = set(self._connected_ids())
        ids = [i for i in self.over if i not in conn]
        return sorted(ids, key=lambda i: (self.over[i].get("name") or i, i))

    def has_overrides(self, mon_id):
        ent = self.over.get(mon_id, {})
        return any(k in ent for k in settings.OVERRIDE_KEYS)

    def entries(self):
        """Scope picker rows: dicts with id, label, kind (all, connected, saved), dot."""
        out = [dict(id=None, label="All monitors", kind="all", dot=False)]
        for n, m in enumerate(self.connected, 1):
            out.append(
                dict(
                    id=m["id"],
                    label=self.display_label(n - 1),
                    kind="connected",
                    dot=self.has_overrides(m["id"]),
                )
            )
        for i in self._saved_ids():
            out.append(
                dict(
                    id=i,
                    label=self.over[i].get("name") or i,
                    kind="saved",
                    dot=self.has_overrides(i),
                )
            )
        return out

    def display_label(self, index):
        """Picker name of connected display `index` (0-based)."""
        return f"Display {index + 1}" + (" (primary)" if index == 0 else "")

    def set_scope(self, mon_id):
        ids = [e["id"] for e in self.entries()]
        self.scope = mon_id if mon_id in ids else None
        self._changed()

    def in_monitor(self):
        return self.scope is not None

    def scope_connected(self):
        return self.scope in self._connected_ids()

    def scope_name(self):
        """Short name for headings: "Display 2", or the stored name of a saved monitor."""
        if self.scope is None:
            return "all monitors"
        ids = self._connected_ids()
        if self.scope in ids:
            return f"Display {ids.index(self.scope) + 1}"
        return self.over.get(self.scope, {}).get("name") or self.scope

    def page_description(self, page):
        return PAGE_DESCRIPTIONS[page].format(scope=self.scope_name())

    def overridden(self, key):
        return (
            self.scope is not None
            and key in settings.OVERRIDE_KEYS
            and key in self.over.get(self.scope, {})
        )

    def effective(self, key):
        """The scope's own value: its override, or the global value."""
        if self.overridden(key):
            return self.over[self.scope][key]
        return self.g[key]

    def effective_preset(self):
        return self.effective("preset")

    def locked(self):
        """The scope's effective preset is a film preset: the effects box is locked."""
        return self.effective_preset() in FILM_PRESETS

    def value(self, key):
        """What the control for `key` shows."""
        if key in FIXED_EFFECTS and self.locked():
            return PRESET_EFFECTS[self.effective_preset()][key]
        return self.effective(key)

    def scope_cfg(self):
        """Full cfg with the scope's overrides applied and no monitor entries (what
        the preview child draws)."""
        cfg = self.to_cfg()
        out = settings.monitor_cfg(cfg, self.scope)
        out["monitors"] = {}
        return out

    def set(self, key, value):
        """An edit from a control. In a monitor scope an overridden key edits the
        override; an overridable key that isn't overridden is read only."""
        if self.scope is not None and key in settings.OVERRIDE_KEYS:
            if not self.overridden(key):
                return
            # Speed and density overrides are stored to 2 decimals.
            self.over[self.scope][key] = self._coerce(key, value, round2=True)
        else:
            self.g[key] = self._coerce(key, value)
        self._changed()

    def font_text(self):
        g = self.g
        return font_text(
            g["message_font"], g["message_bold"], g["message_italic"], g["message_font_size"]
        )

    def set_font(self, family, bold, italic, size):
        """The font picker's result: family, bold, italic and point size in one edit."""
        self.g["message_font"] = settings.clean_message_font(family)
        self.g["message_bold"] = bool(bold)
        self.g["message_italic"] = bool(italic)
        lo, hi = settings.RANGES["message_font_size"]
        self.g["message_font_size"] = min(hi, max(lo, float(size)))
        self._changed()

    def reset_font(self):
        d = settings.DEFAULTS
        self.set_font(
            d["message_font"], d["message_bold"], d["message_italic"], d["message_font_size"]
        )

    def _coerce(self, key, value, round2=False):
        if key == "message_text":
            return clean_text(value)
        if key == "message_font":
            return settings.clean_message_font(value)
        default = settings.DEFAULTS[key]
        if isinstance(default, bool):
            return bool(value)
        if isinstance(default, float):
            lo, hi = settings.RANGES[key]
            value = min(hi, max(lo, float(value)))
            return round(value, 2) if round2 and key in ("speed", "density") else value
        return value

    def create_override(self, key):
        if self.scope is None or key not in settings.OVERRIDE_KEYS or self.overridden(key):
            return
        if key == "color" and self.locked():
            # A film preset locks the Colour row and its pill.
            return
        value = self.g[key]
        if key in ("speed", "density"):
            value = round(float(value), 2)
        self.over.setdefault(self.scope, {})[key] = value
        self._changed()

    def remove_override(self, key):
        if not self.overridden(key):
            return
        del self.over[self.scope][key]
        self._changed()

    def toggle_override(self, key):
        if self.overridden(key):
            self.remove_override(key)
        else:
            self.create_override(key)

    def customise(self):
        """ "Customise these": switch the scope to Custom without the look jumping."""
        preset = self.effective_preset()
        if preset not in FILM_PRESETS:
            return
        if self.scope is None:
            self.g["preset"] = "custom"
            self.g.update(PRESET_EFFECTS[preset])
            self.g["color"] = "film"
        else:
            ent = self.over.setdefault(self.scope, {})
            ent["preset"] = "custom"
            ent.setdefault("color", "film")
        self._changed()

    def forget(self):
        """Remove every override of the monitor in scope."""
        if self.scope is None:
            return
        saved = not self.scope_connected()
        if saved:
            self.over.pop(self.scope, None)
            self.scope = None
        else:
            ent = self.over.get(self.scope)
            if ent is not None:
                for k in settings.OVERRIDE_KEYS:
                    ent.pop(k, None)
        self._changed()

    def can_forget(self):
        return self.scope is not None and self.has_overrides(self.scope)

    def reset(self, keep_overrides=False):
        """Every key to settings.DEFAULTS and no overrides. Saves nothing.
        keep_overrides: keep the per-monitor overrides (the Mac sheet, which cannot
        show or restore them)."""
        over = self.over
        self._load(settings.clean(None))
        if keep_overrides:
            self.over = over
        if self.scope is not None and not self.scope_connected():
            self.scope = None
        self._changed()

    def to_cfg(self):
        """The dict passed to settings.clean then settings.save on OK."""
        out = dict(self.g)
        names = {m["id"]: m["name"] for m in self.connected}
        mons = {}
        for mon_id, ent in self.over.items():
            if not any(k in ent for k in settings.OVERRIDE_KEYS):
                continue
            ent = dict(ent)
            if mon_id in names:
                ent["name"] = names[mon_id]
            mons[mon_id] = ent
        out["monitors"] = mons
        return out

    def message_segment(self):
        m = self.g["message"]
        return "clock" if m in ("clock", "clock_fixed") else m

    def set_message_segment(self, seg):
        if seg == self.message_segment():
            return
        self.set("message", seg)

    def keep_clock(self):
        return self.g["message"] == "clock_fixed"

    def set_keep_clock(self, on):
        if self.message_segment() != "clock":
            return
        self.set("message", "clock_fixed" if on else "clock")

    def options(self, key):
        """-> [(value, label)] of a dropdown, cards, grid or segmented row."""
        if key == "color":
            return list(COLOR_LABELS.items())
        if key == "upscaling":
            return list(UPSCALE_LABELS.items())
        if key == "preset":
            return [(p, preset_title(p)) for p in CARD_ORDER]
        if key == "clock_position":
            return [(p, POSITION_NAMES[p]) for p in settings.CLOCK_POSITIONS]
        if key in SEGMENTS:
            return list(SEGMENTS[key])
        raise KeyError(key)

    def control_value(self, key):
        """What the control for `key` shows (also "message" and "keep_clock")."""
        if key == "message":
            return self.message_segment()
        if key == "keep_clock":
            return self.keep_clock()
        return self.value(key)

    def control_set(self, key, value):
        """An edit from the control for `key` (also "message" and "keep_clock")."""
        if key == "message":
            self.set_message_segment(value)
        elif key == "keep_clock":
            self.set_keep_clock(value)
        else:
            self.set(key, value)

    def row(self, key):
        """Derived state of the row for `key` (also "keep_clock")."""
        g = self.g
        if key == "keep_clock":
            return Row(
                key,
                visible=self.message_segment() == "clock",
                help=HELP["keep_clock"],
                pill=self._plain_pill(),
            )
        if key in settings.OVERRIDE_KEYS:
            return self._override_row(key)
        enabled = True
        visible = True
        if key in SHARED_EFFECTS:
            enabled = not self.locked()
        elif key == "clock_position":
            visible = self.message_segment() == "clock"
            enabled = g["message"] == "clock_fixed"
        elif key == "clock_24h":
            enabled = g["message"] in ("clock", "clock_fixed", "both")
        elif key == "message_text":
            enabled = g["message"] in ("text", "both")
        elif key == "easter_egg":
            enabled = g["message"] == "off"
        elif key == "message_font":
            enabled = g["message"] != "off" or bool(g["easter_egg"])
        elif key in ("live_target", "live_strength"):
            enabled = g["live_source"] != "off"
        elif key in ("upscaling", "hdr"):
            enabled = g["renderer"] != "software"
        elif key == "hdr_peak":
            enabled = g["hdr"] != "off" and g["renderer"] != "software"
        elif key == "sharpness":
            enabled = g["upscaling"] != "off" and g["renderer"] != "software"
        elif key == "image_subfolders":
            enabled = bool(g["image_dir"])
        help_ = HELP.get(key, "")
        if key == "message_text":
            help_ = ""  # the counter line under the box carries HELP["message_text"]
        if not enabled and key in DISABLED_HELP:
            help_ = DISABLED_HELP[key]
        # The six shared effects carry no per-row tag: the box header covers them.
        pill = None if key in SHARED_EFFECTS else self._plain_pill()
        return Row(key, visible=visible, enabled=enabled, help=help_, pill=pill)

    def _plain_pill(self):
        return "all" if self.scope is not None else None

    def _override_row(self, key):
        help_ = HELP.get(key, "")
        if self.scope is None:
            enabled = not (key == "color" and self.locked())
            if key == "preset":
                help_ = ""
            return Row(key, enabled=enabled, help=help_)
        stale = key == "color" and self.locked()
        if self.overridden(key):
            text = f"Global value {fmt(key, self.g[key])}"
            if stale:
                return Row(
                    key,
                    enabled=False,
                    pill="overridden",
                    pill_enabled=False,
                    help=f"Set by {preset_title(self.effective_preset())}",
                    global_text=text,
                    reset_enabled=True,
                )
            return Row(
                key, enabled=True, pill="overridden", help="", global_text=text, reset_enabled=True
            )
        if stale:
            return Row(
                key,
                enabled=False,
                pill="override",
                pill_enabled=False,
                help=f"Set by {preset_title(self.effective_preset())}",
            )
        if key == "preset":
            help_ = FOLLOWING_HELP
        return Row(key, enabled=False, pill="override", help=help_)

    def effects_header(self):
        """-> dict(locked, title, customise, note) for the effects box header."""
        if self.locked():
            return dict(
                locked=True,
                title="Effects set by",
                strong=preset_title(self.effective_preset()),
                customise=True,
                note=None,
            )
        if self.scope is None:
            return dict(locked=False, title="Custom effects", strong="", customise=False, note=None)
        return dict(
            locked=False,
            title="Custom effects · shared by all monitors",
            strong="",
            customise=False,
            note="Only Colour can differ per monitor. "
            "Changes to the other effects apply everywhere.",
        )

    def card_sample(self, preset):
        """Sample colour of a preset card (Custom: the head colour of `color`)."""
        if preset in PRESET_SAMPLE:
            return PRESET_SAMPLE[preset]
        return "#%02X%02X%02X" % settings.COLORS[self.effective("color")][1]

    def overrides_on_page(self, page):
        if self.scope is None:
            return 0
        ent = self.over.get(self.scope, {})
        return sum(1 for k in PAGE_KEYS[page] if k in settings.OVERRIDE_KEYS and k in ent)

    def summary(self, page):
        """-> (text, amber) for the sidebar item of `page`."""
        n = self.overrides_on_page(page)
        if n:
            return (f"{n} override{'s' if n != 1 else ''} on this monitor", True)
        return (self._summary_text(page), False)

    def _summary_text(self, page):
        e = self.effective
        g = self.g
        if page == "look":
            p = e("preset")
            return preset_title(p) if p in FILM_PRESETS else f"Custom · {fmt('color', e('color'))}"
        if page == "motion":
            return f"{e('speed'):.1f}× speed · depth {'on' if e('depth') else 'off'}"
        if page == "message":
            h = "24-hour" if g["clock_24h"] else "12-hour"
            m = g["message"]
            if m == "off":
                return "Off"
            if m == "clock":
                return f"Time every 36 s · {h}"
            if m == "clock_fixed":
                return f"Time · stays {POSITION_NAMES[g['clock_position']].lower()} · {h}"
            if m == "text":
                return f"Your text · {g['message_text']}"
            return f"Time and your text · {h}"
        if page == "live":
            if g["live_source"] == "off":
                return "Off"
            drives = {"speed": "speed", "density": "density", "both": "speed and density"}[
                g["live_target"]
            ]
            return f"{g['live_source'].upper()} · {drives} · {g['live_strength']:.2f}"
        if page == "rendering":
            r = dict(SEGMENTS["renderer"])[g["renderer"]]
            up = g["upscaling"]
            return f"{r} · " + ("upscaling off" if up == "off" else f"{up.capitalize()} upscaling")
        if page == "images":
            order = dict(SEGMENTS["image_order"])[g["image_order"]]
            src = NO_FOLDER_LABEL
            if g["image_dir"]:
                src = "Your folder and subfolders" if g["image_subfolders"] else "Your folder"
            return f"{src} · {order.lower()} · {g['image_period']:.0f} s each"
        raise KeyError(page)

    def overrides_heading(self):
        """Heading of the sidebar overrides summary, or None in All monitors."""
        if self.scope is None:
            return None
        return f"{self.scope_name()} differs in"

    def chips(self):
        """-> [(text, muted)] for the monitor in scope, in OVERRIDE_KEYS order."""
        if self.scope is None:
            return []
        ent = self.over.get(self.scope, {})
        names = {
            "preset": "Film look",
            "color": "Colour",
            "speed": "Fall speed",
            "density": "Rain density",
            "depth": "Depth",
        }
        out = []
        for k in settings.OVERRIDE_KEYS:
            if k not in ent:
                continue
            text = f"{names[k]} {fmt(k, ent[k])}"
            stale = k == "color" and self.locked()
            out.append((text + (" (not used)" if stale else ""), stale))
        return out
