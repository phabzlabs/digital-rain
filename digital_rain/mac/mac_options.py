"""The Mac options sheet: what the Options button in System Settings >
Screen Saver opens, returned from MatrixRainView.configureSheet.

The sheet is built at runtime from the tables the Windows settings window uses
(dialog_model.PAGES, PAGE_ROWS, BOX_ROWS, LABELS, SLIDERS, PICKERS, settings.RANGES),
and every edit goes through dialog_model.Model, so the enable rules are the same
as on Windows. Save writes one JSON blob to ScreenSaverDefaults (mac_settings).

AppKit, Foundation and objc are imported inside functions (_ak), so
tools/checks/check_mac_options.py imports this module on Windows with fake modules.
PyObjC NSObject subclasses reject Python-style methods, so OptionsSheet (plain
Python) does the work and the Objective-C target only forwards its action,
text-delegate and tab-delegate selectors to it.
"""

import functools
import traceback

from digital_rain import dialog_model as dm
from digital_rain import osapi, settings
from digital_rain.mac import mac_settings

WIN_W, WIN_H = 760, 600  # WIN_H is the tallest the sheet gets (see fit_page)
MIN_H = 320
FOOTER_H = 56
TAB_TOP = 50  # tab view height above its page (tab strip and insets)
# The footer status line, between Reset and Cancel: (x, y, width, height).
STATUS_FRAME = (16 + 158, 6, WIN_W - 2 * 16 - 370, FOOTER_H - 10)
MARGIN = 16
LABEL_W = 190  # row labels: the longest (Upscaling (AMD FSR 1.0)) on one line
ROW_GAP = 10

# Tab titles on the Mac: one word each, because the native tab strip gives each
# of the 8 tabs an equal share of the sheet width and truncates longer titles.
# Keyed by page; a page missing here uses dialog_model.PAGE_TITLES.
MAC_TAB_TITLES = {
    "look": "Look",
    "motion": "Motion",
    "message": "Message",
    "live": "Live",
    "rendering": "Graphics",
    "images": "Pictures",
}
# Conservative text metrics for layout (points). AppKit is not measured: these
# are upper bounds on the average width of a character of the system font, so a
# line we think fits does fit. TAB_PAD is a tab segment's padding around its title.
CHAR_W = 7.5  # 13 pt system font
SMALL_CHAR_W = 6.5  # 11 pt small system font
LINE_H = 17
SMALL_LINE_H = 14
TAB_PAD = 24

STATUS_OPEN = "Changes show in the preview after Save."
STATUS_SAVED = (
    "Saved. If the screen saver still shows the old settings, pick another "
    "screen saver and then Digital Rain again, or log out and back in."
)
STATUS_RESET = "Defaults restored. Nothing is saved until you press Save."
MONITORS_NOTE = (
    "{n} displays have their own settings. This sheet changes the "
    "all-monitor values and keeps those."
)
# Facts about the Mac saver, one muted line under the page description.
MAC_NOTES = {
    "live": "GPU load can't be read on Mac, so the GPU source leaves the rain unchanged.",
    "rendering": "The Mac screen saver always draws with the GPU. Draw with is used by "
    "the Windows version only.",
}
MAC_HELP = {
    "image_dir": "The sandboxed screen saver may not be able to read a folder outside its "
    "container; if it can't, no pictures show.",
    "font_path": "The sandboxed screen saver may not be able to open a font outside its "
    "container; if it can't, the built-in font is used.",
}

