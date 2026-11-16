"""Image layer (GPU only, film presets travelling down): any picture drawn by the rain.

Each picture in the images folder is converted to luminance, an open-background mask, a
surface tone and a dark-open mask, and uploaded as a mipmapped texture together with a
glyph-size field that gives the picture a sense of depth. scene.frag draws it only as
glyphs; the picture itself is never shown. A new picture starts every period and sweeps
over the previous one as the rain heads land.

Every tunable can be overridden with a MATRIX_IMAGE_<NAME> environment variable (see
ImageTuning and ENV_NAMES).
"""

import concurrent.futures
import dataclasses
import math
import os
import random
import stat
import struct
import threading
import time
from typing import NamedTuple

import moderngl
import numpy as np
import pygame

from digital_rain import resources, surfaces

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
# Limits of the walk through subfolders (image_subfolders): the listing runs before the first
# frame, so a whole drive or a network share must not stall it.
MAX_FOLDER_DEPTH = 8  # levels below the chosen folder
MAX_PICTURES = 5000
MAX_FOLDERS = 2000  # folders opened, the chosen one included
LISTING_SECONDS = 2.0  # wall-clock budget of the walk
# Folders never searched: system folders that hold no pictures of the user's own, and macOS
# packages (a Photos library is a folder of thumbnails and originals).
SKIPPED_FOLDERS = {"$recycle.bin", "system volume information", "__macosx", "@eadir"}
SKIPPED_FOLDER_SUFFIXES = (".photoslibrary", ".app", ".bundle", ".framework")

# Luma weights (Rec. 709) used to turn RGB into luminance.
LUMA_WEIGHTS = (0.2126, 0.7152, 0.0722)
# Percentiles stretched to black and white when a picture is loaded, so shapes read.
STRETCH_PERCENTILES = (2.0, 98.0)

# Longest side, in pixels, of the working copies each analysis runs on.
VANISHING_POINT_SIZE = 320
DEPTH_FIELD_SIZE = 384
SURFACE_TONE_SIZE = 384
BACKGROUND_MASK_SIZE = 256

# Vanishing point search.
EDGE_PERCENTILE = 93.0  # only the strongest 7% of edge pixels vote
MAX_VOTERS = 4000
DIAGONAL_MIN = 0.3  # |sin 2*angle| below this: axis-aligned edge, no vote
DIAGONAL_FULL = 0.7  # ... and at or above this the edge votes in full
CANDIDATE_GRID = (61, 49)  # candidate vanishing points across and down
CANDIDATE_MARGIN = 0.1  # candidates reach this far outside the frame
VOTE_CHUNK = 500  # voters processed at a time, to bound memory
LINE_TOLERANCE = 0.035  # sine of the angle a line may miss a candidate by
MIN_VOTE_DISTANCE = 0.05  # voters closer than this to a candidate are ignored
BORDER_FADE = 0.12  # confidence reaches 1 this far inside the frame
DIRECTION_BINS = 16

# Surface tone and open regions.
SURFACE_SCALE_SHARE = 0.04  # wide blur radius as a share of the longer side
LOCAL_CONTRAST_SOFTEN = 0.06
WATER_TONE = 0.75  # value written for water in the open mask (sky is 1)
STRUCTURE_FLOOR = 0.012  # minimum fine-detail level that counts as structure
STRUCTURE_PERCENTILE = 90
# Waterline candidates, in picture heights around the horizon.
MIRROR_OFFSETS = (-0.04, -0.02, 0.0, 0.02, 0.04)


