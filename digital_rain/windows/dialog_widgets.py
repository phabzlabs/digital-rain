"""Canvas-drawn controls of the settings window.

Every colour, size and radius is a design token defined once here. Sizes are in
96 DPI pixels and scaled with `set_scale`. Disabled controls are drawn with
their colours blended 55% toward bg-window, because Tk has no opacity.
tools/checks/check_dialog.py reads TOKENS and TEXT_PAIRS and checks every text pair's
contrast.
"""

import contextlib
import tkinter as tk
import tkinter.font as tkfont

TOKENS = {
    "bg-window": "#0B110D",
    "bg-chrome": "#0E1611",
    "bg-panel": "#111A14",
    "bg-input": "#16221B",
    "bg-preview": "#020403",
    "border": "#24372B",
    "border-input": "#2C4434",
    "divider": "#1E2E24",
    "text": "#DDF3E6",
    "text-strong": "#EAFBF1",
    "text-muted": "#9DBDAA",
    "text-disabled": "#93AE9F",
    "accent": "#3DDC84",
    "accent-hover": "#52E393",
    "on-accent": "#06210F",
    "override": "#F2B356",
    "override-chip-bg": "#2A2110",
    "override-chip-text": "#F2C77F",
    "override-chip-border": "#5A4520",
    "section-label": "#7FD9A6",
}
# Every (text, background) pair the window draws; each must reach 4.5:1.
TEXT_PAIRS = [
    ("text", "bg-window"),
    ("text", "bg-chrome"),
    ("text", "bg-panel"),
    ("text", "bg-input"),
    ("text-strong", "bg-window"),
    ("text-strong", "bg-chrome"),
    ("text-strong", "bg-panel"),
    ("text-muted", "bg-window"),
    ("text-muted", "bg-chrome"),
    ("text-muted", "bg-panel"),
    ("text-muted", "bg-input"),
    ("text-muted", "bg-preview"),
    ("text-disabled", "bg-window"),
    ("text-disabled", "bg-chrome"),
    ("text-disabled", "bg-panel"),
    ("section-label", "bg-chrome"),
    ("accent", "bg-window"),
    ("accent", "bg-chrome"),
    ("accent", "bg-panel"),
    ("on-accent", "accent"),
    ("on-accent", "accent-hover"),
    ("override", "bg-window"),
    ("override", "bg-chrome"),
    ("override", "bg-panel"),
    ("override-chip-bg", "override"),
    ("override-chip-text", "override-chip-bg"),
    ("text", "bg-preview"),
]
TYPE = {
    "title": 21,
    "label": 14,
    "help": 12.5,
    "summary": 11.5,
    "body": 13,
    "section": 11,
    "value": 13,
    "card": 13,
}
RADIUS = {"button": 8, "segment": 8, "panel": 10, "input": 6}
MIN_H = {"pill": 30, "control": 36}
SIDEBAR_W = 248
LABEL_W = 230
SCOPE_W = 112
DISABLED_BLEND = 0.55

BG_WINDOW = TOKENS["bg-window"]
BG_CHROME = TOKENS["bg-chrome"]
BG_PANEL = TOKENS["bg-panel"]
BG_INPUT = TOKENS["bg-input"]
BG_PREVIEW = TOKENS["bg-preview"]
BORDER = TOKENS["border"]
BORDER_INPUT = TOKENS["border-input"]
DIVIDER = TOKENS["divider"]
TEXT = TOKENS["text"]
TEXT_STRONG = TOKENS["text-strong"]
TEXT_MUTED = TOKENS["text-muted"]
TEXT_DISABLED = TOKENS["text-disabled"]
ACCENT = TOKENS["accent"]
ACCENT_HOVER = TOKENS["accent-hover"]
ON_ACCENT = TOKENS["on-accent"]
OVERRIDE = TOKENS["override"]
CHIP_BG = TOKENS["override-chip-bg"]
CHIP_TEXT = TOKENS["override-chip-text"]
CHIP_BORDER = TOKENS["override-chip-border"]
SECTION_LABEL = TOKENS["section-label"]

UI_FAMILY = "Segoe UI"
UI_SEMIBOLD = "Segoe UI Semibold"
MONO_FAMILY = "Consolas"
GLYPHS = "ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍ012345789Z:.=*+-<>"

PX = 1.0  # 96 DPI scale, from set_scale()
FONTS = {}  # name -> tkinter.font.Font, from set_scale()


def set_scale(root, px):
    """Scale factor (screen pixels per 96 DPI pixel) and the dialog's fonts."""
    global PX
    PX = px
    FONTS.clear()

    def f(name, family, size, weight="normal"):
        FONTS[name] = tkfont.Font(
            root=root, family=family, size=-max(1, round(size * px)), weight=weight
        )

    f("title", UI_FAMILY, TYPE["title"], "bold")
    f("label", UI_SEMIBOLD, TYPE["label"])
    f("help", UI_FAMILY, TYPE["help"])
    f("summary", UI_FAMILY, TYPE["summary"])
    f("body", UI_FAMILY, TYPE["body"])
    f("body_semi", UI_SEMIBOLD, TYPE["body"])
    f("section", UI_SEMIBOLD, TYPE["section"])
    f("value", MONO_FAMILY, TYPE["value"])
    f("card", UI_SEMIBOLD, TYPE["card"])
    f("glyph", MONO_FAMILY, 11)


def sc(v):
    """96 DPI pixels -> screen pixels."""
    return int(round(v * PX))


def _rgb(c):
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def blend(c, toward=BG_WINDOW, k=DISABLED_BLEND):
    """`c` moved k of the way toward `toward` (hex colours)."""
    a, b = _rgb(c), _rgb(toward)
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * k) for x, y in zip(a, b, strict=True))


