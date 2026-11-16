"""Surface detection for the picture layer: which parts of a photograph are a floor, a wall or
a ceiling, and where the walls and the floor converge.

The picture layer's grid mode draws a corridor out of a photograph (walls and floor in
perspective, everything else flat). That needs a label for every part of the picture, which a
plain image cannot give. A monocular depth network (Depth Anything V2 Small, Apache 2.0) gives a
relative disparity map; on a flat surface disparity is an affine function of the image
coordinates, so sequential RANSAC finds the planes and the sign of each plane's gradient says
what it is. Anything that does not sit on a plane (a phone box, a cat, a chair, the sky) is
labelled frontal and drawn flat. The detector is plain numpy and takes the disparity map.

Packaging: Windows bundles the quantised ONNX model (assets/models) and onnxruntime, macOS a
Core ML conversion. The saver runs the network on a worker thread the first time it shows a
picture and caches the disparity map (a small .npz in `cache_dir()`), so each picture is analysed
once. Where neither network can run, `tools/dev/surface_cache.py` can fill the cache from another
Python; a picture with no cache entry is drawn by the older vanishing-point and depth-class path.
"""

import hashlib
import os
from typing import NamedTuple

import numpy as np

from digital_rain import osapi, resources

# Label codes, as written to the label texture (see FRONT .. CEILING and CODE_STEP).
FRONT, WALL_LEFT, WALL_RIGHT, FLOOR, CEILING = range(5)
KIND_NAMES = ("front", "wall left", "wall right", "floor", "ceiling")
CODE_STEP = 50  # label texture value = kind * CODE_STEP; 255 means "no detection"
NO_DETECTION = 255

DISPARITY_SIZE = 256  # long side of the cached disparity map and of the label map
NETWORK_THREADS = 1
MODEL_SIZE = 518  # the network's square input
PLANE_GRID = 96  # planes are found on this many points across and down
PLANE_TOLERANCE = 0.035  # disparity (0..1) a point may be off a plane and still be on it
LABEL_TOLERANCE = 1.5  # ... in units of the tolerance, when labelling every pixel
MAX_PLANES = 7
MIN_PLANE_SHARE = 0.05  # a plane needs this share of the points
RANSAC_TRIES = 1500
FRONTAL_SLOPE = 0.25  # |gradient| below this on both axes: faces the viewer
SLOPE_RATIO = 1.6  # one gradient axis this much steeper than the other classifies the plane
MIN_LINE_SLOPE = 0.15  # plane pairs whose gradients differ less than this meet in no usable line
VP_MARGIN = 0.6  # the vanishing point may lie this far outside the frame
VP_MAX_RMS = 0.06  # distance of the plane meeting lines from the vanishing point (picture shares)
VP_MIN_ANGLE = 0.25  # sine of the smallest angle between two meeting lines that fixes a point
SMOOTH_PASSES = 2
HORIZON_LOW, HORIZON_HIGH = 0.2, 0.8  # a guessed horizon stays in this band of the picture
ESTIMATE_CONFIDENCE = 0.55  # a vanishing point placed along one line, not fixed by two
# a perspective box (floor, walls, ceiling) needs this share of the picture on its surfaces; a
# picture that is mostly one object facing the viewer (a ship, a cat) has none, whatever the point
# found
MIN_BOX_SHARE = 0.5
# the fans also need the box to be sure of where it recedes: a vanishing point fixed by two meeting
# lines, the camera looking up, or a corridor (each side wall on this share of the picture). A box
# with only a guessed point (a patio under a table, a floor round a person) draws no fans.
CORRIDOR_WALL_SHARE = 0.2
# ... and the main wall plane on each side of a corridor must recede at least this steeply
# (disparity across the picture's width): a depth ramp the network makes of a graphic, a
# portrait's backdrop or a helmet is shallower than a real side wall
CORRIDOR_MIN_SLOPE = 0.8
# every box: at least this share of its surface labels on their own side of the vanishing point (a
# left wall left of it, a floor below it ...): surfaces that disagree with the point are not one box
MIN_SIDE_SHARE = 0.84
# a box has a wall: at least this share of the picture on the bigger side wall (a floor and a
# backdrop alone are a car or a landscape, not a street)
MIN_WALL_SHARE = 0.2
# ... and at most this share of ceiling (the shader draws no ceiling fans; a big "ceiling" is a sky
# ramp or a graphic)
MAX_CEILING_SHARE = 0.2

MODEL_NAME = "depth_anything_v2_small_q.onnx"
MODEL_ENV = "MATRIX_DEPTH_MODEL"
CACHE_ENV = "MATRIX_SURFACE_CACHE"
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


class Plane(NamedTuple):
    """disparity = a*u + b*v + c with u, v in 0..1 across and down the picture."""

    kind: int
    a: float
    b: float
    c: float
    share: float