@dataclasses.dataclass(frozen=True)
class ImageTuning:
    """Look of the image layer. Defaults are the tuned values; each field reads the
    environment variable MATRIX_IMAGE_<ENV_NAMES[field]> when it is set."""

    # Timing and overall blend.
    # seconds per picture (the image_period setting unless set)
    period: float = 30.0
    start: float = 2.0  # seconds before the first picture
    # grid mode: longest wait, in seconds from when a picture is first wanted, for its depth map
    # while the depth network is still working on it (the first run loads the network, about 8 s
    # on a Mac); past it the picture is drawn without depth
    depth_wait: float = 10.0
    strength: float = 0.6
    gain: float = 1.15
    gamma: float = 1.2
    # Glyph level: black point, gain, edge gain, and the picture level below which none shows.
    black_point: float = 0.05
    level_gain: float = 1.8
    edge_gain: float = 1.0
    dim: float = 0.18
    # rain brightness kept where the picture is revealed
    rain: float = 0.0
    # grid mode: rain trail brightness kept in revealed cells (the picture is drawn on top, max)
    grid_rain: float = 0.05
    # grid mode: tone curve of the picture cell level (higher: darker shadows, more contrast)
    grid_gamma: float = 2.0
    # grid mode: coarse tone, the picture blurred over 2**grid_blur cells: share of the cell level
    # it sets, tone curve, depth share of the tone (near bright, far dim) and silhouette gain
    # (outlines from depth jumps)
    grid_coarse: float = 1.0
    grid_cgamma: float = 1.5
    grid_layer: float = 0.0
    grid_sil: float = 0.8
    # grid mode: inner detail (windows, signs, chairs), the cell's edge and texture accent added on
    # top of the coarse tone: share, level on far parts (0 dark .. 1 as near) and curve (higher:
    # only strong edges); column segment length in cells sharing one level (1: per cell; longer
    # made no visible difference); outlines on the nearer side of a depth jump only (1) or both
    # sides (0, which drew a ring round the cat)
    grid_detail: float = 0.3
    grid_detail_far: float = 0.15
    grid_detail_gamma: float = 2.0
    grid_seg: float = 1.0
    grid_sil_side: float = 1.0
    # grid mode: how much far parts lose their coarse tone (0 none .. 1 the farthest is dark
    # whatever its light)
    grid_tone_far: float = 0.0
    # grid mode: share of the edge accent kept in the cell level
    grid_edge: float = 0.3
    # grid mode: thin-line accent (frames, kerbs, floor lines) read at each cell's own scale; 0 off
    grid_ridge: float = 0.0
    # grid mode: picture cell size as a share of the main rain cell (1: the rain's own cells)
    grid_scale: float = 0.45
    # grid mode: picture cell width as a share of its height scale (the film's columns are narrow)
    grid_aspect: float = 0.5
    # grid mode: draw the picture in three depth classes (near, mid, far), each at its own cell
    # size (share of the rain cell, height); the width follows grid_aspect
    grid_depth: bool = True
    grid_near: float = 0.9
    grid_mid: float = 0.8
    grid_far: float = 0.8
    # grid mode: rain kept on the depth layers (not the main one) where the picture is revealed
    grid_back: float = 0.04
    # grid mode: the rain carries the picture. Share of the level a lane can lose, share of the
    # level that follows the falling string (1 - grid_string is kept between strings), and the
    # gain on the picture level
    grid_lane: float = 0.3
    grid_string: float = 0.75
    grid_boost: float = 2.0
    grid_string_gamma: float = 2.5
    # grid mode: parallax, speed of the flat depth passes from depth
    # (1 + grid_parallax * (depth - 0.5))
    grid_parallax: float = 0.8
    # grid mode: floor column width as a multiple of the wall's, so the floor visibly converges
    grid_floor_width: float = 2.5
    # grid mode: sparse large soft particles over the picture (share of cells holding one, peak
    # level)
    grid_part: float = 0.2
    grid_part_level: float = 0.55
    # grid mode: streams on side walls run down the faces (0: rain falls under gravity, level
    # camera) or along the perspective lines toward the far end (1)
    grid_wall_dir: float = 0.0
    # grid mode: the subject shaded by its own light (surfaces.own_light_tone) instead of the
    # stretched coarse tone: switch, dim body floor, shade curve, highlight points, rim on the edge
    # of open background
    grid_own: float = 1.0
    grid_body: float = 0.1
    grid_own_gamma: float = 1.3
    grid_highlight: float = 1.8
    grid_rim: float = 0.0
    # grid mode: blur of the own-light shade, share of the label map's long side
    grid_own_blur: float = 0.002
    # grid mode: objects standing out in front of their surroundings (people, a phone box; see
    # surfaces.subject_mask): switch, their least level, their shade curve, the stretch of their
    # own small light and shade (faces), the level of what is behind them, and 1 to take them
    # off any fitted floor or wall (a person is not a plane)
    grid_subject: float = 1.0
    grid_subject_body: float = 0.35
    grid_subject_gamma: float = 1.0
    grid_subject_contrast: float = 0.8
    grid_behind: float = 0.6
    grid_subject_front: float = 1.0
    # grid mode: a bright smooth area joined to the frame edge counts as open backdrop (black) only
    # where the depth network also puts it at about infinity (disparity 0..1 ramp from the first
    # to the second value): a lit window at the back of a room or a sunny lawn is not sky. 0 0 off.
    grid_flat_far_lo: float = 0.02
    grid_flat_far_hi: float = 0.04
    # grid mode: long side of the label map (kind, depth, tone) in texels; finer than the depth
    # network's map so the tone carries faces
    grid_tone_res: int = 512
    # grid mode: share of the string modulation the brightest picture cells lose (they glow
    # steadily)
    grid_glow: float = 0.8
    # grid mode: outlines (depth jumps, the subject against open background) drawn by a pass of
    # their own in finer glyphs: cell scale as a share of the mid class (0: off, outlines in the
    # body cells) and the least outline strength that pass draws
    grid_outline: float = 0.5
    grid_outline_min: float = 0.15
    # grid mode: rain through the subject (surfaces.rain_mask: near parts that face the viewer or
    # stand out, and a drip below them): level of the rain string there (head 1, fading up the
    # trail; 0 off), its trail curve (higher: shorter bright trails), the share of lanes that
    # carry it, and how far below the subject it drips on (share of the picture's height)
    grid_subject_rain: float = 0.8
    grid_subject_rain_gamma: float = 1.5
    grid_subject_lanes: float = 0.5
    grid_drip: float = 0.12
    # grid mode: white heads over the picture. Share of lanes whose heads light white in the
    # picture passes, how white those heads are (1 full), and how white the main rain's own heads
    # stay over the picture (the heads that bring and take away the picture keep full white)
    grid_white_lanes: float = 0.3
    grid_white: float = 0.5
    grid_rain_head: float = 0.2
    # grid mode: the outline at most this much brighter than the brightest side it divides
    # (1: no cap)
    grid_outline_cap: float = 0.2
    # grid mode: 1 keeps the picture in step with the rain so no lane goes dark beside lanes still
    # in plain rain or still holding it: picture cells take the reveal of the main lane they sit
    # on, a front takes the picture away down each lane (the exit heads mostly come too late, and
    # the let-go timeout dropped every waiting lane at once), and under the exit string the rain
    # is back at full while the picture follows its envelope out. 0 off.
    grid_hold: float = 1.0
    # base glyph level on walls and surfaces (no edges)
    fill: float = 0.45
    move: float = 0.6  # 0 still, 1 strong streaks and shimmer
    # Image glyph cell as a fraction of the rain cell: near, mid and far octave.
    octave_near: float = 0.40
    octave_mid: float = 0.27
    octave_far: float = 0.18
    depth_bias: float = 0.0  # positive: more near (big) glyphs
    # glyph rotation to the local edge direction: 0 upright
    orient: float = 1.0
    # rows glyphs take to settle behind the head (0 off)
    settle_rows: float = 16.0
    settle_burst: float = 1.0  # extra near depth at the head
    tone: float = 0.3  # share of the surface fill that ignores tone
    local_lift: float = 0.2  # lift of dark, detailed regions (0 off)
    # Supporting line directions that give no, and full, confidence in the vanishing point.
    vp_dirs_low: float = 3.4
    vp_dirs_high: float = 4.0
    # Open background: brighter than, and flatter (local deviation) than.
    background_luminance: float = 0.5
    background_flatness: float = 0.12
    # grid mode: empty black at the frame edge (space) counts as sky: mean luminance below this ...
    space_luminance: float = 0.015
    # ... and smooth to within this deviation
    space_flatness: float = 0.02
    # Perspective box grid: on (0 off), the distance from the vanishing point (fraction of
    # width) where glyphs are `persp_near` rain cells tall.
    persp_on: float = 1.0
    persp_reference: float = 0.5
    persp_near: float = 0.7
    # Depth field: on (0 gives the older grids), glyph size (rain cells) near the viewer, far
    # away and with no perspective found, structure scale per height above the horizon, and
    # the depth below the horizon over which standing structures fade out.
    field_on: float = 1.0
    field_near: float = 0.7
    field_far: float = 0.18
    field_flat: float = 0.27
    field_tower: float = 0.35
    field_tower_fade: float = 0.08
    field_size: int = 256  # depth field table size
    # sideways smoothing of glyph size (fraction of the width)
    field_smooth: float = 0.06
    # Dim floor on near ground and water: amount, and the glyph sizes where it starts and is full.
    near_fill_amount: float = 0.35
    near_fill_low: float = 0.3
    near_fill_high: float = 0.65
    # open sky: detail below this share of the 90th percentile
    sky_detail: float = 0.25
    # Horizon: share of columns with sky, median sky depth, line strength over the median row.
    horizon_sky_share: float = 0.5
    horizon_sky_depth: float = 0.1
    horizon_line_strength: float = 1.9
    show_picture: bool = False  # debug: also draw the picture
    # Surface coat: every surface carries glyphs whose brightness and share of lit cells follow
    # how lit it is; edges are a brighter accent on top.
    surface_level: float = 0.7  # level at full tone (0 off)
    surface_floor: float = 0.1  # share of it at the darkest surface
    surface_edge: float = 1.0  # edge accent gain
    surface_density_low: float = 0.15  # share of cells lit on the darkest surface
    surface_density_high: float = 0.95  # ... and on the brightest
    surface_local: float = 0.3  # share of the tone taken from local contrast
    surface_gamma: float = 1.0  # tone curve (below 1 lifts the shadows)
    # At image_detail 1: far, flat and near glyph sizes times these, and the thinnest glyph in
    # render pixels (5 at detail 0).
    detail_far: float = 0.4
    detail_flat: float = 0.45
    detail_min_px: float = 3.0
    detail_near: float = 0.6
    # 1: sky and water carry no surface coat, only strong edges
    surface_sky: float = 1.0
    # share of horizontal streaks above which an area is water
    surface_water: float = 0.8
    open_edge_low: float = 0.8  # in sky and water only edges above this show
    open_edge_high: float = 1.0  # ... in full from here
    water_edge: float = 0.35  # water edges are further scaled by this
    # Pictures with more pixels than this are skipped, unless PIL can decode them downscaled.
    max_pixels: float = 100_000_000.0

    @classmethod
    def from_env(cls):
        values = {}
        for field in dataclasses.fields(cls):
            suffix = ENV_NAMES.get(field.name, field.name.upper())
            raw = os.environ.get("MATRIX_IMAGE_" + suffix)
            if raw is None:
                continue
            if field.type is bool:
                values[field.name] = raw == "1"
            elif field.type is int:
                values[field.name] = int(raw)
            else:
                values[field.name] = float(raw)
        return cls(**values)

    # Uniform-ready groups, in the order scene.frag and the final passes expect them.
    @property
    def blend_uniform(self):
        return (self.strength, self.gain, self.gamma)

    @property
    def level_uniform(self):
        return (self.black_point, self.level_gain, self.edge_gain)

    @property
    def surface_uniform(self):
        return (self.surface_level, self.surface_floor, self.surface_edge)

    @property
    def density_uniform(self):
        return (self.surface_density_low, self.surface_density_high)

    @property
    def open_edge_uniform(self):
        return (self.open_edge_low, self.open_edge_high, self.water_edge)

    @property
    def perspective_uniform(self):
        return (self.persp_on, self.persp_reference, self.persp_near)

    @property
    def settle_uniform(self):
        return (self.settle_rows, self.settle_burst)

    @property
    def near_fill_uniform(self):
        return (self.near_fill_amount, self.near_fill_low, self.near_fill_high)


# Environment variable suffixes that differ from the upper-cased field name.
ENV_NAMES = {
    "black_point": "BLACK",
    "level_gain": "LGAIN",
    "edge_gain": "EDGE",
    "octave_near": "OCT_NEAR",
    "octave_mid": "OCT_MID",
    "octave_far": "OCT_FAR",
    "settle_rows": "SETTLE",
    "settle_burst": "BURST",
    "local_lift": "LOCAL",
    "vp_dirs_low": "VP_DIRS_LO",
    "vp_dirs_high": "VP_DIRS_HI",
    "background_luminance": "BG_LUM",
    "background_flatness": "BG_FLAT",
    "persp_on": "PERSP",
    "persp_reference": "PERSP_REF",
    "field_on": "FIELD",
    "field_size": "FIELD_N",
    "near_fill_amount": "NEAR_FILL",
    "near_fill_low": "NEAR_FILL_LO",
    "near_fill_high": "NEAR_FILL_HI",
    "sky_detail": "SKY_K",
    "horizon_sky_share": "HZ_SKY",
    "horizon_sky_depth": "HZ_DEPTH",
    "horizon_line_strength": "HZ_LINE",
    "show_picture": "PICTURE",
    "surface_level": "SURFACE",
    "surface_floor": "SURF_FLOOR",
    "surface_edge": "SURF_EDGE",
    "surface_density_low": "SURF_DENS_LO",
    "surface_density_high": "SURF_DENS_HI",
    "surface_local": "SURF_LOCAL",
    "surface_gamma": "SURF_GAMMA",
    "detail_min_px": "DETAIL_MINPX",
    "surface_sky": "SURF_SKY",
    "surface_water": "SURF_WATER",
    "open_edge_low": "SURF_OPEN_EDGE_LO",
    "open_edge_high": "SURF_OPEN_EDGE_HI",
    "water_edge": "SURF_WATER_EDGE",
}

TUNING = ImageTuning.from_env()


# added to a vanishing point's confidence (the shader reads z > 1.5 as looking up)
CAMERA_UP_FLAG = 2.0


class VanishingPoint(NamedTuple):
    """Position in 0..1 picture coordinates and confidence 0..1, plus CAMERA_UP_FLAG when the
    point is where the verticals meet over the sky of an up-view (the shader then streams
    radially from it)."""

    x: float
    y: float
    confidence: float


