"""The Mac options sheet and saver, checked on Windows against fake AppKit.

Sections: the shared tables cover every setting and every control kind has a builder; the
bundle manifest lists the modules the sheet needs and one bundle id; the settings blob round
trip and load order (mac_settings, dialog_model); the sheet's wiring (tools/checks/fake_appkit.py);
mac_saver against the same fakes.

No AppKit runs here: the fakes check our calls against our own reading of the API.
design/mac-options-test.md is the manual test on a Mac. Prints "mac options check OK", or the
failures, and exits 1. Runs without a display or a GPU.

Usage: <venv python> tools/checks/check_mac_options.py
"""

import ast
import json
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TOOLS))
for folder in (TOOLS, ROOT):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import fake_appkit
from _gate import Checker, scratch

from digital_rain import dialog_model as dm
from digital_rain import settings
from digital_rain.mac import mac_settings

gate = Checker("mac options")
expect = gate.check

CONNECTED = [dict(id="MON-A", name="DELL U2720Q"), dict(id="MON-B", name="LG 27GL850")]
MONITORS = {
    "MON-A": {"name": "DELL U2720Q", "preset": "reloaded"},
    "MON-B": {"speed": 1.5, "depth": False},
}
KIND_CLASS = {
    "cards": "NSPopUpButton",
    "segmented": "NSSegmentedControl",
    "switch": "NSButton",
    "slider": "NSSlider",
    "dropdown": "NSPopUpButton",
    "grid": "NSPopUpButton",
    "text": "NSTextField",
    "font": "NSTextField",
    "folder": "NSTextField",
    "fontpick": "NSTextField",
    "box": "NSBox",
}
TARGET_SELECTORS = {
    "controlChanged_",
    "save_",
    "cancel_",
    "reset_",
    "choosePath_",
    "clearPath_",
    "chooseFont_",
    "useDefaultFont_",
    "changeFont_",
    "controlTextDidChange_",
    "tabView_didSelectTabViewItem_",
}
MAC_TITLES = ["Look", "Motion", "Message", "Live", "Graphics", "Pictures"]


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as handle:
        return handle.read()


def check_tables_cover_settings():
    from digital_rain.mac import mac_options

    kinds = {k for p in dm.PAGES for _key, k in dm.PAGE_ROWS[p]} | {k for _key, k in dm.BOX_ROWS}
    for kind in sorted(kinds):
        expect(kind in mac_options.KIND_BUILDERS, f"tables: no builder for control kind {kind}")
        name = mac_options.KIND_BUILDERS.get(kind)
        expect(
            name is not None and callable(getattr(mac_options.OptionsSheet, name, None)),
            f"tables: OptionsSheet has no builder {name} for {kind}",
        )
    expect(tuple(dm.PAGE_ROWS) == dm.PAGES, "tables: PAGE_ROWS pages differ from PAGES")
    for p in dm.PAGES:
        rows = [k for k, _ in dm.PAGE_ROWS[p] if k not in ("effects", "keep_clock")]
        if any(k == "effects" for k, _ in dm.PAGE_ROWS[p]):
            rows += list(dm.BOX_KEYS)
        if any(kind == "fontpick" for _k, kind in dm.PAGE_ROWS[p]):
            rows += [k for k in dm.FONT_KEYS if k not in rows]
        expect(
            set(rows) == set(dm.PAGE_KEYS[p]),
            f"tables: PAGE_ROWS[{p}] keys {sorted(rows)} != PAGE_KEYS {sorted(dm.PAGE_KEYS[p])}",
        )
    page_keys = {k for p in dm.PAGES for k in dm.PAGE_KEYS[p]}
    for key in settings.DEFAULTS:
        expect(
            key in page_keys or key in dm.NON_UI_KEYS,
            f"tables: settings key {key} is on no page and not in NON_UI_KEYS",
        )
        expect(
            not (key in page_keys and key in dm.NON_UI_KEYS),
            f"tables: settings key {key} is on a page and in NON_UI_KEYS",
        )
    m = dm.Model(settings.clean(None), ())
    all_rows = [(k, kind) for p in dm.PAGES for k, kind in dm.PAGE_ROWS[p]] + list(dm.BOX_ROWS)
    for key, kind in all_rows:
        if key == "effects":
            continue
        expect(key in dm.LABELS, f"tables: {key} has no LABELS entry")
        if kind == "slider":
            expect(
                key in dm.SLIDERS and key in settings.RANGES,
                f"tables: slider {key} lacks SLIDERS or RANGES",
            )
        if kind == "segmented":
            expect(key in dm.SEGMENTS, f"tables: segmented {key} lacks SEGMENTS")
        if kind in ("dropdown", "cards", "grid"):
            try:
                expect(len(m.options(key)) > 0, f"tables: options({key}) is empty")
            except Exception as exc:
                expect(False, f"tables: options({key}) raised {exc!r}")
    check_no_desktop_or_platform_imports()