class Detected(NamedTuple):
    labels: np.ndarray  # (h, w) uint8 kind per pixel
    planes: tuple
    vanishing: tuple | None  # (x, y, confidence) in picture shares, None: no usable point
    depth: np.ndarray | None = None  # (h, w) disparity 0 (far) .. 1 (near), the network's own
    # CAMERA_LEVEL or CAMERA_UP (looking up between buildings: rain comes at the camera)
    camera: int = 0


def cache_dir():
    """Where the cache is written: the saver's own folder (the container on the sandboxed Mac host,
    the only place it may write), or MATRIX_SURFACE_CACHE."""
    return os.environ.get(CACHE_ENV) or os.path.join(osapi.state_dir(), "surfaces")


def cache_dirs():
    """Folders searched for cached maps and the model, the written one first. Besides it, the
    settings folder (the sandbox may read any path, and tools/dev/surface_cache.py fills it from a
    normal shell)."""
    if os.environ.get(CACHE_ENV):
        return [os.environ[CACHE_ENV]]
    legacy = os.path.join(os.path.dirname(osapi.settings_read_path()), "surfaces")
    return [cache_dir()] + ([legacy] if legacy != cache_dir() else [])


# bumped when the cached maps change meaning: 2 = from the upright picture (EXIF orientation)
CACHE_VERSION = "2"


def _cache_name(path):
    """Cache file name of one picture: keyed by its location, size and modification time, so an
    edited or replaced picture is analysed again."""
    info = os.stat(path)
    key = "%s|%d|%d|%s" % (os.path.abspath(path), info.st_size, info.st_mtime_ns, CACHE_VERSION)
    return hashlib.sha1(key.encode()).hexdigest()[:20] + ".npz"


def cache_path(path):
    """Where the cache file of a picture is written."""
    return os.path.join(cache_dir(), _cache_name(path))


def _cached_file(path):
    """The existing cache file of a picture in any searched folder, or None."""
    name = _cache_name(path)
    for folder in cache_dirs():
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def _load_cached(path):
    found = _cached_file(path)
    if found is None:
        return None
    try:
        with np.load(found) as data:
            return data["disparity"].astype(np.float32)
    except (OSError, ValueError, KeyError):
        return None


def _store(path, disparity):
    os.makedirs(cache_dir(), exist_ok=True)
    target = cache_path(path)
    temp = target + ".tmp.npz"
    np.savez_compressed(temp, disparity=disparity.astype(np.float16))
    os.replace(temp, target)


