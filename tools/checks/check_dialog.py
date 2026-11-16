"""Settings window rules, windowless.

Exercises dialog_model only: no window, no child process. The design tokens and text
colour pairs are imported from dialog_widgets (which loads tkinter but opens nothing).
looks.PRESETS is the reference for the preset effects and sample colours.

Usage: <venv python> tools/checks/check_dialog.py
"""

import json
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TOOLS))
sys.path.insert(0, ROOT)
sys.path.insert(0, TOOLS)

from _gate import Checker, scratch  # noqa: E402

from digital_rain import dialog_model as dm  # noqa: E402
from digital_rain import settings  # noqa: E402

CONNECTED = [dict(id="MON-A", name="DELL U2720Q"), dict(id="MON-B", name="LG 27GL850")]
gate = Checker("dialog model")
expect = gate.check


def model(raw=None, connected=CONNECTED):
    return dm.Model(settings.clean(raw if raw is not None else {"preset": "film_1999"}), connected)


# looks.PRESETS
def check_presets():
    from digital_rain import looks

    for name in dm.FILM_PRESETS:
        ref = looks.PRESETS[name]
        for key in dm.FIXED_EFFECTS:
            expect(
                dm.PRESET_EFFECTS[name][key] == ref[key],
                f"PRESET_EFFECTS[{name}][{key}] {dm.PRESET_EFFECTS[name][key]!r} "
                f"!= looks {ref[key]!r}",
            )
        expect(
            set(dm.PRESET_EFFECTS[name]) == set(dm.FIXED_EFFECTS),
            f"PRESET_EFFECTS[{name}] keys differ from FIXED_EFFECTS",
        )
        last = "#%02X%02X%02X" % ref["palette"][-1][1]
        expect(
            dm.PRESET_SAMPLE[name] == last,
            f"PRESET_SAMPLE[{name}] {dm.PRESET_SAMPLE[name]} != last stop {last}",
        )
    expect(
        set(dm.PRESET_EFFECTS) == set(dm.FILM_PRESETS) == set(dm.PRESET_SAMPLE),
        "preset tables do not cover exactly the film presets",
    )
    m = model({"preset": "custom", "color": "amber"})
    head = "#%02X%02X%02X" % settings.COLORS["amber"][1]
    expect(m.card_sample("custom") == head, "Custom card sample is not the colour's head")


# Enable rules
def check_enable_rules():
    m = model()
    # film preset locks the box, values from PRESET_EFFECTS
    for p in dm.FILM_PRESETS:
        m.set("preset", p)
        for k in dm.SHARED_EFFECTS:
            expect(not m.row(k).enabled, f"{p}: {k} enabled under a film preset")
        expect(not m.row("color").enabled, f"{p}: colour enabled under a film preset")
        for k in dm.FIXED_EFFECTS:
            expect(m.value(k) == dm.PRESET_EFFECTS[p][k], f"{p}: {k} shows {m.value(k)!r}")
        expect(
            m.value("trail_falloff") == m.g["trail_falloff"],
            f"{p}: trail length does not show the stored value",
        )
        h = m.effects_header()
        expect(
            h["locked"] and h["customise"] and h["strong"] == dm.preset_title(p),
            f"{p}: effects header {h}",
        )
    m.set("preset", "custom")
    for k in dm.BOX_KEYS:
        expect(m.row(k).enabled, f"custom: {k} disabled")
    expect(m.effects_header()["title"] == "Custom effects", "custom: header title")
    # message and clock
    for msg in ("off", "clock", "clock_fixed", "text", "both"):
        m.g["message"] = msg
        seg = "clock" if msg in ("clock", "clock_fixed") else msg
        expect(m.message_segment() == seg, f"message {msg}: segment {m.message_segment()}")
        expect(m.row("keep_clock").visible == (seg == "clock"), f"{msg}: keep clock visible")
        cp = m.row("clock_position")
        expect(cp.visible == (seg == "clock"), f"{msg}: clock position visible")
        expect(cp.enabled == (msg == "clock_fixed"), f"{msg}: clock position enabled")
        if seg == "clock" and msg == "clock":
            expect(
                cp.help == "Only used when Keep clock on screen is on.",
                f"{msg}: clock position help {cp.help!r}",
            )
        c24 = m.row("clock_24h")
        expect(c24.visible, f"{msg}: 24-hour hidden")
        expect(c24.enabled == (msg in ("clock", "clock_fixed", "both")), f"{msg}: 24-hour enabled")
        if not c24.enabled:
            expect(c24.help == "Only used when the clock is shown.", f"{msg}: 24-hour help")
        mt = m.row("message_text")
        expect(mt.enabled == (msg in ("text", "both")), f"{msg}: message text enabled")
        if not mt.enabled:
            expect(mt.help == "Only used for Your text or Both.", f"{msg}: message text help")
        # the easter egg only works while no message is set
        ee = m.row("easter_egg")
        expect(ee.enabled == (msg == "off"), f"{msg}: easter egg enabled")
        if msg != "off":
            expect(
                ee.help == "Only used while Show in the rain is Off.",
                f"{msg}: easter egg help {ee.help!r}",
            )
    expect(
        dm.clean_text("ab\x01c" + "x" * 40) == ("abc" + "x" * 40)[:24],
        "message text not cleaned like settings.clean",
    )
    # live strength and target need a source
    for src in ("off", "cpu", "gpu"):
        m.g["live_source"] = src
        for k in ("live_target", "live_strength"):
            r = m.row(k)
            expect(r.enabled == (src != "off"), f"live {src}: {k} enabled")
            if src == "off":
                expect(r.help == "Only used when React to is CPU or GPU.", f"live off: {k} help")
    # upscaling and sharpening follow the renderer
    for ren in ("auto", "gpu", "software"):
        for up in ("off", "quality", "balanced", "performance"):
            m.g["renderer"], m.g["upscaling"] = ren, up
            expect(
                m.row("upscaling").enabled == (ren != "software"), f"{ren}/{up}: upscaling enabled"
            )
            expect(
                m.row("sharpness").enabled == (ren != "software" and up != "off"),
                f"{ren}/{up}: sharpening enabled",
            )
            if ren == "software":
                expect(
                    m.row("upscaling").help == "Only used when drawing with the GPU.",
                    "upscaling help",
                )
    expect(
        list(dm.UPSCALE_LABELS) == list(settings.UPSCALE_RATIO),
        "upscaling options do not follow settings.UPSCALE_RATIO",
    )
    # ranges from settings.RANGES
    for k in (
        "speed",
        "density",
        "glyph_scale",
        "bloom",
        "scanlines",
        "vignette",
        "flicker",
        "trail_falloff",
        "live_strength",
        "sharpness",
    ):
        expect(k in settings.RANGES and k in dm.SLIDERS, f"{k}: slider without a range")