def rrect(cv, x0, y0, x1, y1, r, **kw):
    """Rounded rectangle on a canvas (smoothed polygon)."""
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = [
        x0 + r,
        y0,
        x0 + r,
        y0,
        x1 - r,
        y0,
        x1 - r,
        y0,
        x1,
        y0,
        x1,
        y0 + r,
        x1,
        y0 + r,
        x1,
        y1 - r,
        x1,
        y1 - r,
        x1,
        y1,
        x1 - r,
        y1,
        x1 - r,
        y1,
        x0 + r,
        y1,
        x0 + r,
        y1,
        x0,
        y1,
        x0,
        y1 - r,
        x0,
        y1 - r,
        x0,
        y0 + r,
        x0,
        y0 + r,
        x0,
        y0,
    ]
    return cv.create_polygon(pts, smooth=True, splinesteps=6, **kw)


def text_width(font, text):
    return FONTS[font].measure(text)


def elide(font, text, width, left=False):
    """`text` cut with an ellipsis to fit `width` pixels."""
    f = FONTS[font]
    if f.measure(text) <= width:
        return text
    while text and f.measure("…" + text if left else text + "…") > width:
        text = text[1:] if left else text[:-1]
    return ("…" + text) if left else (text + "…")


class Control(tk.Canvas):
    """A focusable canvas control with a 2 px accent focus ring.

    accessible_name is the row label (Tk on Windows exposes no UI Automation
    names, so this is what a test or a future accessibility layer reads)."""

    ring_pad = 3  # 96 DPI pixels kept around the drawing for the focus ring
    ring_radius = RADIUS["button"]

    def __init__(self, master, width, height, bg, name="", focusable=True):
        super().__init__(
            master,
            width=width,
            height=height,
            bg=bg,
            highlightthickness=0,
            bd=0,
            takefocus=1 if focusable else 0,
        )
        self.bg = bg
        self.accessible_name = name
        self.focusable = focusable
        self.enabled = True
        self.has_focus = False
        self.hover = False
        self.bindtags((str(self), "DlgCtl", "Canvas", self.winfo_toplevel(), "all"))
        if focusable:
            self.bind("<FocusIn>", lambda e: self._focus(True))
            self.bind("<FocusOut>", lambda e: self._focus(False))
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self.bind("<Configure>", lambda e: self.redraw())

    def _focus(self, on):
        self.has_focus = on
        self.redraw()

    def _hover(self, on):
        self.hover = on
        if self.enabled:
            self.redraw()

    def col(self, c):
        return c if self.enabled else blend(c)

    def set_enabled(self, on):
        on = bool(on)
        if on == self.enabled:
            return
        self.enabled = on
        self.configure(
            takefocus=1 if on and self.focusable else 0,
            cursor="hand2" if on and self.clickable() else "",
        )
        if not on and self.has_focus:
            self.winfo_toplevel().focus_set()
        self.redraw()

    def clickable(self):
        return True

    def size(self):
        return max(1, self.winfo_width()), max(1, self.winfo_height())

    def redraw(self):
        self.delete("all")
        self.draw()
        if self.has_focus and self.enabled:
            self.draw_ring()

    def draw_ring(self):
        w, h = self.size()
        rrect(self, 1, 1, w - 2, h - 2, sc(self.ring_radius) + 2, outline=ACCENT, width=2, fill="")

    def draw(self):
        pass

    def click_focus(self):
        if self.enabled and self.focusable:
            self.focus_set()


class Switch(Control):
    """On/off switch, 42 x 24."""

    def __init__(self, master, bg, command=None, name=""):
        p = self.ring_pad
        super().__init__(master, sc(42 + 2 * p), sc(MIN_H["control"]), bg, name)
        self.value = False
        self.command = command
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._click)
        self.bind("<space>", lambda e: self.toggle())

    def set(self, value):
        value = bool(value)
        if value != self.value:
            self.value = value
            self.redraw()

    def _click(self, _e):
        self.click_focus()
        self.toggle()

    def toggle(self):
        if not self.enabled:
            return
        self.set(not self.value)
        if self.command:
            self.command(self.value)

    def draw(self):
        w, h = self.size()
        tw, th = sc(42), sc(24)
        x0, y0 = sc(self.ring_pad), (h - th) // 2
        if self.value:
            rrect(self, x0, y0, x0 + tw, y0 + th, th / 2, fill=self.col(ACCENT), outline="")
            kx = x0 + tw - th / 2
            knob = self.col(TEXT_STRONG)
        else:
            rrect(
                self,
                x0,
                y0,
                x0 + tw,
                y0 + th,
                th / 2,
                fill=self.col(BG_INPUT),
                outline=self.col(BORDER_INPUT),
            )
            kx = x0 + th / 2
            knob = self.col(TEXT_MUTED)
        r = th / 2 - sc(3)
        cy = y0 + th / 2
        self.create_oval(kx - r, cy - r, kx + r, cy + r, fill=knob, outline="")

    def draw_ring(self):
        w, h = self.size()
        th = sc(24)
        y0 = (h - th) // 2
        p = sc(self.ring_pad)
        rrect(
            self,
            p - sc(3),
            y0 - sc(3),
            p + sc(42) + sc(3),
            y0 + th + sc(3),
            th / 2 + sc(3),
            outline=ACCENT,
            width=2,
            fill="",
        )


class Choice(Control):
    """A control that picks one of several cells (Segmented, PresetCards, ClockGrid).

    Subclasses fill `values` (cell order), keep `value` and `command`, and return the
    cell rectangles from cell_boxes() so a click can be mapped to a cell."""

    def _index(self):
        return self.values.index(self.value) if self.value in self.values else 0

    def _pick(self, i):
        if not self.enabled:
            return
        value = self.values[i]
        if value != self.value:
            self.set(value)
            if self.command:
                self.command(value)

    def move(self, step):
        """Move the choice by `step` cells, stopping at the ends."""
        self._pick(max(0, min(len(self.values) - 1, self._index() + step)))
        return "break"

    def _click(self, e):
        self.click_focus()
        for i, (x0, y0, x1, y1) in enumerate(self.cell_boxes()):
            if x0 <= e.x < x1 and y0 <= e.y < y1:
                self._pick(i)
                return


