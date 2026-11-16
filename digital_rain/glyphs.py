"""Glyph set and font loading shared by both renderers."""

import glob
import os
import statistics
import sys
import unicodedata

import numpy as np
import pygame

from digital_rain import osapi, resources
from digital_rain.settings import FILM_FONT_SIZE, FONT_SIZE

# The film's 57-glyph inventory, in the order of Rezmason's glyph-order.txt
# (classic line). Index i is atlas cell i. 0 appears twice, index 29 is blank.
FILM_GLYPHS = (
    "モエヤキオカ7ケサスz152ヨタワ4ネヌナ98ヒ0ホア3ウ セ¦:\"꞊ミラリ╌ツテニハソ▪—<>0|+*コシマムメ"
)
# Matrix-Code.ttf has no U+2014; its long bar is U+30FC.
FILM_FONT_SUBST = {"\u2014": "\u30fc"}
FILM_FONT_NAME = "Matrix-Code.ttf"
# tiles 0 to 134 of the Resurrections atlases (tiles 153 to 155 are unused)
RES_GLYPHS = 135
RES_ATLAS = "resurrections_msdf.png"
RES_GLINT_ATLAS = "resurrections_glint_msdf.png"
RES_GRID = (13, 12)  # columns, rows of 64 px cells; both PNGs are stored top-down
RES_CELL = 64
# a tenth of the cell is cropped on every side
RES_CROP = 6
MIN_CUSTOM_GLYPHS = 20  # a custom font drawing fewer than this is ignored

# Courier New Bold on Windows
LATIN_FONT = osapi.LATIN_FONT
JP_FONTS = osapi.CJK_FONTS


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # source checkout: the repository root (this file is in digital_rain/)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def custom_font_path(configured=""):
    """A user-supplied font: the `font_path` setting, else the first
    .ttf/.otf found in a `fonts` folder next to the program."""
    if configured and os.path.exists(configured):
        return configured
    found = sorted(glob.glob(os.path.join(_app_dir(), "fonts", "*.[to]tf")))
    return found[0] if found else ""


def load_fonts(size, custom=""):
    """(latin_font, japanese_font): Courier New Bold + a CJK fallback, or the
    custom font for everything."""
    if custom:
        font = pygame.font.Font(custom, size)
        return font, font
    if os.path.exists(LATIN_FONT):
        latin = pygame.font.Font(LATIN_FONT, size)
    else:
        latin = pygame.font.SysFont("couriernew", size, bold=True)
    jp = None
    for path in JP_FONTS:
        if os.path.exists(path):
            jp = pygame.font.Font(path, size)
            break
    if jp is None:
        jp = pygame.font.SysFont("msgothic,yugothic,meiryo", size)
    jp.set_bold(True)  # MS Gothic has no bold face; SDL synthesises it
    return latin, jp


def film_font_path():
    """Bundled Matrix-Code.ttf, or "" when it is absent."""
    path = resources.asset_path("rezmason", FILM_FONT_NAME)
    return path if os.path.exists(path) else ""


_RES_CACHE = {}


def _res_decode(path):
    """Coverage of every atlas tile of one MSDF PNG: list of 135 float arrays
    (52 x 52, 0..1), read unflipped (index 0 is the top-left cell)."""
    surf = pygame.image.load(path)
    pixels = pygame.surfarray.array3d(surf).transpose(1, 0, 2)  # (h, w, 3)
    distance = np.median(pixels, axis=2) / 255.0
    cov = np.clip((distance - 0.5) * 4.0 + 0.5, 0.0, 1.0)
    cols = RES_GRID[0]
    out = []
    for i in range(RES_GLYPHS):
        r, c = divmod(i, cols)
        y0, x0 = r * RES_CELL + RES_CROP, c * RES_CELL + RES_CROP
        inner = RES_CELL - 2 * RES_CROP
        out.append(cov[y0 : y0 + inner, x0 : x0 + inner])
    return out