# Overrides
def check_overrides():
    m = model()
    expect(
        [e["label"] for e in m.entries()] == ["All monitors", "Display 1 (primary)", "Display 2"],
        "picker entries",
    )
    # All monitors scope: no pills
    expect(
        all(m.row(k).pill is None for k in ("preset", "speed", "direction")),
        "All monitors scope shows a pill",
    )
    m.set_scope("MON-B")
    r = m.row("speed")
    expect(r.pill == "override" and not r.enabled, f"not overridden speed: {r}")
    expect(m.row("direction").pill == "all", "direction: not the All monitors tag")
    expect(m.row("bloom").pill is None, "shared effect carries a per-row tag")
    before = m.g["speed"]
    m.set("speed", 2.0)  # read only while not overridden
    expect(
        m.g["speed"] == before and not m.overridden("speed"),
        "editing a non-overridden key changed something",
    )
    m.g["speed"] = 1.23456
    m.create_override("speed")
    expect(m.over["MON-B"]["speed"] == 1.23, "override not created with the global value")
    r = m.row("speed")
    expect(
        r.pill == "overridden" and r.enabled and r.global_text == "Global value 1.23×",
        f"overridden speed: {r}",
    )
    m.set("speed", 1.987)
    expect(
        m.over["MON-B"]["speed"] == 1.99 and m.g["speed"] == 1.23456,
        "override edit not rounded, or global touched",
    )
    expect(m.summary("motion") == ("1 override on this monitor", True), "motion page count")
    m.create_override("density")
    expect(m.summary("motion") == ("2 overrides on this monitor", True), "two overrides")
    dens = f"Rain density {round(m.g['density'], 2):.2f}×"
    expect(m.chips() == [("Fall speed 1.99×", False), (dens, False)], f"chips {m.chips()}")
    m.remove_override("density")
    m.toggle_override("speed")
    expect(not m.overridden("speed") and m.summary("motion")[1] is False, "reset override")
    expect(m.chips() == [] and not m.can_forget(), "chips after reset")
    expect(m.overrides_heading() == "Display 2 differs in", "overrides heading")
    # direction is not overridable: edits the global value
    m.set("direction", "sideways")
    expect(m.g["direction"] == "sideways", "direction did not edit the global value")
    # stale colour
    m.create_override("color")  # locked: refused, row is disabled
    expect(not m.overridden("color"), "colour override created under a film preset")
    m.create_override("preset")
    m.set("preset", "custom")
    m.create_override("color")
    m.set("color", "amber")
    r = m.row("color")
    expect(r.enabled and r.pill == "overridden", f"live colour override: {r}")
    m.remove_override("preset")  # back to the global film preset: colour goes stale
    r = m.row("color")
    expect(
        not r.enabled
        and r.pill == "overridden"
        and not r.pill_enabled
        and r.reset_enabled
        and r.help == "Set by The Matrix (1999)"
        and r.global_text == "Global value Film green",
        f"stale colour: {r}",
    )
    expect(m.chips() == [("Colour Amber (not used)", True)], f"stale chip {m.chips()}")
    expect(m.summary("look") == ("1 override on this monitor", True), "look page count")
    expect(m.over["MON-B"]["color"] == "amber", "stale override not kept")
    m.remove_override("color")
    expect(not m.overridden("color"), "stale override reset failed")
    # chips order and format
    m.over["MON-A"] = dict(
        name="x", preset="reloaded", color="amber", speed=1.4, density=0.8, depth=False
    )
    m.set_scope("MON-A")
    expect(
        [t for t, _ in m.chips()]
        == [
            "Film look Reloaded (2003)",
            "Colour Amber (not used)",
            "Fall speed 1.40×",
            "Rain density 0.80×",
            "Depth off",
        ],
        f"chip order {m.chips()}",
    )
    expect(m.entries()[1]["dot"] and not m.entries()[2]["dot"], "amber dots")
    # forget, connected
    m.forget()
    expect(m.scope == "MON-A" and not m.has_overrides("MON-A"), "forget connected")
    expect("MON-A" not in m.to_cfg()["monitors"], "forgotten entry still saved")
    # forget, disconnected
    m.over["OLD"] = dict(name="Old TV", density=0.5)
    ents = m.entries()
    expect(ents[-1]["kind"] == "saved" and ents[-1]["label"] == "Old TV", "saved entry")
    m.set_scope("OLD")
    expect(
        m.overrides_heading() == "Old TV differs in" and not m.scope_connected(),
        "disconnected heading",
    )
    m.forget()
    expect(
        m.scope is None and "OLD" not in [e["id"] for e in m.entries()],
        "forget disconnected did not leave the picker",
    )