class Segmented(Choice):
    """2 to 4 mutually exclusive options; Left and Right move the choice."""

    def __init__(self, master, options, bg, command=None, name=""):
        self.options = list(options)  # [(value, label)]
        self.values = [value for value, _label in self.options]
        pad = 16
        self.widths = [
            max(sc(64), text_width("body_semi", lab) + sc(2 * pad)) for _v, lab in self.options
        ]
        p = sc(self.ring_pad)
        super().__init__(master, sum(self.widths) + 2 * p, sc(MIN_H["control"]) + 2 * p, bg, name)
        self.value = self.values[0]
        self.command = command
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._click)
        self.bind("<Left>", lambda e: self.move(-1))
        self.bind("<Right>", lambda e: self.move(1))

    def set(self, value):
        if value != self.value:
            self.value = value
            self.redraw()

    def cell_boxes(self):
        """Each segment spans the full control height, so a click anywhere on it counts."""
        height = self.size()[1]
        boxes = []
        x = sc(self.ring_pad)
        for width in self.widths:
            boxes.append((x, 0, x + width, height))
            x += width
        return boxes

    def draw(self):
        p = sc(self.ring_pad)
        h = sc(MIN_H["control"])
        x0, y0 = p, p
        total = sum(self.widths)
        r = sc(RADIUS["segment"])
        rrect(
            self,
            x0,
            y0,
            x0 + total,
            y0 + h,
            r,
            fill=self.col(BG_INPUT),
            outline=self.col(BORDER_INPUT),
        )
        sel = self._index()
        x = x0
        for i, ((_v, lab), w) in enumerate(zip(self.options, self.widths, strict=True)):
            if i == sel:
                rrect(self, x, y0, x + w, y0 + h, r, fill=self.col(ACCENT), outline="")
                fg = self.col(ON_ACCENT)
            else:
                fg = self.col(TEXT)
                if i and i - 1 != sel:
                    self.create_line(x, y0 + 1, x, y0 + h - 1, fill=self.col(BORDER_INPUT))
            self.create_text(x + w / 2, y0 + h / 2, text=lab, fill=fg, font=FONTS["body_semi"])
            x += w


class Slider(Control):
    """Numeric slider with the value in monospace on the right and optional end
    labels. Left/Right move 1% of the range, Page Up/Page Down 10%."""

    def __init__(self, master, lo, hi, decimals, unit, ends, bg, command=None, name="", width=320):
        self.lo, self.hi, self.dec, self.unit, self.ends = lo, hi, decimals, unit, ends
        h = MIN_H["control"] + (16 if ends else 0)
        super().__init__(master, sc(width), sc(h), bg, name)
        self.value = lo
        self.command = command
        self.value_w = max(text_width("value", self._fmt(v)) for v in (lo, hi)) + sc(8)
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Left>", lambda e: self.step(-0.01))
        self.bind("<Right>", lambda e: self.step(0.01))
        self.bind("<Prior>", lambda e: self.step(0.1))
        self.bind("<Next>", lambda e: self.step(-0.1))

    def _fmt(self, v):
        return f"{v:.{self.dec}f}{self.unit}"

    def set(self, value):
        value = float(value)
        if value != self.value:
            self.value = value
            self.redraw()

    def _track(self):
        w, _h = self.size()
        p = sc(self.ring_pad) + sc(8)
        return p, w - self.value_w - sc(14)

    def _emit(self, v):
        v = min(self.hi, max(self.lo, v))
        if v != self.value:
            self.set(v)
            if self.command:
                self.command(v)

    def step(self, frac):
        if self.enabled:
            self._emit(self.value + frac * (self.hi - self.lo))
        return "break"

    def _from_x(self, x):
        x0, x1 = self._track()
        k = (x - x0) / max(1, x1 - x0)
        return self.lo + min(1.0, max(0.0, k)) * (self.hi - self.lo)

    def _press(self, e):
        self.click_focus()
        if self.enabled:
            self._emit(self._from_x(e.x))

    def _drag(self, e):
        if self.enabled:
            self._emit(self._from_x(e.x))

    def draw(self):
        w, _h = self.size()
        cy = sc(MIN_H["control"]) / 2
        x0, x1 = self._track()
        k = (self.value - self.lo) / max(1e-9, self.hi - self.lo)
        kx = x0 + k * (x1 - x0)
        th = sc(4)
        rrect(
            self, x0, cy - th / 2, x1, cy + th / 2, th / 2, fill=self.col(BORDER_INPUT), outline=""
        )
        if kx > x0 + 1:
            rrect(self, x0, cy - th / 2, kx, cy + th / 2, th / 2, fill=self.col(ACCENT), outline="")
        r = sc(8)
        self.create_oval(
            kx - r,
            cy - r,
            kx + r,
            cy + r,
            fill=self.col(TEXT_STRONG),
            outline=self.col(BORDER_INPUT),
        )
        self.create_text(
            w - sc(self.ring_pad) - sc(2),
            cy,
            text=self._fmt(self.value),
            anchor="e",
            fill=self.col(TEXT),
            font=FONTS["value"],
        )
        if self.ends:
            y = sc(MIN_H["control"]) + sc(5)
            fg = self.col(TEXT_MUTED)
            self.create_text(
                x0 - sc(6), y, text=self.ends[0], anchor="w", fill=fg, font=FONTS["summary"]
            )
            self.create_text(
                x1 + sc(6), y, text=self.ends[1], anchor="e", fill=fg, font=FONTS["summary"]
            )

    def draw_ring(self):
        w, _h = self.size()
        rrect(
            self,
            1,
            1,
            w - 2,
            sc(MIN_H["control"]) - 2,
            sc(self.ring_radius),
            outline=ACCENT,
            width=2,
            fill="",
        )