# Control kind -> builder method of OptionsSheet. tools/checks/check_mac_options.py
# checks every kind in dialog_model.PAGE_ROWS and BOX_ROWS has one.
KIND_BUILDERS = {
    "cards": "build_popup",
    "segmented": "build_segmented",
    "switch": "build_switch",
    "slider": "build_slider",
    "dropdown": "build_popup",
    "grid": "build_popup",
    "text": "build_text",
    "font": "build_picker",
    "folder": "build_picker",
    "fontpick": "build_fontpick",
    "box": "build_box",
}
BROWSE_LABEL = "Choose…"
BROWSE_WIDTH = 110
# Width of each picker's clear button, which carries the longer text.
CLEAR_WIDTH = {"font_path": 150, "image_dir": 110}
POPUP_KINDS = ("cards", "dropdown", "grid")
# Row height of each kind's control (points), without the help line.
KIND_HEIGHT = {
    "cards": 26,
    "segmented": 26,
    "switch": 22,
    "slider": 40,
    "dropdown": 26,
    "grid": 26,
    "text": 24,
    "font": 56,
    "folder": 56,
    "fontpick": 56,
}
BOLD_FONT_MASK = 2  # NSBoldFontMask
ITALIC_FONT_MASK = 1  # NSItalicFontMask
FONT_WEIGHT_REGULAR = 5  # NSFontManager weight scale, 5 = regular
FONT_WEIGHT_BOLD = 9

_mods = None
_target = None
_flipped = None