# Customise
def check_customise():
    m = model({"preset": "reloaded", "bloom": 0.3, "color": "amber"})
    m.customise()
    expect(m.g["preset"] == "custom" and m.g["color"] == "film", "All: preset/colour")
    for k, v in dm.PRESET_EFFECTS["reloaded"].items():
        expect(m.g[k] == v, f"All customise: {k} {m.g[k]!r}")
    m = model({"preset": "film_1999", "bloom": 0.3, "scanlines": 0.5})
    g_before = dict(m.g)
    m.set_scope("MON-A")
    m.customise()
    expect(m.g == g_before, "monitor customise wrote a global key")
    expect(
        m.over["MON-A"]["preset"] == "custom" and m.over["MON-A"]["color"] == "film",
        f"monitor customise entry {m.over['MON-A']}",
    )
    h = m.effects_header()
    expect(
        h["title"] == "Custom effects · shared by all monitors" and h["note"],
        "monitor custom header",
    )
    expect(m.value("bloom") == 0.3, "monitor custom under film global: not the stored value")
    m.set("bloom", 0.7)
    expect(m.g["bloom"] == 0.7, "shared effect edit did not write the global value")
    m.over["MON-B"] = dict(color="red")
    m.set_scope("MON-B")
    m.create_override("preset")
    m.set("preset", "resurrections")
    m.customise()
    expect(m.over["MON-B"]["color"] == "red", "customise replaced an existing colour override")


# Message
def check_message():
    m = model({"preset": "film_1999", "message": "clock_fixed", "clock_position": "top_right"})
    expect(m.message_segment() == "clock" and m.keep_clock(), "clock_fixed loads as Clock + keep")
    m.set_keep_clock(False)
    expect(m.g["message"] == "clock", "keep off did not store clock")
    m.set_keep_clock(True)
    expect(m.g["message"] == "clock_fixed", "keep on did not store clock_fixed")
    m.set_message_segment("clock")
    expect(m.g["message"] == "clock_fixed", "re-picking Clock lost Keep clock")
    m.set_message_segment("text")
    m.set_keep_clock(True)
    expect(m.g["message"] == "text", "keep clock changed a non-clock message")
    m.set_message_segment("clock")
    expect(m.g["message"] == "clock", "Clock segment did not store clock")
    cfg = settings.clean(json.loads(json.dumps(m.to_cfg())))
    expect(cfg["message"] == "clock", "message did not survive clean")