def _res_scale(tile, size):
    """float 0..1 tile -> uint8 array of `size` (w, h), bilinear."""
    g = (np.clip(tile, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    surf = pygame.surfarray.make_surface(np.repeat(g.T[:, :, None], 3, axis=2))
    surf = pygame.transform.smoothscale(surf, size)
    return pygame.surfarray.array3d(surf)[:, :, 0].T.copy()


def resurrection_set(square=False):
    """(coverage, glint), two lists of 135 uint8 arrays decoded from the
    Rezmason Resurrections MSDF atlases (assets/rezmason), cached after the
    first call. Arrays are 112 x 80 (rows x cols; the GPU tile's inner size),
    or 112 x 112 with `square`. None when a PNG is missing or unreadable."""
    folder = resources.asset_path("rezmason")
    if "tiles" not in _RES_CACHE:
        try:
            _RES_CACHE["tiles"] = (
                _res_decode(os.path.join(folder, RES_ATLAS)),
                _res_decode(os.path.join(folder, RES_GLINT_ATLAS)),
            )
        except (OSError, ValueError, pygame.error) as exc:
            print(f"resurrections atlas unavailable ({exc}); using the classic glyph set")
            _RES_CACHE["tiles"] = None
    tiles = _RES_CACHE["tiles"]
    if tiles is None:
        return None
    key = "square" if square else "gpu"
    if key not in _RES_CACHE:
        # The 80 px wide GPU tile is cut from the 112 px square one; scaling straight from
        # the 52 px coverage would change the tiles slightly.
        if "square" not in _RES_CACHE:
            _RES_CACHE["square"] = tuple(
                [_res_scale(tile, (112, 112)) for tile in kind] for kind in tiles
            )
        if not square:
            _RES_CACHE["gpu"] = tuple(
                [_res_scale(tile.astype(float) / 255.0, (80, 112)) for tile in kind]
                for kind in _RES_CACHE["square"]
            )
    return _RES_CACHE[key]


def resurrection_cells(cw, ch):
    """Software tiles: 135 white-on-black (cw, ch) surfaces from the 52 px
    cropped coverage (the cell is square)."""
    tiles = resurrection_set(square=True)
    if tiles is None:
        return None
    out = []
    for t in tiles[0]:
        g = _res_scale(t.astype(float) / 255.0, (cw, ch))
        out.append(pygame.surfarray.make_surface(np.repeat(g.T[:, :, None], 3, axis=2)))
    return out


def _is_katakana(c):
    return "\u30a0" <= c <= "\u30ff"


def _halfwidth(c):
    for cp in range(0xFF66, 0xFF9E):
        if unicodedata.normalize("NFKC", chr(cp)) == c:
            return chr(cp)
    return c


def _flips(c):
    """Film mirroring for a normal (unmirrored) face: (flip_x, flip_y)."""
    return (_is_katakana(c) or c in "259", c == "3")


def _missing(font, ch):
    m = font.metrics(ch)
    if not m or m[0] is None:
        return True
    return m[0][0] == m[0][1] and ch != " "


def _build(chars_fonts):
    out = []
    for ch, font, fx, fy in chars_fonts:
        if not _missing(font, ch):
            out.append((ch, font, fx, fy))
    return out


def _film_entries(path, size):
    font = pygame.font.Font(path, size)
    ents = [(FILM_FONT_SUBST.get(c, c), font, False, False) for c in FILM_GLYPHS]
    return _build(ents)


def _normal_entries(latin, jp, custom):
    ents = []
    for c in FILM_GLYPHS:
        fx, fy = _flips(c)
        if c == "\ua78a":
            ch, f = "=", latin
        elif _is_katakana(c):
            ch, f = _halfwidth(c), jp
        elif c in "\u00a6\u254c\u25aa\u2014":
            ch, f = c, jp
        else:
            ch, f = c, latin
        ents.append((ch, f, fx, fy))
    return _build(ents)


def glyph_set(scale, custom="", film_font=None, set_name="classic", cell=None):
    """([(char, font, flip_x, flip_y)], source) for the film glyph selection.

    source is "film", "fallback" or "custom". `film_font` None means the
    bundled file, "" forces the fallback fonts, anything else is a path.
    `set_name` "resurrections" with a `cell` (w, h) returns the 135 tiles of
    the Resurrections atlas as ready-to-blit surfaces and source "resurrections";
    when the PNGs are missing it falls through to the classic set.
    """
    if set_name == "resurrections" and cell is not None:
        tiles = resurrection_cells(*cell)
        if tiles is not None:
            return tiles, "resurrections"
    if film_font is None:
        film_font = film_font_path()
    fsize = max(6, round(FONT_SIZE * scale))
    if custom and os.path.basename(custom).lower() == FILM_FONT_NAME.lower():
        film_font, custom = custom, ""
    if custom:
        try:
            f = pygame.font.Font(custom, fsize)
            ents = _normal_entries(f, f, True)
            if len(ents) >= MIN_CUSTOM_GLYPHS:
                return ents, "custom"
        except OSError, pygame.error:
            pass
    if film_font:
        try:
            ents = _film_entries(film_font, max(6, round(FILM_FONT_SIZE * scale)))
            if ents:
                return ents, "film"
        except OSError, pygame.error:
            pass
    latin, jp = load_fonts(fsize)
    return _normal_entries(latin, jp, False), "fallback"


def _raw_glyph(char, font, flip_x, flip_y):
    raw = font.render(char, True, (255, 255, 255))
    if flip_x or flip_y:
        raw = pygame.transform.flip(raw, flip_x, flip_y)
    return raw


def ink_stretch(pairs, iw, ih, fill):
    """One (sx, sy) scale for a whole glyph set so the median ink fills
    `fill` = (fx, fy) of the iw x ih tile, with the tallest and widest glyph
    clipping the scale. Glyphs with empty ink are skipped. Returns (1.0, 1.0)
    when no glyph has ink."""
    sizes = []
    for g, font, fx, fy in pairs:
        r = _raw_glyph(g, font, fx, fy).get_bounding_rect()
        if r.w > 0 and r.h > 0:
            sizes.append((r.w, r.h))
    if not sizes:
        return 1.0, 1.0
    mw = statistics.median(w for w, _ in sizes)
    mh = statistics.median(h for _, h in sizes)
    xw = max(w for w, _ in sizes)
    xh = max(h for _, h in sizes)
    return (min(fill[0] * iw / mw, iw / xw), min(fill[1] * ih / mh, ih / xh))


def render_glyph(char, font, flip_x, flip_y, w, h, stretch=None):
    """White-on-black w x h surface with the glyph centred, flipped as asked
    and scaled down if its ink would not fit the cell. With `stretch` (sx, sy)
    the ink is cropped, smoothscaled by (sx, sy) and centred instead."""
    raw = _raw_glyph(char, font, flip_x, flip_y)
    ink = raw.get_bounding_rect()
    if stretch is not None:
        cell = pygame.Surface((w, h))
        if ink.w > 0 and ink.h > 0:
            crop = raw.subsurface(ink).copy()
            crop = pygame.transform.smoothscale(
                crop, (max(1, round(ink.w * stretch[0])), max(1, round(ink.h * stretch[1])))
            )
            cell.blit(crop, crop.get_rect(center=(w // 2, h // 2)))
        return cell
    if ink.w > w or ink.h > h:
        k = min(w / ink.w, h / ink.h)
        raw = pygame.transform.smoothscale(
            raw, (max(1, round(raw.get_width() * k)), max(1, round(raw.get_height() * k)))
        )
    cell = pygame.Surface((w, h))
    cell.blit(raw, raw.get_rect(center=(w // 2, h // 2)))
    return cell


_FONT_FILES = None


def _norm(name):
    return "".join(ch for ch in name.lower() if ch.isalnum())


def font_file(family, bold=False, italic=False):
    """(path, styled) of the installed font for the picker's family, or None.

    Looks for the family with the style ("Segoe UI Bold Italic"), then without it;
    styled is False when only the plain face was found (bold and italic are then
    synthesised). A family the fonts registry lacks, such as an instance of a variable
    font ("Bahnschrift Light Condensed"), drops its last words until one matches."""
    global _FONT_FILES
    if _FONT_FILES is None:
        try:
            _FONT_FILES = {_norm(k): v for k, v in osapi.font_files().items()}
        except Exception:
            _FONT_FILES = {}
    suffix = " ".join(w for w, on in (("Bold", bold), ("Italic", italic)) if on)
    words = family.split()
    while words:
        base = " ".join(words)
        tries = ((base + " " + suffix, True), (base, False)) if suffix else ((base, True),)
        for name, styled in tries:
            path = _FONT_FILES.get(_norm(name))
            if path and os.path.exists(path):
                return path, styled
        words.pop()
    return None


def text_font(size, family="", bold=True, italic=False):
    """The message font at `size` px, for the rain message, the clock and the typed
    on-screen messages: the family chosen in the OS font picker, else (empty or not
    installed) Courier New."""
    found = font_file(family, bold, italic) if family else None
    if found:
        font = pygame.font.Font(found[0], size)
        if not found[1]:
            font.bold, font.italic = bold, italic  # synthesised
        return font
    if bold and not italic and os.path.exists(LATIN_FONT):
        return pygame.font.Font(LATIN_FONT, size)
    return pygame.font.SysFont("couriernew,courier", size, bold=bold, italic=italic)
