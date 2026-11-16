"""Rain message: the time or a custom text formed by the rain itself.

The letters are made of ordinary rain glyph cells (no font drawn over the rain).
A front steps one whole cell at a time along the rain's lanes, led by a near-white
leader cell, and a second invisible front removes the cells again, like the
film's invisible deletion strings. Shared by both renderers; no GL code here.
"""

import time

import numpy as np

from digital_rain import glyphs, looks
from digital_rain.settings import CELL_H, CELL_W, MESSAGE_FONT_REF_PT

CELLS_PER_SEC = 30.0  # top of the film's fall speed range
REVEAL_AT = 0.5  # first reveal, seconds into the session
HIDE_AFTER = 8.0  # deletion front starts this long after the reveal
SHOW_FOR = 16.0  # cycle end, after the reveal
CYCLE = 36.0  # 20 s of plain rain between cycles
MAX_COL_MARGIN = 4  # mask must leave 2 columns free on each side
ALPHA_CUT = 0.35
# always-up clock, minute change: seconds the changed cells may flicker before their head lands
CLOCK_GLITCH = 1.6
# change codes of an always-up clock cell (0: not a letter cell)
STABLE, APPEAR, VANISH = 3, 2, 1


def display_text(s):
    """Upper-case, Latin only (the message font covers nothing else)."""
    out = []
    for ch in str(s).upper():
        o = ord(ch)
        if 0x20 <= o <= 0x7E or 0xA0 <= o <= 0x24F:
            out.append(ch)
    return "".join(out)


def clock_text(clock_24h):
    tm = time.localtime()
    if clock_24h:
        return time.strftime("%H:%M", tm)
    h = tm.tm_hour % 12 or 12
    return f"{h}:{tm.tm_min:02d}"


def text_style(cfg):
    """(size, font family, bold, italic) of the message settings in cfg."""
    return (
        float(cfg.get("message_font_size", MESSAGE_FONT_REF_PT)) / MESSAGE_FONT_REF_PT,
        cfg.get("message_font", ""),
        bool(cfg.get("message_bold", True)),
        bool(cfg.get("message_italic", False)),
    )


def _font(px, style):
    _size, family, bold, italic = style or (1.0, "", True, False)
    return glyphs.text_font(px, family, bold, italic)