class Pill(Control):
    """Scope pill: "Override" (outlined) or "Overridden" (amber)."""

    def __init__(self, master, bg, command=None, name=""):
        p = self.ring_pad
        w = max(text_width("body_semi", t) for t in ("Override", "Overridden")) + sc(28)
        super().__init__(master, w + sc(2 * p), sc(MIN_H["pill"] + 2 * p), bg, name)
        self.kind = "override"
        self.command = command
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._click)
        self.bind("<space>", lambda e: self._fire())

    def set(self, kind):
        if kind != self.kind:
            self.kind = kind
            self.redraw()

    def _click(self, _e):
        self.click_focus()
        self._fire()

    def _fire(self):
        if self.enabled and self.command:
            self.command()

    def draw(self):
        w, h = self.size()
        p = sc(self.ring_pad)
        x0, y0, x1, y1 = p, p, w - p, h - p
        r = (y1 - y0) / 2
        if self.kind == "overridden":
            rrect(self, x0, y0, x1, y1, r, fill=self.col(OVERRIDE), outline="")
            fg, text = self.col(CHIP_BG), "Overridden"
        else:
            rrect(self, x0, y0, x1, y1, r, fill=self.bg, outline=self.col(OVERRIDE))
            fg, text = self.col(OVERRIDE), "Override"
        self.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=text, fill=fg, font=FONTS["body_semi"])

    def draw_ring(self):
        w, h = self.size()
        rrect(self, 1, 1, w - 2, h - 2, (h - 2) / 2, outline=ACCENT, width=2, fill="")


class Button(Control):
    """kind: "outline", "accent" (filled), "accent-outline" or "link" (text only)."""

    def __init__(
        self,
        master,
        text,
        bg,
        command=None,
        kind="outline",
        name="",
        font=None,
        height=None,
        width=None,
        icon=None,
    ):
        self.text, self.kind, self.icon = text, kind, icon
        self.font = font or ("body_semi" if kind != "link" else "help")
        pad = 0 if kind == "link" else 18
        tw = text_width(self.font, text) + (sc(18) if icon else 0)
        w = width if width is not None else tw + sc(2 * pad) + sc(2 * self.ring_pad)
        h = (
            height
            if height is not None
            else sc(MIN_H["control"]) + (0 if kind == "link" else sc(2 * self.ring_pad))
        )
        super().__init__(master, w, h, bg, name or text)
        self.command = command
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._click)
        self.bind("<space>", lambda e: self.invoke())

    def _click(self, _e):
        self.click_focus()
        self.invoke()

    def invoke(self):
        """Run the command (as ttk.Button.invoke does); nothing when disabled."""
        if self.enabled and self.command:
            return self.command()

    def draw(self):
        w, h = self.size()
        if self.kind == "link":
            fg = self.col(ACCENT)
            tid = self.create_text(
                0, h / 2, text=self.text, anchor="w", fill=fg, font=FONTS[self.font]
            )
            if self.enabled:
                x0, _y0, x1, y1 = self.bbox(tid)
                self.create_line(x0, y1 - 1, x1, y1 - 1, fill=fg)
            return
        p = sc(self.ring_pad)
        x0, y0, x1, y1 = p, p, w - p, h - p
        r = sc(RADIUS["button"])
        if self.kind == "accent":
            fill = ACCENT_HOVER if self.hover else self.col(ACCENT)
            rrect(self, x0, y0, x1, y1, r, fill=fill, outline="")
            fg = self.col(ON_ACCENT)
        else:
            fill = self.col(BG_INPUT) if self.hover and self.enabled else self.bg
            edge = self.col(BORDER_INPUT)
            rrect(self, x0, y0, x1, y1, r, fill=fill, outline=edge)
            fg = self.col(ACCENT if self.kind == "accent-outline" else TEXT)
        cx = (x0 + x1) / 2
        if self.icon == "fullscreen":
            tw = text_width(self.font, self.text)
            ix = cx - (tw + sc(18)) / 2
            cy, s = (y0 + y1) / 2, sc(5)
            for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                bx, by = ix + dx * 2 * s, cy - s + dy * 2 * s
                hx = s * 0.6 * (1 if dx == 0 else -1)
                hy = s * 0.6 * (1 if dy == 0 else -1)
                self.create_line(bx, by + hy, bx, by, bx + hx, by, fill=fg, width=max(1, sc(1.4)))
            cx = ix + sc(18) + tw / 2
        self.create_text(cx, (y0 + y1) / 2, text=self.text, fill=fg, font=FONTS[self.font])

    def draw_ring(self):
        w, h = self.size()
        if self.kind == "link":
            rrect(self, 0, sc(6), w - 1, h - sc(6), sc(4), outline=ACCENT, width=2, fill="")
            return
        super().draw_ring()


class Chip(Control):
    """Override chip (amber), or muted for a stale override."""

    def __init__(self, master, text, bg, muted=False):
        self.text, self.muted = text, muted
        super().__init__(master, self.width_for(text), sc(24), bg, focusable=False)

    @staticmethod
    def width_for(text):
        """Canvas width of a chip showing `text`, so layouts can measure without building one."""
        return text_width("summary", text) + sc(18) + 2

    def clickable(self):
        return False

    def draw(self):
        w, h = self.size()
        if self.muted:
            fill, edge, fg = BG_PANEL, BORDER, TEXT_MUTED
        else:
            fill, edge, fg = CHIP_BG, CHIP_BORDER, CHIP_TEXT
        rrect(self, 0, 0, w - 1, h - 1, (h - 1) / 2, fill=fill, outline=edge)
        self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=FONTS["summary"])