def model_path():
    """The ONNX model file, or None: MATRIX_DEPTH_MODEL, else the copy bundled in assets/models,
    else the cache directory."""
    for candidate in [os.environ.get(MODEL_ENV), resources.asset_path("models", MODEL_NAME)] + [
        os.path.join(d, MODEL_NAME) for d in cache_dirs()
    ]:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def _resize(plane, height, width):
    """Resize a 2-D or 3-D float array (bilinear; area average first when shrinking by 2x or
    more, so thin lines do not alias)."""
    plane = np.asarray(plane, np.float32)
    while plane.shape[0] >= 2 * height and plane.shape[1] >= 2 * width:
        h, w = plane.shape[0] // 2 * 2, plane.shape[1] // 2 * 2
        plane = plane[:h, :w].reshape(h // 2, 2, w // 2, 2, *plane.shape[2:]).mean((1, 3))
    ys = (np.arange(height) + 0.5) * plane.shape[0] / height - 0.5
    xs = (np.arange(width) + 0.5) * plane.shape[1] / width - 0.5
    y0 = np.clip(np.floor(ys).astype(int), 0, plane.shape[0] - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, plane.shape[1] - 1)
    y1, x1 = np.minimum(y0 + 1, plane.shape[0] - 1), np.minimum(x0 + 1, plane.shape[1] - 1)
    fy = np.clip(ys - y0, 0.0, 1.0)
    fx = np.clip(xs - x0, 0.0, 1.0)
    if plane.ndim == 3:
        fy, fx = fy[:, None, None], fx[None, :, None]
    else:
        fy, fx = fy[:, None], fx[None, :]
    top = plane[y0][:, x0] * (1 - fx) + plane[y0][:, x1] * fx
    bottom = plane[y1][:, x0] * (1 - fx) + plane[y1][:, x1] * fx
    return top * (1 - fy) + bottom * fy


def estimate_disparity(rgb, model):
    """Relative disparity (larger is nearer) of an RGB uint8 picture, at DISPARITY_SIZE on the
    long side. Needs onnxruntime; raises ImportError without it."""
    import onnxruntime  # in requirements/requirements.txt; absent on macOS, which uses Core ML

    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = NETWORK_THREADS  # never compete with the render loop
    options.inter_op_num_threads = 1
    session = onnxruntime.InferenceSession(
        model, options, providers=["CPUExecutionProvider"]
    )
    x = _resize(rgb.astype(np.float32) / 255.0, MODEL_SIZE, MODEL_SIZE)
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
    out = session.run(None, {session.get_inputs()[0].name: x})[0][0]
    height, width = rgb.shape[:2]
    scale = DISPARITY_SIZE / max(height, width)
    return _resize(out, max(8, round(height * scale)), max(8, round(width * scale)))


def lookup(path, pad=None):
    """The detected surfaces of a picture from its cached disparity map, or None when there is
    none (yet). Never runs the network: the picture is then drawn by the older path rather than
    waiting. `pad` (plane, fill) -> plane widens the map the way the picture was widened; the
    added sides have disparity 0, infinitely far, so they are open background."""
    disparity = _load_cached(path)
    if disparity is None:
        return None
    return detect_stable(disparity if pad is None else pad(disparity, 0.0))


# the plane fit is random (RANSAC): on a borderline picture one draw fixes the vanishing point and
# the next only guesses it, so the fans came and went between runs (and between machines, where the
# arithmetic differs in the last bits). Several draws vote instead.
STABLE_RUNS = 5


def detect_stable(disparity, runs=STABLE_RUNS):
    """detect() over `runs` seeds: the majority decides whether the picture is a confident box,
    and of the runs that agree, the one whose vanishing point is nearest their median is kept."""
    found = [detect(disparity, seed) for seed in range(runs)]
    votes = [confident_box(f) for f in found]
    side = sum(votes) * 2 > runs
    agree = [f for f, v in zip(found, votes, strict=True) if v == side]
    points = [f.vanishing for f in agree if f.vanishing is not None]
    if not points:
        return agree[0]
    middle = np.median(np.array([p[:2] for p in points]), 0)
    return min(
        (f for f in agree if f.vanishing is not None),
        key=lambda f: float(np.hypot(f.vanishing[0] - middle[0], f.vanishing[1] - middle[1])),
    )


def _backend():
    """Which depth network runs here: 'coreml' (macOS, in process), 'onnx' (the model file and
    onnxruntime are present) or None."""
    try:
        from digital_rain.mac import depth_coreml

        if depth_coreml.available():
            return "coreml"
    except ImportError:
        pass
    if model_path() is not None:
        try:
            import onnxruntime  # noqa: F401

            return "onnx"
        except ImportError:
            pass
    return None


def _estimate(rgb, backend):
    if backend == "coreml":
        from digital_rain.mac import depth_coreml

        out = depth_coreml.predict(rgb)
        height, width = rgb.shape[:2]
        scale = DISPARITY_SIZE / max(height, width)
        return _resize(out, max(8, round(height * scale)), max(8, round(width * scale)))
    return estimate_disparity(rgb, model_path())


def fill_cache(path, load_rgb):
    """Run the depth network for one picture and cache its disparity map. True when it is cached.
    Slow (the first Core ML call several seconds, then about 50 ms; ONNX about half a second):
    call it from a background thread only. False without a backend."""
    if _cached_file(path):
        return True
    backend = _backend()
    if backend is None:
        return False
    try:
        rgb = load_rgb(path, 1024)
        disparity = _estimate(rgb, backend)
        _store(path, disparity)
    except (ImportError, OSError):  # no runtime, a failed model, or a read-only or sandboxed folder
        return False
    return True


def can_estimate():
    """True when fill_cache could run here."""
    return _backend() is not None


def _fit_planes(points, rng):
    """Sequential RANSAC: planes (a, b, c) and their point counts, biggest first."""
    remaining = np.ones(len(points), bool)
    found = []
    design = np.c_[points[:, 0], points[:, 1], np.ones(len(points))]
    for _ in range(MAX_PLANES):
        idx = np.flatnonzero(remaining)
        if len(idx) < MIN_PLANE_SHARE * len(points):
            break
        # all candidate planes at once: three random points each, solved as one batch
        picks = rng.integers(0, len(idx), (RANSAC_TRIES, 3))
        samples = design[idx[picks]]  # (tries, 3, 3)
        targets = points[idx[picks], 2]
        determinant = np.linalg.det(samples)
        usable = np.abs(determinant) > 1e-9
        if not usable.any():
            break
        coefs = np.linalg.solve(samples[usable], targets[usable][..., None])[..., 0]
        counts = (np.abs(coefs @ design[idx].T - points[idx, 2][None, :]) < PLANE_TOLERANCE).sum(1)
        best_count, best = int(counts.max()), coefs[int(counts.argmax())]
        if best is None or best_count < MIN_PLANE_SHARE * len(points):
            break
        coef = best
        for _ in range(3):  # refit on the inliers
            inliers = remaining & (np.abs(design @ coef - points[:, 2]) < PLANE_TOLERANCE)
            if inliers.sum() < 3:
                break
            coef = np.linalg.lstsq(design[inliers], points[inliers, 2], rcond=None)[0]
        inliers = remaining & (np.abs(design @ coef - points[:, 2]) < PLANE_TOLERANCE)
        found.append((coef, int(inliers.sum()) / len(points)))
        remaining &= ~inliers
    return found


def classify(a, b):
    """What a plane of disparity gradient (a, b) is: the floor gets nearer toward the bottom
    of the picture (b > 0), a left wall toward the left (a < 0)."""
    if abs(a) < FRONTAL_SLOPE and abs(b) < FRONTAL_SLOPE:
        return FRONT
    if abs(b) > SLOPE_RATIO * abs(a):
        return FLOOR if b > 0 else CEILING
    if abs(a) > SLOPE_RATIO * abs(b):
        return WALL_LEFT if a < 0 else WALL_RIGHT
    return FRONT


def _majority(labels, passes):
    """Replace each label by the most common one in its 3x3 neighbourhood (specks go)."""
    for _ in range(passes):
        padded = np.pad(labels, 1, mode="edge")
        counts = np.zeros((len(KIND_NAMES),) + labels.shape, np.int8)
        for dy in range(3):
            for dx in range(3):
                window = padded[dy : dy + labels.shape[0], dx : dx + labels.shape[1]]
                for kind in range(len(KIND_NAMES)):
                    counts[kind] += window == kind
        labels = counts.argmax(0).astype(np.uint8)
    return labels


def _horizon(planes):
    """Row (0..1) of the horizon guessed from the biggest floor: the network's disparity is
    zero at the farthest point of the picture, so the floor plane's zero line is near the
    horizon when the picture has sky or a far end. None without a floor."""
    floors = [p for p in planes if p.kind == FLOOR]
    if not floors:
        return None
    floor = max(floors, key=lambda p: p.share)
    return float(np.clip(-(floor.a * 0.5 + floor.c) / floor.b, HORIZON_LOW, HORIZON_HIGH))


# a small ceiling (under this share) whose meeting lines spoil an otherwise agreeing vanishing
# point is left out of it: a stray patch of a street the fit takes for a ceiling (the shader
# draws no ceiling fans; leaving out a stray wall instead let portraits and graphics find a point)
STRAY_PLANE_SHARE = 0.1


def _meeting_lines(surfaces):
    lines = []
    for i, p in enumerate(surfaces):
        for q in surfaces[i + 1 :]:
            if p.kind == q.kind:
                continue
            na, nb, nc = p.a - q.a, p.b - q.b, p.c - q.c
            norm = float(np.hypot(na, nb))
            if norm < MIN_LINE_SLOPE:
                continue
            lines.append((na / norm, nb / norm, nc / norm, min(p.share, q.share)))
    return lines


def _fixed_point(lines):
    """(rms, x, y) where two or more meeting lines that are not (nearly) parallel cross, or None."""
    if len(lines) < 2:
        return None
    normals = np.array([[n[0], n[1]] for n in lines])
    offsets = np.array([n[2] for n in lines])
    weights = np.array([n[3] for n in lines])
    spread = max(
        abs(normals[i, 0] * normals[j, 1] - normals[i, 1] * normals[j, 0])
        for i in range(len(lines))
        for j in range(i + 1, len(lines))
    )
    if spread < VP_MIN_ANGLE:
        return None
    root = np.sqrt(weights)[:, None]
    point = np.linalg.lstsq(normals * root, -offsets * root[:, 0], rcond=None)[0]
    rms = float(np.sqrt(np.average((normals @ point + offsets) ** 2, weights=weights)))
    x, y = float(point[0]), float(point[1])
    if rms > VP_MAX_RMS or not (-VP_MARGIN < x < 1 + VP_MARGIN and -VP_MARGIN < y < 1 + VP_MARGIN):
        return None
    return rms, x, y


def _vanishing(planes):
    """Where the surfaces converge: the planes of a corridor meet pairwise in lines that all
    pass through one point (the one the corridor recedes to). Disparity from the network has an
    unknown scale and offset, but a difference of two planes keeps the line, so the lines are
    usable as they are. Two lines that agree fix the point (confidence 0.5..1), if need be with one
    small stray ceiling left out (STRAY_PLANE_SHARE); one line or none leaves it to be placed along
    that line at the guessed horizon (confidence ESTIMATE_CONFIDENCE).
    Returns (x, y, confidence), or None when the picture has no surface at all."""
    surfaces = [p for p in planes if p.kind != FRONT]
    if not surfaces:
        return None
    lines = _meeting_lines(surfaces)
    fixed = _fixed_point(lines)
    if fixed is None:
        tries = [
            _fixed_point(_meeting_lines([q for q in surfaces if q is not p]))
            for p in surfaces
            if p.kind == CEILING and p.share < STRAY_PLANE_SHARE
        ]
        tries = [t for t in tries if t is not None]
        fixed = min(tries) if tries else None
    if fixed is not None:
        rms, x, y = fixed
        return x, y, float(np.clip(1.0 - rms / VP_MAX_RMS * 0.5, 0.5, 1.0))
    horizon = _horizon(planes)
    if horizon is None:
        horizon = 0.5
    x = 0.5
    if lines:
        # the heaviest meeting line, met at the horizon row (or its nearest point if flat)
        na, nb, nc, _ = max(lines, key=lambda n: n[3])
        if abs(na) > 0.2:
            x = float(np.clip(-(nb * horizon + nc) / na, -0.3, 1.3))
        else:
            horizon = float(np.clip(-(na * x + nc) / nb, HORIZON_LOW, HORIZON_HIGH))
    return x, horizon, ESTIMATE_CONFIDENCE


# the depth network puts sky at 0; the far end of a street is above this
SKY_DISPARITY = (0.003, 0.012)


# Camera position. Rain falls straight down in the world, so on screen it follows where the world's
# verticals meet: nowhere for a level camera (straight down the faces); in the sky when looking up
# between buildings, where it comes from the sky toward the camera. Looking down is not detected.
CAMERA_LEVEL, CAMERA_UP = 0, 1
UP_SKY_SHARE = 0.02  # an up-view shows at least this share of sky between its walls ...
UP_SKY_HEIGHT = 0.6  # ... in a strip at least this share of the picture tall
UP_ABOVE_SKY = 0.05  # the verticals meet this far (picture height) above the top of the sky strip
UP_CONFIDENCE = 0.8


def _gravity_point(planes, depth):
    """(x, y, confidence) where the verticals meet when the camera looks up between buildings:
    side walls only (no floor or ceiling) and a tall strip of sky between them. None otherwise."""
    kinds = {p.kind for p in planes}
    if FLOOR in kinds or CEILING in kinds or not {WALL_LEFT, WALL_RIGHT} <= kinds:
        return None
    sky = depth < SKY_DISPARITY[0]
    if sky.mean() < UP_SKY_SHARE:
        return None
    ys, xs = np.nonzero(sky)
    if np.ptp(ys) < UP_SKY_HEIGHT * depth.shape[0]:
        return None  # sky over a street lies in a band along the top, not a strip between walls
    x = float((xs.mean() + 0.5) / depth.shape[1])
    return (x, float(ys.min() / depth.shape[0] - UP_ABOVE_SKY), UP_CONFIDENCE)


def detect(disparity, seed=0):
    """Planes, the per-pixel label map and the vanishing point of a disparity map."""
    disparity = np.asarray(disparity, np.float32)
    height, width = disparity.shape
    rng = np.random.default_rng(seed)
    grid = _resize(disparity, PLANE_GRID, PLANE_GRID)
    low, high = float(grid.min()), float(grid.max())
    scale = max(high - low, 1e-6)
    grid = (grid - low) / scale
    ys, xs = np.mgrid[0:PLANE_GRID, 0:PLANE_GRID]
    points = np.stack(
        [((xs + 0.5) / PLANE_GRID).ravel(), ((ys + 0.5) / PLANE_GRID).ravel(), grid.ravel()], 1
    )
    fitted = _fit_planes(points, rng)
    planes = tuple(
        Plane(classify(float(c[0]), float(c[1])), float(c[0]), float(c[1]), float(c[2]), share)
        for c, share in fitted
    )
    labels = np.full((height, width), FRONT, np.uint8)
    depth = np.clip((disparity - low) / scale, 0.0, 1.0)
    if planes:
        u = (np.arange(width) + 0.5) / width
        v = (np.arange(height) + 0.5) / height
        full = (disparity - low) / scale
        residual = np.stack(
            [full - (p.a * u[None, :] + p.b * v[:, None] + p.c) for p in planes]
        )
        best = np.abs(residual).argmin(0)
        on_surface = np.abs(np.take_along_axis(residual, best[None], 0)[0]) < (
            LABEL_TOLERANCE * PLANE_TOLERANCE
        )
        kinds = np.array([p.kind for p in planes], np.uint8)
        # anything off every plane (nearer than the wall behind it, a gap, the sky) is frontal
        labels = np.where(on_surface, kinds[best], FRONT).astype(np.uint8)
        labels = _majority(labels, SMOOTH_PASSES)
    gravity = _gravity_point(planes, depth)
    if gravity is not None:
        # looking up, everything but the sky is a building face: a frontal patch (a balcony nearer
        # than the fitted wall) joins the wall on its side of the sky, or it shows as a dark notch
        left = np.arange(width) / width < gravity[0]
        side = np.where(left, WALL_LEFT, WALL_RIGHT).astype(np.uint8)
        labels = np.where((labels == FRONT) & (depth >= SKY_DISPARITY[0]), side[None, :], labels)
        return Detected(labels, planes, gravity, depth, CAMERA_UP)
    return Detected(labels, planes, _vanishing(planes), depth)




def sky_mask(detected):
    """1 where the depth network sees infinity (sky, clouds included), fading out by
    SKY_DISPARITY."""
    lo, hi = SKY_DISPARITY
    return 1.0 - np.clip((detected.depth - lo) / (hi - lo), 0.0, 1.0)


def box_share(detected):
    """Share of the picture on fitted surfaces that are not frontal (floor, walls, ceiling)."""
    return float(sum(p.share for p in detected.planes if p.kind != FRONT))


def has_box(detected):
    """Does the picture have a perspective box (enough floor, wall and ceiling)?"""
    return box_share(detected) >= MIN_BOX_SHARE


def side_share(detected):
    """Share of the wall, floor and ceiling labels that lie on their own side of the vanishing
    point (left wall left of it, right wall right of it, floor below, ceiling above); 1.0 without
    a point or any such label."""
    if detected.vanishing is None:
        return 1.0
    wrong = _off_side(detected)
    surfaces = int((detected.labels != FRONT).sum())
    return 1.0 if surfaces == 0 else 1.0 - float(wrong.sum()) / surfaces


def _off_side(detected):
    """True where a wall, floor or ceiling label lies on the wrong side of the vanishing point."""
    labels = detected.labels
    h, w = labels.shape
    vx, vy = detected.vanishing[0], detected.vanishing[1]
    right = ((np.arange(w) + 0.5) / w > vx)[None, :]
    below = ((np.arange(h) + 0.5) / h > vy)[:, None]
    return (
        ((labels == WALL_LEFT) & right)
        | ((labels == WALL_RIGHT) & ~right)
        | ((labels == FLOOR) & ~below)
        | ((labels == CEILING) & below)
    )


def on_side(detected):
    """The labels with every wall, floor or ceiling on the wrong side of the vanishing point made
    frontal: the perspective pass draws a fan by where a cell lies from the point, so such a patch
    (a left wall right of the point, a floor above it) would recede the wrong way. Up-views are
    left alone (everything streams out of the sky there)."""
    if detected.vanishing is None or detected.camera == CAMERA_UP:
        return detected
    labels = np.where(_off_side(detected), FRONT, detected.labels).astype(detected.labels.dtype)
    return detected._replace(labels=labels)


def _main_slope(detected, kind):
    planes = [p for p in detected.planes if p.kind == kind]
    return abs(max(planes, key=lambda p: p.share).a) if planes else 0.0


def confident_box(detected):
    """Does the picture have a perspective box whose recession is known well enough to draw its
    fans: has_box with the camera looking up; or has_box, a side wall (MIN_WALL_SHARE), little
    ceiling (MAX_CEILING_SHARE), surfaces that agree with the vanishing point (MIN_SIDE_SHARE),
    and that point fixed by two lines or walls on both sides (see CORRIDOR_WALL_SHARE)?"""
    if not has_box(detected):
        return False
    if detected.camera == CAMERA_UP:
        return True
    labels = detected.labels
    left = float((labels == WALL_LEFT).mean())
    right = float((labels == WALL_RIGHT).mean())
    if max(left, right) < MIN_WALL_SHARE or float((labels == CEILING).mean()) > MAX_CEILING_SHARE:
        return False
    if side_share(detected) < MIN_SIDE_SHARE:
        return False
    if detected.vanishing is not None and detected.vanishing[2] > ESTIMATE_CONFIDENCE:
        return True
    return min(left, right) >= CORRIDOR_WALL_SHARE and min(
        _main_slope(detected, WALL_LEFT), _main_slope(detected, WALL_RIGHT)
    ) >= CORRIDOR_MIN_SLOPE


def label_texels(detected, tone=None, rain=None):
    """(h, w, 4) uint8 texels for the label texture: R the kind of surface (kind * CODE_STEP),
    G the disparity (0 far, 255 near), which sets the glyph size of cells off every plane, B the
    coarse tone (see coarse_tone; 0 when not given), A the rain mask (see rain_mask; 0 when not
    given)."""
    depth = np.round(detected.depth * 255.0).astype(np.uint8)
    if tone is None:
        tone = np.zeros_like(depth)
    if rain is None:
        rain = np.zeros_like(depth)
    return np.ascontiguousarray(
        np.stack([detected.labels * CODE_STEP, depth, tone, rain], 2), np.uint8
    )


SUBJECT_DEPTH = (0.15, 0.35)  # rain_mask: parts nearer than this ramp can be subject ...
# ... if frontal, or if they stand out of a blur over the first share of the long side by the
# second in depth (the plane fit can take a small object for a wall)
SUBJECT_STAND = (0.06, 0.08)


def rain_mask(detected, drip=0.12):
    """Where the rain runs through the picture, uint8 at the label map's size: 255 on the subject
    (parts that are not far and face the viewer or stand out in front of their surroundings: the
    cat, a car, a ship; an out-of-focus backdrop and open background are far), then fading out
    below it over `drip` of the picture's height, so the streams that run through the subject drip
    on below it. `detected.depth` must already be zeroed on open background."""
    h, w = detected.labels.shape
    depth = detected.depth
    lo, hi = SUBJECT_DEPTH
    near = np.clip((depth - lo) / (hi - lo), 0.0, 1.0)
    share, rise = SUBJECT_STAND
    stand = np.clip((depth - _blur2(depth, max(h, w) * share)) / rise, 0.0, 1.0)
    out = np.maximum(detected.labels == FRONT, stand) * (near * near * (3.0 - 2.0 * near))
    if drip > 0.0:
        step = 1.0 / max(drip * h, 1.0)
        out = out.astype(np.float32)
        for y in range(1, h):
            out[y] = np.maximum(out[y], out[y - 1] - step)
    return np.round(np.clip(out, 0.0, 1.0) * 255.0).astype(np.uint8)


def _blur2(a, sigma):
    """Separable gaussian blur of a 2-D float array, edges padded."""
    radius = max(1, int(3 * sigma))
    taps = np.exp(-0.5 * (np.arange(-radius, radius + 1) / max(sigma, 1e-3)) ** 2)
    taps /= taps.sum()
    a = np.pad(a, radius, mode="edge")
    a = np.apply_along_axis(np.convolve, 0, a, taps, "valid")
    return np.apply_along_axis(np.convolve, 1, a, taps, "valid").astype(np.float32)


# subject_mask: an object stands out where its disparity exceeds the open-free average of its
# surroundings at any of these scales (shares of the long side) by SUBJECT_MARGIN, fully by
# SUBJECT_MARGIN + SUBJECT_SOFT. A plane (a wall, a floor) never does, edges included.
SUBJECT_SCALES = (0.06, 0.12, 0.25)
SUBJECT_MARGIN = 0.04
SUBJECT_SOFT = 0.06
MIN_NEAR_SHARE = 0.02  # own_light_tone: fewer near pixels than this, no near treatment
NEAR_DETAIL_SHARE = 0.03  # own_light_tone: neighbourhood of the near objects' detail stretch
NEAR_HALO_SHARE = 0.04  # own_light_tone: reach of the dimming round the near objects


def _blur_linear(a, sigma, odd):
    """Gaussian blur with the edges mirrored; `odd` mirrors about the edge value as well, so a
    linear ramp (a plane's disparity) blurs to itself right up to the border."""
    radius = max(1, min(int(3 * sigma), min(a.shape) - 1))
    taps = np.exp(-0.5 * (np.arange(-radius, radius + 1) / max(sigma, 1e-3)) ** 2)
    taps /= taps.sum()
    a = np.pad(a, radius, mode="reflect", reflect_type="odd" if odd else "even")
    a = np.apply_along_axis(np.convolve, 0, a, taps, "valid")
    return np.apply_along_axis(np.convolve, 1, a, taps, "valid").astype(np.float32)


def subject_mask(depth, open_mask):
    """0..1 per pixel: how clearly this is part of an object standing out in front of its
    surroundings (a person before a wall, a phone box in a street), from disparity relief. The
    open background (`open_mask`, sky and space) is left out of the surroundings, so a skyline
    against the sky is not an object."""
    depth = np.asarray(depth, np.float32)
    keep = 1.0 - np.clip(np.asarray(open_mask, np.float32), 0.0, 1.0)
    n = max(depth.shape)
    relief = np.zeros_like(depth)
    for share in SUBJECT_SCALES:
        # the open area takes the depth of what surrounds it, so it neither pulls the average
        # down nor mirrors negative across the picture's edge
        fill = _blur_linear(depth * keep, n * share, False)
        fill /= np.maximum(_blur_linear(keep, n * share, False), 1e-3)
        around = _blur_linear(depth * keep + fill * (1.0 - keep), n * share, True)
        relief = np.maximum(relief, depth - around)
    return np.clip((relief - SUBJECT_MARGIN) / SUBJECT_SOFT, 0.0, 1.0) * keep


def refine(detected, long_side):
    """The detection resampled to `long_side` texels on its long side (labels nearest, depth
    bilinear), so the tone carried with it is finer than the depth network's map."""
    h, w = detected.labels.shape
    if max(h, w) >= long_side:
        return detected
    nh, nw = max(1, round(h * long_side / max(h, w))), max(1, round(w * long_side / max(h, w)))
    ys = np.minimum((np.arange(nh) * h) // nh, h - 1)
    xs = np.minimum((np.arange(nw) * w) // nw, w - 1)
    depth = None if detected.depth is None else _resize(detected.depth, nh, nw)
    return detected._replace(labels=detected.labels[ys][:, xs], depth=depth)


BLACK_LUM = 0.015  # own_light_tone: open background grows over pixels darker than this ...
OPEN_GROW = 12  # ... by up to this many label texels


def grow_open(open_mask, small):
    """The open masks (sky, space, backdrop; 0..1) are found on a blurred, smaller picture and stop
    short of the subject: grow them over the black pixels (`small`, luminance at the mask's size)
    they touch, up to the subject's edge."""
    opened = np.clip(open_mask, 0.0, 1.0) > 0.5
    black = small < BLACK_LUM
    for _ in range(max(1, round(OPEN_GROW * max(small.shape) / DISPARITY_SIZE))):
        grown = opened.copy()
        grown[1:] |= opened[:-1]
        grown[:-1] |= opened[1:]
        grown[:, 1:] |= opened[:, :-1]
        grown[:, :-1] |= opened[:, 1:]
        grown &= black | opened
        if (grown == opened).all():
            break
        opened = grown
    return np.maximum(np.clip(open_mask, 0.0, 1.0), _blur2(opened.astype(np.float32), 0.7))


def own_light_tone(
    lum,
    shape,
    open_mask,
    body=0.15,
    gamma=1.6,
    highlight=1.0,
    rim=0.0,
    blur=0.01,
    near=None,
    near_body=0.0,
    near_gamma=None,
    near_contrast=0.0,
    behind=1.0,
):
    """The subject shaded by the photo's own light, uint8 at `shape` (h, w): open background (sky,
    space, a plain backdrop; `open_mask` 0..1) is black; everything else keeps at least `body`
    (a dark side still carries code), its light and shade above that through `gamma`, plus
    small bright points brighter than their surroundings (lit windows, eyes, glints) at
    `highlight`, and an inner rim along the edge of the open background at `rim`.

    `near` (0..1 at `shape`, see subject_mask) marks objects standing out in front of their
    surroundings, such as people: they keep at least `near_body`, are shaded through
    `near_gamma`, and get their own small light and shade (eyes, mouth, folds) stretched by
    `near_contrast`, which the glyphs' own flicker would otherwise drown; what is right behind
    them is dimmed to `behind`, so a person darker than the wall behind them still stands out."""
    h, w = shape
    small = _resize(np.clip(lum, 0.0, 1.0), h, w)
    subject = 1.0 - grow_open(open_mask, small)
    shade = _blur2(small * subject, max(h, w) * blur)
    lo, hi = np.percentile(shade[subject > 0.5] if (subject > 0.5).any() else shade, (2, 98))
    shade = np.clip((shade - lo) / max(hi - lo, 0.03), 0.0, 1.0)
    has_near = near is not None and float((near > 0.5).mean()) >= MIN_NEAR_SHARE
    if has_near:
        near = np.clip(near, 0.0, 1.0) * subject
        # the near objects' own range, not the brighter scene's
        inside = near > 0.5
        nlo, nhi = np.percentile(shade[inside], (2, 98))
        own = np.clip((shade - nlo) / max(nhi - nlo, 0.03), 0.0, 1.0)
        if near_contrast > 0.0:
            radius = max(h, w) * NEAR_DETAIL_SHARE
            weight = _blur2(near, radius) + 1e-3
            mean = _blur2(small * near, radius) / weight
            spread = np.sqrt(_blur2((small - mean) ** 2 * near, radius) / weight)
            detail = np.clip((small - mean) / (2.0 * spread + 0.03), -1.0, 1.0)
            own = np.clip(own + near_contrast * 0.5 * detail, 0.0, 1.0)
        own = own ** (gamma if near_gamma is None else near_gamma)
        own = near_body + (1.0 - near_body) * own
        shade = shade**gamma
        # dimmed only in a halo round the near objects: they stand out, the rest keeps its light
        halo = np.clip(_blur2(near, max(h, w) * NEAR_HALO_SHARE) * 2.0, 0.0, 1.0)
        shade = (body + (1.0 - body) * shade) * (1.0 - (1.0 - behind) * halo * (1.0 - near))
        shade = shade * (1.0 - near) + np.maximum(own, shade) * near
        body = 0.0
    else:
        shade = shade**gamma
    # points: the fine luminance above its neighbourhood, relative to the picture's own range
    local = _blur2(small, max(h, w) * 0.012)
    spread = max(float(np.percentile(small, 98) - np.percentile(small, 2)), 0.05)
    points = np.clip((small - local - 0.12 * spread) / (0.3 * spread), 0.0, 1.0) * highlight
    edge = np.clip((1.0 - _blur2(subject, 1.2)) * 3.0, 0.0, 1.0) * subject * rim
    if has_near:
        points = points * (1.0 - near)  # no sparkle over faces: the near detail draws them
    tone = np.maximum(np.maximum(body + (1.0 - body) * shade, points), edge) * subject
    return np.round(np.clip(tone, 0.0, 1.0) * 255.0).astype(np.uint8)


def coarse_tone(lum, shape, blur=0.01, open_mask=None):
    """Large-scale light and shade of the picture at `shape` (h, w), uint8: the raw luminance
    blurred over `blur` of the long side, then stretched so its 2nd to 98th percentile fills 0..255
    (a dark photo still gets full light-against-shade contrast). `open_mask` (0..1, at `shape`) is
    open background such as sky: it counts as dark, so the sky carries no glyphs."""
    h, w = shape
    small = _resize(np.clip(lum, 0.0, 1.0) * 255.0, h, w)
    if open_mask is not None:
        small = small * (1.0 - np.clip(open_mask, 0.0, 1.0))
    sigma = max(h, w) * blur
    radius = max(1, int(3 * sigma))
    taps = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    taps /= taps.sum()
    a = np.pad(small, radius, mode="edge")
    a = np.apply_along_axis(np.convolve, 0, a, taps, "valid")
    a = np.apply_along_axis(np.convolve, 1, a, taps, "valid").astype(np.float32)
    lo, hi = np.percentile(a, (2, 98))
    return np.round(np.clip((a - lo) / max(hi - lo, 8.0), 0.0, 1.0) * 255.0).astype(np.uint8)