def _block(font, lines):
    """Render the lines (stacked, each centred) and return (surface, ink rect)."""
    import pygame

    ls = font.get_linesize()
    widths = [font.size(line)[0] for line in lines]
    surf = pygame.Surface((max(widths) + 8, ls * len(lines) + 8), pygame.SRCALPHA)
    for i, line in enumerate(lines):
        img = font.render(line, True, (255, 255, 255))
        surf.blit(img, ((surf.get_width() - img.get_width()) // 2, 4 + i * ls))
    ink = surf.get_bounding_rect()
    if ink.w <= 0 or ink.h <= 0:
        return surf, None
    cap = font.render("H", True, (255, 255, 255)).get_bounding_rect()
    if cap.w > 0 and cap.h > 0:
        top = 4 + cap.top
        bottom = 4 + (len(lines) - 1) * ls + cap.bottom
        y0, y1 = min(ink.top, top), max(ink.bottom, bottom)
        ink = pygame.Rect(ink.left, y0, ink.w, y1 - y0)
    return surf, ink


def _try_rows(lines, nrows, cols, style=None):
    """Mask for the lines at `nrows` rows, or None; returns (mask, msg_cols)."""
    import pygame

    size = 8 * nrows if len(lines) == 1 else 4 * nrows
    font = _font(size, style)
    surf, ink = _block(font, lines)
    if ink is None or ink.w <= 0 or ink.h <= 0:
        return None
    msg_cols = round(ink.w / ink.h * nrows * CELL_H / CELL_W)
    if msg_cols < 1:
        return None
    block = surf.subsurface(ink).copy()
    small = pygame.transform.smoothscale(block, (msg_cols, nrows))
    alpha = pygame.surfarray.array_alpha(small).T
    top = alpha.max()
    if top <= 0:
        return None
    mask = alpha >= ALPHA_CUT * top
    if not mask.any():
        return None
    return mask, msg_cols


def anchor_of(position):
    """'top_right' -> (2, 0): (column, row) of the segment in the 3 x 3 grid."""
    from digital_rain.settings import CLOCK_POSITIONS

    i = CLOCK_POSITIONS.index(position) if position in CLOCK_POSITIONS else 2
    return i % 3, i // 3


def message_mask(text, cols, rows, anchor=None, style=None):
    """-> (mask (R, msg_cols) bool, col0, row0) or None when it does not fit.

    anchor (ax, ay), each 0..2, puts a single-line message in that segment of the
    3 x 3 screen grid instead of the centre of the whole screen. style is
    text_style(cfg): its size scales the preferred letter height in rows."""
    import pygame

    text = display_text(text)
    if not text.strip():
        return None
    try:
        if not pygame.font.get_init():
            pygame.font.init()
        text = text.strip()
        scale = style[0] if style else 1.0
        if anchor is not None:
            seg_w, seg_h = cols // 3, rows // 3
            # larger than 1 may grow past its segment's height and width
            room = min(int((seg_h - 2) * max(1.0, scale)), rows - 4)
            top = min(room, max(4, round(13 * scale)))
            # may run a little past its third
            limit = min(cols - MAX_COL_MARGIN, int(seg_w * 1.3 * max(1.0, scale)))
            for nrows in range(top, 3, -1):
                got = _try_rows([text], nrows, cols, style)
                if got is None:
                    return None
                if got[1] <= limit:
                    w = got[1]
                    ax, ay = anchor
                    c0 = 2 if ax == 0 else (cols - w - 2 if ax == 2 else (cols - w) // 2)
                    r0 = 2 if ay == 0 else (rows - nrows - 2 if ay == 2 else (rows - nrows) // 2)
                    return got[0], max(0, c0), max(0, r0)
            return None
        fit = cols - MAX_COL_MARGIN
        start = min(min(max(round(rows * 0.25 * scale), 7), max(7, round(13 * scale))), rows - 4)
        if start >= 7:
            for nrows in range(start, 6, -1):
                got = _try_rows([text], nrows, cols, style)
                if got is None:
                    return None
                if got[1] <= fit:
                    return got[0], (cols - got[1]) // 2, (rows - nrows) // 2
        if " " in text:
            start = min(
                min(max(round(rows * 0.5 * scale), 15), max(15, round(27 * scale))), rows - 4
            )
            if start >= 15:
                for nrows in range(start, 14, -1):
                    lines = _split(text, nrows, style)
                    if lines is None:
                        return None
                    got = _try_rows(lines, nrows, cols, style)
                    if got is None:
                        return None
                    if got[1] <= fit:
                        return got[0], (cols - got[1]) // 2, (rows - nrows) // 2
    except pygame.error:
        return None
    return None


def _split(text, nrows, style=None):
    """Split at the space that gives the smallest wider line; None if no split."""
    font = _font(4 * nrows, style)
    best = None
    for i, ch in enumerate(text):
        if ch != " ":
            continue
        a, b = text[:i].strip(), text[i + 1 :].strip()
        if not a or not b:
            continue
        wide = max(font.size(a)[0], font.size(b)[0])
        if best is None or wide < best[0]:
            best = (wide, [a, b])
    return best[1] if best else None


FINE_MIN_SCALE = 0.25  # the finest message cell, as a share of the main rain cell
FINE_MIN_CELL = 3  # px, the smallest message cell


def fine_grid(cols, rows, scale, px=None):
    """The message's own glyph grid: (c, fine cols, fine rows).

    From 36 pt up (scale 1 or more) the message uses the main rain grid, c is 1. Below it
    the message gets a finer grid whose cell is the main cell scaled by c = max(scale, 0.25)
    on both axes, so the letters keep their row count and shrink on screen. px is optional
    (width, height, main cell width, main cell height) in the renderer's pixels: the grid
    is then counted from the rounded pixel cell, as the renderer draws it."""
    if scale >= 1.0:
        return 1.0, cols, rows
    c = max(scale, FINE_MIN_SCALE)
    if px is not None:
        w, h, cw, ch = px
        fw = max(FINE_MIN_CELL, int(np.floor(cw * c + 0.5)))
        fh = max(FINE_MIN_CELL, int(np.floor(ch * c + 0.5)))
        return c, int(w // fw), int(h // fh)
    return c, int(cols / c), int(rows / c)


def fine_cell(cell, c):
    """Pixel size of a message cell of the main cell (cw, ch) at scale c."""
    return tuple(max(FINE_MIN_CELL, int(np.floor(v * c + 0.5))) for v in cell)


def message_layout(text, cols, rows, anchor, style, px=None):
    """-> (c, (mask, col0, row0) or None): the message on the grid it is drawn on.

    c is 1 for the main grid, below 1 for the fine grid of fine_grid; the mask then counts
    fine cells and is laid out with the 36 pt letter heights."""
    c, fcols, frows = fine_grid(cols, rows, style[0] if style else 1.0, px)
    if c < 1.0:
        style = (1.0,) + tuple(style[1:])
        cols, rows = fcols, frows
    return c, message_mask(text, cols, rows, anchor, style)


def main_grid(w, h, dpi, glyph_scale, cell_scale, k, gpu, columns=0):
    """The main layer's grid in that renderer's pixels:
    (cols, rows, cell_w, cell_h, pad_x). `columns` above 0 makes the cell
    square from the monitor width, as looks.cell_px does."""
    if columns > 0:
        k_ = k if gpu else 1.0
        cw = ch = looks.cell_px(dict(columns=columns), w * k_, 1.0, glyph_scale, 1.0)[0]
        cols = int(np.floor(w * k_ / cw))
        rows = int(np.floor(h * k_ / ch))
        pad_x = int(np.floor((w * k_ - cols * cw) / 2))
        return cols, rows, cw, ch, pad_x
    if gpu:
        sc = dpi * k * glyph_scale * cell_scale
        cw = int(np.floor(CELL_W * sc + 0.5))
        ch = int(np.floor(CELL_H * sc + 0.5))
        cols = int(np.floor(w * k / cw))
        rows = int(np.floor(h * k / ch))
        pad_x = int(np.floor((w * k - cols * cw) / 2))
    else:
        scale = dpi * glyph_scale * cell_scale
        cw = max(4, round(CELL_W * scale))
        ch = max(6, round(CELL_H * scale))
        cols, rows = w // cw, h // ch
        pad_x = (w - cols * cw) // 2
    return cols, rows, cw, ch, pad_x


def cell_states(
    mask, col0, row0, lane, along, j1, j2, t, reveal_start, hide_start, direction="down"
):
    """int8 (rows, cols): 0 none, 1 lit, 2 leader, for the whole grid.

    lane / along are the rain's per-cell lane and position-along-lane arrays and
    j1 / j2 the per-lane jitters (0..1). The reveal front moves 30 cells a second
    and steps one whole cell at a time; the deletion front has no leader."""
    rows, cols = along.shape
    out = np.zeros((rows, cols), np.int8)
    mr, mc = mask.shape
    r1, c1 = min(rows, row0 + mr), min(cols, col0 + mc)
    r0, c0 = max(row0, 0), max(col0, 0)
    if r1 <= r0 or c1 <= c0:
        return out
    inside = np.zeros((rows, cols), bool)
    inside[r0:r1, c0:c1] = mask[r0 - row0 : r1 - row0, c0 - col0 : c1 - col0]
    a0 = col0 if direction == "sideways" else row0
    lane_i = np.asarray(lane)
    j1c, j2c = np.asarray(j1)[lane_i], np.asarray(j2)[lane_i]
    fr = np.floor(a0 - 4.0 * j1c + (t - reveal_start - 0.6 * j2c) * CELLS_PER_SEC)
    de = np.floor(a0 - 4.0 * j1c + (t - hide_start - 0.6 * j2c) * CELLS_PER_SEC)
    lit = inside & (fr >= along) & (de < along)
    out[lit] = 1
    out[lit & (fr == along)] = 2
    return out


def fine_states(codes, col0, row0, lane, along, j1, j2, t, reveal, hide, direction, changed):
    """cell_states for the message's own fine grid, which has no heads to latch on.

    codes: change codes of change_codes (or a bool mask). changed False: the plain reveal and
    deletion fronts. changed True (always-up clock, minute change): cells that stay are lit,
    cells that appear light when the front reaches them, cells that vanish go out as it passes."""
    if codes.dtype == bool:
        codes = codes.astype(np.uint8) * STABLE
    if not changed:
        return cell_states(codes > 0, col0, row0, lane, along, j1, j2, t, reveal, hide, direction)
    never = 1.0e9
    came = cell_states(
        codes >= APPEAR, col0, row0, lane, along, j1, j2, t, reveal, never, direction
    )
    gone = cell_states(
        codes == VANISH, col0, row0, lane, along, j1, j2, t, reveal, never, direction
    )
    out = came.copy()
    out[(gone == 0) & _placed(codes == VANISH, col0, row0, came.shape)] = 1
    out[_placed(codes == STABLE, col0, row0, came.shape)] = 1
    return out


def _placed(mask, col0, row0, shape):
    """The mask laid on a grid of `shape` at (col0, row0), clipped."""
    out = np.zeros(shape, bool)
    r0, c0 = max(row0, 0), max(col0, 0)
    r1, c1 = min(shape[0], row0 + mask.shape[0]), min(shape[1], col0 + mask.shape[1])
    if r1 > r0 and c1 > c0:
        out[r0:r1, c0:c1] = mask[r0 - row0 : r1 - row0, c0 - col0 : c1 - col0]
    return out


def change_codes(old, new):
    """Always-up clock, minute change: merge the old and the new mask into one code grid.
    old, new: (mask, col0, row0) or None. -> (codes uint8, col0, row0) or None, with
    STABLE where both have ink (stays latched), APPEAR where only the new one has
    (latches on the first head of its lane after the change), VANISH where only the old
    one has (stays lit until that head passes). Shared by both renderers."""
    if new is None:
        return None
    if old is None:
        mask, c0, r0 = new
        return mask.astype(np.uint8) * STABLE, c0, r0
    (om, oc, orw), (nm, nc, nr) = old, new
    c0, r0 = min(oc, nc), min(orw, nr)
    c1 = max(oc + om.shape[1], nc + nm.shape[1])
    r1 = max(orw + om.shape[0], nr + nm.shape[0])
    a = np.zeros((r1 - r0, c1 - c0), bool)
    b = np.zeros_like(a)
    a[orw - r0 : orw - r0 + om.shape[0], oc - c0 : oc - c0 + om.shape[1]] = om
    b[nr - r0 : nr - r0 + nm.shape[0], nc - c0 : nc - c0 + nm.shape[1]] = nm
    codes = np.zeros(a.shape, np.uint8)
    codes[a & b] = STABLE
    codes[b & ~a] = APPEAR
    codes[a & ~b] = VANISH
    return codes, c0, r0


class MessageSchedule:
    def __init__(self, cfg):
        self.cfg = cfg
        self._texts = {}

    def _text(self, n):
        if n not in self._texts:
            mode = self.cfg["message"]
            if mode == "both":
                mode = "clock" if n % 2 == 0 else "text"
            if mode == "clock":
                txt = clock_text(self.cfg["clock_24h"])
            else:
                txt = display_text(self.cfg["message_text"])
            self._texts = {n: txt}  # keep only the current cycle
        return self._texts[n]

    def _fixed_state(self, t):
        """clock_fixed: the clock is always up. A new minute reveals again."""
        if t < REVEAL_AT:
            return None
        txt = clock_text(self.cfg["clock_24h"])
        cur = getattr(self, "_fixed", None)
        if cur is None or cur[0] != txt:
            self._fixed = cur = (txt, t, (cur[2] + 1) if cur else 0)
        return txt, cur[1], 1.0e6, cur[2]

    def state(self, t):
        """None, or (text, reveal_start, hide_start, n)."""
        if self.cfg["message"] == "clock_fixed":
            return self._fixed_state(t)
        if self.cfg["message"] == "off" or t < REVEAL_AT:
            return None
        n = int((t - REVEAL_AT) // CYCLE)
        start = REVEAL_AT + CYCLE * n
        if t >= start + SHOW_FOR:
            return None
        return self._text(n), start, start + HIDE_AFTER, n


class MessageLatch:
    """Rain-clock times for head-latched message letters, shared by both renderers.

    A letter cell lights when the first rain head of its lane lands on it after the reveal and
    stays lit until the first head after the deletion. Those times are on the rain clock, which
    the live speed control warps, so they are converted once per message and the deletion is
    frozen once passed (latched cells never shift with the live speed)."""

    # A hide time at or beyond this is "never deleted" (the always-up clock uses 1e6).
    NEVER_HIDE_AFTER = 1.0e5

    def __init__(self):
        self.key = None  # (cycle, text) of the message being shown
        # always-up clock: the text before the last minute change
        self.previous_text = None
        self.reveal_clock = 0.0  # rain-clock time of the reveal
        self.hide_clock = 0.0  # rain-clock time of the deletion (-1: never)
        # always-up clock: rain-clock time of the last change (-1: none)
        self.change_clock = -1.0
        self._clock_key = None

    def note_message(self, cycle, text, fixed):
        """Record the message shown this frame; True when it is a new one. For the always-up
        clock after its first minute, previous_text is what it showed before."""
        if self.key == (cycle, text):
            return False
        self.previous_text = self.key[1] if (fixed and self.key is not None and cycle > 0) else None
        self.key = (cycle, text)
        return True

    def update_clocks(self, cycle, text, reveal, hide, t, rain_offset):
        """Convert the reveal and deletion times to the rain clock (once per message)."""
        new_message = self._clock_key != (cycle, text)
        restart = new_message and self.previous_text is None
        if new_message:
            self._clock_key = (cycle, text)
            if self.previous_text is not None:
                # always-up clock: the clock stays, only the changed cells move
                self.change_clock = float(reveal + rain_offset)
            else:
                self.reveal_clock = float(reveal + rain_offset)
                self.change_clock = -1.0
        if restart or t < hide:
            never = hide >= self.NEVER_HIDE_AFTER
            self.hide_clock = -1.0 if never else float(hide + rain_offset)