class PresetCards(Choice):
    """Four preset cards with a colour sample each; Left/Right move the choice."""

    CARD_H = 112
    GAP = 10

    def __init__(self, master, cards, bg, command=None, name=""):
        self.cards = list(cards)  # [(value, title, subtitle)]
        self.values = [card[0] for card in self.cards]
        self.samples = {}
        self.columns = 4
        super().__init__(
            master,
            sc(4 * 128 + 3 * self.GAP + 2 * self.ring_pad),
            sc(self.CARD_H + 2 * self.ring_pad),
            bg,
            name,
        )
        self.value = self.values[0]
        self.command = command
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._click)
        self.bind("<Left>", lambda e: self.move(-1))
        self.bind("<Right>", lambda e: self.move(1))
        self.bind("<Up>", lambda e: self.move(-self.columns) if self.columns == 2 else None)
        self.bind("<Down>", lambda e: self.move(self.columns) if self.columns == 2 else None)

    def set(self, value, samples=None):
        changed = value != self.value or (samples is not None and samples != self.samples)
        self.value = value
        if samples is not None:
            self.samples = dict(samples)
        if changed:
            self.redraw()

    def set_columns(self, n):
        if n == self.columns:
            return
        self.columns = n
        rows = 4 // n
        self.configure(height=sc(rows * self.CARD_H + (rows - 1) * self.GAP + 2 * self.ring_pad))
        self.redraw()

    def cell_boxes(self):
        w, _h = self.size()
        p = sc(self.ring_pad)
        n = self.columns
        gap = sc(self.GAP)
        cw = min(sc(150), (w - 2 * p - (n - 1) * gap) / n)
        ch = sc(self.CARD_H)
        out = []
        for i in range(4):
            r, c = divmod(i, n)
            x0 = p + c * (cw + gap)
            y0 = p + r * (ch + gap)
            out.append((x0, y0, x0 + cw, y0 + ch))
        return out

    def draw(self):
        sel = self._index()
        for i, ((value, title, sub), (x0, y0, x1, y1)) in enumerate(
            zip(self.cards, self.cell_boxes(), strict=True)
        ):
            on = i == sel
            rrect(
                self,
                x0,
                y0,
                x1,
                y1,
                sc(RADIUS["panel"]),
                fill=self.col(BG_PANEL),
                outline=self.col(ACCENT if on else BORDER),
                width=2 if on else 1,
            )
            pad = sc(8)
            sx0, sy0, sx1, sy1 = x0 + pad, y0 + pad, x1 - pad, y0 + pad + sc(44)
            rrect(
                self, sx0, sy0, sx1, sy1, sc(RADIUS["input"]), fill=self.col(BG_PREVIEW), outline=""
            )
            colour = self.col(self.samples.get(value, ACCENT))
            gw = FONTS["glyph"].measure("0")
            cols = max(1, int((sx1 - sx0 - sc(8)) // gw))
            for row in range(3):
                line = "".join(
                    GLYPHS[(i * 7 + row * 11 + c * 5) % len(GLYPHS)] for c in range(cols)
                )
                self.create_text(
                    sx0 + sc(4),
                    sy0 + sc(8) + row * sc(13),
                    text=line,
                    anchor="w",
                    fill=colour,
                    font=FONTS["glyph"],
                )
            self.create_text(
                x0 + pad,
                sy1 + sc(16),
                text=elide("card", title, x1 - x0 - 2 * pad),
                anchor="w",
                fill=self.col(TEXT_STRONG),
                font=FONTS["card"],
            )
            self.create_text(
                x0 + pad,
                sy1 + sc(36),
                text=sub,
                anchor="w",
                fill=TEXT_MUTED if self.enabled else TEXT_DISABLED,
                font=FONTS["summary"],
            )
        if self.has_focus and self.enabled:
            x0, y0, x1, y1 = self.cell_boxes()[sel]
            rrect(
                self,
                x0 - sc(3),
                y0 - sc(3),
                x1 + sc(3),
                y1 + sc(3),
                sc(RADIUS["panel"]) + sc(3),
                outline=ACCENT,
                width=2,
                fill="",
            )

    def draw_ring(self):
        pass  # drawn around the selected card in draw()


class ClockGrid(Choice):
    """3 x 3 grid of the nine clock positions; arrow keys move the choice."""

    CELL_W, CELL_H, GAP, PAD = 56, 36, 4, 6
    ring_radius = RADIUS["panel"]

    def __init__(self, master, values, names, bg, command=None, name=""):
        self.values, self.names = list(values), dict(names)
        w = 3 * self.CELL_W + 2 * self.GAP + 2 * self.PAD + 2 * self.ring_pad
        h = 3 * self.CELL_H + 2 * self.GAP + 2 * self.PAD + 2 * self.ring_pad
        super().__init__(master, sc(w), sc(h), bg, name)
        self.value = self.values[0]
        self.command = command
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._click)
        for key, d in (
            ("<Left>", (-1, 0)),
            ("<Right>", (1, 0)),
            ("<Up>", (0, -1)),
            ("<Down>", (0, 1)),
        ):
            self.bind(key, lambda e, d=d: self.move(*d))

    def set(self, value):
        if value != self.value:
            self.value = value
            self.redraw()

    def cell_boxes(self):
        o = sc(self.ring_pad + self.PAD)
        cw, ch, g = sc(self.CELL_W), sc(self.CELL_H), sc(self.GAP)
        return [
            (o + c * (cw + g), o + r * (ch + g), o + c * (cw + g) + cw, o + r * (ch + g) + ch)
            for r in range(3)
            for c in range(3)
        ]

    def move(self, dx, dy):
        row, col = divmod(self._index(), 3)
        row, col = max(0, min(2, row + dy)), max(0, min(2, col + dx))
        self._pick(row * 3 + col)
        return "break"

    def draw(self):
        w, h = self.size()
        p = sc(self.ring_pad)
        rrect(
            self,
            p,
            p,
            w - p,
            h - p,
            sc(RADIUS["panel"]),
            fill=self.col(BG_PANEL),
            outline=self.col(BORDER),
        )
        for i, (x0, y0, x1, y1) in enumerate(self.cell_boxes()):
            on = self.values[i] == self.value
            rrect(
                self,
                x0,
                y0,
                x1,
                y1,
                sc(RADIUS["input"]),
                fill=self.col(ACCENT if on else BG_INPUT),
                outline="",
            )


class Popup(tk.Toplevel):
    """Drop-down list. entries: dicts with kind "item" (value, label, muted, right,
    dot), "divider" or "heading" (label). Up/Down/Enter/Space/Esc and the mouse."""

    current = None  # the open popup: the dialog's Enter and Esc leave it alone
    ROW_H, DIV_H, HEAD_H = 36, 9, 26

    def __init__(self, owner, entries, selected, on_pick, width):
        super().__init__(owner)
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg=BORDER)
        self.owner, self.entries, self.on_pick = owner, entries, on_pick
        self.items = [i for i, e in enumerate(entries) if e["kind"] == "item"]
        self.active = next(
            (i for i in self.items if entries[i]["value"] == selected),
            self.items[0] if self.items else None,
        )
        heights = [
            sc(
                self.ROW_H
                if e["kind"] == "item"
                else self.DIV_H
                if e["kind"] == "divider"
                else self.HEAD_H
            )
            for e in entries
        ]
        self.tops = [sum(heights[:i]) + sc(4) for i in range(len(entries))]
        self.heights = heights
        h = sum(heights) + sc(8)
        self.cv = tk.Canvas(
            self, width=width - 2, height=h, bg=BG_INPUT, highlightthickness=0, bd=0
        )
        self.cv.pack(padx=1, pady=1)
        self.width = width - 2
        x, y = owner.winfo_rootx(), owner.winfo_rooty() + owner.winfo_height() + sc(2)
        if y + h > owner.winfo_screenheight() and owner.winfo_rooty() - h - sc(2) > 0:
            y = owner.winfo_rooty() - h - sc(2)
        self.geometry(f"{width}x{h + 2}+{x}+{y}")
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<Button-1>", self._click)
        self.bind("<Button-1>", self._click_outside)
        self.cv.bind("<Up>", lambda e: self._move(-1))
        self.cv.bind("<Down>", lambda e: self._move(1))
        for k in ("<Return>", "<space>", "<KP_Enter>"):
            self.cv.bind(k, lambda e: self._pick(self.active))
        self.cv.bind("<Escape>", lambda e: self.close())
        self.cv.bind("<Tab>", lambda e: self.close())
        self.draw()
        self.deiconify()
        self.lift()
        Popup.current = self
        self.cv.focus_set()
        with contextlib.suppress(tk.TclError):
            self.grab_set()

    def _row_at(self, y):
        for i, (t, hgt) in enumerate(zip(self.tops, self.heights, strict=True)):
            if t <= y < t + hgt and self.entries[i]["kind"] == "item":
                return i
        return None

    def _motion(self, e):
        i = self._row_at(e.y)
        if i is not None and i != self.active:
            self.active = i
            self.draw()

    def _click(self, e):
        if not (0 <= e.x < self.width and 0 <= e.y < int(self.cv["height"])):
            self.close()
            return "break"
        i = self._row_at(e.y)
        if i is not None:
            self._pick(i)
        return "break"

    def _click_outside(self, e):
        if e.widget is self:
            self.close()

    def _move(self, d):
        if self.active is None:
            return "break"
        k = self.items.index(self.active) + d
        if 0 <= k < len(self.items):
            self.active = self.items[k]
            self.draw()
        return "break"

    def _pick(self, i):
        value = self.entries[i]["value"] if i is not None else None
        self.close()
        if i is not None:
            self.on_pick(value)
        return "break"

    def close(self):
        if Popup.current is self:
            Popup.current = None
        with contextlib.suppress(tk.TclError):
            self.grab_release()
            self.destroy()
        with contextlib.suppress(tk.TclError):
            self.owner.focus_set()
        return "break"

    def draw(self):
        cv = self.cv
        cv.delete("all")
        w = self.width
        for i, e in enumerate(self.entries):
            t, hgt = self.tops[i], self.heights[i]
            if e["kind"] == "divider":
                cv.create_line(sc(8), t + hgt / 2, w - sc(8), t + hgt / 2, fill=DIVIDER)
                continue
            if e["kind"] == "heading":
                cv.create_text(
                    sc(12),
                    t + hgt / 2,
                    text=e["label"].upper(),
                    anchor="w",
                    fill=TEXT_MUTED,
                    font=FONTS["section"],
                )
                continue
            if i == self.active:
                rrect(
                    cv,
                    sc(4),
                    t + 1,
                    w - sc(4),
                    t + hgt - 1,
                    sc(RADIUS["input"]),
                    fill=BG_PANEL,
                    outline=BORDER,
                )
            fg = TEXT_MUTED if e.get("muted") else TEXT
            cv.create_text(
                sc(12), t + hgt / 2, text=e["label"], anchor="w", fill=fg, font=FONTS["body"]
            )
            right = w - sc(12)
            if e.get("dot"):
                r = sc(3.5)
                cv.create_oval(
                    right - 2 * r,
                    t + hgt / 2 - r,
                    right,
                    t + hgt / 2 + r,
                    fill=OVERRIDE,
                    outline="",
                )
                right -= sc(14)
            if e.get("right"):
                cv.create_text(
                    right,
                    t + hgt / 2,
                    text=e["right"],
                    anchor="e",
                    fill=TEXT_MUTED,
                    font=FONTS["summary"],
                )