class FieldInfo(NamedTuple):
    """What the shader needs to read a depth field table."""

    v_min: float
    v_max: float
    mode: float
    smallest_size: float


class PreparedField(NamedTuple):
    width: int
    height: int
    data: bytes
    info: FieldInfo


class PreparedLabels(NamedTuple):
    """The surface label map of a picture (surfaces.py), four bytes per texel (kind, disparity,
    coarse tone, rain mask); a 1x1 map of surfaces.NO_DETECTION when the picture has none."""

    width: int
    height: int
    data: bytes
    components: int = 4


NO_LABELS = PreparedLabels(1, 1, bytes([surfaces.NO_DETECTION, 0, 0, 0]))


class PreparedImage(NamedTuple):
    width: int
    height: int
    texels: bytes
    vanishing_point: VanishingPoint
    field: PreparedField
    labels: PreparedLabels = NO_LABELS


class ImageState(NamedTuple):
    """mode 0 off, 1 one picture, 2 sweeping from the previous one. The times are on the rain
    clock; end is when the picture is taken away again (-1: not yet)."""

    mode: int
    parity: int
    current_start: float
    previous_start: float
    end: float
    previous_end: float = -1.0  # gap mode: when the previous picture was taken away


IMAGE_OFF = ImageState(0, 0, 0.0, 0.0, -1.0)


def _box_blur_axis(values, radius, axis, edge_mode="edge"):
    """Box blur of width 2 * radius + 1 along one axis, by cumulative sums. Outside the array
    the edge value is repeated (edge_mode "edge") or zero is used ("constant")."""
    if radius < 1:
        return values
    pad = [(0, 0), (0, 0)]
    pad[axis] = (radius + 1, radius)
    sums = np.cumsum(np.pad(values, pad, mode=edge_mode), axis, dtype=np.float64)
    width = 2 * radius + 1
    if axis == 0:
        return (sums[width:] - sums[:-width]) / width
    return (sums[:, width:] - sums[:, :-width]) / width


def _box_blur(values, radius, edge_mode="edge"):
    """Box blur along both axes of a 2-D array (float32 result)."""
    if radius < 1:
        return values
    rows = _box_blur_axis(values, radius, 0, edge_mode)
    return _box_blur_axis(rows, radius, 1, edge_mode).astype(np.float32)


def _gaussian(values, sigma):
    """Gaussian-like blur: three box blurs of a radius matched to sigma."""
    radius = max(1, int(round(sigma * 0.9)))
    for _ in range(3):
        values = _box_blur(values, radius)
    return values


def _gray_surface(plane):
    """24-bit surface from a 2-D uint8 array (rows = y), without copying into three channels."""
    height, width = plane.shape
    return pygame.surfarray.make_surface(np.broadcast_to(plane.T[:, :, None], (width, height, 3)))


def _red_plane(surface):
    """The red channel of a surface as a 2-D uint8 array (rows = y)."""
    return np.ascontiguousarray(pygame.surfarray.pixels_red(surface).T)


