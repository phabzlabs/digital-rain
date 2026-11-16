"""Settings window shown by Windows for the screensaver's "Settings" button.

A sidebar of pages with live summaries, a live preview strip and a monitor scope
picker that folds the per-monitor overrides into the normal controls. The rules live in
dialog_model.py, the controls in dialog_widgets.py and the preview child in
dialog_preview.py; this module builds the window from them.
"""

import contextlib
import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from digital_rain import dialog_model as dm
from digital_rain import osapi, settings
from digital_rain.windows import dialog_preview
from digital_rain.windows import dialog_widgets as dw
from digital_rain.windows.dialog_widgets import sc

OPEN_SIZE = (1200, 1040)  # 96 DPI units
MIN_SIZE = (960, 600)
PAD = 20  # margins of the preview strip and the page area
DECOR = (16, 39)  # title bar and frame around the client area, 96 DPI units

# The Keep clock row sits indented under the Message row it refines.
KEEP_CLOCK_INDENT = 20
BROWSE_LABEL = "Browse…"
# Control widths in 96 DPI units; the compact ones are for the effects box.
SLIDER_WIDTH = 360
COMPACT_SLIDER_WIDTH = 250
DROPDOWN_WIDTH = 280
COMPACT_DROPDOWN_WIDTH = 170
PICKER_BOX_WIDTH = 300


def apply_theme(root):
    """Dark window base: ttk clam for the scrollbars, dark title bar."""
    root.configure(bg=dw.BG_WINDOW)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        "Vertical.TScrollbar",
        background=dw.BORDER_INPUT,
        troughcolor=dw.BG_WINDOW,
        bordercolor=dw.BG_WINDOW,
        lightcolor=dw.BORDER_INPUT,
        darkcolor=dw.BORDER_INPUT,
        arrowcolor=dw.TEXT_MUTED,
        gripcount=0,
    )
    style.map("Vertical.TScrollbar", background=[("active", dw.BORDER)])
    style.configure("Side.Vertical.TScrollbar", troughcolor=dw.BG_CHROME, bordercolor=dw.BG_CHROME)
    root.update_idletasks()
    osapi.set_dark_title_bar(int(root.wm_frame(), 16))


def _connected_monitors():
    try:
        return osapi.list_monitors()
    except Exception as exc:  # the dialog still works without the per-monitor scopes
        osapi.log(f"config_dialog: monitor list failed: {exc!r}")
        return []


def wheel_steps(delta):
    """Scroll steps for one <MouseWheel> event: Windows sends 120 per notch."""
    return -int(delta / 120) or (-1 if delta > 0 else 1)


def _label(parent, text, font, fg, bg, **kw):
    return tk.Label(
        parent,
        text=text,
        font=dw.FONTS[font],
        fg=fg,
        bg=bg,
        anchor="w",
        justify="left",
        bd=0,
        padx=0,
        pady=0,
        **kw,
    )


class RowView:
    """One setting row: label + help (230) · control · scope column (112)."""

    def __init__(self, app, parent, key, bg, divider=True):
        self.app, self.key, self.bg = app, key, bg
        indent = sc(KEEP_CLOCK_INDENT) if key == "keep_clock" else 0
        self.divider = tk.Frame(parent, bg=dw.DIVIDER, height=1) if divider else None
        f = self.frame = tk.Frame(parent, bg=bg)
        f.grid_columnconfigure(0, minsize=sc(dw.LABEL_W))
        f.grid_columnconfigure(1, weight=1)
        f.grid_columnconfigure(2, minsize=sc(dw.SCOPE_W))
        left = tk.Frame(f, bg=bg, width=sc(dw.LABEL_W))
        left.grid(row=0, column=0, sticky="nw", padx=(indent, sc(12)), pady=sc(12))
        name = dm.LABELS[key]
        self.label = _label(left, name, "label", dw.TEXT, bg)
        self.label.pack(anchor="w")
        wrap = sc(dw.LABEL_W - 16) - indent
        self.help = _label(left, "", "help", dw.TEXT_MUTED, bg, wraplength=wrap)
        self.glob = tk.Frame(left, bg=bg)
        self.glob_text = _label(self.glob, "", "help", dw.TEXT_MUTED, bg)
        self.glob_text.pack(side="left")
        self.reset = dw.Button(
            self.glob,
            "reset",
            bg,
            kind="link",
            name=f"Reset {name}",
            command=lambda: app.model.remove_override(key),
        )
        self.reset.pack(side="left", padx=(sc(4), 0))
        self.cell = tk.Frame(f, bg=bg)
        self.cell.grid(row=0, column=1, sticky="w", pady=sc(10))
        self.scope = tk.Frame(f, bg=bg)
        self.scope.grid(row=0, column=2, sticky="ne", pady=sc(10))
        self.pill = None
        self.all_label = None
        self.state = None

    def grid(self, row):
        if self.divider is not None:
            self.divider.grid(row=2 * row, column=0, sticky="ew")
        self.frame.grid(row=2 * row + 1, column=0, sticky="ew")

    def update(self, r):
        key = (r.visible, r.enabled, r.pill, r.pill_enabled, r.help, r.global_text, r.reset_enabled)
        if key == self.state:
            return
        self.state = key
        if not r.visible:
            self.frame.grid_remove()
            if self.divider is not None:
                self.divider.grid_remove()
            return
        self.frame.grid()
        if self.divider is not None:
            self.divider.grid()
        dim = not r.enabled and not (r.pill == "override" and r.pill_enabled)
        self.label.configure(fg=dw.TEXT_DISABLED if dim else dw.TEXT)
        if r.help:
            self.help.configure(text=r.help, fg=dw.TEXT_DISABLED if dim else dw.TEXT_MUTED)
            self.help.pack(anchor="w", pady=(sc(2), 0), after=self.label)
        else:
            self.help.pack_forget()
        if r.global_text:
            self.glob_text.configure(text=f"{r.global_text} ·")
            self.reset.set_enabled(r.reset_enabled)
            self.glob.pack(anchor="w")
        else:
            self.glob.pack_forget()
        if r.pill in ("override", "overridden"):
            if self.all_label is not None:
                self.all_label.pack_forget()
            if self.pill is None:
                self.pill = dw.Pill(
                    self.scope,
                    self.bg,
                    name=f"{dm.LABELS[self.key]} override",
                    command=lambda: self.app.model.toggle_override(self.key),
                )
            self.pill.set(r.pill)
            self.pill.set_enabled(r.pill_enabled)
            self.pill.pack(anchor="e")
        elif r.pill == "all":
            if self.pill is not None:
                self.pill.pack_forget()
            if self.all_label is None:
                self.all_label = _label(
                    self.scope, "All monitors", "summary", dw.TEXT_MUTED, self.bg
                )
            self.all_label.pack(anchor="e", pady=sc(9))
        else:
            for w in (self.pill, self.all_label):
                if w is not None:
                    w.pack_forget()