class Dropdown(Control):
    """Closed drop-down: the chosen label and a chevron. Space or Alt+Down opens
    the list; Enter and Esc go to the list while it is open."""

    ring_radius = RADIUS["input"]

    def __init__(self, master, options, bg, command=None, name="", width=220):
        self.options = list(options)  # [(value, label)] or entry dicts
        super().__init__(master, sc(width), sc(MIN_H["control"]), bg, name)
        self.value = None
        self.command = command
        self.configure(cursor="hand2")
        self.bind("<Button-1>", lambda e: (self.click_focus(), self.open()))
        self.bind("<space>", lambda e: self.open())
        self.bind("<Alt-Down>", lambda e: self.open())

    def set(self, value, options=None):
        changed = value != self.value
        if options is not None and options != self.options:
            self.options = list(options)
            changed = True
        self.value = value
        if changed:
            self.redraw()

    def entries(self):
        out = []
        for o in self.options:
            out.append(o if isinstance(o, dict) else dict(kind="item", value=o[0], label=o[1]))
        return out

    def label(self):
        for e in self.entries():
            if e["kind"] == "item" and e["value"] == self.value:
                return e["label"]
        return ""

    def open(self):
        if not self.enabled or Popup.current is not None:
            return "break"
        Popup(self, self.entries(), self.value, self._picked, self.winfo_width())
        return "break"

    def _picked(self, value):
        if value != self.value:
            self.set(value)
            if self.command:
                self.command(value)

    def draw(self):
        w, h = self.size()
        rrect(
            self,
            1,
            1,
            w - 2,
            h - 2,
            sc(RADIUS["input"]),
            fill=self.col(BG_INPUT),
            outline=self.col(BORDER_INPUT),
        )
        self.create_text(
            sc(12),
            h / 2,
            text=elide("body", self.label(), w - sc(40)),
            anchor="w",
            fill=self.col(TEXT),
            font=FONTS["body"],
        )
        cx, cy, s = w - sc(16), h / 2, sc(4)
        self.create_line(
            cx - s,
            cy - s / 2,
            cx,
            cy + s / 2,
            cx + s,
            cy - s / 2,
            fill=self.col(TEXT_MUTED),
            width=max(1, sc(1.5)),
        )