def _wide_blur(values, factor=24):
    """Cheap wide blur: shrink by `factor` and scale back up (pygame smoothscale)."""
    height, width = values.shape
    small_size = (max(2, width // factor), max(2, height // factor))
    surface = _gray_surface((np.clip(values, 0, 1) * 255).astype(np.uint8))
    small = pygame.transform.smoothscale(surface, small_size)
    blurred = pygame.transform.smoothscale(small, (width, height))
    return _red_plane(blurred).astype(np.float32) / 255.0


def _flood(seed, passable):
    """Grow `seed` through 4-connected passable cells."""
    filled = seed & passable
    for _ in range(2 * sum(passable.shape)):
        grown = filled.copy()
        grown[1:, :] |= filled[:-1, :]
        grown[:-1, :] |= filled[1:, :]
        grown[:, 1:] |= filled[:, :-1]
        grown[:, :-1] |= filled[:, 1:]
        grown &= passable
        if np.array_equal(grown, filled):
            break
        filled = grown
    return filled


def _structure_mask(small):
    """True where the picture has structure rather than open sky. Fine detail (windows, lights,
    edges) is the smoothed difference from a blurred copy; `small` is float luminance."""
    detail = _gaussian(np.abs(small - _gaussian(small, 2.0)), 3.0)
    level = max(
        STRUCTURE_FLOOR, TUNING.sky_detail * float(np.percentile(detail, STRUCTURE_PERCENTILE))
    )
    return _box_blur((detail > level).astype(np.float32), 2) > 0.5


def _top_of_structure(structure):
    """Per column, the first structure row from the top as a fraction of the height."""
    height = structure.shape[0]
    return np.where(structure.any(0), structure.argmax(0), height) / height


def _line_support(cand_x, cand_y, voter_x, voter_y, line_x, line_y, weight):
    """How strongly each voter's line supports each candidate point, as (support, dx, dy).

    Support is the voter's weight, falling off with the sine of the angle by which its line
    misses the candidate. Voters closer than MIN_VOTE_DISTANCE to a candidate do not count."""
    dx = cand_x - voter_x
    dy = cand_y - voter_y
    distance = np.sqrt(dx * dx + dy * dy) + 1e-6
    miss = np.abs(dx * line_y - dy * line_x) / distance
    support = weight * np.exp(-((miss / LINE_TOLERANCE) ** 2)) * (distance > MIN_VOTE_DISTANCE)
    return support, dx, dy


def vanishing_point(lum):
    """Estimate the vanishing point of a uint8 luminance picture.

    Every strong, coherent, clearly diagonal edge (structure tensor on a 320 px copy) votes
    for the candidate points its line passes through. Confidence is 1 for a peak well inside
    the frame, falling to 0 at the border (an aerial shot or a flat illustration has no
    single vanishing point; the peak then sits on the edge), and also needs the supporting
    lines to come from many directions."""
    height, width = lum.shape
    step = max(1, max(height, width) // VANISHING_POINT_SIZE)
    small = lum[::step, ::step].astype(np.float32) / 255.0
    grad_y, grad_x = np.gradient(small)
    tensor_xx = _box_blur(grad_x * grad_x, 3, "constant")
    tensor_xy = _box_blur(grad_x * grad_y, 3, "constant")
    tensor_yy = _box_blur(grad_y * grad_y, 3, "constant")
    coherence = np.sqrt((tensor_xx - tensor_yy) ** 2 + 4.0 * tensor_xy**2) / (
        tensor_xx + tensor_yy + 1e-9
    )
    gradient_angle = 0.5 * np.arctan2(2.0 * tensor_xy, tensor_xx - tensor_yy)
    line_x, line_y = -np.sin(gradient_angle), np.cos(gradient_angle)
    # 0 for axis-aligned edges, 1 at 45 degrees
    diagonal = np.abs(np.sin(2.0 * gradient_angle))
    diagonal_share = np.clip((diagonal - DIAGONAL_MIN) / (DIAGONAL_FULL - DIAGONAL_MIN), 0.0, 1.0)
    edge_weight = np.sqrt(tensor_xx + tensor_yy) * coherence**2 * diagonal_share

    small_h, small_w = small.shape
    rows, cols = np.mgrid[0:small_h, 0:small_w]
    aspect = width / height
    keep = edge_weight > np.percentile(edge_weight, EDGE_PERCENTILE)
    strongest = np.argsort(-edge_weight[keep])[:MAX_VOTERS]
    voter_x = ((cols[keep] + 0.5) / small_w * aspect)[strongest]
    voter_y = ((rows[keep] + 0.5) / small_h)[strongest]
    voter_line_x, voter_line_y = line_x[keep][strongest], line_y[keep][strongest]
    voter_weight = edge_weight[keep][strongest]

    grid_x = np.linspace(
        -CANDIDATE_MARGIN * aspect, (1 + CANDIDATE_MARGIN) * aspect, CANDIDATE_GRID[0]
    )
    grid_y = np.linspace(-CANDIDATE_MARGIN, 1 + CANDIDATE_MARGIN, CANDIDATE_GRID[1])
    mesh_x, mesh_y = np.meshgrid(grid_x, grid_y)
    cand_x = mesh_x.ravel()[:, None]
    cand_y = mesh_y.ravel()[:, None]
    score = np.zeros(len(cand_x))
    for start in range(0, len(voter_x), VOTE_CHUNK):
        chunk = slice(start, start + VOTE_CHUNK)
        support, _, _ = _line_support(
            cand_x,
            cand_y,
            voter_x[None, chunk],
            voter_y[None, chunk],
            voter_line_x[None, chunk],
            voter_line_y[None, chunk],
            voter_weight[None, chunk],
        )
        score += support.sum(1)
    best_row, best_col = np.unravel_index(int(np.argmax(score)), mesh_y.shape)
    x, y = float(grid_x[best_col] / aspect), float(grid_y[best_row])
    border_distance = min(x, 1.0 - x, y, 1.0 - y)

    # A real vanishing point gathers lines from many directions; two crossing lines (a hill
    # side, a diagonal stroke in a logo) do not. Count the effective number of supporting
    # directions as the exponential of the entropy of their direction histogram.
    support, dx, dy = _line_support(
        grid_x[best_col],
        grid_y[best_row],
        voter_x,
        voter_y,
        voter_line_x,
        voter_line_y,
        voter_weight,
    )
    direction = np.mod(np.arctan2(dy, dx), np.pi)
    bins = np.minimum((direction / np.pi * DIRECTION_BINS).astype(int), DIRECTION_BINS - 1)
    histogram = np.bincount(bins, weights=support, minlength=DIRECTION_BINS)
    share = histogram / max(histogram.sum(), 1e-9)
    direction_count = float(np.exp(-np.sum(share[share > 0] * np.log(share[share > 0]))))
    direction_span = TUNING.vp_dirs_high - TUNING.vp_dirs_low
    confidence = float(
        np.clip(border_distance / BORDER_FADE, 0.0, 1.0)
        * np.clip((direction_count - TUNING.vp_dirs_low) / direction_span, 0.0, 1.0)
    )
    return VanishingPoint(x, y, confidence)


def horizon(small, sky_top):
    """Horizon (0..1 of the height) and confidence 0..1.

    The horizon is the long near-horizontal line just below the lowest sky (shore, water
    line, kerb) when there is one, otherwise how low the sky reaches. `small` is a small
    float luminance array and `sky_top` the first-structure row per column."""
    height, width = small.shape
    sky_columns = sky_top > 0.03
    if (
        sky_columns.mean() < TUNING.horizon_sky_share
        or np.median(sky_top[sky_columns]) < TUNING.horizon_sky_depth
    ):
        # no sky: a portrait, a comic panel, an aerial shot
        return 0.5, 0.0
    sky_bottom = float(np.percentile(sky_top[sky_columns], 85))
    grad_y = np.zeros_like(small)
    grad_y[1:-1] = (small[2:] - small[:-2]) * 0.5
    grad_x = np.zeros_like(small)
    grad_x[:, 1:-1] = (small[:, 2:] - small[:, :-2]) * 0.5
    horizontal = np.abs(grad_y) * (np.abs(grad_y) > 2.5 * np.abs(grad_x))
    strong = _box_blur((horizontal > np.percentile(horizontal, 90)).astype(np.float32), 2) > 0
    on = strong.astype(np.int8)
    edges = np.diff(np.pad(on, ((0, 0), (1, 1))), axis=1)
    longest_run = np.zeros(height)
    for row in range(height):
        starts = np.flatnonzero(edges[row] > 0)
        ends = np.flatnonzero(edges[row] < 0)
        if len(starts):
            longest_run[row] = (ends - starts).max() / width
    score = on.mean(1) * 0.5 + longest_run
    low, high = int(0.2 * height), int(0.92 * height)
    score[:low] = 0.0
    score[high:] = 0.0
    best_row = int(np.argmax(score))
    ratio = score[best_row] / max(float(np.median(score[low:high])), 1e-6)
    line_y = best_row / height
    if ratio >= TUNING.horizon_line_strength and sky_bottom - 0.03 <= line_y <= sky_bottom + 0.35:
        # a long line just below the lowest sky: shore or street edge
        return line_y, 1.0
    return sky_bottom, 1.0


def detail_of(cfg=None):
    """Image detail 0 (default sizes) to 1 (finest): MATRIX_IMAGE_DETAIL, else the
    image_detail setting."""
    value = os.environ.get("MATRIX_IMAGE_DETAIL")
    if value is None:
        value = (cfg or {}).get("image_detail", 0.0)
    try:
        return min(max(float(value), 0.0), 1.0)
    except TypeError, ValueError:
        return 0.0


def _finer(size, shrink, detail, cell_px):
    """Glyph size (rain cells) at image detail 0..1: shrinks toward size * shrink, never
    thinner than detail_min_px render pixels on the smallest rain cell (cell_px), never bigger
    than size."""
    result = size * (1.0 + (shrink - 1.0) * detail)
    if detail > 0.0 and cell_px > 0.0:
        result = max(result, TUNING.detail_min_px / cell_px)
    return min(result, size)


def depth_field(lum, vanishing, detail=0.0, cell_px=0.0):
    """Per-picture glyph size field: returns (glyph_size, horizon_y, mode).

    glyph_size[n, n] is the glyph height as a fraction of the rain cell at each picture
    point (small far away, large near the viewer); horizon_y is the horizon as 0..1 of the
    height; mode is 0 flat (no perspective found: portraits, comics, aerial shots), 1 depth
    field, 2 street canyon (no open sky but a confident vanishing point: the box grid).

    Each surface gets its own scale: ground and water below the horizon grow toward the viewer
    (size proportional to distance below the horizon); a structure standing above the horizon
    keeps one scale down to where it meets the ground, set by how high it reaches above the
    horizon (a near tower is bigger than the distant skyline; thin spires do not count).
    `lum` is uint8 luminance before the local lift."""
    tune = TUNING
    height, width = lum.shape
    step = max(1, max(height, width) // DEPTH_FIELD_SIZE)
    small = lum[::step, ::step].astype(np.float32) / 255.0
    small_h, small_w = small.shape
    sky_top = _top_of_structure(_structure_mask(small))
    horizon_y, horizon_confidence = horizon(small, sky_top)
    table = tune.field_size
    if horizon_confidence <= 0.0 or tune.field_on <= 0.0:
        # finer detail: smaller glyphs everywhere
        flat = _finer(tune.field_flat, tune.detail_flat, detail, cell_px)
        mode = 2 if vanishing.confidence > 0.5 else 0
        return np.full((table, table), flat, np.float32), 0.5, mode

    xs = (np.arange(table) + 0.5) / table
    ys = (np.arange(table) + 0.5) / table
    # finer detail: the far end shrinks most
    near = _finer(tune.field_near, tune.detail_near, detail, cell_px)
    far = _finer(tune.field_far, tune.detail_far, detail, cell_px)
    below_horizon = max(1.0 - horizon_y, 0.08)
    # ground and water grow toward the viewer
    ground = near * np.clip((ys - horizon_y) / below_horizon, 0.0, 1.0)[:, None]
    glyph_size = np.maximum(ground, far) * np.ones((1, table))
    # Where the first structure starts, per table column, ignoring spires and masts (70th
    # percentile over a sliding window), then smoothed.
    structure_top = np.interp(xs, (np.arange(small_w) + 0.5) / small_w, sky_top)
    half_window = max(1, table // 25)
    padded = np.pad(structure_top, half_window, mode="edge")
    structure_top = np.array(
        [np.percentile(padded[i : i + 2 * half_window + 1], 70) for i in range(table)]
    )
    structure_top = _box_blur(structure_top[None, :], half_window)[0]
    # standing structures keep one scale down to the ground
    tower_size = (
        tune.field_tower * near * np.clip((horizon_y - structure_top) / below_horizon, 0.0, None)
    )
    # the structure ends just below the horizon, so the water and ground in front keep
    # straight rows
    fade = np.clip(1.0 - (ys - horizon_y) / max(tune.field_tower_fade, 1e-3), 0.0, 1.0)[:, None]
    below_top = ys[:, None] > structure_top[None, :] - 0.02
    glyph_size = np.maximum(glyph_size, np.minimum(tower_size, near)[None, :] * below_top * fade)
    glyph_size = _gaussian(np.clip(glyph_size, far, near).astype(np.float32), table * 0.012)
    # sideways smoothing keeps the rows from waving between neighbours
    radius = int(table * tune.field_smooth * 0.9)
    if radius >= 1:
        for _ in range(3):
            glyph_size = _box_blur_axis(glyph_size, radius, 1).astype(np.float32)
    return glyph_size.astype(np.float32), horizon_y, 1


def field_tables(glyph_size, focus_x, focus_y, aspect):
    """Coordinate tables for the depth field: returns an RGB float32 array [n, n, 3] and
    (v_min, v_max).

    R is the row coordinate V, the integral of dy / size down each column from focus_y
    (picture heights). G is the column coordinate U, the integral of dx / size along each row
    of constant V from focus_x (the row index on the texture's y axis spans v_min..v_max). B is
    the glyph size itself. Rows and columns start at the horizon and the vanishing point, so
    where the glyphs shrink with depth their rows and columns run toward it, as on a receding
    surface."""
    rows, cols = glyph_size.shape
    ys = (np.arange(rows) + 0.5) / rows
    inverse = 1.0 / glyph_size
    row_coord = np.concatenate(
        [np.zeros((1, cols)), np.cumsum(0.5 * (inverse[1:] + inverse[:-1]), 0) / rows], 0
    )
    focus_row = np.clip(focus_y * rows - 0.5, 0, rows - 1)
    row_coord = (
        row_coord
        - np.array([np.interp(focus_row, np.arange(rows), row_coord[:, i]) for i in range(cols)])[
            None, :
        ]
    )
    v_min, v_max = float(row_coord.min()), float(row_coord.max())
    v_grid = np.linspace(v_min, v_max, rows)
    # glyph size along each row of constant V
    size_on_v = np.empty((rows, cols), np.float32)
    for i in range(cols):
        y_at_v = np.interp(v_grid, row_coord[:, i], ys)
        size_on_v[:, i] = np.interp(y_at_v, ys, glyph_size[:, i])
    inverse_across = aspect / size_on_v / cols
    col_coord = np.concatenate(
        [np.zeros((rows, 1)), np.cumsum(0.5 * (inverse_across[:, 1:] + inverse_across[:, :-1]), 1)],
        1,
    )
    focus_col = np.clip(focus_x * cols - 0.5, 0, cols - 1)
    col_coord = (
        col_coord
        - np.array([np.interp(focus_col, np.arange(cols), col_coord[j]) for j in range(rows)])[
            :, None
        ]
    )
    tables = np.stack([row_coord, col_coord, glyph_size], 2).astype(np.float32)
    return np.ascontiguousarray(tables), (v_min, v_max)


def local_lift(lum, amount):
    """Lift dark regions that have detail (shaded facades, faces in shadow, night scenes)
    toward their local contrast so the glyphs find their structure; bright smooth areas (sky,
    white backgrounds) are left alone. `lum` is float 0..1."""
    if amount <= 0.0:
        return lum
    mean = _wide_blur(lum)
    deviation = np.sqrt(np.maximum(_wide_blur(lum * lum) - mean * mean, 0.0))
    local = np.clip(0.5 + (lum - mean) / (2.5 * deviation + LOCAL_CONTRAST_SOFTEN), 0.0, 1.0)
    return np.clip(lum + amount * np.maximum(local - lum, 0.0) * (1.0 - mean), 0.0, 1.0)


def space_mask(lum):
    """1 where the picture is empty black connected to the frame edge (space round a ship, a black
    backdrop): the depth network reads it as near ground, so grid mode treats it as sky instead.
    Stars are too small to break it; a black cat's fur is not smooth enough to join it."""
    height, width = lum.shape
    step = max(1, max(height, width) // BACKGROUND_MASK_SIZE)
    small = lum[::step, ::step]
    mean = _wide_blur(small, 6)
    deviation = np.sqrt(np.maximum(_wide_blur(small * small, 6) - mean * mean, 0.0))
    open_pixel = (mean < TUNING.space_luminance) & (deviation < TUNING.space_flatness)
    border = np.zeros_like(open_pixel)
    border[0, :] = border[-1, :] = True
    border[:, 0] = border[:, -1] = True
    space = _flood(border, open_pixel)
    big = pygame.transform.smoothscale(_gray_surface(space.astype(np.uint8) * 255), (width, height))
    return _red_plane(big).astype(np.float32) / 255.0


def background_mask(lum):
    """1 where the picture is open background: bright, smooth and connected to the frame edge
    (sky, a white or pale studio backdrop). The glyphs leave it dark; bright smooth areas
    inside the picture (a face, a lit wall, a logo fill) keep their glyphs. `lum` is float
    0..1, full size."""
    height, width = lum.shape
    step = max(1, max(height, width) // BACKGROUND_MASK_SIZE)
    small = lum[::step, ::step]
    mean = _wide_blur(small, 6)
    deviation = np.sqrt(np.maximum(_wide_blur(small * small, 6) - mean * mean, 0.0))
    open_pixel = (small > TUNING.background_luminance) & (deviation < TUNING.background_flatness)
    border = np.zeros_like(open_pixel)
    border[0, :] = border[-1, :] = True
    border[:, 0] = border[:, -1] = True
    background = _flood(border, open_pixel)
    big = pygame.transform.smoothscale(
        _gray_surface(background.astype(np.uint8) * 255), (width, height)
    )
    return _red_plane(big).astype(np.float32) / 255.0


def _water_candidates(small, sky, horizon_y):
    """Water below the horizon: rows whose structure is mostly horizontal streaks (ripples), or
    that mirror what stands above the waterline (local correlation of the picture with its
    reflection). Returns a bool array, not yet closed up into bands."""
    rows_n, cols_n = small.shape
    blurred = _gaussian(small, 1.0)
    grad_x = np.zeros_like(blurred)
    grad_y = np.zeros_like(blurred)
    grad_x[:, 1:-1] = blurred[:, 2:] - blurred[:, :-2]
    grad_y[1:-1] = blurred[2:] - blurred[:-2]
    energy_x = _gaussian(grad_x * grad_x, 4.0)
    energy_y = _gaussian(grad_y * grad_y, 4.0)
    # 1: only horizontal streaks (ripples)
    streaks = energy_y / (energy_x + energy_y + 1e-6)
    row_index = np.arange(rows_n)
    best_score, mirror = -1.0, np.zeros_like(small)
    for offset in MIRROR_OFFSETS:
        waterline = int(round((horizon_y + offset) * rows_n))
        if waterline < 4 or waterline > rows_n - 4:
            continue
        source = np.clip(2 * waterline - row_index, 0, rows_n - 1)
        reflected = blurred[source]
        mean_a, mean_b = _gaussian(blurred, 3.0), _gaussian(reflected, 3.0)
        covariance = _gaussian(blurred * reflected, 3.0) - mean_a * mean_b
        var_a = np.maximum(_gaussian(blurred * blurred, 3.0) - mean_a * mean_a, 1e-5)
        var_b = np.maximum(_gaussian(reflected * reflected, 3.0) - mean_b * mean_b, 1e-5)
        correlation = (
            covariance
            / np.sqrt(var_a * var_b)
            * (row_index[:, None] > waterline)
            * (source[:, None] > 0)
        )
        score = float(correlation[waterline:].mean())
        if score > best_score:
            best_score, mirror = score, _gaussian(correlation, 4.0)
    below = (row_index / rows_n)[:, None] > horizon_y + 0.01
    candidate = below & ((streaks > TUNING.surface_water) | (mirror > 0.25)) & ~sky
    candidate = _box_blur(candidate.astype(np.float32), 3) > 0.5
    # water spans the frame
    row_share = np.repeat(candidate.mean(1, keepdims=True), cols_n, 1).astype(np.float32)
    coverage = _gaussian(row_share, 3.0)
    # mostly-water rows are water right across (reflected lights included)
    water = (candidate & (coverage > 0.45)) | (below & (coverage > 0.6))
    # close small holes
    return _box_blur(water.astype(np.float32), 4) > 0.35


def open_regions(small):
    """Low-information regions that carry no surface coat: returns (sky, water) bool arrays
    for a small float luminance array.

    Sky has no fine detail and is reached from the top edge (smooth ramps, sunset glow), plus
    detail islands that float in it without touching structure that reaches the ground
    (clouds, birds, the moon). Water is below the horizon, where the structure is mostly
    horizontal streaks (ripples, reflections)."""
    rows_n, cols_n = small.shape
    structure = _structure_mask(small)
    seed = np.zeros_like(structure)
    seed[0, :] = True
    sky = _flood(seed, ~structure)
    no_water = np.zeros_like(sky)
    if not sky.any():
        return sky, no_water
    # structure reaching the bottom or the lower sides
    seed = np.zeros_like(structure)
    seed[-1, :] = True
    seed[:, 0] = seed[:, -1] = True
    seed[: max(1, rows_n // 3)] = False
    ground = _flood(seed & ~sky, ~sky)
    # floating islands join the sky
    sky = sky | ~ground
    if TUNING.surface_water <= 0.0:
        return sky, no_water
    horizon_y, horizon_confidence = horizon(small, _top_of_structure(~sky))
    if horizon_confidence <= 0.0:
        return sky, no_water
    water = _water_candidates(small, sky, horizon_y)
    # close gaps across a row (pillars of reflected light)
    radius = max(1, int(cols_n * 0.05))
    widened = _box_blur_axis(water.astype(np.float32), radius, 1) > 0.0
    water = _box_blur_axis(widened.astype(np.float32), radius, 1) > 0.999
    # bands between water are water too
    water = np.maximum.accumulate(water, 0) & np.maximum.accumulate(water[::-1], 0)[::-1]
    water &= ~sky
    return sky, water


def surface_tone(lum):
    """Returns (tone, open_mask), both uint8 and full size.

    tone is how lit each surface is, part global and part relative to its wide surroundings
    (surface_local), so a shaded facade beside a lit one still reads as a surface. open_mask
    is 255 for sky and 191 for water (see open_regions); those carry no surface coat and only
    strong edges. Worked out at about 384 px."""
    tune = TUNING
    height, width = lum.shape
    step = max(1, max(height, width) // SURFACE_TONE_SIZE)
    small_w, small_h = max(2, width // step), max(2, height // step)
    scaled = pygame.transform.smoothscale(
        _gray_surface((lum * 255).astype(np.uint8)), (small_w, small_h)
    )
    small = _red_plane(scaled).astype(np.float32) / 255.0
    sigma = max(small_w, small_h) * SURFACE_SCALE_SHARE
    mean = _gaussian(small, sigma)
    deviation = np.sqrt(np.maximum(_gaussian(small * small, sigma) - mean * mean, 0.0))
    relative = np.clip(0.5 + (small - mean) / (2.5 * deviation + LOCAL_CONTRAST_SOFTEN), 0.0, 1.0)
    tone = (1.0 - tune.surface_local) * np.power(
        small, tune.surface_gamma
    ) + tune.surface_local * relative
    if tune.surface_sky > 0.0:
        sky, water = open_regions(small)
        open_value = np.where(sky, 1.0, np.where(water, WATER_TONE, 0.0)).astype(np.float32)
    else:
        open_value = np.zeros_like(small)
    packed = np.stack([tone, open_value, open_value], 2)
    surface = pygame.surfarray.make_surface(
        (np.clip(packed, 0, 1) * 255).astype(np.uint8).transpose(1, 0, 2)
    )
    big = pygame.transform.smoothscale(surface, (width, height))
    return _red_plane(big), np.ascontiguousarray(pygame.surfarray.pixels_green(big).T)


def folder(cfg=None):
    """The images folder: the image_dir setting, else MATRIX_IMAGE_DIR. None (layer off) for an
    empty setting or a missing folder. Only a config without the image_dir key at all falls
    back to the pictures that ship with the saver, when there are any."""
    cfg = cfg or {}
    chosen = cfg.get("image_dir") or os.environ.get("MATRIX_IMAGE_DIR", "")
    if chosen:
        # a folder that is gone means off, never the bundled pictures
        return chosen if os.path.isdir(chosen) else None
    if "image_dir" in cfg:
        return None
    shipped = resources.asset_path("images")
    if os.path.isdir(shipped) and any(
        name.lower().endswith(IMAGE_EXTENSIONS) for name in os.listdir(shipped)
    ):
        return shipped
    return None


def _skipped_folder(entry):
    """Hidden, system, linked or package folders are not searched for pictures."""
    name = entry.name
    if name.startswith(".") or name.lower() in SKIPPED_FOLDERS:
        return True
    if name.lower().endswith(SKIPPED_FOLDER_SUFFIXES):
        return True
    try:
        if not entry.is_dir(follow_symlinks=False) or entry.is_junction():
            return True  # links and junctions could loop back up the tree
        info = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    hidden = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0) | getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 0)
    if getattr(info, "st_file_attributes", 0) & hidden:
        return True
    return bool(getattr(info, "st_flags", 0) & getattr(stat, "UF_HIDDEN", 0))


def list_images(path, subfolders=False):
    """The picture files of folder `path` in name order. With `subfolders`, also those of every
    folder inside it, each folder's own pictures before its subfolders', within the limits above
    (depth, picture and folder counts, time); hidden and system folders are skipped."""
    found = []
    folders = 0
    deadline = time.monotonic() + LISTING_SECONDS

    def walk(folder, depth):
        nonlocal folders
        folders += 1
        try:
            with os.scandir(folder) as listing:
                entries = sorted(listing, key=lambda e: e.name)
        except OSError:
            return
        for entry in entries:
            if len(found) >= MAX_PICTURES:
                return
            if entry.name.lower().endswith(IMAGE_EXTENSIONS) and _is_file(entry):
                found.append(entry.path)
        if not subfolders or depth >= MAX_FOLDER_DEPTH:
            return
        for entry in entries:
            if len(found) >= MAX_PICTURES or folders >= MAX_FOLDERS:
                return
            if time.monotonic() > deadline:
                return
            if not _skipped_folder(entry):
                walk(entry.path, depth + 1)

    walk(path, 0)
    return found


def _is_file(entry):
    try:
        return entry.is_file()
    except OSError:
        return False


def _image_size(path):
    """(width, height) read from the file header (PNG, BMP, JPEG, WebP), or None when unknown.
    Reads a few KB at most. Stored size: an EXIF orientation tag is not applied."""
    try:
        with open(path, "rb") as stream:
            head = stream.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", head[16:24])
            if head[:2] == b"BM":
                width, height = struct.unpack("<ii", head[18:26])
                return abs(width), abs(height)
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                return _webp_size(head)
            if head[:2] == b"\xff\xd8":
                return _jpeg_size(stream)
    except OSError, struct.error:
        pass
    return None


def _webp_size(head):
    """Size from the first 30 bytes of a WebP file, or None for an unknown variant."""
    kind = head[12:16]
    if kind == b"VP8X":
        return (
            int.from_bytes(head[24:27], "little") + 1,
            int.from_bytes(head[27:30], "little") + 1,
        )
    if kind == b"VP8L":
        packed = int.from_bytes(head[21:25], "little")
        return (packed & 0x3FFF) + 1, ((packed >> 14) & 0x3FFF) + 1
    if kind == b"VP8 ":
        width, height = struct.unpack("<HH", head[26:30])
        return width & 0x3FFF, height & 0x3FFF
    return None


# JPEG start-of-frame markers, which carry the picture size.
JPEG_FRAME_MARKERS = (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF)


def _jpeg_size(stream):
    """Size of a JPEG, walking its segments from the start; None if the header is damaged."""
    stream.seek(2)
    while True:
        marker = stream.read(4)
        if len(marker) < 4 or marker[0] != 0xFF:
            return None
        if marker[1] in JPEG_FRAME_MARKERS:
            frame = stream.read(5)
            return struct.unpack(">HH", frame[1:5])[::-1]
        stream.seek(struct.unpack(">H", marker[2:4])[0] - 2, 1)


def load_rgb(path, max_size):
    """Decode a picture no bigger than max_size on its long side -> uint8 array (h, w, 3).

    With PIL a JPEG is decoded downscaled (draft mode) and any picture is shrunk with
    thumbnail(). Without it pygame decodes the picture, once the header says the pixel count
    is sane. Raises on a corrupt file or one over the pixel budget."""
    try:
        from PIL import Image  # optional: only makes huge pictures cheaper to decode
    except ImportError:
        return _load_rgb_with_pygame(path, max_size)
    with Image.open(path) as picture:
        if picture.format == "JPEG":
            # decodes at 1/2, 1/4 or 1/8 size
            picture.draft("RGB", (max_size, max_size))
        elif picture.width * picture.height > TUNING.max_pixels:
            raise ValueError("picture too large (%dx%d)" % picture.size)
        if max(picture.size) > max_size:
            picture.thumbnail((max_size, max_size))
        # phone cameras store the sensor's orientation and a tag saying how to turn it upright
        picture = _upright(picture)
        return np.asarray(picture.convert("RGB"), np.uint8)


def _upright(picture):
    """The picture turned the way its EXIF orientation tag says (portrait and upside-down phone
    photos); unchanged without the tag or when it cannot be read."""
    try:
        from PIL import ImageOps

        return ImageOps.exif_transpose(picture) or picture
    except Exception:  # a broken tag must cost the rotation, never the picture
        return picture


def _load_rgb_with_pygame(path, max_size):
    """load_rgb without PIL."""
    size = _image_size(path)
    if size is not None and size[0] * size[1] > TUNING.max_pixels:
        raise ValueError("picture too large (%dx%d)" % size)
    surface = pygame.image.load(path)
    width, height = surface.get_size()
    if max(width, height) > max_size:
        scale = max_size / max(width, height)
        surface = pygame.transform.smoothscale(
            surface, (max(1, int(width * scale)), max(1, int(height * scale)))
        )
        width, height = surface.get_size()
    return np.frombuffer(pygame.image.tobytes(surface, "RGB"), np.uint8).reshape(height, width, 3)


def _submit(function, *args):
    """Run function(*args) on a daemon thread -> Future. A daemon thread never keeps the process
    alive: a worker stuck in a huge decode must not hold the saver open on exit."""
    future = concurrent.futures.Future()

    def work():
        try:
            future.set_result(function(*args))
        except BaseException as exc:  # MemoryError included: a failed picture, not a dead thread
            future.set_exception(exc)

    threading.Thread(target=work, daemon=True, name="image-prepare").start()
    return future


def _load_luminance(path, max_size):
    """Decode a picture to a float luminance array 0..1, stretched to full range."""
    rgb = load_rgb(path, max_size)
    lum = rgb @ np.array(LUMA_WEIGHTS, np.float32)
    low, high = np.percentile(lum, STRETCH_PERCENTILES)
    return np.clip((lum - low) / max(high - low, 1.0), 0.0, 1.0)


# grid mode: a picture narrower than this (portrait, square) is shown whole on black sides, padded
# to FRAME_ASPECT, instead of cropped to the screen (which cuts a portrait's heads off)
PAD_BELOW_ASPECT = 1.2
FRAME_ASPECT = 16.0 / 9.0


def pad_columns(width, height):
    """(left, right) black columns that widen a picture of this size to FRAME_ASPECT, or (0, 0)."""
    if width >= height * PAD_BELOW_ASPECT:
        return 0, 0
    extra = max(0, round(height * FRAME_ASPECT) - width)
    return extra // 2, extra - extra // 2


def pad_sides(plane, fill=0.0):
    """A 2-D plane widened with `fill` columns per pad_columns."""
    left, right = pad_columns(plane.shape[1], plane.shape[0])
    if left + right == 0:
        return plane
    return np.pad(plane, ((0, 0), (left, right)), constant_values=fill)


def _detect_surfaces(path, pad=False):
    """surfaces.lookup, or None: a detector failure must cost the picture its perspective,
    never the picture."""
    try:
        return surfaces.lookup(path, pad_sides if pad else None)
    except Exception as exc:
        print("image layer: no surfaces for %s (%s)" % (os.path.basename(path), exc))
        return None



def analyse(path, max_size, detail, cell_px, detect=False):
    """Decode and analyse one picture on the CPU. The texture packs luminance (R), open
    background (G), surface tone (B) and dark open background (A). With `detect` (grid mode) the
    floor, walls and vanishing point come from surfaces.py when it has them for this picture
    (cached disparity map), and the picture also carries a label map; without them the
    luminance-only analysis below is used."""
    tune = TUNING
    lum = _load_luminance(path, max_size)
    if detect:
        lum = pad_sides(lum)
    height, width = lum.shape
    background = (background_mask(lum) * 255.0).astype(np.uint8)
    tone, dark_open = surface_tone(lum)
    raw = (lum * 255.0).astype(np.uint8)
    lifted = (local_lift(lum, tune.local_lift) * 255.0).astype(np.uint8)
    vanishing = vanishing_point(lifted)
    glyph_size, horizon_y, mode = depth_field(raw, vanishing, detail, cell_px)
    if tune.field_on <= 0.0 and mode != 2:
        # depth field off: the older octave grids
        mode = -1
    if mode != 2:
        # the box grid only for a street canyon
        vanishing = VanishingPoint(vanishing.x, vanishing.y, 0.0)
    tables, (v_min, v_max) = field_tables(
        glyph_size, vanishing.x if mode == 2 else 0.5, horizon_y, width / height
    )
    labels = NO_LABELS
    found = _detect_surfaces(path, pad=True) if detect else None
    if found is not None:
        h, w = found.labels.shape
        # sky and open background stay dark: flat bright background, or infinity on the depth map
        # black on a fitted wall is a building in shadow, not space
        walls = np.isin(found.labels, (surfaces.WALL_LEFT, surfaces.WALL_RIGHT))
        space = surfaces._resize(space_mask(lum), h, w) * ~walls
        flat = surfaces._resize(background / 255.0, h, w)
        lo, hi = tune.grid_flat_far_lo, tune.grid_flat_far_hi
        if hi > lo:
            flat = flat * np.clip((hi - found.depth) / (hi - lo), 0.0, 1.0)
        near = None
        if tune.grid_subject > 0.0:
            # what stands out in front (a person) is never flat backdrop, however plain its hair
            near = surfaces.subject_mask(found.depth, np.maximum(space, surfaces.sky_mask(found)))
            flat = flat * (1.0 - near)
        open_area = np.maximum(np.maximum(flat, space), surfaces.sky_mask(found))
        # grown up to the subject's edge, or a strip of false ground is left round it (and outlined)
        open_area = surfaces.grow_open(open_area, surfaces._resize(np.clip(lum, 0.0, 1.0), h, w))
        # open area is at infinity whatever the depth network made of it (it reads black space as
        # ground)
        found = found._replace(depth=found.depth * (1.0 - open_area))
        if near is not None:
            near = near * (1.0 - open_area)
            if tune.grid_subject_front > 0.0:
                planes = found.labels != surfaces.FRONT
                found = found._replace(
                    labels=np.where(planes & (near > 0.5), surfaces.FRONT, found.labels).astype(
                        found.labels.dtype
                    )
                )
        if tune.grid_tone_res > max(h, w):
            found = surfaces.refine(found, tune.grid_tone_res)
            h, w = found.labels.shape
            open_area = surfaces._resize(open_area, h, w)
            near = None if near is None else surfaces._resize(near, h, w)
        if tune.grid_own > 0.0:
            ctone = surfaces.own_light_tone(
                lum,
                (h, w),
                open_area,
                tune.grid_body,
                tune.grid_own_gamma,
                tune.grid_highlight,
                tune.grid_rim,
                tune.grid_own_blur,
                near,
                tune.grid_subject_body,
                tune.grid_subject_gamma,
                tune.grid_subject_contrast,
                tune.grid_behind,
            )
        else:
            ctone = surfaces.coarse_tone(lum, (h, w), open_mask=open_area)
        confident = surfaces.confident_box(found)
        if confident:
            # a wall or floor patch on the wrong side of the vanishing point would fan the wrong way
            found = surfaces.on_side(found)
        rain = surfaces.rain_mask(found, tune.grid_drip)
        labels = PreparedLabels(w, h, surfaces.label_texels(found, ctone, rain).tobytes())
        if found.vanishing is not None:
            vanishing = VanishingPoint(*found.vanishing)
        if not confident:
            # mostly one object facing the viewer, or a box with only a guessed vanishing point: no
            # floor or wall fans, the flat passes draw it all
            vanishing = VanishingPoint(vanishing.x, vanishing.y, 0.0)
        elif found.camera == surfaces.CAMERA_UP:
            # looking up: the shader streams radially out of this point, toward the camera
            vanishing = VanishingPoint(
                vanishing.x, vanishing.y, vanishing.confidence + CAMERA_UP_FLAG
            )
    texels = np.ascontiguousarray(np.stack([lifted, background, tone, dark_open], 2)).tobytes()
    field = PreparedField(
        glyph_size.shape[1],
        glyph_size.shape[0],
        tables.tobytes(),
        FieldInfo(v_min, v_max, float(mode), float(glyph_size.min())),
    )
    return PreparedImage(width, height, texels, vanishing, field, labels)


class ImageLayer:
    """Pictures are decoded and analysed on a worker thread, one or two ahead, and uploaded to
    the GPU on the main thread only when ready: a big folder must never block the first frame
    (Windows flags a saver that does not answer for a few seconds as hung and closes it).
    MATRIX_IMAGE_SYNC=1 prepares them inline instead (frame harness, checks)."""

    def __init__(self, ctx, path, max_size=4096, cfg=None):
        cfg = cfg or {}
        self.ctx = ctx
        self.max_size = max_size
        if "MATRIX_IMAGE_PERIOD" in os.environ:
            self.period = TUNING.period
        else:
            self.period = float(cfg.get("image_period", TUNING.period))
        # plain rain between pictures, on top of the period: a picture is held for `period`
        # seconds from its start, the rain then takes it away and rests, and the next picture
        # starts `gap` seconds after the removal began
        self.gap = max(0.0, float(cfg.get("image_gap", 0.0)))
        self.cycle = self.period + self.gap
        self.shuffle = cfg.get("image_order", "sequence") == "shuffle"
        # 0 keeps the default glyph sizes, 1 the finest (smaller far glyphs, thinner floor)
        self.detail = detail_of(cfg)
        # smallest rain cell height in render px, set by the renderer (0: unknown, no floor)
        self.cell_px = 0.0
        self.rng = random.Random()
        self.files = list_images(path, bool(cfg.get("image_subfolders", False)))
        if not self.files:
            raise ValueError("no images in " + path)
        self.sync = os.environ.get("MATRIX_IMAGE_SYNC", "0") == "1"
        # picture index -> future of its prepared data (at most one still running)
        self.jobs = {}
        # picture -> [prepared image, texture or None, mipmaps built]: upload in steps
        self.staged = {}
        # picture indexes that failed to load: never shown again
        self.bad = set()
        # every picture failed: the layer is off
        self.dead = False
        # Uploaded pictures and depth fields by picture index; only the current and the
        # previous one stay.
        self.textures_by_pic = {}
        self.sizes = {}
        self.vanishing_points = {}
        self.fields_by_pic = {}
        self.labels_by_pic = {}
        self.detect = cfg.get("image_mode", "classic") == "grid"
        self.number = -1  # index of the current image in the show order
        self.order = []  # picture index of the n-th image shown
        # rain-clock start of the current image, then the previous
        self.starts = []
        self.started_at = 0.0  # real time the current image started
        self.end = -1.0  # rain-clock end of the current image (gap mode)
        self.previous_end = -1.0  # rain-clock end of the previous image (gap mode)
        self.last_state = IMAGE_OFF
        # depth: pictures the network has finished with (cached or failed), the picture to do
        # next whatever the order, and when each picture was first wanted
        self.depth_done = set()
        self.depth_next = None
        self.depth_asked = {}
        self.warming = False
        if self.detect and surfaces.can_estimate():
            # the network runs on its own low-priority thread, one picture at a time over the
            # whole folder, and only fills the disk cache. A picture waits for its entry up to
            # TUNING.depth_wait (see _want), then is drawn by the older detector and fake depth.
            # Started last: it reads self.number.
            self.warming = True
            threading.Thread(target=self._warm, daemon=True, name="image-surfaces").start()

    def _warm(self):
        """Cache the depth map of every picture: one a preparation is waiting for first, then
        the next ones to be shown."""
        try:
            while not self.dead:
                start = max(self.number, 0)
                order = [self._pic_for_warm(start + k) for k in range(len(self.files))]
                waiting = self.depth_next
                if waiting is not None:
                    order.insert(0, waiting)
                todo = [pic for pic in order if pic not in self.depth_done]
                if not todo:
                    return
                pic = todo[0]
                try:
                    surfaces.fill_cache(self.files[pic], load_rgb)
                except Exception as exc:  # one bad picture must not stop the rest
                    name = os.path.basename(self.files[pic])
                    print("image layer: no depth for %s (%s)" % (name, exc))
                self.depth_done.add(pic)
        finally:
            # nothing more is coming: no preparation waits any longer
            self.warming = False

    def _depth_pending(self, pic):
        """True while picture `pic` should wait for its depth map: the network is running, has
        not finished with it, and it has waited less than TUNING.depth_wait. Synchronous layers
        (tests, frame checks) never wait."""
        if self.sync or not self.warming or pic in self.depth_done:
            return False
        asked = self.depth_asked.setdefault(pic, time.monotonic())
        if time.monotonic() - asked >= TUNING.depth_wait:
            return False
        self.depth_next = pic
        return True

    def _pic_for_warm(self, number):
        """Picture index of show position `number` (sequence order; a shuffled show only
        loses a little head start)."""
        return number % len(self.files)

    def close(self):
        """Release the GPU textures and forget pending work (a daemon worker may finish on its
        own)."""
        for pic in list(self.textures_by_pic):
            self._release(pic)
        self.jobs.clear()
        self.dead = True

    def _release(self, pic):
        self.textures_by_pic.pop(pic).release()
        self.fields_by_pic.pop(pic)[0].release()
        self.labels_by_pic.pop(pic).release()
        self.sizes.pop(pic)
        self.vanishing_points.pop(pic)

    def _prepare(self, pic):
        return analyse(self.files[pic], self.max_size, self.detail, self.cell_px, self.detect)

    def _want(self, pic):
        """Start preparing picture `pic` if nobody has."""
        # staged: prepared and part uploaded; without this a second job prepared it again
        if pic in self.textures_by_pic or pic in self.staged or pic in self.jobs or pic in self.bad:
            return
        if any(not future.done() for future in self.jobs.values()):
            # one preparation at a time: a slow disk must not pile up jobs
            return
        if self._depth_pending(pic):
            # its depth map is on the way (the first run loads the network): plain rain a few
            # seconds longer beats a picture drawn without depth for its whole period
            return
        if self.sync:
            future = concurrent.futures.Future()
            try:
                future.set_result(self._prepare(pic))
            except Exception as exc:
                # kept on the future and re-raised by result() in _ready
                future.set_exception(exc)
            self.jobs[pic] = future
        else:
            self.jobs[pic] = _submit(self._prepare, pic)

    def _ready(self, pic):
        """True once picture `pic` is on the GPU. Uploads it here, on the main thread, when its
        data is done. False while it is still being prepared; None when it failed (it is then
        marked bad, see _fail)."""
        if pic in self.textures_by_pic:
            return True
        if pic in self.staged:
            return self._upload_step(pic) or (self.sync and self._ready(pic))
        self._want(pic)
        future = self.jobs.get(pic)
        if future is None or not future.done():
            return False
        del self.jobs[pic]
        try:
            image = future.result()
        except Exception as exc:  # corrupt, unreadable or too large: drop this picture only
            self._fail(pic, exc)
            return None
        self.staged[pic] = [image, None, False]
        # synchronous layers (tests, frame checks) finish the upload at once
        return self._ready(pic)

    def _upload_step(self, pic):
        """One step of the upload of a prepared picture, so no single frame carries all of it (the
        texture upload and mipmaps alone cost 30 to 60 ms on a large picture). True once done."""
        image, texture, mips = self.staged[pic]
        if texture is None:
            # row 0 is the top, as the shaders sample (top-left origin)
            texture = self.ctx.texture((image.width, image.height), 4, image.texels)
            self.staged[pic][1] = texture
            return False
        if not mips:
            texture.build_mipmaps()
            texture.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
            texture.anisotropy = 8.0
            texture.repeat_x = texture.repeat_y = False
            self.staged[pic][2] = True
            return False
        field = image.field
        field_texture = self.ctx.texture((field.width, field.height), 3, field.data, dtype="f4")
        field_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        field_texture.repeat_x = field_texture.repeat_y = False
        label = image.labels
        label_texture = self.ctx.texture((label.width, label.height), label.components, label.data)
        label_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        label_texture.repeat_x = label_texture.repeat_y = False
        self.labels_by_pic[pic] = label_texture
        self.textures_by_pic[pic] = texture
        self.sizes[pic] = (float(image.width), float(image.height))
        self.vanishing_points[pic] = image.vanishing_point
        self.fields_by_pic[pic] = (field_texture, field.info)
        del self.staged[pic]
        return True

    def _fail(self, pic, exc):
        """Picture `pic` cannot be used: skip it from now on. The layer is dead when none is
        left."""
        self.bad.add(pic)
        print("image layer: skipping %s (%s)" % (os.path.basename(self.files[pic]), exc))
        # the pictures already shown stay; the rest of the order is planned again
        self.order = self.order[: self.number + 1]
        if len(self.bad) >= len(self.files):
            self.dead = True
            print("image layer off: no usable pictures")

    def _pic(self, number):
        """Picture index of image `number`: in sequence, or shuffled a round at a time (no
        repeat across rounds)."""
        usable = [pic for pic in range(len(self.files)) if pic not in self.bad] or [0]
        count = len(usable)
        while len(self.order) <= number:
            if self.shuffle:
                round_order = list(usable)
                self.rng.shuffle(round_order)
                if count > 1 and self.order and round_order[0] == self.order[-1]:
                    round_order[0], round_order[-1] = round_order[-1], round_order[0]
                self.order += round_order
            else:
                self.order.append(usable[len(self.order) % count])
        return self.order[number]

    def update(self, t, rain_offset):
        """Advance the show to time `t` and return the ImageState.

        A new image starts only once its data is ready; until then the old state carries on."""
        if t < TUNING.start or self.dead:
            return IMAGE_OFF
        target = int(math.floor((t - TUNING.start) / self.cycle))
        wanted = {self._pic(target), self._pic(self.number + 1)}
        for pic in [
            pic for pic, future in self.jobs.items() if pic not in wanted and future.done()
        ]:
            # finished but no longer wanted (a clock jump, a skipped picture)
            del self.jobs[pic]
        if target > self.number:
            if not self._ready(self._pic(target)):
                return IMAGE_OFF if self.dead else self.last_state
            self.number = target
            self.started_at = t
            # gap mode: the previous picture stays while its exit runs on (slow lanes can still hold
            # it when the next one starts; dropping it then changed all of them in one frame)
            carry = self.gap <= 0.0 or self.end >= 0.0
            self.previous_end = self.end if self.gap > 0.0 else -1.0
            self.end = -1.0
            self.starts = [t + rain_offset] + (self.starts[:1] if carry else [])
            keep = {self._pic(target), self._pic(max(target - 1, 0)), self._pic(target + 1)}
            for pic in [pic for pic in self.textures_by_pic if pic not in keep]:
                self._release(pic)
        if self.number < 0:
            return IMAGE_OFF
        # the next picture is decoded while this one shows
        following = self._pic(self.number + 1)
        self._want(following)
        if following in self.staged or (following in self.jobs and self.jobs[following].done()):
            self._ready(following)   # one upload step per frame while the current picture shows
        if self.gap > 0.0 and self.end < 0.0 and t >= self.started_at + self.period:
            # the rain takes the picture away, then rests until the next one
            self.end = t + rain_offset
        mode = 2 if len(self.starts) == 2 else 1
        previous = self.starts[1] if mode == 2 else 0.0
        self.last_state = ImageState(
            mode, self.number % 2, self.starts[0], previous, self.end,
            self.previous_end if mode == 2 else -1.0,
        )
        return self.last_state

    def _channel_pictures(self):
        """Picture indices for texture channels 0 and 1: the current and previous picture,
        swapped on odd images so each picture keeps its channel while it sweeps."""
        number = max(self.number, 0)
        current = self._pic(number)
        previous = self._pic(number - 1) if number > 0 else current
        if previous not in self.textures_by_pic:
            previous = current
        return (current, previous) if number % 2 == 0 else (previous, current)

    def detail_uniforms(self):
        """Returns ((octave cell fractions), (thinnest glyph px of the octave and box grids,
        of the depth field)) for the current image detail."""
        tune = TUNING
        far = 1.0 + (tune.detail_far - 1.0) * self.detail
        octaves = (tune.octave_near, tune.octave_mid * math.sqrt(far), tune.octave_far * far)
        return octaves, (5.0 + (tune.detail_min_px - 5.0) * self.detail, 0.0)

    def textures(self):
        """(texture 0, texture 1, size 0, size 1, vanishing point 0, vanishing point 1)."""
        a, b = self._channel_pictures()
        return (
            self.textures_by_pic[a],
            self.textures_by_pic[b],
            self.sizes[a],
            self.sizes[b],
            self.vanishing_points[a],
            self.vanishing_points[b],
        )

    def fields(self):
        """(depth field texture 0, texture 1, field info 0, info 1)."""
        a, b = self._channel_pictures()
        return (
            self.fields_by_pic[a][0],
            self.fields_by_pic[b][0],
            self.fields_by_pic[a][1],
            self.fields_by_pic[b][1],
        )

    def label_textures(self):
        """(surface label texture 0, texture 1), by channel like textures()."""
        a, b = self._channel_pictures()
        return self.labels_by_pic[a], self.labels_by_pic[b]