# to_cfg
def check_to_cfg():
    fixture = {
        "color": "amber",
        "bloom": 0.8,
        "scanlines": 0.1,
        "interlace": False,
        "vignette": 0.2,
        "flicker": 0.0,
        "speed": 1.5,
        "density": 0.7,
        "glyph_scale": 1.2,
        "trail_falloff": 2.0,
        "depth": False,
        "easter_egg": False,
        "renderer": "software",
        "font_path": "",
    }
    three = {
        "preset": "reloaded",
        "speed": 1.234567,
        "monitors": {
            "MON-A": {"name": "DELL U2720Q", "speed": 1.4, "color": "amber"},
            "MON-B": {"name": "LG 27GL850", "preset": "custom"},
            "GONE": {"name": "Old TV", "density": 0.5, "depth": False},
        },
    }
    for name, raw in (("v1.1.0 fixture", fixture), ("three monitors", three)):
        want = settings.clean(json.loads(json.dumps(raw)))
        m = dm.Model(want, CONNECTED)
        got = settings.clean(json.loads(json.dumps(m.to_cfg())))
        differing = {
            k: (got.get(k), want.get(k)) for k in set(got) | set(want) if got.get(k) != want.get(k)
        }
        expect(got == want, f"to_cfg after no edits differs for {name}: {differing}")
    # names written for connected monitors, empty entries dropped
    m = dm.Model(settings.clean({"monitors": {"MON-A": {"speed": 1.2}}}), CONNECTED)
    m.set_scope("MON-B")
    m.create_override("depth")
    m.remove_override("depth")
    out = m.to_cfg()["monitors"]
    expect(out == {"MON-A": {"speed": 1.2, "name": "DELL U2720Q"}}, f"monitors out {out}")


# Summaries
def check_summaries():
    m = model()
    s = lambda p: m.summary(p)[0]  # noqa: E731
    expect(s("look") == "The Matrix (1999)", f"look {s('look')}")
    m.g.update(preset="custom", color="amber")
    expect(s("look") == "Custom · Amber", f"look custom {s('look')}")
    m.g.update(speed=1.0, depth=True)
    expect(s("motion") == "1.0× speed · depth on", f"motion {s('motion')}")
    cases = [
        (dict(message="off"), "Off"),
        (dict(message="clock", clock_24h=True), "Time every 36 s · 24-hour"),
        (
            dict(message="clock_fixed", clock_position="top_right", clock_24h=True),
            "Time · stays top right · 24-hour",
        ),
        (dict(message="text", message_text="Wake up, Neo..."), "Your text · Wake up, Neo..."),
        (dict(message="both", clock_24h=False), "Time and your text · 12-hour"),
    ]
    for upd, want in cases:
        m.g.update(upd)
        expect(s("message") == want, f"message {s('message')!r} != {want!r}")
    m.g.update(live_source="off")
    expect(s("live") == "Off", s("live"))
    m.g.update(live_source="cpu", live_target="both", live_strength=0.6)
    expect(s("live") == "CPU · speed and density · 0.60", s("live"))
    m.g.update(renderer="auto", upscaling="off")
    expect(s("rendering") == "Auto · upscaling off", s("rendering"))
    m.g.update(renderer="gpu", upscaling="quality")
    expect(s("rendering") == "GPU · Quality upscaling", s("rendering"))
    # monitor scope summarises effective values
    m.g.update(preset="film_1999", speed=1.0)
    m.over["MON-A"] = dict(preset="reloaded")
    m.set_scope("MON-A")
    expect(m.summary("look") == ("1 override on this monitor", True), "look count")
    m.set_scope("MON-B")
    expect(s("look") == "The Matrix (1999)", "monitor scope summary")


# Reset, cancel
def check_reset_cancel():
    raw = {
        "preset": "reloaded",
        "speed": 2.0,
        "monitors": {"MON-A": {"speed": 1.4}, "GONE": {"density": 0.5}},
    }
    m = model(raw)
    loaded = settings.clean(json.loads(json.dumps(raw)))
    m.set_scope("GONE")
    m.reset()
    expect(m.to_cfg() == dict(settings.DEFAULTS, monitors={}), "reset is not the defaults")
    expect(m.scope is None, "reset kept a disconnected scope")
    # Cancel: the model never touches the saved file; the file is unchanged.
    expect(settings.clean(json.loads(json.dumps(raw))) == loaded, "cancel changed the file")
    with scratch() as appdata:
        os.environ["APPDATA"] = appdata
        edited = model(raw)
        edited.set_scope("MON-A")
        edited.reset()
        expect(
            not os.path.exists(settings.settings_path()),
            "editing the model wrote a settings file (only OK may save)",
        )