class SettingsWindow:
    def __init__(self, root, shot_size=None):
        self.root = root
        apply_theme(root)
        self.px = root.winfo_fpixels("1i") / 96
        dw.set_scale(root, self.px)
        cfg = settings.load()
        self.model = dm.Model(cfg, _connected_monitors())
        root.title("Digital Rain Settings")
        root.resizable(True, True)
        self.page = None
        self.pages = {}  # page -> frame
        self.page_title = {}  # page -> description label
        self.rows = {}  # key -> RowView
        self.controls = {}  # key -> control
        self.builders = {
            "cards": self._build_cards,
            "segmented": self._build_segmented,
            "switch": self._build_switch,
            "slider": self._build_slider,
            "dropdown": self._build_dropdown,
            "grid": self._build_grid,
            "text": self._build_text,
            "font": self._build_picker,
            "folder": self._build_picker,
            "fontpick": self._build_fontpick,
        }
        self.box = None
        self.strip_h = self.footer_h = None
        self.columns = None
        self._build()
        self._place(shot_size)
        self.show_page("look")
        self.model.listeners.append(self.refresh)
        self.refresh()

    def _place(self, shot_size):
        root = self.root
        root.update_idletasks()
        if shot_size:
            # Shots: a fixed size on every machine, whatever the screen.
            w, h = sc(shot_size[0]), sc(shot_size[1])
            root.maxsize(max(w, 20000), max(h, 20000))
            root.minsize(sc(MIN_SIZE[0]), sc(MIN_SIZE[1]))
            root.geometry(f"{w}x{h}+0+0")
            return
        try:
            ax, ay, aw, ah = osapi.work_area(int(root.wm_frame(), 16))
        except Exception as exc:  # fall back to the whole screen
            osapi.log(f"config_dialog: work area failed: {exc!r}")
            ax, ay, aw, ah = 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()
        aw, ah = aw - sc(DECOR[0]), ah - sc(DECOR[1])
        w, h = min(sc(OPEN_SIZE[0]), aw), min(sc(OPEN_SIZE[1]), ah)
        root.minsize(min(sc(MIN_SIZE[0]), aw), min(sc(MIN_SIZE[1]), ah))
        x = ax + max(0, (aw - w) // 2)
        y = ay + max(0, (ah - h) // 2)
        root.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        root = self.root
        root.grid_columnconfigure(2, weight=1)
        root.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        tk.Frame(root, bg=dw.BORDER, width=1).grid(row=0, column=1, sticky="ns")
        main = self.main = tk.Frame(root, bg=dw.BG_WINDOW)
        main.grid(row=0, column=2, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)
        self._build_strip(main)
        self._build_page_area(main)
        tk.Frame(root, bg=dw.BORDER, height=1).grid(row=1, column=0, columnspan=3, sticky="ew")
        self._build_footer()
        root.bind("<Configure>", self._configure, add="+")
        root.bind("<Return>", self._enter)
        root.bind("<KP_Enter>", self._enter)
        root.bind("<Escape>", self._escape)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind_all("<MouseWheel>", self._wheel)
        root.bind_class("DlgCtl", "<FocusIn>", self._see, add="+")
        root.bind("<Activate>", lambda e: self._activation(True), add="+")
        root.bind("<Deactivate>", lambda e: self._activation(False), add="+")
        root.bind("<Map>", lambda e: self._activation(True) if e.widget is root else None, add="+")
        root.bind(
            "<Unmap>", lambda e: self._activation(False) if e.widget is root else None, add="+"
        )

    def _build_sidebar(self):
        bg = dw.BG_CHROME
        side = tk.Frame(self.root, bg=bg, width=sc(dw.SIDEBAR_W))
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        side.grid_rowconfigure(0, weight=1)
        side.grid_columnconfigure(0, weight=1)
        cv = self.side_cv = tk.Canvas(side, bg=bg, highlightthickness=0, bd=0, takefocus=0)
        cv.grid(row=0, column=0, sticky="nsew")
        self.side_bar = ttk.Scrollbar(
            side, orient="vertical", command=cv.yview, style="Side.Vertical.TScrollbar"
        )
        cv.configure(yscrollcommand=self.side_bar.set, yscrollincrement=sc(20))
        inner = self.side_in = tk.Frame(cv, bg=bg)
        self.side_win = cv.create_window(0, 0, anchor="nw", window=inner)
        cv.bind("<Configure>", lambda e: self._fit_sidebar())
        inner.bind("<Configure>", lambda e: self._fit_sidebar())

        top = tk.Frame(inner, bg=bg)
        top.pack(side="top", fill="x", padx=sc(12), pady=(sc(18), 0))
        _label(top, "EDITING SETTINGS FOR", "section", dw.SECTION_LABEL, bg).pack(
            anchor="w", padx=sc(6), pady=(0, sc(6))
        )
        self.picker = dw.Dropdown(
            top,
            [],
            bg,
            command=self.model.set_scope,
            name="Editing settings for",
            width=dw.SIDEBAR_W - 24,
        )
        self.picker.pack(anchor="w")
        dw.Tooltip(self.picker, dm.TOOLTIP_PICKER)
        tk.Frame(top, bg=dw.DIVIDER, height=1).pack(fill="x", pady=(sc(14), sc(8)))
        self.nav = {}
        for page in dm.PAGES:
            item = dw.NavItem(
                top, dm.PAGE_TITLES[page], bg, command=lambda p=page: self.show_page(p)
            )
            item.pack(anchor="w", pady=(0, sc(2)))
            item.bind("<Up>", lambda e, p=page: self._nav_step(p, -1))
            item.bind("<Down>", lambda e, p=page: self._nav_step(p, 1))
            self.nav[page] = item

        self.ov_panel = dw.Panel(inner, bg, pad=12)
        pin = self.ov_panel.inner
        self.ov_head = _label(pin, "", "body_semi", dw.TEXT_STRONG, dw.BG_PANEL)
        self.ov_head.pack(anchor="w")
        self.ov_chips = tk.Frame(pin, bg=dw.BG_PANEL)
        self.ov_chips.pack(anchor="w", fill="x", pady=(sc(6), 0))
        self.ov_none = _label(pin, "Follows All monitors", "help", dw.TEXT_MUTED, dw.BG_PANEL)
        self.ov_forget = dw.Button(
            pin,
            "Forget this monitor",
            dw.BG_PANEL,
            kind="link",
            font="body_semi",
            command=self.model.forget,
        )
        self.ov_forget.pack(anchor="w")
        self.ov_state = None

    def _fit_sidebar(self):
        cv = self.side_cv
        w, h = cv.winfo_width(), cv.winfo_height()
        req = self.side_in.winfo_reqheight()
        cv.itemconfigure(self.side_win, width=w, height=max(h, req))
        cv.configure(scrollregion=(0, 0, w, max(h, req)))
        if req > h + 1:
            self.side_bar.grid(row=0, column=1, sticky="ns")
        else:
            self.side_bar.grid_remove()
            cv.yview_moveto(0)

    def _build_strip(self, main):
        box = self.strip = tk.Frame(
            main,
            bg=dw.BG_PREVIEW,
            highlightthickness=1,
            highlightbackground=dw.BORDER,
            height=sc(180),
        )
        box.grid(row=0, column=0, columnspan=2, sticky="ew", padx=sc(PAD), pady=(sc(16), 0))
        box.pack_propagate(False)
        self.host = tk.Frame(box, bg=dw.BG_PREVIEW)
        self.host.pack(fill="both", expand=True)
        self.strip_cv = tk.Canvas(
            self.host, bg=dw.BG_PREVIEW, highlightthickness=0, bd=0, takefocus=0
        )
        self.strip_cv.pack(fill="both", expand=True)
        self.preview = dialog_preview.Preview(
            self.root, self.host, self.strip_cv, self._preview_cfg, on_full=self._full_state
        )
        self.strip_cv.bind("<Configure>", lambda e: self._strip_resized())
        self.full_btn = dw.Button(
            box,
            "Full screen",
            dw.BG_PREVIEW,
            kind="outline",
            icon="fullscreen",
            command=self.preview.full_screen,
        )
        self.full_btn.place(relx=1.0, rely=1.0, anchor="se", x=-sc(8), y=-sc(8))
        self.nc_chip = tk.Canvas(box, bg=dw.BG_PREVIEW, highlightthickness=0, bd=0, takefocus=0)
        self._draw_nc_chip()
        self._strip_size = None

    def _draw_nc_chip(self):
        cv = self.nc_chip
        bold = dw.FONTS["body_semi"]
        rest = " Preview uses the settings saved for this monitor."
        tw = bold.measure("Not connected.") + dw.FONTS["help"].measure(rest)
        w, h = tw + sc(44), sc(30)
        cv.configure(width=w, height=h)
        dw.rrect(cv, 0, 0, w - 1, h - 1, sc(8), fill=dw.BG_PANEL, outline=dw.BORDER)
        dw.draw_icon(cv, "unplugged", sc(10), h / 2 - sc(7), dw.TEXT_MUTED)
        x = sc(32)
        cv.create_text(x, h / 2, text="Not connected.", anchor="w", fill=dw.TEXT_STRONG, font=bold)
        cv.create_text(
            x + bold.measure("Not connected."),
            h / 2,
            text=rest,
            anchor="w",
            fill=dw.TEXT_MUTED,
            font=dw.FONTS["help"],
        )

    def _strip_resized(self):
        size = (self.strip_cv.winfo_width(), self.strip_cv.winfo_height())
        if size != self._strip_size:
            self._strip_size = size
            self.preview.changed()

    def _build_page_area(self, main):
        cv = self.page_cv = tk.Canvas(
            main, bg=dw.BG_WINDOW, highlightthickness=0, bd=0, takefocus=0
        )
        cv.grid(row=1, column=0, sticky="nsew", padx=(sc(PAD), 0), pady=(sc(4), 0))
        self.page_bar = ttk.Scrollbar(main, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=self.page_bar.set, yscrollincrement=sc(20))
        self.page_in = tk.Frame(cv, bg=dw.BG_WINDOW)
        self.page_win = cv.create_window(0, 0, anchor="nw", window=self.page_in)
        cv.bind("<Configure>", lambda e: self._fit_page())
        self.page_in.bind("<Configure>", lambda e: self._fit_page())

    def _fit_page(self):
        cv = self.page_cv
        w, h = cv.winfo_width(), cv.winfo_height()
        cv.itemconfigure(self.page_win, width=max(1, w - sc(PAD)))
        req = self.page_in.winfo_reqheight()
        cv.configure(scrollregion=(0, 0, w, max(h, req)))
        if req > h + 1:
            self.page_bar.grid(row=1, column=1, sticky="ns", pady=(sc(4), 0))
        else:
            self.page_bar.grid_remove()
            cv.yview_moveto(0)
        self._apply_columns()

    def _build_footer(self):
        bg = dw.BG_CHROME
        foot = self.footer = tk.Frame(self.root, bg=bg, height=sc(68))
        foot.grid(row=2, column=0, columnspan=3, sticky="ew")
        foot.pack_propagate(False)
        self.buttons = {
            "reset": dw.Button(foot, "Reset to defaults", bg, command=self.reset),
            "ok": dw.Button(
                foot,
                "OK",
                bg,
                kind="accent",
                command=self.ok,
                width=sc(96 + 2 * dw.Control.ring_pad),
            ),
            "cancel": dw.Button(
                foot, "Cancel", bg, command=self.close, width=sc(96 + 2 * dw.Control.ring_pad)
            ),
        }
        self.buttons["reset"].pack(side="left", padx=(sc(PAD - 3), 0))
        self.buttons["ok"].pack(side="right", padx=(sc(6), sc(PAD - 3)))
        self.buttons["cancel"].pack(side="right")

    def show_page(self, page):
        if page not in self.pages:
            self._build_page(page)
        if self.page and self.page != page:
            self.pages[self.page].pack_forget()
        self.page = page
        self.pages[page].pack(fill="x", anchor="n")
        for p, item in self.nav.items():
            item.set(selected=p == page)
        self.page_cv.yview_moveto(0)
        self.refresh()

    def _nav_step(self, page, d):
        i = dm.PAGES.index(page) + d
        if 0 <= i < len(dm.PAGES):
            p = dm.PAGES[i]
            self.show_page(p)
            self.nav[p].focus_set()
        return "break"

    def _build_page(self, page):
        bg = dw.BG_WINDOW
        frame = tk.Frame(self.page_in, bg=bg)
        self.pages[page] = frame
        head = tk.Frame(frame, bg=bg)
        head.pack(fill="x", pady=(sc(14), sc(10)))
        _label(head, dm.PAGE_TITLES[page], "title", dw.TEXT_STRONG, bg).pack(anchor="w")
        desc = _label(head, "", "body", dw.TEXT_MUTED, bg)
        desc.pack(anchor="w", pady=(sc(2), 0))
        self.page_title[page] = desc
        body = tk.Frame(frame, bg=bg)
        body.pack(fill="x")
        body.grid_columnconfigure(0, weight=1)
        for i, (key, kind) in enumerate(dm.PAGE_ROWS[page]):
            if kind == "box":
                self.box = EffectsBox(self, body)
                self.box.panel.grid(row=2 * i + 1, column=0, sticky="ew", pady=(sc(14), sc(20)))
                continue
            row = RowView(self, body, key, bg, divider=True)
            row.grid(i)
            self.rows[key] = row
            self.controls[key] = self.make_control(row.cell, key, kind, bg)
        self._apply_columns(force=True)

    def make_control(self, parent, key, kind, bg, compact=False):
        """Build the control for one row. `compact` is the narrower effects-box size."""
        name = dm.LABELS.get(key, key)
        return self.builders[kind](parent, key, name, bg, compact)

    def _build_cards(self, parent, key, name, bg, compact):
        cards = []
        for preset in dm.CARD_ORDER:
            title, _, subtitle = dm.preset_title(preset).partition(" (")
            cards.append(
                (preset, title, subtitle.rstrip(")") if preset != "custom" else "Your own")
            )
        w = dw.PresetCards(
            parent, cards, bg, name=name, command=lambda v: self.model.set("preset", v)
        )
        w.pack(anchor="w")
        return w

    def _build_segmented(self, parent, key, name, bg, compact):
        w = dw.Segmented(
            parent,
            dm.SEGMENTS[key],
            bg,
            name=name,
            command=lambda v: self.model.control_set(key, v),
        )
        w.pack(anchor="w")
        return w

    def _build_switch(self, parent, key, name, bg, compact):
        w = dw.Switch(parent, bg, name=name, command=lambda v: self.model.control_set(key, v))
        w.pack(anchor="w")
        return w

    def _build_slider(self, parent, key, name, bg, compact):
        lo, hi = settings.RANGES[key]
        decimals, unit, ends = dm.SLIDERS[key]
        w = dw.Slider(
            parent,
            lo,
            hi,
            decimals,
            unit,
            ends,
            bg,
            name=name,
            command=lambda v: self.model.set(key, v),
            width=COMPACT_SLIDER_WIDTH if compact else SLIDER_WIDTH,
        )
        w.pack(anchor="w")
        return w

    def _build_dropdown(self, parent, key, name, bg, compact):
        w = dw.Dropdown(
            parent,
            self.model.options(key),
            bg,
            name=name,
            command=lambda v: self.model.set(key, v),
            width=COMPACT_DROPDOWN_WIDTH if compact else DROPDOWN_WIDTH,
        )
        w.pack(anchor="w")
        return w

    def _build_grid(self, parent, key, name, bg, compact):
        holder = tk.Frame(parent, bg=bg)
        holder.pack(anchor="w")
        w = dw.ClockGrid(
            holder,
            settings.CLOCK_POSITIONS,
            dm.POSITION_NAMES,
            bg,
            name=name,
            command=lambda v: self.model.set("clock_position", v),
        )
        w.pack(side="left")
        w.chosen = _label(holder, "", "help", dw.TEXT_MUTED, bg)
        w.chosen.pack(side="left", anchor="s", padx=(sc(10), 0), pady=(0, sc(6)))
        return w

    def _build_text(self, parent, key, name, bg, compact):
        w = dw.TextField(
            parent,
            bg,
            settings.MESSAGE_TEXT_MAX,
            dm.clean_text,
            dm.HELP["message_text"],
            name=name,
            command=lambda v: self.model.set("message_text", v),
        )
        w.pack(anchor="w", fill="x")
        w.entry.bind("<FocusIn>", self._see, add="+")
        return w

    def _build_picker(self, parent, key, name, bg, compact):
        """A read-only box with Browse and clear buttons, from dm.PICKERS."""
        spec = dm.PICKERS[key]
        holder = tk.Frame(parent, bg=bg)
        holder.pack(anchor="w")
        w = dw.ValueBox(holder, bg, name=name, width=PICKER_BOX_WIDTH)
        w.grid(row=0, column=0, columnspan=2, sticky="w")
        dw.Button(
            holder, BROWSE_LABEL, bg, command=lambda: self._browse(spec), name=spec.browse_name
        ).grid(row=1, column=0, sticky="w", pady=(sc(6), 0))
        dw.Button(
            holder,
            spec.clear_label,
            bg,
            command=lambda: self.model.set(key, ""),
            name=spec.clear_name,
        ).grid(row=1, column=1, sticky="w", padx=(sc(6), 0), pady=(sc(6), 0))
        return w

    def _build_fontpick(self, parent, key, name, bg, compact):
        """A read-only box with the font's name, a Choose font and a Use default button."""
        holder = tk.Frame(parent, bg=bg)
        holder.pack(anchor="w")
        w = dw.ValueBox(holder, bg, name=name, width=PICKER_BOX_WIDTH)
        w.grid(row=0, column=0, columnspan=2, sticky="w")
        dw.Button(
            holder,
            dm.CHOOSE_FONT,
            bg,
            command=self._choose_font,
            name="Choose the letter font",
        ).grid(row=1, column=0, sticky="w", pady=(sc(6), 0))
        dw.Button(
            holder,
            dm.USE_DEFAULT_FONT,
            bg,
            command=self.model.reset_font,
            name="Use the default letter font",
        ).grid(row=1, column=1, sticky="w", padx=(sc(6), 0), pady=(sc(6), 0))
        return w

    def _choose_font(self):
        """Open the system font picker (the native ChooseFont dialog on Windows)."""
        g = self.model.g
        family = g["message_font"] or settings.DEFAULT_MESSAGE_FONT
        spec = (
            (family, round(g["message_font_size"]))
            + (("bold",) if g["message_bold"] else ())
            + (("italic",) if g["message_italic"] else ())
        )
        self.root.tk.call("tk", "fontchooser", "configure", "-parent", self.root)
        self.root.tk.call("tk", "fontchooser", "configure", "-font", tkfont.Font(font=spec))
        self.root.tk.call(
            "tk", "fontchooser", "configure", "-command", self.root.register(self._font_chosen)
        )
        self.root.tk.call("tk", "fontchooser", "show")

    def _font_chosen(self, desc):
        """The picker's callback: `desc` is the chosen font description."""
        actual = tkfont.Font(root=self.root, font=desc).actual()
        size = int(actual["size"])
        if size < 0:  # negative sizes are pixels
            size = round(abs(size) * 72 / self.root.winfo_fpixels("1i"))
        self.model.set_font(
            actual["family"], actual["weight"] == "bold", actual["slant"] == "italic", size
        )

    def _browse(self, spec):
        if spec.directory:
            path = filedialog.askdirectory(parent=self.root, mustexist=True)
            path = os.path.normpath(path) if path else path
        else:
            patterns = " ".join(f"*.{ext}" for ext in spec.extensions)
            path = filedialog.askopenfilename(
                parent=self.root, filetypes=[(spec.file_label, patterns), ("All files", "*.*")]
            )
        if path:
            self.model.set(spec.key, path)

    def refresh(self):
        m = self.model
        # sidebar
        ents, saved = [], False
        for e in m.entries():
            if e["kind"] == "saved" and not saved:
                saved = True
                ents += [dict(kind="divider"), dict(kind="heading", label="Saved, not connected")]
            ents.append(
                dict(
                    kind="item",
                    value=e["id"],
                    label=e["label"],
                    muted=e["kind"] == "saved",
                    right="not connected" if e["kind"] == "saved" else None,
                    dot=e["dot"],
                )
            )
        self.picker.set(m.scope, ents)
        for page, item in self.nav.items():
            text, amber = m.summary(page)
            item.set(summary=text, amber=amber)
        self._refresh_overrides()
        # strip
        if m.in_monitor() and not m.scope_connected():
            self.nc_chip.place(x=sc(8), y=sc(8), anchor="nw")
            self.nc_chip.lift()
        else:
            self.nc_chip.place_forget()
        # page
        if self.page:
            self.page_title[self.page].configure(text=m.page_description(self.page))
            for key, _kind in dm.PAGE_ROWS[self.page]:
                if key == "effects":
                    self.box.refresh()
                    continue
                self.rows[key].update(m.row(key))
                self._refresh_control(key, self.controls[key], m.row(key))
        self.preview.changed()

    def _refresh_control(self, key, w, r):
        m = self.model
        if key == "preset":
            w.set(m.value("preset"), {p: m.card_sample(p) for p in dm.CARD_ORDER})
        elif key == "message":
            w.set(m.message_segment())
        elif key == "keep_clock":
            w.set(m.keep_clock())
        elif key == "clock_position":
            w.set(m.value(key))
            w.chosen.configure(
                text=dm.POSITION_NAMES[m.value(key)],
                fg=dw.TEXT_MUTED if r.enabled else dw.TEXT_DISABLED,
            )
        elif key == "message_font":
            w.set(m.font_text())
        elif key in dm.PICKERS:
            path = m.value(key)
            w.set(path or dm.PICKERS[key].empty_label, placeholder=not path)
        else:
            w.set(m.value(key))
        w.set_enabled(r.enabled)

    def _refresh_overrides(self):
        m = self.model
        heading = m.overrides_heading()
        chips = m.chips()
        state = (heading, tuple(chips), m.can_forget())
        if state == self.ov_state:
            return
        self.ov_state = state
        if heading is None:
            self.ov_panel.pack_forget()
            return
        self.ov_panel.pack(side="bottom", fill="x", padx=sc(12), pady=sc(12))
        self.ov_head.configure(text=heading)
        for c in self.ov_chips.winfo_children():
            c.destroy()
        if chips:
            self.ov_none.pack_forget()
            self.ov_chips.pack(anchor="w", fill="x", pady=(sc(6), 0), after=self.ov_head)
            avail = sc(dw.SIDEBAR_W - 48)
            line, x = None, avail
            for text, muted in chips:
                cw = dw.Chip.width_for(text) + sc(6)
                if line is None or x + cw > avail:
                    line = tk.Frame(self.ov_chips, bg=dw.BG_PANEL)
                    line.pack(anchor="w", pady=(0, sc(4)))
                    x = 0
                chip = dw.Chip(line, text, dw.BG_PANEL, muted=muted)
                chip.pack(side="left", padx=(0, sc(6)))
                x += cw
        else:
            self.ov_chips.pack_forget()
            self.ov_none.pack(anchor="w", pady=(sc(4), sc(2)), after=self.ov_head)
        self.ov_forget.set_enabled(m.can_forget())

    def _configure(self, e):
        if e.widget is not self.root:
            return
        w96 = self.root.winfo_width() / self.px
        h96 = self.root.winfo_height() / self.px
        strip = 120 if w96 < 1000 or h96 < 800 else 180
        foot = 60 if h96 < 800 else 68
        if strip != self.strip_h:
            self.strip_h = strip
            self.strip.configure(height=sc(strip))
        if foot != self.footer_h:
            self.footer_h = foot
            self.footer.configure(height=sc(foot))

    def _apply_columns(self, force=False):
        width96 = (self.page_cv.winfo_width() - sc(PAD)) / self.px
        if width96 <= 1:
            width96 = (sc(OPEN_SIZE[0] - dw.SIDEBAR_W - 2 * PAD)) / self.px
        cols = 2 if width96 >= 760 else 1
        if cols == self.columns and not force:
            return
        self.columns = cols
        if "preset" in self.controls:
            self.controls["preset"].set_columns(4 if cols == 2 else 2)
        if self.box is not None:
            self.box.set_columns(cols)

    def _enter(self, _e=None):
        if dw.Popup.current is None:
            self.buttons["ok"].invoke()
        return "break"

    def _escape(self, _e=None):
        if dw.Popup.current is None:
            self.close()
        return "break"

    def _inside(self, w, container):
        while w is not None:
            if w is container:
                return True
            w = w.master
        return False

    def _wheel(self, e):
        try:
            w = self.root.winfo_containing(e.x_root, e.y_root)
        except tk.TclError, KeyError:
            return
        steps = wheel_steps(e.delta)
        if self._inside(w, self.page_cv) and self.page_bar.winfo_ismapped():
            self.page_cv.yview_scroll(steps * 3, "units")
        elif self._inside(w, self.side_cv) and self.side_bar.winfo_ismapped():
            self.side_cv.yview_scroll(steps * 3, "units")

    def _see(self, e):
        """Scroll the page area so the focused control is visible."""
        w = e.widget
        if not self._inside(w, self.page_in) or not self.page_bar.winfo_ismapped():
            return
        cv = self.page_cv
        top = w.winfo_rooty() - self.page_in.winfo_rooty()
        bottom = top + w.winfo_height()
        total = max(1, self.page_in.winfo_height())
        view0, view1 = cv.yview()
        y0, y1 = view0 * total, view1 * total
        if top < y0:
            cv.yview_moveto(max(0, top - sc(12)) / total)
        elif bottom > y1:
            cv.yview_moveto((bottom + sc(12) - (y1 - y0)) / total)

    def _activation(self, active):
        if active:
            self.preview.resume()
            return

        def check():
            try:
                if self.root.focus_get() is None or self.root.state() == "iconic":
                    self.preview.pause()
            except tk.TclError, KeyError:
                pass

        self.root.after(150, check)

    def _preview_cfg(self):
        m = self.model
        return m.scope_cfg(), m.to_cfg(), m.card_sample(m.effective_preset())

    def _full_state(self, running):
        self.full_btn.set_enabled(not running)

    def reset(self):
        if messagebox.askyesno("Reset to defaults", dm.RESET_QUESTION, parent=self.root):
            self.model.reset()

    def ok(self):
        cfg = self.model.to_cfg()
        # Clean the values as load() would, so out-of-range values are clamped.
        settings.save(settings.clean(json.loads(json.dumps(cfg))))
        self.close()

    def close(self):
        self.preview.close()
        with contextlib.suppress(tk.TclError):
            self.root.destroy()


class EffectsBox:
    """The preset-controlled effects panel of the Look page."""

    def __init__(self, app, parent):
        self.app = app
        bg = dw.BG_PANEL
        self.panel = dw.Panel(parent, dw.BG_WINDOW, pad=16)
        inner = self.inner = self.panel.inner
        inner.grid_columnconfigure(0, weight=1)
        head = tk.Frame(inner, bg=bg)
        head.grid(row=0, column=0, sticky="ew")
        self.icon = tk.Canvas(
            head, width=sc(18), height=sc(18), bg=bg, highlightthickness=0, bd=0, takefocus=0
        )
        self.icon.pack(side="left", padx=(0, sc(8)))
        self.title = _label(head, "", "body_semi", dw.TEXT, bg)
        self.title.pack(side="left")
        self.strong = _label(head, "", "body_semi", dw.TEXT_STRONG, bg)
        self.customise = dw.Button(
            head, "Customise these", bg, kind="accent-outline", command=app.model.customise
        )
        self.note = _label(inner, "", "help", dw.TEXT_MUTED, bg)
        self.colour_row = RowView(app, inner, "color", bg, divider=False)
        self.colour_ctl = app.make_control(self.colour_row.cell, "color", "dropdown", bg)
        self.grid = tk.Frame(inner, bg=bg)
        self.grid.grid(row=3, column=0, sticky="ew", pady=(sc(10), 0))
        self.items = {}
        for key in dm.BOX_KEYS:
            cell = tk.Frame(self.grid, bg=bg)
            lab = _label(cell, dm.LABELS[key], "body", dw.TEXT, bg, width=0)
            lab.grid(row=0, column=0, sticky="w")
            dw.Tooltip(lab, dm.EFFECT_TIPS[key])
            cell.grid_columnconfigure(0, minsize=sc(120))
            holder = tk.Frame(cell, bg=bg)
            holder.grid(row=0, column=1, sticky="w")
            kind = dict(dm.BOX_ROWS)[key]
            ctl = app.make_control(holder, key, kind, bg, compact=True)
            self.items[key] = (cell, lab, ctl)
        self.columns = 2
        self.layout_key = None

    def set_columns(self, n):
        self.columns = n
        self._layout()

    def _layout(self):
        mon = self.app.model.in_monitor()
        key = (self.columns, mon)
        if key == self.layout_key:
            return
        self.layout_key = key
        keys = [k for k in dm.BOX_KEYS if not (mon and k == "color")]
        for k in dm.BOX_KEYS:
            self.items[k][0].grid_forget()
        for c in range(2):
            self.grid.grid_columnconfigure(
                c, weight=1 if c < self.columns else 0, uniform="box" if c < self.columns else ""
            )
        for i, k in enumerate(keys):
            r, c = divmod(i, self.columns)
            self.items[k][0].grid(row=r, column=c, sticky="w", pady=sc(3), padx=(0, sc(16)))

    def refresh(self):
        m = self.app.model
        h = m.effects_header()
        self.icon.delete("all")
        dw.draw_icon(
            self.icon,
            "lock" if h["locked"] else "shared" if h["note"] else "",
            sc(2),
            sc(2),
            dw.TEXT_MUTED,
        )
        if not h["locked"] and not h["note"]:
            self.icon.pack_forget()
        else:
            self.icon.pack(side="left", padx=(0, sc(8)), before=self.title)
        self.title.configure(text=h["title"])
        if h["strong"]:
            self.strong.configure(text=" " + h["strong"])
            self.strong.pack(side="left", after=self.title)
        else:
            self.strong.pack_forget()
        if h["customise"]:
            self.customise.pack(side="right")
        else:
            self.customise.pack_forget()
        if h["note"]:
            self.note.configure(text=h["note"])
            self.note.grid(row=1, column=0, sticky="w", pady=(sc(4), 0))
        else:
            self.note.grid_remove()
        mon = m.in_monitor()
        if mon:
            self.colour_row.frame.grid(row=2, column=0, sticky="ew", pady=(sc(6), 0))
            r = m.row("color")
            self.colour_row.update(r)
            self.colour_ctl.set(m.value("color"))
            self.colour_ctl.set_enabled(r.enabled)
        else:
            self.colour_row.frame.grid_remove()
        self._layout()
        for key, (_cell, lab, ctl) in self.items.items():
            if mon and key == "color":
                continue
            r = m.row(key)
            ctl.set(m.value(key))
            ctl.set_enabled(r.enabled)
            lab.configure(fg=dw.TEXT if r.enabled else dw.TEXT_DISABLED)


def build(root):
    """Fill `root` (a tk.Tk) with the settings widgets; -> the SettingsWindow.

    Starts no child process: show() starts the live preview after first paint."""
    return SettingsWindow(root)


def capture(root, shot):
    """Save a PNG of the mapped window. Raises RuntimeError when it is clipped."""
    root.update()
    osapi.set_dark_title_bar(int(root.wm_frame(), 16))  # again, now it is mapped
    root.after(300)
    root.update()
    mw, mh = root.minsize()
    if root.winfo_width() < mw or root.winfo_height() < mh:
        raise RuntimeError(
            f"dialog clipped: {root.winfo_width()}x{root.winfo_height()} shown, {mw}x{mh} minimum"
        )
    osapi.capture_window(int(root.wm_frame(), 16), shot)


def show(shot=None, scale=None, size=None):
    """Open the settings window. With `shot`, save a PNG of it and exit instead
    (scale: simulate a monitor at that multiple of 96 DPI; size: (w, h) in 96 DPI
    units, default 1200 x 1040). Capture errors raise RuntimeError after the
    window is closed."""
    root = tk.Tk()
    app = None
    try:
        if shot and scale:
            root.tk.call("tk", "scaling", scale * 96 / 72)
        app = SettingsWindow(root, shot_size=(size or OPEN_SIZE) if shot else None)
        if not shot:
            root.after_idle(app.preview.start)
            root.mainloop()
            return
        capture(root, shot)
    finally:
        if app is not None:
            app.preview.close()
        with contextlib.suppress(tk.TclError):
            root.destroy()