def _logged(what):
    """Decorator for the methods the Objective-C target forwards to. A Python
    exception that escaped into AppKit would take the screen saver host down, so
    it is logged with its traceback instead and the call returns None."""

    def wrap(fn):
        @functools.wraps(fn)
        def run(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                osapi.log(f"mac_options: {what} FAILED\n" + traceback.format_exc())
                return None

        return run

    return wrap


def _ak():
    """-> (objc, AppKit, Foundation), imported on first use."""
    global _mods
    if _mods is None:
        import AppKit
        import Foundation
        import objc

        _mods = (objc, AppKit, Foundation)
    return _mods


def _target_class():
    """MatrixRainOptionsTarget, defined once per process (a second definition of
    the same Objective-C class name raises)."""
    global _target
    if _target is None:
        _objc, _AppKit, Foundation = _ak()

        class MatrixRainOptionsTarget(Foundation.NSObject):
            def controlChanged_(self, sender):
                self.sheet.control_changed(sender)

            def save_(self, sender):
                self.sheet.save(sender)

            def cancel_(self, sender):
                self.sheet.cancel(sender)

            def reset_(self, sender):
                self.sheet.reset(sender)

            def choosePath_(self, sender):
                self.sheet.choose_path(sender)

            def clearPath_(self, sender):
                self.sheet.clear_path(sender)

            def chooseFont_(self, sender):
                self.sheet.choose_font(sender)

            def useDefaultFont_(self, sender):
                self.sheet.use_default_font(sender)

            def changeFont_(self, sender):
                self.sheet.font_changed(sender)

            def controlTextDidChange_(self, note):
                self.sheet.text_changed(note.object())

            def tabView_didSelectTabViewItem_(self, tab_view, item):
                self.sheet.page_selected(item)

        _target = MatrixRainOptionsTarget
    return _target


def _flipped_class():
    """A document view with y growing downwards, so rows lay out top to bottom."""
    global _flipped
    if _flipped is None:
        _objc, AppKit, _Foundation = _ak()

        class MatrixRainFlippedView(AppKit.NSView):
            def isFlipped(self):
                return True

        _flipped = MatrixRainFlippedView
    return _flipped


def tab_title(page):
    """The Mac tab title of `page`: MAC_TAB_TITLES, else the shared title."""
    return MAC_TAB_TITLES.get(page, dm.PAGE_TITLES[page])


def tab_view_width():
    return WIN_W - 2 * (MARGIN - 4)


def tab_segment_width():
    """Width of one tab when the strip is shared equally between the pages."""
    return tab_view_width() / len(dm.PAGES)


def text_lines(text, width, small=False):
    """Lines `text` wraps to in a label `width` points wide (word wrap with the
    conservative CHAR_W / SMALL_CHAR_W), at least 1."""
    per_line = max(1, int(width // (SMALL_CHAR_W if small else CHAR_W)))
    lines, used = 1, 0
    for word in str(text).split():
        n = len(word)
        if used and used + 1 + n > per_line:
            lines += 1 + (n - 1) // per_line
            used = n % per_line or per_line
        elif not used and n > per_line:
            lines += (n - 1) // per_line
            used = n % per_line or per_line
        else:
            used += (1 if used else 0) + n
    return lines


def text_height(text, width, small=False):
    """Height of a wrapping label that shows all of `text` at `width`; 0 for no text."""
    if not str(text).strip():
        return 0
    return text_lines(text, width, small) * (SMALL_LINE_H if small else LINE_H) + 2


def help_texts(key):
    """Every help line the row for `key` can show on the Mac sheet (the model's
    scope is always None here, so the per-monitor strings never appear)."""
    out = []
    for text in (
        dm.HELP.get(key, "") if key != "message_text" else "",
        dm.DISABLED_HELP.get(key, ""),
    ):
        if key in MAC_HELP:
            text = (text + " " + MAC_HELP[key]).strip()
        if text:
            out.append(text)
    return out


def build(on_saved=None, on_closed=None):
    """Resolve the settings as the saver does (mac_settings.resolve) and build the
    sheet. -> OptionsSheet; its .window is what configureSheet returns."""
    blob = mac_settings.read_saved_blob("mac_options")
    cfg, source, problems = mac_settings.resolve(blob, osapi.settings_read_path())
    for p in problems:
        osapi.log(f"mac_options: {p}")
    osapi.log(f"mac_options: opening, settings source={source} preset={cfg['preset']}")
    return OptionsSheet(cfg, on_saved=on_saved, on_closed=on_closed)


class OptionsSheet:
    """The window, its controls and the Model they edit."""

    def __init__(self, cfg, on_saved=None, on_closed=None):
        objc, AppKit, _Foundation = _ak()
        self.ak = AppKit
        self.on_saved = on_saved
        self.on_closed = on_closed
        self.model = dm.Model(cfg, ())
        self.target = _target_class().alloc().init()
        self.target.sheet = self
        self.rows = {}  # key -> dict(kind, control, views, help, values, ...)
        self.controls = {}  # key -> the row's main control ("effects": the NSBox)
        self.tags = []  # control tag -> key
        self.page_desc = {}
        self.page_heights = {}  # page -> height of its document view
        self.monitors_label = None
        self.box = None
        self.customise_button = None
        self.closed = False
        self._build_window()
        self.model.listeners.append(self.refresh)
        self.refresh()
        self.set_status(STATUS_OPEN)

    def _rect(self, x, y, w, h):
        return self.ak.NSMakeRect(x, y, w, h)

    def _label(self, parent, text, x, y, w, h, muted=False, small=False):
        """A wrapping label. Callers size `h` with text_height for every text the
        label can show, so wrapped lines are never cut off."""
        ak = self.ak
        lab = ak.NSTextField.wrappingLabelWithString_(text)
        lab.setFrame_(self._rect(x, y, w, h))
        lab.setPreferredMaxLayoutWidth_(w)
        if small:
            lab.setFont_(ak.NSFont.systemFontOfSize_(ak.NSFont.smallSystemFontSize()))
        if muted:
            lab.setTextColor_(ak.NSColor.secondaryLabelColor())
        parent.addSubview_(lab)
        return lab

    def _register(self, control, key):
        """Give `control` the next tag, so the target can find its key again."""
        control.setTag_(len(self.tags))
        self.tags.append(key)

    def _tag(self, control, key):
        self._register(control, key)
        control.setTarget_(self.target)
        control.setAction_("controlChanged:")

    def _button(self, parent, title, action, x, y, w):
        btn = self.ak.NSButton.buttonWithTitle_target_action_(title, self.target, action)
        btn.setFrame_(self._rect(x, y, w, 32))
        parent.addSubview_(btn)
        return btn

    def _build_window(self):
        ak = self.ak
        win = ak.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            self._rect(0, 0, WIN_W, WIN_H),
            ak.NSWindowStyleMaskTitled,
            ak.NSBackingStoreBuffered,
            False,
        )
        win.setTitle_("Digital Rain Options")
        win.setReleasedWhenClosed_(False)
        self.window = win
        content = win.contentView()
        tabs = ak.NSTabView.alloc().initWithFrame_(
            self._rect(MARGIN - 4, FOOTER_H, tab_view_width(), WIN_H - FOOTER_H - 8)
        )
        tabs.setAutoresizingMask_(ak.NSViewWidthSizable | ak.NSViewHeightSizable)
        content.addSubview_(tabs)
        self.tab_view = tabs
        for page in dm.PAGES:
            item = ak.NSTabViewItem.alloc().initWithIdentifier_(page)
            item.setLabel_(tab_title(page))
            item.setView_(self._build_page(page))
            tabs.addTabViewItem_(item)
        # set after the items, so adding them sends no selection callbacks
        tabs.setDelegate_(self.target)
        # footer: Reset on the left, Cancel and Save on the right, status above
        self.reset_button = self._button(content, "Reset to defaults", "reset:", MARGIN, 12, 150)
        self.cancel_button = self._button(
            content, "Cancel", "cancel:", WIN_W - MARGIN - 200, 12, 96
        )
        self.cancel_button.setKeyEquivalent_("\x1b")
        self.save_button = self._button(content, "Save", "save:", WIN_W - MARGIN - 96, 12, 96)
        self.save_button.setKeyEquivalent_("\r")
        self.status = self._label(content, "", *STATUS_FRAME, muted=True, small=True)
        self.fit_page(dm.PAGES[0], animate=False)

    def _build_page(self, page):
        ak = self.ak
        w = WIN_W - 2 * MARGIN - 20
        scroll = ak.NSScrollView.alloc().initWithFrame_(
            self._rect(0, 0, w, WIN_H - FOOTER_H - TAB_TOP)
        )
        scroll.setHasVerticalScroller_(True)
        scroll.setAutoresizingMask_(ak.NSViewWidthSizable | ak.NSViewHeightSizable)
        doc = _flipped_class().alloc().initWithFrame_(self._rect(0, 0, w - 16, 100))
        inner = w - 16 - 2 * MARGIN
        y = 12
        desc = self.model.page_description(page)
        h = text_height(desc, inner)
        self.page_desc[page] = self._label(doc, desc, MARGIN, y, inner, h)
        y += h + 6
        if page in MAC_NOTES:
            h = text_height(MAC_NOTES[page], inner, small=True)
            self._label(doc, MAC_NOTES[page], MARGIN, y, inner, h, muted=True, small=True)
            y += h + 6
        if page == "look":
            h = text_height(MONITORS_NOTE.format(n=99), inner, small=True)
            self.monitors_label = self._label(doc, "", MARGIN, y, inner, h, muted=True, small=True)
            y += h + 6
        y += 4
        for key, kind in dm.PAGE_ROWS[page]:
            y = getattr(self, KIND_BUILDERS[kind])(doc, key, kind, MARGIN, y, inner)
        self.page_heights[page] = y + 12
        doc.setFrame_(self._rect(0, 0, w - 16, y + 12))
        scroll.setDocumentView_(doc)
        return scroll

    def window_height(self, page):
        """Content height of the window for `page`: the page's rows plus the tab
        strip and footer, between MIN_H and WIN_H (a taller page scrolls)."""
        h = self.page_heights.get(page, WIN_H) + FOOTER_H + TAB_TOP
        return max(MIN_H, min(WIN_H, h))

    @_logged("fit to page")
    def fit_page(self, page, animate=True):
        """Resize the window to `page`, keeping its top edge where it is (a sheet
        stays attached under the parent's title bar)."""
        win = self.window
        want = self.window_height(page)
        have = win.contentView().frame().size.height
        if abs(want - have) < 1:
            return
        fr = win.frame()
        dh = want - have
        win.setFrame_display_animate_(
            self._rect(fr.origin.x, fr.origin.y - dh, fr.size.width, fr.size.height + dh),
            True,
            bool(animate),
        )

    @_logged("tab selection")
    def page_selected(self, item):
        self.fit_page(str(item.identifier()))

    def _row(self, parent, key, kind, x, y, width, control, views, label=True, **extra):
        """Register a row: its label (left), the control and a help line under it."""
        views = list(views)
        if label:
            lab = self._label(parent, dm.LABELS[key], x, y + 3, LABEL_W - 8, 20)
            if key in dm.EFFECT_TIPS:
                lab.setToolTip_(dm.EFFECT_TIPS[key])
            views.append(lab)
        h = KIND_HEIGHT[kind]
        # tall enough for the longest help this row can show, wrapped; none: no gap
        help_h = max([text_height(t, width - LABEL_W, small=True) for t in help_texts(key)] + [0])
        help_ = self._label(
            parent, "", x + LABEL_W, y + h + 2, width - LABEL_W, help_h, muted=True, small=True
        )
        views.append(help_)
        self.rows[key] = dict(kind=kind, control=control, views=views, help=help_, **extra)
        self.controls[key] = control
        return y + h + (help_h + 2 if help_h else 0) + ROW_GAP

    def build_popup(self, parent, key, kind, x, y, width):
        """A pop-up button: the cards, dropdown and clock grid rows."""
        ak = self.ak
        opts = self.model.options(key)
        pop = ak.NSPopUpButton.alloc().initWithFrame_pullsDown_(
            self._rect(x + LABEL_W, y, min(280, width - LABEL_W), 26), False
        )
        pop.addItemsWithTitles_([label for _v, label in opts])
        self._tag(pop, key)
        parent.addSubview_(pop)
        return self._row(parent, key, kind, x, y, width, pop, [pop], values=[v for v, _l in opts])

    def build_segmented(self, parent, key, kind, x, y, width):
        ak = self.ak
        opts = self.model.options(key)
        seg = ak.NSSegmentedControl.alloc().initWithFrame_(
            self._rect(x + LABEL_W, y, min(90 * len(opts), width - LABEL_W), 26)
        )
        seg.setSegmentCount_(len(opts))
        for i, (_v, label) in enumerate(opts):
            seg.setLabel_forSegment_(label, i)
        seg.setTrackingMode_(ak.NSSegmentSwitchTrackingSelectOne)
        self._tag(seg, key)
        parent.addSubview_(seg)
        return self._row(parent, key, kind, x, y, width, seg, [seg], values=[v for v, _l in opts])

    def build_switch(self, parent, key, kind, x, y, width):
        ak = self.ak
        btn = ak.NSButton.alloc().initWithFrame_(self._rect(x + LABEL_W, y, width - LABEL_W, 22))
        btn.setButtonType_(ak.NSButtonTypeSwitch)
        btn.setTitle_(dm.LABELS[key])
        self._tag(btn, key)
        parent.addSubview_(btn)
        return self._row(parent, key, kind, x, y, width, btn, [btn])

    def build_slider(self, parent, key, kind, x, y, width):
        ak = self.ak
        lo, hi = settings.RANGES[key]
        _dec, _unit, ends = dm.SLIDERS[key]
        sw = min(260, width - LABEL_W - 90)
        sl = ak.NSSlider.alloc().initWithFrame_(self._rect(x + LABEL_W, y, sw, 22))
        sl.setMinValue_(lo)
        sl.setMaxValue_(hi)
        sl.setContinuous_(True)
        self._tag(sl, key)
        parent.addSubview_(sl)
        views = [sl]
        value_label = self._label(parent, "", x + LABEL_W + sw + 10, y + 2, 80, 20)
        views.append(value_label)
        if ends:
            half = sw // 2
            views.append(
                self._label(parent, ends[0], x + LABEL_W, y + 22, half, 16, muted=True, small=True)
            )
            right = self._label(
                parent, ends[1], x + LABEL_W + half, y + 22, sw - half, 16, muted=True, small=True
            )
            right.setAlignment_(ak.NSTextAlignmentRight)
            views.append(right)
        return self._row(parent, key, kind, x, y, width, sl, views, value_label=value_label)

    def build_text(self, parent, key, kind, x, y, width):
        ak = self.ak
        field = ak.NSTextField.alloc().initWithFrame_(
            self._rect(x + LABEL_W, y, min(280, width - LABEL_W), 24)
        )
        self._register(field, key)
        field.setDelegate_(self.target)
        parent.addSubview_(field)
        y2 = self._row(parent, key, kind, x, y, width, field, [field])
        h = text_height(dm.HELP["message_text"], width - LABEL_W, small=True)
        note = self._label(
            parent,
            dm.HELP["message_text"],
            x + LABEL_W,
            y2 - ROW_GAP,
            width - LABEL_W,
            h,
            muted=True,
            small=True,
        )
        self.rows[key]["views"].append(note)
        return y2 + h

    def build_picker(self, parent, key, kind, x, y, width):
        """A read-only path box with a Choose and a clear button (dm.PICKERS)."""
        ak = self.ak
        spec = dm.PICKERS[key]
        field = ak.NSTextField.alloc().initWithFrame_(
            self._rect(x + LABEL_W, y, width - LABEL_W, 22)
        )
        field.setEditable_(False)
        field.setSelectable_(True)
        parent.addSubview_(field)
        choose = self._button(
            parent, BROWSE_LABEL, "choosePath:", x + LABEL_W, y + 26, BROWSE_WIDTH
        )
        clear = self._button(
            parent,
            spec.clear_label,
            "clearPath:",
            x + LABEL_W + BROWSE_WIDTH + 6,
            y + 26,
            CLEAR_WIDTH[key],
        )
        self._register(choose, key)
        self._register(clear, key)
        return self._row(
            parent, key, kind, x, y, width, field, [field, choose, clear], buttons=[choose, clear]
        )

    def build_fontpick(self, parent, key, kind, x, y, width):
        """The letter font row: the font's name, a Choose font and a Use default button
        (the font panel is NSFontPanel, driven through NSFontManager)."""
        ak = self.ak
        field = ak.NSTextField.alloc().initWithFrame_(
            self._rect(x + LABEL_W, y, width - LABEL_W, 22)
        )
        field.setEditable_(False)
        field.setSelectable_(True)
        parent.addSubview_(field)
        choose = self._button(
            parent, dm.CHOOSE_FONT, "chooseFont:", x + LABEL_W, y + 26, BROWSE_WIDTH + 20
        )
        default = self._button(
            parent,
            dm.USE_DEFAULT_FONT,
            "useDefaultFont:",
            x + LABEL_W + BROWSE_WIDTH + 26,
            y + 26,
            BROWSE_WIDTH,
        )
        return self._row(
            parent,
            key,
            kind,
            x,
            y,
            width,
            field,
            [field, choose, default],
            buttons=[choose, default],
        )

    def build_box(self, parent, key, kind, x, y, width):
        """The effects box: an NSBox drawn behind one labelled row per BOX_ROWS entry
        (the rows sit on the flipped page view, not in the box's own content view)."""
        ak = self.ak
        top = y
        box = ak.NSBox.alloc().initWithFrame_(self._rect(x, y, width, 100))
        parent.addSubview_(box)
        self.box = box
        self.controls[key] = box
        y += 28
        self.box_note = self._label(parent, "", x + 12, y, width - 24, 16, muted=True, small=True)
        self.customise_button = self._button(
            parent, "Customise these", "controlChanged:", x + width - 172, y - 6, 160
        )
        self._register(self.customise_button, "customise")
        y += 30
        for box_key, box_kind in dm.BOX_ROWS:
            y = getattr(self, KIND_BUILDERS[box_kind])(
                parent, box_key, box_kind, x + 12, y, width - 24
            )
        box.setFrame_(self._rect(x, top, width, y - top + 4))
        return y + ROW_GAP

    def refresh(self):
        """Every row from the model: value, enabled, hidden, help; the box header."""
        ak = self.ak
        m = self.model
        for page, lab in self.page_desc.items():
            lab.setStringValue_(m.page_description(page))
        if self.monitors_label is not None:
            n = len(m.to_cfg()["monitors"])
            self.monitors_label.setStringValue_(MONITORS_NOTE.format(n=n) if n else "")
            self.monitors_label.setHidden_(not n)
        for key, r in self.rows.items():
            row = m.row(key)
            value = m.control_value(key)
            ctl, kind = r["control"], r["kind"]
            if kind in POPUP_KINDS:
                if value in r["values"]:
                    ctl.selectItemAtIndex_(r["values"].index(value))
            elif kind == "segmented":
                if value in r["values"]:
                    ctl.setSelectedSegment_(r["values"].index(value))
            elif kind == "switch":
                ctl.setState_(ak.NSControlStateValueOn if value else ak.NSControlStateValueOff)
            elif kind == "slider":
                ctl.setDoubleValue_(float(value))
                r["value_label"].setStringValue_(dm.fmt(key, value))
            elif kind == "text":
                if str(ctl.stringValue()) != value:
                    ctl.setStringValue_(value)
            elif kind == "fontpick":
                ctl.setStringValue_(m.font_text())
                for b in r["buttons"]:
                    b.setEnabled_(row.enabled)
            elif kind in ("font", "folder"):
                ctl.setStringValue_(value or dm.PICKERS[key].empty_label)
                for b in r["buttons"]:
                    b.setEnabled_(row.enabled)
            ctl.setEnabled_(row.enabled)
            help_ = row.help
            if key in MAC_HELP:
                help_ = (help_ + " " + MAC_HELP[key]).strip()
            r["help"].setStringValue_(help_)
            for v in r["views"]:
                v.setHidden_(not row.visible)
        if self.box is not None:
            head = m.effects_header()
            self.box.setTitle_(f"{head['title']} {head['strong']}".strip())
            self.customise_button.setHidden_(not head["customise"])
            self.box_note.setStringValue_(head["note"] or "")

    def set_status(self, text):
        self.status.setStringValue_(text)

    @_logged("control change")
    def control_changed(self, control):
        key = self.tags[int(control.tag())]
        if key == "customise":
            self.model.customise()
            return
        r = self.rows[key]
        kind = r["kind"]
        if kind in POPUP_KINDS:
            value = r["values"][int(control.indexOfSelectedItem())]
        elif kind == "segmented":
            value = r["values"][int(control.selectedSegment())]
        elif kind == "switch":
            value = control.state() == self.ak.NSControlStateValueOn
        elif kind == "slider":
            value = round(float(control.doubleValue()), dm.SLIDERS[key][0])
        else:
            return
        self.model.control_set(key, value)

    @_logged("text change")
    def text_changed(self, field):
        text = str(field.stringValue())
        cleaned = dm.clean_text(text)
        if cleaned != text:
            field.setStringValue_(cleaned)
        self.model.control_set("message_text", cleaned)

    @_logged("path choice")
    def choose_path(self, sender):
        """Ask for the file or folder of the picker row `sender` belongs to."""
        ak = self.ak
        key = self.tags[int(sender.tag())]
        spec = dm.PICKERS[key]
        panel = ak.NSOpenPanel.openPanel()
        panel.setCanChooseFiles_(not spec.directory)
        panel.setCanChooseDirectories_(spec.directory)
        panel.setAllowsMultipleSelection_(False)
        if spec.extensions:
            panel.setAllowedFileTypes_(list(spec.extensions))
        if panel.runModal() == ak.NSModalResponseOK:
            urls = panel.URLs()
            if urls:
                self.model.control_set(key, str(urls[0].path()))

    def _current_font(self):
        """The NSFont the font panel starts on: the model's family, bold and italic."""
        ak = self.ak
        g = self.model.g
        fm = ak.NSFontManager.sharedFontManager()
        traits = (BOLD_FONT_MASK if g["message_bold"] else 0) | (
            ITALIC_FONT_MASK if g["message_italic"] else 0
        )
        weight = FONT_WEIGHT_BOLD if g["message_bold"] else FONT_WEIGHT_REGULAR
        family = g["message_font"] or settings.DEFAULT_MESSAGE_FONT
        size = float(g["message_font_size"])
        font = fm.fontWithFamily_traits_weight_size_(family, traits, weight, size)
        return font or ak.NSFont.systemFontOfSize_(size)

    @_logged("font choice")
    def choose_font(self, sender):
        """Open the system font panel on the current font; changeFont: reports the pick."""
        fm = self.ak.NSFontManager.sharedFontManager()
        fm.setTarget_(self.target)
        fm.setSelectedFont_isMultiple_(self._current_font(), False)
        fm.orderFrontFontPanel_(sender)

    @_logged("font change")
    def font_changed(self, manager):
        """The font panel's changeFont: action."""
        self.apply_font(manager.convertFont_(self._current_font()))

    def apply_font(self, font):
        """Store `font`'s family, bold, italic and point size."""
        fm = self.ak.NSFontManager.sharedFontManager()
        traits = int(fm.traitsOfFont_(font))
        self.model.set_font(
            str(font.familyName()),
            bool(traits & BOLD_FONT_MASK),
            bool(traits & ITALIC_FONT_MASK),
            round(float(font.pointSize())),
        )

    @_logged("font reset")
    def use_default_font(self, sender):
        self.model.reset_font()

    @_logged("path clear")
    def clear_path(self, sender):
        self.model.control_set(self.tags[int(sender.tag())], "")

    @_logged("saving the options")
    def _store(self, cfg):
        """Write cfg to ScreenSaverDefaults; True when it reports success."""
        ok = mac_settings.write_blob(mac_settings.open_defaults(), cfg)
        if not ok:
            osapi.log(
                "mac_options: save FAILED: ScreenSaverDefaults synchronize "
                "returned False\n" + "".join(traceback.format_stack())
            )
        return ok

    @_logged("save")
    def save(self, sender=None):
        cfg = self.model.to_cfg()
        if not self._store(cfg):
            self.set_status(f"Could not save. Details are in {osapi.log_path()}.")
            return False
        n = len(mac_settings.encode(cfg).encode("utf-8"))
        osapi.log(f"mac_options: saved {n} bytes to ScreenSaverDefaults {mac_settings.MODULE_NAME}")
        osapi.log(f"mac_options: {STATUS_SAVED}")
        self.set_status(STATUS_SAVED)
        try:
            if self.on_saved is not None:
                self.on_saved()
            _objc, _AppKit, Foundation = _ak()
            Foundation.NSDistributedNotificationCenter.defaultCenter().postNotificationName_object_(
                mac_settings.CHANGED_NOTE, None
            )
        finally:
            self.close(sender)
        return True

    @_logged("cancel")
    def cancel(self, sender=None):
        osapi.log("mac_options: cancelled")
        self.close(sender)

    @_logged("reset")
    def reset(self, sender=None):
        self.model.reset(keep_overrides=True)
        self.set_status(STATUS_RESET)

    def close(self, sender=None):
        """End the sheet (or close the window when it is not a sheet), then tell
        the owner through on_closed."""
        win = sender.window() if sender is not None else None
        if win is None:
            win = self.window
        parent = win.sheetParent()
        if parent is not None:
            parent.endSheet_(win)
        else:
            win.close()
        self.closed = True
        if self.on_closed is not None:
            self.on_closed()