# Letter font row
def check_font_row():
    expect(("message_font", "fontpick") in dm.PAGE_ROWS["message"], "no Letter font row")
    expect([k for k, _ in dm.PAGE_ROWS["message"]].count("message_bold") == 0, "stale bold row")
    expect(dm.LABELS["message_font"] == "Letter font", "font row label")
    expect(
        dm.HELP["message_font"]
        == "Opens your system's font picker. Its size sets how big the letters are; "
        "36 pt is the standard size. Bold letters read best in the rain; "
        "thin strokes can break up.",
        "font row help",
    )
    expect("message_font" not in dm.SEGMENTS, "message_font still has segments")
    for k in dm.FONT_KEYS:
        expect(k in dm.PAGE_KEYS["message"], f"{k} not in the message page keys")
    expect("message_size" not in dm.LABELS, "stale")
    expect(dm.font_text("", True, False, 36) == "Courier New Bold, 36 pt", "default font text")
    expect(dm.font_text("Georgia", False, True, 20) == "Georgia Italic, 20 pt", "italic text")
    expect(dm.font_text("Segoe UI", False, False, 12.5) == "Segoe UI, 12.5 pt", "plain text")
    expect(dm.font_text("Arial", True, True, 72) == "Arial Bold Italic, 72 pt", "bold italic")
    for msg, egg in (("off", False), ("off", True), ("clock", False), ("both", False)):
        m = model({"message": msg, "easter_egg": egg})
        r = m.row("message_font")
        expect(r.enabled == (msg != "off" or egg), f"{msg}/{egg}: font enabled {r.enabled}")
        if not r.enabled:
            expect(r.help == dm.DISABLED_HELP["message_font"], "font disabled help")
        else:
            expect(r.help == dm.HELP["message_font"], f"{msg}/{egg}: font help")
    m = model({"message": "clock"})
    expect(m.font_text() == "Courier New Bold, 36 pt", f"default shows {m.font_text()!r}")
    m.set_font("Georgia", False, True, 48)
    expect(m.font_text() == "Georgia Italic, 48 pt", f"edit shows {m.font_text()!r}")
    cfg = settings.clean(m.to_cfg())
    expect(
        (cfg["message_font"], cfg["message_bold"], cfg["message_italic"], cfg["message_font_size"])
        == ("Georgia", False, True, 48.0),
        "font edit did not survive settings.clean",
    )
    m.set_scope("MON-A")
    m.set_font("Segoe UI", False, False, 14)
    expect(m.to_cfg()["message_font"] == "Segoe UI", "font edit in a monitor scope not global")
    m.set_font("A" + chr(1) + "b" * 200, True, False, 500)
    expect(len(m.g["message_font"]) == 128 and chr(1) not in m.g["message_font"], "font cleaning")
    expect(m.g["message_font_size"] == 144.0, "size not clamped high")
    m.set_font("A", True, False, 1)
    expect(m.g["message_font_size"] == 8.0, "size not clamped low")
    m.reset_font()
    expect(
        (m.g["message_font"], m.g["message_bold"], m.g["message_italic"]) == ("", True, False)
        and m.g["message_font_size"] == 36.0
        and m.font_text() == "Courier New Bold, 36 pt",
        "Use default did not restore the default font",
    )
    m.set_font("Georgia", False, True, 60)
    m.reset()
    expect(m.font_text() == "Courier New Bold, 36 pt", "Reset kept the chosen font")


# Contrast
def check_contrast():
    from digital_rain.windows import dialog_widgets

    tokens, pairs = dialog_widgets.TOKENS, dialog_widgets.TEXT_PAIRS

    def lum(c):
        out = []
        for i in (1, 3, 5):
            v = int(c[i : i + 2], 16) / 255
            out.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]

    for fg, bg in pairs:
        hi, lo = sorted((lum(tokens[fg]), lum(tokens[bg])), reverse=True)
        ratio = (hi + 0.05) / (lo + 0.05)
        # WCAG AA for normal text.
        expect(ratio >= 4.5, f"contrast {fg} on {bg} is {ratio:.2f}:1 (need 4.5)")


def main():
    for fn in (
        check_presets,
        check_enable_rules,
        check_overrides,
        check_customise,
        check_message,
        check_to_cfg,
        check_summaries,
        check_reset_cancel,
        check_font_row,
        check_contrast,
    ):
        gate.run(fn)
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