# Importing the options sheet and the blob module must work without tkinter or the desktop
# dialog (the bundle excludes them) and without AppKit at import time (it loads lazily).
BLOCKED_IMPORTS = (
    "digital_rain.windows.config_dialog",
    "digital_rain.windows.dialog_widgets",
    "digital_rain.windows.dialog_preview",
    "tkinter",
    "AppKit",
    "Foundation",
    "ScreenSaver",
    "objc",
)
IMPORT_PROBE = (
    "import sys\n"
    f"for name in {BLOCKED_IMPORTS!r}:\n"
    "    sys.modules[name] = None\n"
    "from digital_rain.mac import mac_options, mac_settings\n"
)


def check_no_desktop_or_platform_imports():
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_PROBE],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    expect(
        result.returncode == 0,
        f"tables: mac_options/mac_settings import a blocked module: {result.stderr.strip()[-300:]}",
    )


def _assigned(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    return None


def _strings(node):
    return {
        n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }


def check_bundle_manifest():
    """setup_mac.py (parsed, never run) bundles what the sheet needs and names one bundle id."""
    tree = ast.parse(read("setup_mac.py"))
    needed = (
        "digital_rain",
        "digital_rain.mac",
        "digital_rain.dialog_model",
        "digital_rain.settings",
        "digital_rain.mac.mac_saver",
        "digital_rain.mac.mac_settings",
        "digital_rain.mac.mac_options",
        "digital_rain.osapi",
        "digital_rain.osapi.common",
        "digital_rain.osapi.mac",
    )
    own = _strings(_assigned(tree, "OWN_MODULES"))
    for mod in needed:
        expect(mod in own, f"bundle: setup_mac.py OWN_MODULES lacks {mod}")
    opts = _assigned(tree, "OPTIONS")
    excludes = set()
    if isinstance(opts, ast.Dict):
        for key, value in zip(opts.keys, opts.values, strict=True):
            if isinstance(key, ast.Constant) and key.value == "excludes":
                excludes = _strings(value)
    expect(bool(excludes), "bundle: setup_mac.py OPTIONS has no excludes list")
    for mod in needed:
        expect(mod not in excludes, f"bundle: setup_mac.py excludes {mod}")
    for mod in (
        "digital_rain.windows",
        "digital_rain.windows.config_dialog",
        "digital_rain.windows.dialog_widgets",
        "digital_rain.windows.dialog_preview",
        "tkinter",
    ):
        expect(mod in excludes, f"bundle: setup_mac.py no longer excludes {mod}")
    bundle_id = _assigned(tree, "BUNDLE_ID")
    gate.equal(
        bundle_id.value if isinstance(bundle_id, ast.Constant) else None,
        mac_settings.MODULE_NAME,
        "bundle: setup_mac.py BUNDLE_ID against MODULE_NAME",
    )


def _new_value(m, key):
    """A valid value for `key` that differs from the model's current one."""
    cur = m.control_value(key)
    try:
        opts = [v for v, _l in m.options(key)]
    except KeyError:
        opts = None
    if opts:
        return next(v for v in opts if v != cur)
    default = settings.DEFAULTS.get(key)
    if isinstance(default, bool) or key == "keep_clock":
        return not cur
    if key == "message_font_size":
        return 60.0
    if isinstance(default, float):
        lo, hi = settings.RANGES[key]
        dec = dm.SLIDERS[key][0]
        return round(lo if abs(cur - lo) > 1e-6 else hi, dec)
    if key == "message_text":
        return "HELLO NEO"
    if key == "message_font":
        return "Georgia"
    if key == "font_path":
        return "/Library/Fonts/Test.ttf"
    if key == "image_dir":
        return "/Users/test/Pictures/Images"
    raise ValueError(f"no test value for {key}")


def check_settings_blob():
    base = settings.clean(None)
    cfg, problem = mac_settings.decode(mac_settings.encode(base))
    expect(cfg == base and problem is None, "settings blob: defaults do not survive encode/decode")
    for page in dm.PAGES:
        for key in dm.PAGE_KEYS[page]:
            m = dm.Model(settings.clean(None), ())
            if key in dm.FIXED_EFFECTS:
                m.control_set("preset", "custom")
            value = _new_value(m, key)
            m.control_set(key, value)
            got, _p = mac_settings.decode(mac_settings.encode(m.to_cfg()))
            ok = got[key] == value
            expect(ok, f"settings blob: {key}={value!r} came back as {got[key]!r}")
    got, _p = mac_settings.decode(
        mac_settings.encode({"speed": 99, "bloom": -5, "message_text": "A" * 40})
    )
    expect(
        got["speed"] == settings.RANGES["speed"][1] and got["bloom"] == 0.0,
        "settings blob: out-of-range numbers not clamped",
    )
    expect(
        got["message_text"] == "A" * settings.MESSAGE_TEXT_MAX,
        "settings blob: message_text not cut to 24",
    )
    expect(mac_settings.decode(None) == (None, None), "settings blob: decode(None)")
    for bad in ("{", "[]", "3", 3, b"{}"):
        cfg, problem = mac_settings.decode(bad)
        expect(
            cfg is None and bool(problem), f"settings blob: decode({bad!r}) gave {cfg}, {problem}"
        )
    check_load_order()
    check_monitor_overrides()


def check_load_order():
    """Blob against settings file: the blob wins, a corrupt blob falls back to the file."""
    with scratch("matrix_mac_options_") as tmp:
        path = os.path.join(tmp, "settings.json")
        missing = os.path.join(tmp, "missing.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"preset": "resurrections"}, handle)
        blob = mac_settings.encode(dict(settings.clean(None), preset="reloaded"))
        cfg, src, probs = mac_settings.resolve(blob, missing)
        expect(
            src == "defaults" and cfg["preset"] == "reloaded" and not probs,
            "settings blob: blob only",
        )
        cfg, src, probs = mac_settings.resolve(None, path)
        expect(
            src == "file" and cfg["preset"] == "resurrections" and not probs,
            "settings blob: file only",
        )
        cfg, src, probs = mac_settings.resolve(blob, path)
        expect(
            src == "defaults" and cfg["preset"] == "reloaded", "settings blob: both: blob must win"
        )
        cfg, src, probs = mac_settings.resolve("{", path)
        expect(
            src == "file" and len(probs) == 1,
            f"settings blob: corrupt blob plus file gave {src} {probs}",
        )
        cfg, src, probs = mac_settings.resolve(None, missing)
        expect(
            src == "built-in" and cfg == settings.clean(None) and not probs,
            "settings blob: neither",
        )


def check_monitor_overrides():
    """Per-monitor overrides pass through a save untouched; reset keeps or drops them."""
    fixture = settings.clean({"monitors": MONITORS})["monitors"]
    expect(fixture == MONITORS, "settings blob: monitors fixture is not clean")
    m = dm.Model(settings.clean({"preset": "film_1999", "monitors": MONITORS}), ())
    m.control_set("speed", 2.0)
    m.control_set("preset", "reloaded")
    m.control_set("depth", False)
    got, _p = mac_settings.decode(mac_settings.encode(m.to_cfg()))
    expect(
        got["monitors"] == MONITORS, f"settings blob: monitors changed by a save: {got['monitors']}"
    )
    expect(got["speed"] == 2.0, "settings blob: all-monitor speed not saved")
    m.reset(keep_overrides=True)
    expect(
        m.to_cfg()["monitors"] == MONITORS,
        "settings blob: reset(keep_overrides=True) lost monitors",
    )
    expect(m.to_cfg()["speed"] == settings.DEFAULTS["speed"], "settings blob: reset kept speed")
    m.reset()
    expect(m.to_cfg()["monitors"] == {}, "settings blob: reset() kept monitors (Windows behaviour)")
    check_module_name_and_labels()


def check_module_name_and_labels():
    name = mac_settings.MODULE_NAME
    expect(
        mac_settings.check_module_name(name, "/Library/Screen Savers/MatrixRain.saver") is None,
        "settings blob: check_module_name warns for the right id",
    )
    expect(
        mac_settings.check_module_name(
            "org.python.python", "/Library/Frameworks/Python.framework/Python.app"
        )
        is None,
        "settings blob: check_module_name warns under the host runner",
    )
    expect(
        bool(mac_settings.check_module_name("x.y", "/Users/a/MatrixRain.saver")),
        "settings blob: check_module_name misses a wrong id",
    )


class _Log:
    def __init__(self):
        self.lines = []

    def __call__(self, msg):
        self.lines.append(str(msg))

    def text(self):
        return "\n".join(self.lines)


def _read_control(sheet, key):
    """What the control for `key` shows, as a model value."""
    import AppKit

    r = sheet.rows[key]
    ctl, kind = r["control"], r["kind"]
    if kind in ("cards", "dropdown", "grid"):
        return r["values"][ctl.indexOfSelectedItem()]
    if kind == "segmented":
        return r["values"][ctl.selectedSegment()]
    if kind == "switch":
        return ctl.state() == AppKit.NSControlStateValueOn
    if kind == "slider":
        return round(ctl.doubleValue(), dm.SLIDERS[key][0])
    if kind == "text":
        return ctl.stringValue()
    if kind == "font":
        text = ctl.stringValue()
        return "" if text == dm.FILM_GLYPHS_LABEL else text
    if kind == "folder":
        text = ctl.stringValue()
        return "" if text == dm.NO_FOLDER_LABEL else text
    raise ValueError(kind)


def _fire(sheet, key, value):
    """Set the control for `key` to `value` and send its action, as a click does."""
    import AppKit

    r = sheet.rows[key]
    ctl, kind = r["control"], r["kind"]
    if kind in ("cards", "dropdown", "grid"):
        ctl.selectItemAtIndex_(r["values"].index(value))
    elif kind == "segmented":
        ctl.setSelectedSegment_(r["values"].index(value))
    elif kind == "switch":
        ctl.setState_(AppKit.NSControlStateValueOn if value else AppKit.NSControlStateValueOff)
    elif kind == "slider":
        ctl.setDoubleValue_(value)
    elif kind == "text":
        ctl.type_text(value)
        return
    elif kind in ("font", "folder"):
        if value:
            AppKit.NSOpenPanel.result = value
            r["buttons"][0].fire()
        else:
            r["buttons"][1].fire()
        return
    ctl.fire()


def _sheet(cfg=None, parent=True):
    from digital_rain.mac import mac_options

    calls = dict(saved=0, closed=0)

    def saved():
        calls["saved"] += 1

    def closed():
        calls["closed"] += 1

    if cfg is None:
        sheet = mac_options.build(on_saved=saved, on_closed=closed)
    else:
        sheet = mac_options.OptionsSheet(cfg, on_saved=saved, on_closed=closed)
    if parent:
        sheet.window.parent = fake_appkit.NSWindow()
    return sheet, calls


def _labels(sheet):
    """Every non-editable text field (label) in the window, tab pages included."""
    views = sheet.window.contentView().descendants()
    controls = [c for c in sheet.controls.values()]
    return [
        v
        for v in views
        if type(v) is fake_appkit.NSTextField
        and not v.editable
        and not any(v is c for c in controls)
    ]


def check_sheet_layout(sheet):
    """Tab titles fit, wrapped text is never cut off, pages size the window."""
    from digital_rain.mac import mac_options as mo

    # tab titles: one equal share of the tab strip each, with a per-character budget
    seg = mo.tab_segment_width()
    expect(
        sheet.tab_view.frame().size.width == mo.tab_view_width() <= mo.WIN_W,
        "sheet: tab view width is not tab_view_width()",
    )
    for item in sheet.tab_view.tabViewItems():
        need = len(item.label()) * mo.CHAR_W + mo.TAB_PAD
        expect(need <= seg, f"sheet: tab {item.label()!r} needs {need:.0f} pt, segment {seg:.0f}")
    expect(mo.tab_title("look") == "Look", "sheet: tab_title(look)")
    dm.PAGE_TITLES["zz_future"] = "Future page"
    try:
        expect(mo.tab_title("zz_future") == "Future page", "sheet: unknown page has no title")
    finally:
        del dm.PAGE_TITLES["zz_future"]
    # wrapping: the help line under Live > Source wraps and is tall enough
    src = dm.HELP["live_source"]
    hl = sheet.rows["live_source"]["help"].frame()
    expect(
        mo.text_lines(src, hl.size.width, small=True) >= 2,
        "sheet: live_source help expected to need 2 lines (metrics changed?)",
    )
    for key, r in sheet.rows.items():
        f = r["help"].frame()
        for text in mo.help_texts(key):
            need = mo.text_height(text, f.size.width, small=True)
            expect(
                f.size.height >= need,
                f"sheet: help of {key} is {f.size.height} pt, needs {need} for {text!r}",
            )
    for lab in _labels(sheet):
        f = lab.frame()
        small = lab.font is not None
        need = mo.text_height(lab.stringValue(), f.size.width, small=small)
        expect(
            f.size.height >= need,
            f"sheet: label {lab.stringValue()[:40]!r} is {f.size.height} pt high, needs {need}",
        )
        expect(
            lab.max_layout_width == f.size.width,
            f"sheet: label {lab.stringValue()[:40]!r} has no preferred max layout width",
        )
    st = sheet.status.frame()
    for text in (mo.STATUS_OPEN, mo.STATUS_SAVED, mo.STATUS_RESET):
        need = mo.text_height(text, st.size.width, small=True)
        expect(st.size.height >= need, f"sheet: status {text[:30]!r} needs {need} pt")
    expect(st.origin.y + st.size.height <= mo.FOOTER_H, "sheet: status line overlaps the tabs")
    # page height follows the rows; the window follows the selected tab
    win = sheet.window
    for page in dm.PAGES:
        doc = sheet.tab_view.tabViewItems()[dm.PAGES.index(page)].view().documentView()
        expect(
            doc.frame().size.height == sheet.page_heights[page],
            f"sheet: {page} document height is not page_heights",
        )
    live = sheet.window_height("live")
    expect(live < mo.WIN_H, f"sheet: the Live page fills the tallest sheet ({live})")
    expect(
        win.contentView().frame().size.height == sheet.window_height(dm.PAGES[0]),
        "sheet: the sheet does not open at the first page's height",
    )
    i_live = dm.PAGES.index("live")
    top = win.frame().origin.y + win.frame().size.height
    sheet.tab_view.select(i_live)
    expect(
        win.contentView().frame().size.height == live,
        "sheet: selecting Live did not resize the window to its rows",
    )
    expect(
        win.frame().origin.y + win.frame().size.height == top,
        "sheet: resizing for a tab moved the top edge",
    )
    expect(win.frames and win.frames[-1][2] is True, "sheet: tab resize is not animated")
    sheet.tab_view.select(0)
    expect(
        win.contentView().frame().size.height == sheet.window_height(dm.PAGES[0]),
        "sheet: selecting Look did not restore its height",
    )
    for page in dm.PAGES:
        h = sheet.window_height(page)
        expect(mo.MIN_H <= h <= mo.WIN_H, f"sheet: {page} window height {h}")


def check_font_row(sheet):
    """The Letter font row: Choose font opens the panel, a pick stores family, bold and
    italic, Use default restores them, and the row follows the message enable rule."""
    import AppKit

    m = sheet.model
    row = sheet.rows["message_font"]
    field = row["control"]
    expect(type(field).__name__ == "NSTextField", "font row: no text field")
    expect(dm.LABELS["message_font"] == "Letter font", "font row: label")
    expect(
        field.stringValue() == "Courier New Bold, 36 pt", f"font row: shows {field.stringValue()!r}"
    )
    fm = AppKit.NSFontManager.sharedFontManager()
    row["buttons"][0].fire()
    expect(fm.panel_opened == 1, "font row: Choose font did not open the font panel")
    expect(
        fm.selected.family == "Courier New"
        and fm.selected.traits == 2
        and fm.selected.pointSize() == 36.0,
        "font row: panel not started on the current font",
    )
    fm.pick("Georgia", 1, 48.0)
    cfg = m.to_cfg()
    expect(
        (cfg["message_font"], cfg["message_bold"], cfg["message_italic"], cfg["message_font_size"])
        == ("Georgia", False, True, 48.0),
        f"font row: pick stored {cfg['message_font']!r}",
    )
    expect(
        field.stringValue() == "Georgia Italic, 48 pt", f"font row: shows {field.stringValue()!r}"
    )
    fm.pick("Segoe UI", 3, 500.0)
    expect(
        (m.g["message_bold"], m.g["message_italic"], m.g["message_font_size"])
        == (True, True, 144.0),
        "font row: bold italic pick or size not clamped",
    )
    row["buttons"][1].fire()
    cfg = m.to_cfg()
    expect(
        (cfg["message_font"], cfg["message_bold"], cfg["message_italic"], cfg["message_font_size"])
        == ("", True, False, 36.0),
        "font row: Use default did not restore the default",
    )
    expect(field.stringValue() == "Courier New Bold, 36 pt", "font row: default text after reset")
    m.set("message", "off")
    m.set("easter_egg", False)
    expect(
        not field.isEnabled() and not any(b.isEnabled() for b in row["buttons"]),
        "font row: enabled with nothing shown",
    )
    m.set("message", "clock")
    expect(field.isEnabled(), "font row: disabled while the time shows")


def check_sheet_wiring():
    from digital_rain.mac import mac_options

    fake_appkit.reset()
    sheet, calls = _sheet()
    items = sheet.tab_view.tabViewItems()
    expect(
        [i.label() for i in items] == MAC_TITLES, f"sheet: tab titles {[i.label() for i in items]}"
    )
    expect(len(items) == 6, f"sheet: {len(items)} tabs, not 6")
    check_sheet_layout(sheet)
    for item, page in zip(items, dm.PAGES, strict=True):
        inside = item.view().descendants()
        for key, kind in dm.PAGE_ROWS[page]:
            ctl = sheet.controls.get(key)
            expect(
                type(ctl).__name__ == KIND_CLASS[kind],
                f"sheet: {key} is a {type(ctl).__name__}, not {KIND_CLASS[kind]}",
            )
            expect(any(v is ctl for v in inside), f"sheet: {key} is not on the {page} tab")
            if kind == "box":
                for bkey, bkind in dm.BOX_ROWS:
                    bctl = sheet.controls.get(bkey)
                    expect(
                        type(bctl).__name__ == KIND_CLASS[bkind],
                        f"sheet: box {bkey} is a {type(bctl).__name__}",
                    )
                    expect(any(v is bctl for v in inside), f"sheet: box {bkey} not on {page}")
    expect(sheet.status.stringValue() == mac_options.STATUS_OPEN, "sheet: no open status line")
    expect(sheet.window.released_when_closed is False, "sheet: window released when closed")
    # every control edits its key
    m = sheet.model
    _fire(sheet, "preset", "custom")
    for page in dm.PAGES:
        keys = [k for k, _ in dm.PAGE_ROWS[page] if k not in ("effects", "keep_clock")]
        if page == "look":
            keys += list(dm.BOX_KEYS)
        keys = [k for k in keys if k != "message_font"]
        for key in keys:
            value = _new_value(m, key)
            _fire(sheet, key, value)
            got = m.message_segment() if key == "message" else m.to_cfg()[key]
            expect(got == value, f"sheet: firing {key}={value!r} gave {got!r}")
            expect(
                _read_control(sheet, key) == value,
                f"sheet: control {key} shows {_read_control(sheet, key)!r}",
            )
            if key == "preset":  # a film preset locks the box; unlock it for its rows
                _fire(sheet, "preset", "custom")
    check_font_row(sheet)
    _fire(sheet, "message", "clock")
    expect(m.to_cfg()["message"] == "clock", "sheet: message segment Clock")
    expect(not sheet.controls["keep_clock"].isHidden(), "sheet: keep_clock hidden for Clock")
    _fire(sheet, "keep_clock", True)
    expect(m.to_cfg()["message"] == "clock_fixed", "sheet: keep_clock switch not set_keep_clock")
    expect(
        sheet.controls["clock_position"].isEnabled(), "sheet: clock_position off with keep clock"
    )
    _fire(sheet, "message", "clock")  # same segment: stays clock_fixed (set_message_segment)
    expect(m.to_cfg()["message"] == "clock_fixed", "sheet: re-picking Clock dropped keep clock")
    _fire(sheet, "message", "text")
    expect(
        m.to_cfg()["message"] == "text" and sheet.controls["keep_clock"].isHidden(),
        "sheet: message Text",
    )
    sheet.rows["message_text"]["control"].type_text("WAKE\x07 UP " + "N" * 30)
    expect(
        m.to_cfg()["message_text"] == dm.clean_text("WAKE\x07 UP " + "N" * 30)
        and sheet.rows["message_text"]["control"].stringValue() == m.g["message_text"],
        "sheet: message text not cleaned and written back",
    )
    # enable rules
    _fire(sheet, "live_source", "off")
    expect(
        not sheet.controls["live_target"].isEnabled()
        and not sheet.controls["live_strength"].isEnabled(),
        "sheet: live_source off",
    )
    _fire(sheet, "live_source", "cpu")
    expect(
        sheet.controls["live_target"].isEnabled() and sheet.controls["live_strength"].isEnabled(),
        "sheet: live_source cpu",
    )
    _fire(sheet, "preset", "film_1999")
    expect(
        all(
            not sheet.controls[k].isEnabled()
            for k in dm.SHARED_EFFECTS
            if dict(dm.BOX_ROWS)[k] == "slider"
        ),
        "sheet: film preset leaves box sliders on",
    )
    expect(not sheet.customise_button.isHidden(), "sheet: no Customise button for a film preset")
    expect("The Matrix" in sheet.box.title(), f"sheet: box title {sheet.box.title()!r}")
    sheet.customise_button.fire()
    expect(
        m.to_cfg()["preset"] == "custom"
        and sheet.customise_button.isHidden()
        and sheet.controls["bloom"].isEnabled(),
        "sheet: Customise these",
    )
    # Save
    defaults = fake_appkit.defaults()
    defaults.store.clear()
    win, parent = sheet.window, sheet.window.parent
    expect(sheet.save_button.window() is win, "sheet: Save button is not in the window")
    sheet.save_button.fire()
    expect(
        set(defaults.store) == {mac_settings.BLOB_KEY},
        f"sheet: Save wrote keys {sorted(defaults.store)}",
    )
    got, _p = mac_settings.decode(defaults.store.get(mac_settings.BLOB_KEY))
    expect(got == settings.clean(m.to_cfg()), "sheet: saved blob differs from the model")
    expect(calls["saved"] == 1 and calls["closed"] == 1, f"sheet: Save callbacks {calls}")
    expect(
        (mac_settings.CHANGED_NOTE, None) in fake_appkit.center().posts,
        "sheet: Save posted no change notification",
    )
    expect(parent.ended == [win] and win.closed == 0, "sheet: Save did not end the sheet")
    sheet, calls = _sheet(parent=False)
    sheet.save_button.fire()
    expect(sheet.window.closed == 1, "sheet: Save without a sheet parent did not close")
    # Save that fails
    fake_appkit.reset()
    sheet, calls = _sheet()
    fake_appkit.defaults().sync_result = False
    _fire(sheet, "speed", 2.0)
    sheet.save_button.fire()
    expect("Could not save" in sheet.status.stringValue(), "sheet: failed Save shows no error")
    expect(
        calls["saved"] == 0
        and calls["closed"] == 0
        and not sheet.window.parent.ended
        and not sheet.window.closed,
        "sheet: failed Save closed the sheet or reloaded",
    )
    # Cancel
    fake_appkit.reset()
    sheet, calls = _sheet()
    _fire(sheet, "speed", 2.0)
    _fire(sheet, "color", "red" if "red" in settings.COLORS else list(settings.COLORS)[-1])
    sheet.cancel_button.fire()
    expect(not fake_appkit.defaults().store, "sheet: Cancel wrote settings")
    expect(
        sheet.window.parent.ended == [sheet.window]
        and calls["closed"] == 1
        and calls["saved"] == 0,
        "sheet: Cancel did not end the sheet",
    )
    # Reset
    fake_appkit.reset()
    sheet, calls = _sheet(settings.clean({"preset": "custom", "monitors": MONITORS}))
    for key in ("speed", "density", "bloom", "renderer", "message"):
        _fire(sheet, key, _new_value(sheet.model, key))
    sheet.reset_button.fire()
    ref = dm.Model(settings.clean(None), ())
    for key in sheet.rows:
        if key == "message_font":
            expect(
                sheet.rows[key]["control"].stringValue() == ref.font_text(),
                "sheet: after Reset the letter font text",
            )
            continue
        expect(
            _read_control(sheet, key) == ref.control_value(key),
            f"sheet: after Reset {key} shows {_read_control(sheet, key)!r}",
        )
    expect(sheet.model.to_cfg()["monitors"] == MONITORS, "sheet: Reset dropped monitors")
    expect(
        not fake_appkit.defaults().store and calls["closed"] == 0, "sheet: Reset saved or closed"
    )
    expect(sheet.status.stringValue() == mac_options.STATUS_RESET, "sheet: Reset status line")
    expect(
        not sheet.monitors_label.isHidden()
        and sheet.monitors_label.stringValue().startswith("2 displays"),
        "sheet: Look tab does not mention the per-display settings",
    )


class _Ctx:
    def makeCurrentContext(self):
        pass


class _GLView:
    def openGLContext(self):
        return _Ctx()


class _Renderer:
    closed = 0

    def close(self):
        self.closed += 1


def check_saver_hooks():
    from digital_rain import osapi

    fake_appkit.reset()
    from digital_rain.mac import mac_options, mac_saver

    defaults = fake_appkit.defaults()
    defaults.store[mac_settings.BLOB_KEY] = mac_settings.encode(
        dict(settings.clean(None), preset="reloaded")
    )
    expect(mac_saver.load_settings()["preset"] == "reloaded", "saver: blob not loaded")
    with scratch("matrix_mac_saver_") as tmp:
        path = os.path.join(tmp, "s.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"preset": "resurrections"}, handle)
        mac_saver.settings_file = path
        try:
            expect(
                mac_saver.load_settings()["preset"] == "resurrections",
                "saver: settings_file does not win over the blob",
            )
        finally:
            mac_saver.settings_file = None
    view = fake_appkit.ScreenSaverView()
    saver = mac_saver._Saver(view, True, 99)
    win = saver.configure_sheet()
    expect(
        isinstance(saver.sheet_target, mac_options.OptionsSheet)
        and win is saver.sheet_target.window,
        "saver: configure_sheet is not the options sheet",
    )
    saver.sheet_target.cancel_button.fire()
    expect(saver.sheet_target is None, "saver: closing the sheet kept sheet_target")
    gate.equal(
        mac_saver.SAVER_BUNDLE_ID,
        mac_settings.MODULE_NAME,
        "saver: SAVER_BUNDLE_ID against MODULE_NAME",
    )
    log = _Log()
    real_log, real_build = osapi.log, mac_options.build
    osapi.log = log

    def broken(**_kw):
        raise RuntimeError("sheet test failure")

    mac_options.build = broken
    try:
        win = saver.configure_sheet()
    finally:
        mac_options.build = real_build
        osapi.log = real_log
    texts = [v.stringValue() for v in win.contentView().subviews() if hasattr(v, "stringValue")]
    expect(
        isinstance(saver.sheet_target, mac_saver.MatrixRainSheetTarget)
        and any("could not open" in t for t in texts),
        "saver: no fallback sheet",
    )
    expect(
        "Traceback" in log.text() and "sheet test failure" in log.text(),
        "saver: fallback did not log the traceback",
    )
    saver.glview, saver.failed, saver.stopped = _GLView(), False, False
    saver.cfg = settings.clean(None)
    renderer = saver.renderer = _Renderer()
    saver._ensure_renderer = lambda: False
    saver.request_reload()
    saver.tick()
    expect(
        saver.cfg is None and saver.renderer is None and renderer.closed == 1 and not saver.reload,
        "saver: request_reload then tick did not reload",
    )
    saver.stopped = True
    saver.request_reload()
    saver.tick()
    expect(saver.reload, "saver: a stopped view dropped the reload flag")
    for ident, path, warn in (
        ("x.y", "/Library/Screen Savers/MatrixRain.saver", True),
        (mac_settings.MODULE_NAME, "/Library/Screen Savers/MatrixRain.saver", False),
    ):
        fake_appkit.NSBundle.ident, fake_appkit.NSBundle.path = ident, path
        log = _Log()
        osapi.log = log
        try:
            mac_saver._check_bundle()
        finally:
            osapi.log = real_log
        expect(("WARNING" in log.text()) == warn, f"saver: _check_bundle({ident}) log {log.lines}")
    check_srgb_tagging(mac_saver)
    cls = mac_options._target_class()
    expect(mac_options._target_class() is cls, "saver: _target_class made a second class")
    own = {k for k, v in vars(cls).items() if callable(v) and not k.startswith("__")}
    expect(own == TARGET_SELECTORS, f"saver: target class methods {sorted(own)}")


def _srgb_run(mac_saver, layer=True, window=True, screen=True):
    """A fresh view and _Saver; apply_srgb before and after it has a window.
    -> (saver, window, gl layer, log lines mentioning a colour space)."""
    import AppKit

    from digital_rain import osapi

    log = _Log()
    real_log = osapi.log
    osapi.log = log
    win = None
    try:
        view = fake_appkit.ScreenSaverView()
        saver = mac_saver._Saver(view, True, 98)  # GL view fails on the fakes (logged)
        saver.glview = fake_appkit.NSOpenGLView()
        gl_layer = saver.glview._layer = fake_appkit.Layer() if layer else None
        saver.apply_srgb()  # no window yet: nothing, and tries again later
        if window:
            win = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                AppKit.NSMakeRect(0, 0, 300, 200), 1, 2, False
            )
            if screen:
                win._screen = fake_appkit.Screen("Adobe RGB (1998)")
            win.contentView().addSubview_(view)
            saver.apply_srgb()
            saver.apply_srgb()  # second call (startAnimation after the move): no-op
    finally:
        osapi.log = real_log
    return saver, win, gl_layer, [ln for ln in log.lines if "colour space" in ln]


def check_srgb_tagging(mac_saver):
    """The sRGB colour-space tag (unverified on a Mac; this checks the calls)."""
    import AppKit

    saver, win, gl_layer, lines = _srgb_run(mac_saver)
    expect(len(lines) == 1, f"saver: colour space logged {len(lines)} times: {lines}")
    expect(
        len(win.color_spaces) == 1 and win.color_spaces[0].localizedName() == "sRGB IEC61966-2.1",
        f"saver: window colour space calls {win.color_spaces}",
    )
    expect(
        gl_layer.spaces == [("CGColorSpace", "sRGB IEC61966-2.1")],
        f"saver: GL layer colour space calls {gl_layer.spaces}",
    )
    expect(
        lines
        and "window and GL view layer" in lines[0]
        and "Adobe RGB (1998)" in lines[0]
        and "Traceback" not in lines[0],
        f"saver: colour space log line {lines}",
    )
    # not layer-backed, no screen: window only, still one line
    saver, win, _l, lines = _srgb_run(mac_saver, layer=False, screen=False)
    expect(
        len(lines) == 1 and "set on window;" in lines[0] and "space None" in lines[0],
        f"saver: colour space without a layer {lines}",
    )
    # never in a window: nothing set, nothing logged
    saver, _w, gl_layer, lines = _srgb_run(mac_saver, window=False)
    expect(
        not lines and not saver.color_done and not gl_layer.spaces,
        f"saver: colour space set with no window {lines}",
    )
    # AppKit without NSColorSpace, then a window without setColorSpace_: no raise
    real = AppKit.NSColorSpace
    del AppKit.NSColorSpace
    try:
        saver, win, gl_layer, lines = _srgb_run(mac_saver)
    finally:
        AppKit.NSColorSpace = real
    expect(
        len(lines) == 1
        and "neither window nor layer" in lines[0]
        and "no NSColorSpace" in lines[0]
        and not win.color_spaces
        and not gl_layer.spaces,
        f"saver: colour space with no NSColorSpace {lines}",
    )
    real_set = AppKit.NSWindow.setColorSpace_
    del AppKit.NSWindow.setColorSpace_
    try:
        saver, win, gl_layer, lines = _srgb_run(mac_saver)
    finally:
        AppKit.NSWindow.setColorSpace_ = real_set
    expect(
        len(lines) == 1
        and "window not set" in lines[0]
        and "set on GL view layer" in lines[0]
        and "FAILED" not in lines[0],
        f"saver: colour space with no setColorSpace_ {lines}",
    )


def main():
    fake_appkit.install()
    for fn in (
        check_tables_cover_settings,
        check_bundle_manifest,
        check_settings_blob,
        check_sheet_wiring,
        check_saver_hooks,
    ):
        gate.run(fn)
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