class TextField(tk.Frame):
    """Text box with an "n / max" counter line under it. `clean` filters what is
    typed; command(text) runs on every change."""

    def __init__(self, master, bg, maxlen, clean, help_text, command=None, name="", width=300):
        super().__init__(master, bg=bg)
        self.accessible_name = name
        self.maxlen, self.clean, self.help_text = maxlen, clean, help_text
        self.command = command
        self.enabled = True
        self.var = tk.StringVar()
        self.box = tk.Canvas(
            self,
            width=sc(width),
            height=sc(MIN_H["control"]),
            bg=bg,
            highlightthickness=0,
            bd=0,
            takefocus=0,
        )
        self.box.pack(anchor="w")
        self.entry = tk.Entry(
            self.box,
            textvariable=self.var,
            bg=BG_INPUT,
            fg=TEXT,
            disabledbackground=blend(BG_INPUT),
            disabledforeground=blend(TEXT),
            insertbackground=TEXT,
            selectbackground=BORDER_INPUT,
            selectforeground=TEXT_STRONG,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=FONTS["value"],
        )
        self.entry.accessible_name = name
        self.win = self.box.create_window(
            sc(10), sc(MIN_H["control"]) / 2, anchor="w", window=self.entry
        )
        # Wraps to the box width: a wraplength that follows the label's own width
        # changes its requested size and loops on <Configure>.
        self.counter = tk.Label(
            self,
            bg=bg,
            fg=TEXT_MUTED,
            font=FONTS["help"],
            anchor="w",
            justify="left",
            wraplength=sc(width),
        )
        self.counter.pack(anchor="w", fill="x", pady=(sc(4), 0))
        self.focused = False
        self.entry.bind("<FocusIn>", lambda e: self._focus(True))
        self.entry.bind("<FocusOut>", lambda e: self._focus(False))
        self.box.bind("<Configure>", lambda e: self._draw())
        self._busy = False
        self.var.trace_add("write", self._changed)

    def _focus(self, on):
        self.focused = on
        self._draw()

    def _draw(self):
        cv = self.box
        cv.delete("frame")
        w, h = max(1, cv.winfo_width()), max(1, cv.winfo_height())
        fill = BG_INPUT if self.enabled else blend(BG_INPUT)
        edge = BORDER_INPUT if self.enabled else blend(BORDER_INPUT)
        rrect(cv, 1, 1, w - 2, h - 2, sc(RADIUS["input"]), fill=fill, outline=edge, tags="frame")
        if self.focused and self.enabled:
            rrect(
                cv,
                1,
                1,
                w - 2,
                h - 2,
                sc(RADIUS["input"]) + 1,
                outline=ACCENT,
                width=2,
                fill="",
                tags="frame",
            )
        cv.tag_lower("frame")
        cv.itemconfigure(self.win, width=max(10, w - sc(20)))
        self._count()

    def _count(self):
        n = len(self.var.get())
        self.counter.configure(
            text=f"{n} / {self.maxlen} · {self.help_text}",
            fg=TEXT_MUTED if self.enabled else TEXT_DISABLED,
        )

    def _changed(self, *_a):
        if self._busy:
            return
        text = self.var.get()
        good = self.clean(text)
        if good != text:
            self._busy = True
            pos = self.entry.index("insert")
            self.var.set(good)
            self.entry.icursor(min(pos, len(good)))
            self._busy = False
        self._count()
        if self.command:
            self.command(good)

    def set(self, text):
        if text != self.var.get():
            self._busy = True
            self.var.set(text)
            self._busy = False
            self._count()

    def set_enabled(self, on):
        on = bool(on)
        if on == self.enabled:
            return
        self.enabled = on
        self.entry.configure(state="normal" if on else "disabled", takefocus=1 if on else 0)
        self._draw()


