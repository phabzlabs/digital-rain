"""Software (CPU) renderer, used when OpenGL is unavailable (e.g. Remote Desktop or some VMs).

Film presets get the same rain model, directions, pulse, 24 fps stepping, lane share, tooth
gamma, glyph crossfade and defocus as the GPU path. The differences from it (no flicker,
film grain, bloom pyramid, lead_core or glint; one reduced-resolution bloom; palette applied
per glyph level) are listed in design/film-reference.md.
"""

import numpy as np
import pygame

from digital_rain import glyphs, live_load, looks, rain_message
from digital_rain.easter_egg import EasterEgg
from digital_rain.settings import (
    CELL_H,
    CELL_W,
    TRAIL_LEN_ROWS,
    active_layers,
    main_layer_index,
    monitor_cfg,
)

LEVELS = 20  # brightness steps pre-rendered per glyph
BLOOM_Q = 4  # bloom is composed at 1/Q resolution
FLICKER_PER_SEC = 0.35


def trail_brightness(dist, length, falloff):
    """Brightness 0..1 of a cell `dist` rows behind the column head."""
    t = np.clip(1.0 - dist / length, 0.0, 1.0)
    return np.where(dist < 0, 0.0, t**falloff)


def build_atlas(layer, look, custom, cellsize=None):
    """atlas[level * n + glyph] -> opaque surface (additive-blended).

    Levels 0..LEVELS-1 are the brightness ramp, level LEVELS is the head.
    `cellsize` (looks.cell_px) fixes the square cell of a `columns` look.
    """
    scale, dim, soft = layer["scale"], layer["dim"], layer["soft"]
    if cellsize is not None:
        cw, ch = cellsize
    else:
        cw, ch = max(4, round(CELL_W * scale)), max(6, round(CELL_H * scale))
    if look["glyph_set"] != "classic":
        pairs, source = glyphs.glyph_set(scale, custom, None, look["glyph_set"], (cw, ch))
    else:
        pairs, source = glyphs.glyph_set(scale, custom)
    # the tiles are surfaces already
    ready = pairs if source == "resurrections" else None

    stretch = None
    if ready is None and look.get("ink_fill") is not None:
        stretch = glyphs.ink_stretch(pairs, cw, ch, look["ink_fill"])
    masters = []
    for gi, item in enumerate(pairs):
        cell = (
            ready[gi].copy() if ready is not None else glyphs.render_glyph(*item, cw, ch, stretch)
        )
        # Glow: blurred copy (down-up scale) added under the sharp glyph.
        small = pygame.transform.smoothscale(cell, (max(1, cw // 3), max(1, ch // 3)))
        halo = pygame.transform.smoothscale(small, (cw, ch))
        halo.fill((HALO_LEVEL,) * 3, special_flags=pygame.BLEND_MULT)
        cell.blit(halo, (0, 0), special_flags=pygame.BLEND_ADD)
        if soft > 0:  # defocus: crossfade the sharp glyph with a blurred one
            blur = pygame.transform.smoothscale(
                pygame.transform.smoothscale(cell, (max(1, cw // 4), max(1, ch // 4))), (cw, ch)
            )
            k = int(255 * soft)
            blur.fill((k, k, k), special_flags=pygame.BLEND_MULT)
            cell.fill((255 - k,) * 3, special_flags=pygame.BLEND_MULT)
            cell.blit(blur, (0, 0), special_flags=pygame.BLEND_ADD)
        d = look["defocus"] * cw if look["film"] and look["defocus"] > 0 else 0.0
        if d >= 1.0:  # film defocus: a down-up blur of about d px
            cell = pygame.transform.smoothscale(
                pygame.transform.smoothscale(cell, (max(1, round(cw / d)), max(1, round(ch / d)))),
                (cw, ch),
            )
        masters.append(cell.convert())

    def tinted(color):
        out = []
        for m in masters:
            s = m.copy()
            s.fill(color, special_flags=pygame.BLEND_MULT)
            out.append(s)
        return out

    atlas = []
    if look["film"]:
        tints = []
        for lv in range(LEVELS):
            rgb = looks.palette_rgb(look["palette"], (lv + 0.5) / LEVELS) * 255 * dim
            tints.append(tuple(int(c) for c in np.clip(rgb, 0, 255)))
        head = np.clip(np.array(look["cursor"]) * 255, 0, 255) * dim
        tints.append(tuple(int(c) for c in head))
        for tint in tints:
            atlas += tinted(tint)
        if look["crossfade"]:
            # Half-intensity copy of every level (crossfade frames): the half
            # copy of atlas index i is at i + (LEVELS + 1) * n.
            for tint in tints:
                atlas += tinted(tuple(int(c / 2) for c in tint))
        return atlas, len(pairs), (cw, ch), source
    base, head = look["base"], look["head"]
    for lv in range(LEVELS):
        k = ((lv + 1) / LEVELS) ** 1.2 * dim
        atlas += tinted(tuple(int(c * k) for c in base))
    atlas += tinted(tuple(int(c * dim) for c in head))
    return atlas, len(pairs), (cw, ch), source


def build_masks(size, mons, origin, params):
    """BLEND_MULT masks: scanlines (one per interlace field) with the
    per-monitor vignette baked in. params[i] = (scan, interlace, vig) for
    monitor i. None when no monitor has scanlines or a vignette."""
    if all(scan <= 0 and vig <= 0 for scan, _il, vig in params):
        return None
    vw, vh = size
    vign = np.ones((vw, vh), np.float32)
    for m, (_scan, _il, vig) in zip(mons, params, strict=True):
        xs = (np.arange(m["w"]) / m["w"] - 0.5) * 2
        ys = (np.arange(m["h"]) / m["h"] - 0.5) * 2
        d = np.sqrt(xs[:, None] ** 2 + ys[None, :] ** 2)
        x = np.clip((d - 0.35) / (1.45 - 0.35), 0, 1)
        v = 1.0 - vig * (x * x * (3 - 2 * x))
        x0, y0 = m["x"] - origin[0], m["y"] - origin[1]
        vign[x0 : x0 + m["w"], y0 : y0 + m["h"]] = v
    rows = np.arange(vh)
    masks = []
    for field in (0, 1) if any(il for _s, il, _v in params) else (0,):
        arr_line = np.ones((vw, vh), np.float32)
        for m, (scan, il, _vig) in zip(mons, params, strict=True):
            x0, y0 = m["x"] - origin[0], m["y"] - origin[1]
            off = field if il else 0
            ln = np.where((rows[y0 : y0 + m["h"]] + off) % 2 == 0, 1.0 - scan, 1.0)
            arr_line[x0 : x0 + m["w"], y0 : y0 + m["h"]] = ln[None, :]
        arr = (vign * arr_line * 255).astype(np.uint8)
        surf = pygame.Surface((vw, vh))
        pygame.surfarray.blit_array(surf, np.repeat(arr[:, :, None], 3, axis=2))
        masks.append(surf.convert())
    return masks


# Salt multiplier for hashes that also take a tooth index or glyph slot.
TOOTH_SALT_STRIDE = 1000003
# Hash salts: one per independent random value drawn from the same lane or cell.
SALT_LANE_SPEED = 1
SALT_LANE_OFFSET = 4
SALT_LANE_LIT = 7
SALT_CELL_PHASE = 300
SALT_CELL_SEQUENCE = 700
SALT_GLYPH = 400
SALT_HIGHLIGHT = 500
SALT_CHANGING = 600
SALT_DENSITY = 800
SALT_CHURN = 900
SALT_GLITCH = 950
SALT_GLITCH_LEVEL = 951
# Lit lanes are drawn at this multiple of the density when churn is on.
CHURN_SUPERSET = 3.0
# Live density fades a string out over this much of the density control.
DENSITY_FADE = 0.1
# A string needs at least this share of full density to keep its bright leader.
LEADER_KEEP = 0.5
# Cells of a trail fainter than this are not drawn (custom model).
TRAIL_VISIBLE = 0.03
# The glitch flicker of a changing clock cell re-rolls this many times per second.
GLITCH_RATE = 14.0
# Share of glitching cells lit, for cells that vanish and for cells that appear.
GLITCH_LIT_VANISH = 0.75
GLITCH_LIT_APPEAR = 0.45
# A glitching clock cell is dimmed to this share of the held level: minimum plus a random span.
GLITCH_LEVEL_MIN = 0.3
GLITCH_LEVEL_SPAN = 0.55
# The glow of a glyph is its blurred copy at this grey level (of 255).
HALO_LEVEL = 110
# Weights of the tiny-grid blur behind the glow.
GLOW_CENTRE = 0.4
GLOW_NEAR = 0.3
GLOW_FAR = 0.25


def tooth_phase(clock, offset, speed, along, tooth, shift=0.0):
    """Wobbling position along the sawtooth of cells (arrays), in teeth. `shift` moves it
    back by that many rows."""
    return looks.wobble(((clock + offset) * speed - along - shift) / tooth)


def cell_ids(rows, cols, grid_cols):
    return (rows * grid_cols + cols).astype(np.int64)


def build_dot_masks(size, mons, origin, lks):
    """Ink dots (look key ink_dots): (mult, floor) surfaces, or None when no monitor has them.
    The frame is multiplied by the mask (BLEND_MULT) and then max-ed with the palette floor
    (BLEND_MAX), which keeps the background exact; ink becomes max(c * m, floor), within
    floor * strength (under 1 level) of the GPU form. No near-white sparing (the soft path has
    no lead_core). The pitch scales with each monitor's dpi; rows count from the bottom, as
    in GL."""
    if not any(lk.get("ink_dots") and lk["ink_dots"][1] > 0 for lk in lks):
        return None
    vw, vh = size
    mult = np.full((vw, vh), 255, np.uint8)
    floor = np.zeros((vw, vh, 3), np.uint8)
    for mon, lk in zip(mons, lks, strict=True):
        dots = lk.get("ink_dots")
        if not dots or dots[1] <= 0:
            continue
        pitch = float(dots[0]) * float(mon["dpi"])
        strength, x_share = float(dots[1]), float(dots[2])
        x0, y0 = mon["x"] - origin[0], mon["y"] - origin[1]
        xx = np.arange(x0, x0 + mon["w"]) + 0.5
        yy = np.arange(vh - (y0 + mon["h"]), vh - y0)[::-1] + 0.5
        across = 0.5 + 0.5 * np.cos(2 * np.pi * xx / pitch)
        down = 0.5 + 0.5 * np.cos(2 * np.pi * yy / pitch)
        shade = 1.0 - strength * down[None, :] * (1.0 - x_share + x_share * across[:, None])
        mult[x0 : x0 + mon["w"], y0 : y0 + mon["h"]] = np.round(shade * 255).astype(np.uint8)
        if lk["film"]:
            colour = [int(c) for c in looks.palette_rgb(lk["palette"], 0.0) * 255]
        else:
            colour = [0, 0, 0]
        floor[x0 : x0 + mon["w"], y0 : y0 + mon["h"]] = colour
    mult_surface = pygame.Surface((vw, vh))
    pygame.surfarray.blit_array(mult_surface, np.repeat(mult[:, :, None], 3, axis=2))
    floor_surface = pygame.Surface((vw, vh))
    pygame.surfarray.blit_array(floor_surface, floor)
    return mult_surface.convert(), floor_surface.convert()


class Rain:
    """Independent rain field for one monitor and one depth layer.

    The grid is split into lanes: rain travels along each lane. `custom`
    keeps one drop per lane with a moving head; film presets draw the
    sawtooth statelessly from the clock.
    """

    def __init__(self, mon, origin, atlas, glyph_count, cell, layer, look, rng, churn=False):
        self.churn = churn
        self.ox, self.oy = mon["x"] - origin[0], mon["y"] - origin[1]
        self.w, self.h = mon["w"], mon["h"]
        self.cw, self.ch = cell
        self.layer, self.atlas, self.look = layer, atlas, look
        self.base = look["base"]
        self.falloff = look["falloff"]
        self.cols = self.w // self.cw
        self.rows = self.h // self.ch
        self.pad_x = (self.w - self.cols * self.cw) // 2
        self.glyph_count = glyph_count
        self.rng = rng
        self.seed = int(rng.integers(0, 2**20))
        rows, cols = self.rows, self.cols
        grid_y, grid_x = np.mgrid[0:rows, 0:cols]
        self.grid = (grid_y, grid_x)
        direction = look["direction"]
        if direction == "sideways":
            self.lane, self.along = grid_y, grid_x
            self.n_lanes, self.extent = rows, cols
        elif direction == "diagonal":
            self.lane, self.along = grid_x - grid_y + rows, grid_y
            self.n_lanes, self.extent = cols + rows + 1, rows
        else:
            self.lane, self.along = grid_x, grid_y
            self.n_lanes, self.extent = cols, rows
        self.gap = self.extent * 0.6 / layer["density"]
        self.speed_range = tuple(v * layer["speed"] for v in look["speed"])
        self.glow_small = pygame.Surface((cols, rows))
        self.glow_big = pygame.Surface((cols * self.cw // BLOOM_Q, rows * self.ch // BLOOM_Q))
        # per-cell brightness of the last draw, which the glow reads
        self.brightness = np.zeros((rows, cols), np.float32)
        self.glows = layer["dim"] >= 0.9  # the dim far layer doesn't bloom
        self.clock = 0.0
        # rain clock (session time warped by live speed)
        self.rain_clock = 0.0
        self.density_k = 1.0
        # drop model: lanes lit this cycle
        self.lit = np.ones(self.n_lanes, bool)
        # full-grid glyph hashes for message cells (saw)
        self.message_cells = None
        # this frame's message states come from latch_states (head-latched letters)
        self.message_latched = False
        # dimmed level of glitching clock cells, 0 elsewhere (set by latch_states)
        self.message_glitch = None
        self._glow_scratch = {}
        if look["model"] == "saw":
            self._init_saw(grid_y, grid_x)
        else:
            self.trail_range = tuple(v * layer["trail"] for v in TRAIL_LEN_ROWS)
            self.glyph = rng.integers(0, glyph_count, (rows, cols))
            self.head = rng.uniform(-self.gap * 2.5, self.extent, self.n_lanes)
            self.speed = rng.uniform(*self.speed_range, self.n_lanes)
            self.length = rng.uniform(*self.trail_range, self.n_lanes)

    def _lane_hash(self, lane, salt):
        return looks.lane_hash(lane + self.seed, salt)

    def _init_saw(self, grid_y, grid_x):
        look = self.look
        lanes = np.arange(self.n_lanes)
        lo, hi = self.speed_range
        self.lane_speed = lo + (hi - lo) * self._lane_hash(lanes, SALT_LANE_SPEED)
        self.lane_offset = self._lane_hash(lanes, SALT_LANE_OFFSET) * 1000.0
        density = self.layer["density"]
        if look["lanes"] != 1.0:
            density = min(1.0, density * look["lanes"])
        cluster = look.get("cluster")
        if cluster and cluster[1] > 0:
            gain = looks.cluster_gain(lanes, self.seed, cluster[0], cluster[1])
            density = np.clip(density * gain, 0.0, 1.0)
        # Live churn (run != 0). Lit lanes are a superset; each string is kept with
        # probability density / superset, so the mean is unchanged.
        lane_density = np.broadcast_to(np.asarray(density, np.float64), lanes.shape)
        lane_hash = self._lane_hash(lanes, SALT_LANE_LIT)
        if self.churn:
            superset = np.minimum(1.0, CHURN_SUPERSET * lane_density)
            self.keep_probability = lane_density / np.maximum(superset, 1e-9)
            self.lane_lit = lane_hash < superset
        else:
            self.lane_lit = lane_hash < density
        self.lit_mask = self.lane_lit[self.lane]
        self.tooth = look["tooth"] * self.layer["trail"]
        # the cells of lit lanes, as flat arrays
        self.lit_rows, self.lit_cols = np.nonzero(self.lit_mask)
        self.cell_lane = self.lane[self.lit_rows, self.lit_cols].astype(np.int64)
        self.cell_along = self.along[self.lit_rows, self.lit_cols].astype(np.float64)
        self.cell_id = cell_ids(self.lit_rows, self.lit_cols, self.cols)
        self.cell_speed = self.lane_speed[self.cell_lane]
        self.cell_offset = self.lane_offset[self.cell_lane]
        self.cell_phase = looks.lane_hash(self.cell_id + self.seed, SALT_CELL_PHASE)
        self.cell_sequence = looks.lane_hash(self.cell_id + self.seed, SALT_CELL_SEQUENCE)

    def _cell_phase(self, clock, shift=0.0):
        return tooth_phase(
            clock, self.cell_offset, self.cell_speed, self.cell_along, self.tooth, shift
        )

    def _sawtooth(self):
        """Where each lit-lane cell is in its tooth.
        -> (tooth_index, ramp, ramp_ahead, highlighted): `ramp` is 1 at the head falling to 0,
        `ramp_ahead` the same one row ahead, and `highlighted` marks strings with a leader."""
        look = self.look
        clock = self.rain_clock
        pulse_clock = looks.pulse_time(clock, look["pulse"])
        fps = look["step_fps"]
        if fps > 0:  # heads step whole frames at step_fps (24 fps film)
            clock = looks.step_time(clock, fps)
            pulse_clock = looks.step_time(pulse_clock, fps)
        phase = self._cell_phase(clock)
        tooth_index = np.floor(phase).astype(np.int64)
        salt = SALT_HIGHLIGHT * TOOTH_SALT_STRIDE + tooth_index
        highlighted = self._lane_hash(self.cell_lane, salt) < look["lead_ratio"]
        ramp = 1.0 - (phase - tooth_index)
        ahead = self._cell_phase(clock, 1.0)
        ramp_ahead = 1.0 - (ahead - np.floor(ahead))
        # highlighted strings follow the pulse
        if highlighted.any() and pulse_clock != clock:
            pulse_phase = self._cell_phase(pulse_clock)
            pulse_ahead = self._cell_phase(pulse_clock, 1.0)
            ramp = np.where(highlighted, 1.0 - (pulse_phase - np.floor(pulse_phase)), ramp)
            ramp_ahead = np.where(
                highlighted, 1.0 - (pulse_ahead - np.floor(pulse_ahead)), ramp_ahead
            )
        return tooth_index, ramp, ramp_ahead, highlighted

    def _brightness(self, tooth_index, ramp, ramp_ahead, highlighted):
        """Brightness of each lit-lane cell. -> (bright, leader, draw): `leader` marks cells
        drawn at the head level, `draw` the cells that show at all."""
        look = self.look
        lane = self.cell_lane
        shaded = np.clip(ramp * look["contrast"] + look["bias"], 0.0, 1.0)
        base = shaded
        if look["gamma"] != 1.0:
            base = base ** look["gamma"]
        if look["flat"] >= 0:
            base = np.full_like(base, look["flat"])
        on = shaded > 0
        if self.churn:
            salt = SALT_CHURN * TOOTH_SALT_STRIDE + tooth_index
            kept = self._lane_hash(lane, salt) < self.keep_probability[lane]
            on &= kept
            highlighted &= kept
        leader = highlighted & (ramp > ramp_ahead) & on
        # Live density: whole strings fade out, one value per string.
        salt = SALT_DENSITY * TOOTH_SALT_STRIDE + tooth_index
        fade = np.clip(
            (self.density_k - self._lane_hash(lane, salt)) / DENSITY_FADE + 1.0, 0.0, 1.0
        )
        base = base * fade
        on &= fade > 0
        leader_kept = leader & (fade >= LEADER_KEEP)
        demoted = leader & ~leader_kept
        draw = on
        base = np.where(on, base, 0.0)
        bright = np.where(leader_kept, 1.0, np.minimum(1.0, np.where(demoted, fade, base)))
        return bright, leader_kept, draw

    def _hashed_glyphs(self, cell, slot):
        """Glyph id from the cell hash at a glyph slot (a number or an array)."""
        ids = np.floor(
            looks.lane_hash(cell, SALT_GLYPH * TOOTH_SALT_STRIDE + slot) * self.glyph_count
        )
        return np.minimum(np.asarray(ids, np.int64), self.glyph_count - 1)

    def _glyphs(self, t, tooth_index):
        """Glyph id of each lit-lane cell -> (glyph, old). `old` holds the previous glyph of
        changing cells on a crossfade frame and -1 elsewhere; None when nothing crossfades."""
        look = self.look
        period, sequential, sync = look["cycle"]
        count = self.glyph_count
        seeded = self.cell_id + self.seed
        old = None
        if sync > 0:
            salt = SALT_CHANGING * TOOTH_SALT_STRIDE + tooth_index
            changing = self._lane_hash(self.cell_lane, salt) < sync
            if look["step_fps"] > 0 or look["crossfade"]:
                slot_now, slot_prev, mix = looks.glyph_phase(
                    t, period, look["step_fps"], look["crossfade"]
                )
            else:
                slot_now, slot_prev, mix = int(t // period), 0, 0.0
            slot = np.where(changing, slot_now, tooth_index + 65536)
            glyph = self._hashed_glyphs(seeded, slot)
            if mix > 0:
                previous = self._hashed_glyphs(seeded, slot_prev)
                old = np.where(changing, previous, -1)
            return glyph, old
        slot = np.floor(t / period + self.cell_phase).astype(np.int64)
        if sequential > 0.5:
            return (np.floor(self.cell_sequence * count).astype(np.int64) + slot) % count, old
        return self._hashed_glyphs(seeded, slot), old

    def _saw(self, t):
        """Level and glyph for every cell in a lit lane.
        -> (rows, cols, level, glyph, old); see _glyphs for `old`."""
        tooth_index, ramp, ramp_ahead, highlighted = self._sawtooth()
        bright, leader, draw = self._brightness(tooth_index, ramp, ramp_ahead, highlighted)
        glyph, old = self._glyphs(t, tooth_index)
        level = np.minimum((bright * LEVELS).astype(np.int64), LEVELS - 1)
        level[leader] = LEVELS
        self.brightness = np.zeros((self.rows, self.cols), np.float32)
        self.brightness[self.lit_rows[draw], self.lit_cols[draw]] = bright[draw]
        rows, cols = self.lit_rows[draw], self.lit_cols[draw]
        level, glyph = level[draw], glyph[draw]
        if old is not None:
            old = old[draw]
        return rows, cols, level, glyph, old

    def update(self, dt, t, rain_t=None, speed_k=1.0, density_k=1.0):
        self.clock = t
        self.rain_clock = t if rain_t is None else rain_t
        self.density_k = density_k
        if self.look["model"] == "saw":
            return
        rng = self.rng
        step = dt * speed_k
        if self.look["pulse"]:
            step = looks.pulse_time(self.rain_clock, True) - looks.pulse_time(
                self.rain_clock - dt * speed_k, True
            )
        previous = np.floor(self.head).astype(int)
        self.head += self.speed * step
        # Stamp a fresh random glyph on every cell the head crossed.
        current = np.floor(self.head).astype(int)
        moved = (current != previous) & (current >= 0) & (current < self.extent)
        if moved.any():
            hit = moved[self.lane] & (self.along == current[self.lane])
            count = int(hit.sum())
            if count:
                self.glyph[hit] = rng.integers(0, self.glyph_count, count)
        # Recycle lanes whose tail has left the screen.
        dead = self.head - self.length > self.extent
        count = int(dead.sum())
        if count:
            self.lit[dead] = rng.random(count) < density_k
            self.head[dead] = -rng.uniform(0, self.gap, count)
            self.speed[dead] = rng.uniform(*self.speed_range, count)
            self.length[dead] = rng.uniform(*self.trail_range, count)
        # Random glyph mutation inside the trails.
        mutations = int(self.glyph.size * FLICKER_PER_SEC * dt * 0.1)
        if mutations:
            rows = rng.integers(0, self.rows, mutations)
            cols = rng.integers(0, self.cols, mutations)
            self.glyph[rows, cols] = rng.integers(0, self.glyph_count, mutations)

    def latch_states(self, mask, col0, row0, rain_t, reveal_rt, hide_rt, change_rt=-1.0):
        """Head-latched message (film presets, travel down): a letter cell lights when
        the first head of its own lane lands on it after the reveal and stays lit until
        the first head after the deletion (hide_rt < 0: never). The rain is untouched.
        mask may hold change codes (rain_message.change_codes, always-up clock): APPEAR
        cells latch on the first head after change_rt, VANISH cells stay until it, and
        both flicker until then (the shader does the same: a glitching cell is dimmed to
        0.3 to 0.85 of the held level, kept in self.message_glitch, and is never a leader).
        The leader is the cell only while the first head is on it, not for the whole tooth.
        -> int8 (rows, cols): 0 none, 1 lit, 2 leader (the landing head)."""
        self.message_glitch = np.zeros((self.rows, self.cols), np.float32)
        out = np.zeros((self.rows, self.cols), np.int8)
        mask_rows, mask_cols = mask.shape
        row_end, col_end = min(self.rows, row0 + mask_rows), min(self.cols, col0 + mask_cols)
        row_start, col_start = max(row0, 0), max(col0, 0)
        if row_end <= row_start or col_end <= col_start:
            return out
        code = np.zeros((self.rows, self.cols), np.uint8)
        code[row_start:row_end, col_start:col_end] = mask[
            row_start - row0 : row_end - row0, col_start - col0 : col_end - col0
        ]
        if mask.dtype == bool:
            code *= rain_message.STABLE
        rows, cols = np.nonzero(code)
        kind = code[rows, cols]
        lane = self.lane[rows, cols]
        along = self.along[rows, cols].astype(np.float64)
        speed, offset = self.lane_speed[lane], self.lane_offset[lane]
        fps = self.look["step_fps"]
        now = looks.step_time(rain_t, fps) if fps > 0 else rain_t

        def head_index(clock):
            return np.floor(tooth_phase(clock, offset, speed, along, self.tooth))

        now_index = head_index(now)
        reveal_index = head_index(reveal_rt) + 1.0
        if hide_rt < 0:
            hide_index = np.full_like(now_index, 1.0e9)
        else:
            hide_index = head_index(hide_rt) + 1.0
        glitch = np.zeros_like(now_index, bool)
        if change_rt >= 0:
            change_index = head_index(change_rt) + 1.0
            appearing, vanishing = kind == rain_message.APPEAR, kind == rain_message.VANISH
            reveal_index = np.where(appearing, change_index, reveal_index)
            hide_index = np.where(vanishing, change_index, hide_index)
            glitch = (
                (appearing | vanishing)
                & (now_index < change_index)
                & (now - change_rt < rain_message.CLOCK_GLITCH)
            )
        latched = (now_index >= reveal_index) & (now_index < hide_index)
        if glitch.any():
            fade = 1.0 - (now - change_rt) / rain_message.CLOCK_GLITCH
            frame_tick = np.int64(np.floor(now * GLITCH_RATE))
            # the shader's cell number: column * 4099 + row
            cell_hash = cols.astype(np.int64) * 4099 + rows + frame_tick * 7919
            roll = looks.lane_hash(cell_hash, SALT_GLITCH)
            lit_share = np.where(
                kind == rain_message.VANISH, GLITCH_LIT_VANISH, GLITCH_LIT_APPEAR
            ) * (0.4 + 0.6 * fade)
            latched = np.where(glitch, roll < lit_share, latched)
            glitching = glitch & latched
            dimmed = GLITCH_LEVEL_MIN + GLITCH_LEVEL_SPAN * looks.lane_hash(
                cell_hash, SALT_GLITCH_LEVEL
            )
            self.message_glitch[rows[glitching], cols[glitching]] = dimmed[glitching]
        else:
            glitching = glitch
        # The leader is the cell the first head is on (no tooth wrap just below it).
        ramp = self._ramp_at(now, offset, speed, along)
        ramp_ahead = self._ramp_at(now, offset, speed, along, 1.0)
        head_here = ramp > ramp_ahead
        leader = latched & (now_index == reveal_index) & head_here & ~glitching
        out[rows[latched], cols[latched]] = 1
        out[rows[leader], cols[leader]] = 2
        return out

    def _ramp_at(self, clock, offset, speed, along, shift=0.0):
        """1 at a tooth's head falling to 0, for the given cells."""
        phase = tooth_phase(clock, offset, speed, along, self.tooth, shift)
        return 1.0 - (phase - np.floor(phase))

    def latch_glyphs(self, cells, t):
        """Glyph ids, and crossfade old ids (-1 none), for latched message cells. They follow
        the rain's tooth-synchronised change rule, evaluated at the cell's own tooth index
        (the shader keeps msg == 0 for them). cells = (rows, cols)."""
        look = self.look
        rows, cols = cells
        period, _sequential, sync = look["cycle"]
        if sync <= 0:
            return self._message_glyphs()[rows, cols], None
        lane = self.lane[rows, cols].astype(np.int64)
        along = self.along[rows, cols].astype(np.float64)
        seeded = cell_ids(rows, cols, self.cols) + self.seed
        clock = self.rain_clock
        if look["step_fps"] > 0:
            clock = looks.step_time(clock, look["step_fps"])
        tooth_index = np.floor(
            tooth_phase(clock, self.lane_offset[lane], self.lane_speed[lane], along, self.tooth)
        ).astype(np.int64)
        salt = SALT_CHANGING * TOOTH_SALT_STRIDE + tooth_index
        changing = self._lane_hash(lane, salt) < sync
        if look["step_fps"] > 0 or look["crossfade"]:
            slot_now, slot_prev, mix = looks.glyph_phase(
                t, period, look["step_fps"], look["crossfade"]
            )
        else:
            slot_now, slot_prev, mix = int(t // period), 0, 0.0
        slot = np.where(changing, slot_now, tooth_index + 65536)
        glyph = self._hashed_glyphs(seeded, slot)
        old = None
        if mix > 0:
            old = np.where(changing, self._hashed_glyphs(seeded, slot_prev), -1)
        return glyph, old

    def _message_glyphs(self):
        """Glyph ids for message cells on the whole grid."""
        if self.look["model"] != "saw":
            return self.glyph
        if self.message_cells is None:
            cell = (
                np.arange(self.rows)[:, None] * self.cols + np.arange(self.cols)[None, :]
            ).astype(np.int64) + self.seed
            self.message_cells = (
                cell,
                looks.lane_hash(cell, SALT_CELL_PHASE),
                looks.lane_hash(cell, SALT_CELL_SEQUENCE),
            )
        cell, phase, sequence = self.message_cells
        period, sequential, _sync = self.look["cycle"]
        count = self.glyph_count
        slot = np.floor(self.clock / period + phase).astype(np.int64)
        if sequential > 0.5:
            glyph = (np.floor(sequence * count).astype(np.int64) + slot) % count
        else:
            glyph = np.floor(
                looks.lane_hash(cell, SALT_GLYPH * TOOTH_SALT_STRIDE + slot) * count
            ).astype(np.int64)
        return np.minimum(glyph, count - 1)

    def _drop_cells(self):
        """Cells to draw for the custom drop model -> (rows, cols, level, glyph)."""
        dist = self.head[self.lane] - self.along
        bright = trail_brightness(dist, self.length[self.lane], self.falloff)
        bright = bright * self.lit[self.lane]
        inside = bright > TRAIL_VISIBLE
        self.brightness = bright
        rows, cols = np.nonzero(inside)
        level = np.minimum((bright[rows, cols] * LEVELS).astype(int), LEVELS - 1)
        level[(dist[rows, cols] < 1.0) & inside[rows, cols]] = LEVELS  # head
        return rows, cols, level, self.glyph[rows, cols]

    def _with_message(self, msg, rows, cols, level, glyph, old):
        """Merge the message cells (the larger of rain and message level, message glyph)."""
        shape = (self.rows, self.cols)
        level_grid = np.full(shape, -1, np.int64)
        glyph_grid = np.zeros(shape, np.int64)
        level_grid[rows, cols] = level
        glyph_grid[rows, cols] = glyph
        message = msg > 0
        message_level = np.where(msg == 2, LEVELS, LEVELS - 1)
        level_grid[message] = np.maximum(level_grid[message], message_level[message])
        if self.message_latched and self.message_glitch is not None:
            # glitching clock cells are dimmed, never at full level
            glitching = message & (self.message_glitch > 0)
            level_grid[glitching] = np.minimum(
                (self.message_glitch[glitching] * (LEVELS - 1)).astype(np.int64), LEVELS - 1
            )
        old_grid = None
        if self.message_latched:
            # latched cells follow the rain's tooth-synchronised glyph rule, like the GPU
            message_rows, message_cols = np.nonzero(message)
            latched_glyph, latched_old = self.latch_glyphs((message_rows, message_cols), self.clock)
            glyph_grid[message_rows, message_cols] = latched_glyph
            if old is not None or latched_old is not None:
                old_grid = np.full(shape, -1, np.int64)
                if old is not None:
                    old_grid[rows, cols] = old
                old_grid[message] = -1
                if latched_old is not None:
                    old_grid[message_rows, message_cols] = latched_old
                if old is None:
                    old = np.zeros(1, np.int64)
        else:
            glyph_grid[message] = self._message_glyphs()[message]
            if old is not None:  # message cells keep their own glyph rule
                old_grid = np.full(shape, -1, np.int64)
                old_grid[rows, cols] = old
                old_grid[message] = -1
        rows, cols = np.nonzero(level_grid >= 0)
        if old is not None:
            old = old_grid[rows, cols]
        self.brightness = np.maximum(self.brightness, message.astype(np.float32))
        return rows, cols, level_grid[rows, cols], glyph_grid[rows, cols], old

    def draw(self, screen, msg=None):
        old = None
        if self.look["model"] == "saw":
            rows, cols, level, glyph, old = self._saw(self.clock)
        else:
            rows, cols, level, glyph = self._drop_cells()
        if msg is not None and (msg > 0).any():
            rows, cols, level, glyph, old = self._with_message(msg, rows, cols, level, glyph, old)
        if rows.size == 0:
            return
        index = level * self.glyph_count + glyph
        xs = cols * self.cw + self.pad_x + self.ox
        ys = rows * self.ch + self.oy
        add = pygame.BLEND_ADD
        if old is not None and (old >= 0).any():
            # Crossfade frame: old then new glyph, both from the half copies.
            half = (LEVELS + 1) * self.glyph_count
            crossfading = old >= 0
            old_index = level[crossfading] * self.glyph_count + old[crossfading] + half
            screen.blits(
                (
                    (self.atlas[i], (x, y), None, add)
                    for i, x, y in zip(
                        old_index.tolist(),
                        xs[crossfading].tolist(),
                        ys[crossfading].tolist(),
                        strict=True,
                    )
                ),
                doreturn=False,
            )
            index = np.where(crossfading, index + half, index)
        screen.blits(
            (
                (self.atlas[i], (x, y), None, add)
                for i, x, y in zip(index.tolist(), xs.tolist(), ys.tolist(), strict=True)
            ),
            doreturn=False,
        )

    def _scratch(self, name, like):
        """A reusable array shaped and typed like `like`."""
        array = self._glow_scratch.get(name)
        if array is None or array.shape != like.shape or array.dtype != like.dtype:
            array = np.empty_like(like)
            self._glow_scratch[name] = array
        return array

    def glow(self, low, gain):
        """Bloom: 1 px per cell -> blur on the tiny grid -> add into `low`."""
        bright = self._scratch("bright", self.brightness)
        # only bright glyphs bloom
        np.multiply(self.brightness, self.brightness, out=bright)
        halo = self._scratch("halo", bright)
        np.multiply(bright, GLOW_CENTRE, out=halo)
        for axis in (0, 1):
            halo[:] += GLOW_NEAR * (np.roll(bright, 1, axis) + np.roll(bright, -1, axis))
        halo += GLOW_FAR * (
            np.roll(halo, 2, 0) + np.roll(halo, -2, 0) + np.roll(halo, 2, 1) + np.roll(halo, -2, 1)
        )
        rgb = np.clip(
            halo[..., None] * np.array(self.base, np.float32) * gain * self.layer["dim"], 0, 255
        ).astype(np.uint8)
        pygame.surfarray.blit_array(self.glow_small, rgb.transpose(1, 0, 2))
        pygame.transform.smoothscale(self.glow_small, self.glow_big.get_size(), self.glow_big)
        low.blit(self.glow_big, (self.pad_x // BLOOM_Q, 0), special_flags=pygame.BLEND_ADD)


class MessageGrid:
    """The message's own finer glyph grid over one monitor's rain (message sizes below 36 pt).

    The cell is the main rain cell scaled by rain_message.fine_grid's c, with its own atlas of
    the same glyphs and colours. It draws only the message cells; the rain beneath is untouched."""

    def __init__(self, main, c, custom, rng):
        self.ox, self.oy, self.w, self.h = main.ox, main.oy, main.w, main.h
        self.look = main.look
        cell = rain_message.fine_cell((main.cw, main.ch), c)
        layer = dict(main.layer, scale=main.layer["scale"] * c)
        self.atlas, self.glyph_count, (self.cw, self.ch), _source = build_atlas(
            layer, main.look, custom, cell
        )
        self.cols, self.rows = self.w // self.cw, self.h // self.ch
        self.pad_x = (self.w - self.cols * self.cw) // 2
        self.seed = int(rng.integers(0, 2**20))
        self.clock = 0.0
        self.message_cells = None
        self.glyph = rng.integers(0, self.glyph_count, (self.rows, self.cols))
        grid_y, grid_x = np.mgrid[0 : self.rows, 0 : self.cols]
        direction = main.look["direction"]
        if direction == "sideways":
            self.lane, self.along, self.n_lanes = grid_y, grid_x, self.rows
        elif direction == "diagonal":
            self.lane, self.along = grid_x - grid_y + self.rows, grid_y
            self.n_lanes = self.cols + self.rows + 1
        else:
            self.lane, self.along, self.n_lanes = grid_x, grid_y, self.cols

    _message_glyphs = Rain._message_glyphs

    def draw(self, screen, msg):
        """Blit the message cells: lit ones at the top ramp level, the leader as the head glyph."""
        rows, cols = np.nonzero(msg > 0)
        if rows.size == 0:
            return
        level = np.where(msg[rows, cols] == 2, LEVELS, LEVELS - 1)
        index = level * self.glyph_count + self._message_glyphs()[rows, cols]
        xs = cols * self.cw + self.pad_x + self.ox
        ys = rows * self.ch + self.oy
        screen.blits(
            (
                (self.atlas[i], (x, y), None, pygame.BLEND_ADD)
                for i, x, y in zip(index.tolist(), xs.tolist(), ys.tolist(), strict=True)
            ),
            doreturn=False,
        )


class SoftRenderer:
    name = "software"

    def __init__(self, mons, cfg, origin, size, screen, run=None, churn=True):
        self.cfg, self.mons, self.origin, self.size = cfg, mons, origin, size
        self.screen = screen
        self.mon_cfgs = [monitor_cfg(cfg, m.get("id", "")) for m in mons]
        self.looks = [looks.resolve(c) for c in self.mon_cfgs]
        self.look = self.looks[0]  # monitor 0 also draws the easter egg
        self.base, self.head = self.look["base"], self.look["head"]
        custom = glyphs.custom_font_path(cfg["font_path"])
        if run is None:
            run = int(np.random.default_rng().integers(1, 2**32))
        self.run = int(run)
        rng = self.rng = np.random.default_rng(self.run)
        cache = {}
        self.fields = []
        for i, mon in enumerate(mons):
            look = self.looks[i]
            mscale = mon["dpi"] * cfg["glyph_scale"] * look["cell_scale"]
            layers = []
            for layer in active_layers(self.mon_cfgs[i], look):
                lay = dict(layer, scale=layer["scale"] * mscale)
                csize = (
                    looks.cell_px(look, mon["w"], layer["scale"], cfg["glyph_scale"], 1.0)
                    if look["columns"] > 0
                    else None
                )
                key = (
                    round(lay["scale"], 3),
                    lay["dim"],
                    lay["soft"],
                    look["name"],
                    tuple(look["base"]),
                    tuple(look["head"]),
                    csize,
                )
                if key not in cache:
                    cache[key] = build_atlas(lay, look, custom, csize)
                atlas, n, cell, self.glyph_source = cache[key]
                layers.append(
                    Rain(mon, origin, atlas, n, cell, lay, look, rng, churn=churn and self.run != 0)
                )
            low = pygame.Surface((mon["w"] // BLOOM_Q, mon["h"] // BLOOM_Q))
            wide = pygame.Surface((mon["w"] // BLOOM_Q * BLOOM_Q, mon["h"] // BLOOM_Q * BLOOM_Q))
            gain = look["bloom"] * 0.3
            bg = (
                tuple(int(c) for c in looks.palette_rgb(look["palette"], 0.0) * 255)
                if look["film"]
                else (0, 0, 0)
            )
            self.fields.append((layers, low, wide, gain, bg))
        self.masks = build_masks(
            size,
            mons,
            origin,
            [(lk["scanlines"], lk["interlace"], lk["vignette"]) for lk in self.looks],
        )
        self.dot_masks = build_dot_masks(size, mons, origin, self.looks)
        self.egg = EasterEgg(cfg["easter_egg"] and cfg["message"] == "off")
        self.text = None
        self.rain_off = 0.0
        # per monitor (mask, col0, row0) or None
        self.msg_masks = [None] * len(mons)
        # per monitor: the message's own fine grid, or None (the message sits on the main grid)
        self.msg_fine = [None] * len(mons)
        c = rain_message.fine_grid(0, 0, rain_message.text_style(cfg)[0])[0]
        if c < 1.0 and cfg["message"] != "off":
            for i in range(len(mons)):
                self.msg_fine[i] = MessageGrid(self._main(i), c, custom, rng)
        self.msg_jitter = [None] * len(mons)
        self.latch = rain_message.MessageLatch()
        self.msg = rain_message.MessageSchedule(cfg)
        self.live = live_load.LiveControl(cfg)

    def _main(self, i):
        layers = self.fields[i][0]
        return layers[1 if self.mon_cfgs[i]["depth"] else 0]

    def _message_states(self, t):
        """Per-monitor int8 state arrays for the rain message, or None."""
        state = self.msg.state(t)
        if state is None:
            return None, False
        text, reveal, hide, n = state
        if self.latch.key is None or self.latch.key[0] != n:
            for i in range(len(self.mons)):
                lanes = (self.msg_fine[i] or self._main(i)).n_lanes
                self.msg_jitter[i] = (self.rng.random(lanes), self.rng.random(lanes))
        fixed = self.cfg["message"] == "clock_fixed"
        if self.latch.note_message(n, text, fixed):
            anchor = rain_message.anchor_of(self.cfg["clock_position"]) if fixed else None
            style = rain_message.text_style(self.cfg)
            previous = self.latch.previous_text
            for i in range(len(self.mons)):
                field = self._main(i)
                px = (field.w, field.h, field.cw, field.ch)
                new = rain_message.message_layout(text, field.cols, field.rows, anchor, style, px)[
                    1
                ]
                old = (
                    rain_message.message_layout(
                        previous, field.cols, field.rows, anchor, style, px
                    )[1]
                    if previous
                    else None
                )
                self.msg_masks[i] = (
                    rain_message.change_codes(old, new) if anchor is not None else new
                )
        self.latch.update_clocks(n, text, reveal, hide, t, self.rain_off)
        out = []
        for i in range(len(self.mons)):
            got = self.msg_masks[i]
            if got is None:
                out.append(None)
                continue
            f = self._main(i)
            mask, col0, row0 = got
            lk = self.looks[i]
            fine = self.msg_fine[i]
            if fine is not None:
                f.message_latched = False
                j1, j2 = self.msg_jitter[i]
                fine.clock = t
                out.append(
                    rain_message.fine_states(
                        mask,
                        col0,
                        row0,
                        fine.lane,
                        fine.along,
                        j1,
                        j2,
                        t,
                        reveal,
                        hide,
                        lk["direction"],
                        self.latch.previous_text is not None,
                    )
                )
                continue
            if lk["film"] and lk["model"] == "saw" and lk["direction"] == "down":
                f.message_latched = True
                out.append(
                    f.latch_states(
                        mask,
                        col0,
                        row0,
                        t + self.rain_off,
                        self.latch.reveal_clock,
                        self.latch.hide_clock,
                        self.latch.change_clock,
                    )
                )
                continue
            f.message_latched = False
            j1, j2 = self.msg_jitter[i]
            out.append(
                rain_message.cell_states(
                    # change codes: the new text is every cell that appears or stays
                    (mask >= rain_message.APPEAR) if mask.dtype != bool else mask,
                    col0,
                    row0,
                    f.lane,
                    f.along,
                    j1,
                    j2,
                    t,
                    reveal,
                    hide,
                    self.looks[i]["direction"],
                )
            )
        return out, True

    def rain_grid(self, mi):
        """(mon_x, mon_y, pad_x, cell_w, cell_h, cols, rows) of monitor mi's main layer."""
        layers = self.fields[mi][0]
        r = layers[min(main_layer_index(self.mon_cfgs[mi]), len(layers) - 1)]
        return (r.ox, r.oy, r.pad_x, r.cw, r.ch, r.cols, r.rows)

    def render(self, t, dt, frame):
        screen = self.screen
        refresh = frame % 2 == 0  # bloom is rebuilt every other frame
        speed_k, density_k = self.live.update(dt)
        self.rain_off += dt * (speed_k - 1.0)
        rain_t = t + self.rain_off
        states, showing = self._message_states(t)
        for i, (layers, low, wide, gain, bg) in enumerate(self.fields):
            main = self._main(i)
            first = layers[0]
            screen.fill(bg, (first.ox, first.oy, first.w, first.h))
            if refresh:
                low.fill((0, 0, 0))
            for f in layers:  # far -> near
                f.update(dt, t, rain_t, speed_k, density_k)
                fine = self.msg_fine[i]
                f.draw(screen, states[i] if states and f is main and fine is None else None)
                if states and f is main and fine is not None and states[i] is not None:
                    fine.draw(screen, states[i])
                if refresh and gain > 0 and f.glows:
                    f.glow(low, gain)
            if gain > 0:
                if refresh:
                    pygame.transform.scale(low, wide.get_size(), wide)
                screen.blit(wide, (first.ox, first.oy), special_flags=pygame.BLEND_ADD)
        if not showing:
            self._draw_egg(t)
        if self.dot_masks:
            screen.blit(self.dot_masks[0], (0, 0), special_flags=pygame.BLEND_MULT)
            screen.blit(self.dot_masks[1], (0, 0), special_flags=pygame.BLEND_MAX)
        if self.masks:
            screen.blit(
                self.masks[frame % len(self.masks)], (0, 0), special_flags=pygame.BLEND_MULT
            )

    def _draw_egg(self, t):
        state = self.egg.update(t)
        if state is None:
            return
        text, shown, alpha, cursor = state
        mon = self.mons[0]
        size, family, bold, italic = rain_message.text_style(self.cfg)
        height = max(8, int(mon["h"] * 0.05 * mon["dpi"] ** 0.5 * size))
        if self.text is None or self.text[0] != text:
            font = glyphs.text_font(height, family, bold, italic)
            head = (230, 0, 0) if self.look["film"] else tuple(int(c) for c in self.head)
            self.text = (text, font.render(text, True, head, (0, 0, 0)))
        surf = self.text[1]
        tw, th = surf.get_size()
        x = mon["x"] - self.origin[0] + int(mon["w"] * 0.10)
        y = mon["y"] - self.origin[1] + int(mon["h"] * 0.42)
        pad = int(height * 0.6)
        back = pygame.Surface((tw + pad * 2 + height, th + int(pad * 1.2)), pygame.SRCALPHA)
        back.fill((0, 0, 0, int(225 * alpha)))
        self.screen.blit(back, (x - pad, y - int(pad * 0.6)))
        fade = surf.copy()
        k = int(255 * alpha)
        fade.fill((k, k, k), special_flags=pygame.BLEND_MULT)
        cw = tw / len(text)
        self.screen.blit(fade, (x, y), (0, 0, int(cw * shown), th), special_flags=pygame.BLEND_ADD)
        if cursor:
            col = (180, 0, 0) if self.look["film"] else self.base
            self.screen.fill(
                tuple(int(c * alpha) for c in col),
                (x + int(cw * shown), y + int(th * 0.12), int(cw * 0.8), int(th * 0.76)),
                special_flags=pygame.BLEND_ADD,
            )

    def screenshot(self, path):
        pygame.image.save(self.screen, path)

    def close(self):
        self.live.close()