class ValueBox(Control):
    """Read-only field (the custom font path)."""

    def __init__(self, master, bg, name="", width=300):
        super().__init__(master, sc(width), sc(MIN_H["control"]), bg, name, focusable=False)
        self.text = ""
        self.placeholder = False

    def clickable(self):
        return False

    def set(self, text, placeholder=False):
        if (text, placeholder) != (self.text, self.placeholder):
            self.text, self.placeholder = text, placeholder
            self.redraw()

    def draw(self):
        w, h = self.size()
        rrect(self, 1, 1, w - 2, h - 2, sc(RADIUS["input"]), fill=BG_INPUT, outline=BORDER_INPUT)
        font = "body" if self.placeholder else "value"
        self.create_text(
            sc(12),
            h / 2,
            text=elide(font, self.text, w - sc(24), left=True),
            anchor="w",
            fill=TEXT_MUTED if self.placeholder else TEXT,
            font=FONTS[font],
        )


class Tooltip:
    """A small tooltip shown after the pointer rests on `widget` for 600 ms."""

    def __init__(self, widget, text):
        self.widget, self.text, self.tip, self.job = widget, text, None, None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<Button-1>", self._leave, add="+")

    def _enter(self, _e):
        self.job = self.widget.after(600, self._show)

    def _leave(self, _e=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None

    def _show(self):
        self.job = None
        if Popup.current is not None:
            return
        w = self.widget
        self.tip = tk.Toplevel(w)
        self.tip.overrideredirect(True)
        self.tip.configure(bg=BORDER)
        tk.Label(
            self.tip,
            text=self.text,
            bg=BG_PANEL,
            fg=TEXT,
            font=FONTS["help"],
            padx=sc(8),
            pady=sc(4),
        ).pack(padx=1, pady=1)
        self.tip.geometry(f"+{w.winfo_rootx()}+{w.winfo_rooty() + w.winfo_height() + sc(4)}")


class NavItem(Control):
    """Sidebar page: name and a one-line live summary (amber for override counts)."""

    def __init__(self, master, title, bg, command=None, name=""):
        super().__init__(master, sc(SIDEBAR_W - 24), sc(50), bg, name or title)
        self.title = title
        self.summary = ""
        self.amber = False
        self.selected = False
        self.command = command
        self.configure(cursor="hand2")
        self.bind("<Button-1>", lambda e: (self.click_focus(), self._fire()))
        self.bind("<space>", lambda e: self._fire())

    def _fire(self):
        if self.command:
            self.command()

    def set(self, summary=None, amber=None, selected=None):
        new = (
            self.summary if summary is None else summary,
            self.amber if amber is None else amber,
            self.selected if selected is None else selected,
        )
        if new != (self.summary, self.amber, self.selected):
            self.summary, self.amber, self.selected = new
            self.redraw()

    def draw(self):
        w, h = self.size()
        if self.selected:
            rrect(self, 1, 1, w - 2, h - 2, sc(RADIUS["button"]), fill=BG_PANEL, outline=BORDER)
        elif self.hover:
            rrect(self, 1, 1, w - 2, h - 2, sc(RADIUS["button"]), fill=BG_PANEL, outline="")
        x = sc(10)
        self.create_text(
            x,
            h / 2 - sc(9),
            text=self.title,
            anchor="w",
            fill=TEXT_STRONG if self.selected else TEXT,
            font=FONTS["body_semi"],
        )
        self.create_text(
            x,
            h / 2 + sc(10),
            text=elide("summary", self.summary, w - 2 * x),
            anchor="w",
            fill=OVERRIDE if self.amber else TEXT_MUTED,
            font=FONTS["summary"],
        )


class Panel(tk.Canvas):
    """Rounded bordered panel; put children in `.inner` (a tk.Frame). The canvas
    follows the inner frame's requested height and fills its own width."""

    def __init__(
        self, master, outer_bg, fill=BG_PANEL, outline=BORDER, pad=16, radius=RADIUS["panel"]
    ):
        super().__init__(master, bg=outer_bg, highlightthickness=0, bd=0, height=10, takefocus=0)
        self.fill, self.outline, self.pad, self.radius = fill, outline, sc(pad), sc(radius)
        self.inner = tk.Frame(self, bg=fill)
        self.win = self.create_window(self.pad, self.pad, anchor="nw", window=self.inner)
        self.inner.bind("<Configure>", lambda e: self._fit())
        self.bind("<Configure>", lambda e: self._fit())

    def _fit(self):
        w = max(1, self.winfo_width())
        h = self.inner.winfo_reqheight() + 2 * self.pad
        if int(self["height"]) != h:
            self.configure(height=h)
        self.itemconfigure(self.win, width=max(1, w - 2 * self.pad))
        self.delete("bg")
        rrect(
            self, 0, 0, w - 1, h - 1, self.radius, fill=self.fill, outline=self.outline, tags="bg"
        )
        self.tag_lower("bg")


def draw_icon(cv, kind, x, y, colour, s=None):
    """Small line icons: "lock", "shared" (two monitors), "unplugged"."""
    s = s or sc(14)
    lw = max(1, sc(1.4))
    if kind == "lock":
        cv.create_rectangle(x, y + s * 0.45, x + s * 0.8, y + s, outline=colour, width=lw)
        cv.create_arc(
            x + s * 0.15,
            y,
            x + s * 0.65,
            y + s * 0.8,
            start=0,
            extent=180,
            style="arc",
            outline=colour,
            width=lw,
        )
    elif kind == "shared":
        cv.create_rectangle(x, y, x + s * 0.65, y + s * 0.5, outline=colour, width=lw)
        cv.create_rectangle(
            x + s * 0.35, y + s * 0.35, x + s, y + s * 0.85, outline=colour, width=lw
        )
    elif kind == "unplugged":
        cv.create_rectangle(x, y + s * 0.3, x + s * 0.5, y + s * 0.7, outline=colour, width=lw)
        cv.create_line(x + s * 0.5, y + s * 0.4, x + s * 0.7, y + s * 0.4, fill=colour, width=lw)
        cv.create_line(x + s * 0.5, y + s * 0.6, x + s * 0.7, y + s * 0.6, fill=colour, width=lw)
        cv.create_line(x + s * 0.8, y + s * 0.1, x + s, y + s * 0.9, fill=colour, width=lw)
