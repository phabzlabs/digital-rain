"""Image measurements shared by the film checks and the reference tooling.

The helpers take a max-channel (or RGB) float array and return the glyph geometry the gate
windows are written in: row pitch, ink columns, stroke fill, halo rings. Windows are in px at
1915 px wide (the Blu-ray width), so stills and saver frames of any width share one ruler.
"""

import numpy as np

LIT = 40  # max channel above this counts as lit (8 bit)
WHITE = 180  # every channel above this counts as near-white leader ink


def box(a, r):
    """Box blur of a 2D array with radius r (edge padded)."""
    k = 2 * r + 1
    p = np.pad(a, r, mode="edge")
    c = p.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def dilate(mask, n=1, square=False):
    """Binary dilation by n steps: 4-neighbour (a diamond), or with `square` the 3 x 3 square."""
    out = mask.copy()
    for _ in range(n):
        m = out.copy()
        m[1:] |= out[:-1]
        m[:-1] |= out[1:]
        m[:, 1:] |= out[:, :-1]
        m[:, :-1] |= out[:, 1:]
        if square:
            m[1:, 1:] |= out[:-1, :-1]
            m[:-1, :-1] |= out[1:, 1:]
            m[1:, :-1] |= out[:-1, 1:]
            m[:-1, 1:] |= out[1:, :-1]
        out = m
    return out


def distance_rings(mask, nmax):
    """Integer city-block distance from mask, up to nmax (nmax+1 beyond)."""
    dist = np.full(mask.shape, nmax + 1, np.int16)
    dist[mask] = 0
    cur = mask
    for d in range(1, nmax + 1):
        nxt = dilate(cur, 1)
        dist[nxt & ~cur] = d
        cur = nxt
    return dist


def _separated_peaks(sm, thr, sep):
    """Local maxima of `sm` above `thr`, strongest first, at least `sep` apart; sorted by x."""
    cand = [
        x
        for x in range(1, len(sm) - 1)
        if sm[x] >= sm[x - 1] and sm[x] >= sm[x + 1] and sm[x] > thr
    ]
    cand.sort(key=lambda x: -sm[x])
    taken = []
    for x in cand:
        if all(abs(x - t) >= sep for t in taken):
            taken.append(x)
    taken.sort()
    return taken


def row_pitch_and_columns(mx, lo, hi):
    """Row pitch from vertical autocorrelation inside ink columns, and a column count.

    Rain columns are not on one strict horizontal grid in every shot (the
    opening layers columns of several sizes), so columns are counted as peaks
    of the column ink profile, separated by at least 0.6 of the row pitch.
    Sparse shots skip columns, so the spacing can be a multiple of the true
    column pitch (see design/film-reference.md).
    """
    prof = mx.mean(0)
    hp = mx - box(mx, max(8, hi // 2))
    # strongest ink x positions: top quarter of the column profile
    xs = np.where(prof > np.percentile(prof, 75))[0]
    acs = []
    for x in xs[:: max(1, len(xs) // 200)]:
        v = hp[:, x] - hp[:, x].mean()
        ac = np.correlate(v, v, "full")[len(v) - 1 : len(v) + hi + 1]
        if ac[0] > 0:
            acs.append(ac / ac[0])
    rp = float("nan")
    if acs:
        ac = np.mean(acs, 0)
        k = 1
        while k < len(ac) - 1 and not (ac[k] <= ac[k - 1] and ac[k] <= ac[k + 1]):
            k += 1
        peaks = [
            j
            for j in range(max(k + 1, lo), len(ac) - 1)
            if ac[j] >= ac[j - 1] and ac[j] >= ac[j + 1]
        ]
        if peaks:
            j = max(peaks, key=lambda q: ac[q])
            a, b, c = ac[j - 1], ac[j], ac[j + 1]
            rp = j + 0.5 * (a - c) / (a - 2 * b + c + 1e-9)
    if not np.isfinite(rp):
        return rp, 0, float("nan")
    r = max(1, int(rp * 0.15))
    sm = np.convolve(np.pad(prof, r, mode="edge"), np.ones(2 * r + 1) / (2 * r + 1), "valid")
    floor = np.percentile(sm, 20)
    thr = floor + 0.25 * (np.percentile(sm, 95) - floor)
    sep = int(rp * 0.6)
    taken = _separated_peaks(sm, thr, sep)
    cp = float(np.median(np.diff(taken))) if len(taken) > 2 else float("nan")
    return rp, len(taken), cp


def col_pitch(mx, scale):
    """Fundamental pitch (native px) of the column grid and its strength.

    Autocorrelation of the column ink profile after subtracting a box blur of
    +-10 px at 1915 wide (that removes blobs wider than a column but keeps the
    column period); the first local maximum above 0.1 at a lag of at least 14 px
    (at 1915 wide) is one column pitch. In sparse shots that skip columns a
    skipped column lowers the peak but does not move it. `scale` is 1915 / frame
    width. Returns (pitch, strength), nan when there is none."""
    prof = mx.mean(0)
    k = max(3, int(round(10 / scale)))
    hp = prof - np.convolve(np.pad(prof, k, mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), "valid")
    hi = int(60 / scale)
    ac = np.correlate(hp, hp, "full")[len(hp) - 1 : len(hp) + hi + 1]
    if ac[0] <= 0:
        return float("nan"), 0.0
    ac = ac / ac[0]
    for q in range(max(2, int(round(14 / scale))), len(ac) - 1):
        if ac[q] >= ac[q - 1] and ac[q] >= ac[q + 1] and ac[q] > 0.1:
            u, v, w = ac[q - 1], ac[q], ac[q + 1]
            return q + 0.5 * (u - w) / (u - 2 * v + w + 1e-9), float(v)
    return float("nan"), 0.0


def stroke_width(mx, scale):
    """(stroke, fill, long): horizontal stroke width and how filled-in the glyphs are.

    Along every third row a pixel is "on" when it exceeds half of the local
    maximum (window +-14 px at 1915 wide) and that maximum exceeds 120. `stroke`
    is the median length (native px) of the on-runs up to 14 px at 1915 wide (one
    stroke; longer runs are horizontal strokes or merged glyphs), `fill` the share
    of on pixels among the pixels with local maximum above 120 (low for open
    strokes, near 1 for blobs) and `long` the share of on pixels in runs longer
    than 14 px. Windows are fixed in px at 1915 wide so film stills and saver
    frames of any width are compared on the same ruler."""
    r = max(2, int(round(14 / scale)))
    rows = mx[::3]
    pad = np.pad(rows, ((0, 0), (r, r)), mode="edge")
    loc = np.maximum.reduce([pad[:, i : i + rows.shape[1]] for i in range(0, 2 * r + 1, 2)])
    hot = loc > 120
    on = (rows > 0.5 * loc) & hot
    z = np.zeros((on.shape[0], 1), np.int8)
    d = np.diff(np.concatenate([z, on.astype(np.int8), z], axis=1), axis=1).ravel()
    st, en = np.where(d == 1)[0], np.where(d == -1)[0]
    ln = en - st
    short = ln[(ln >= 1) & (ln <= r)]
    if len(short) < 50 or hot.sum() < 500:
        return float("nan"), float("nan"), float("nan")
    return (
        float(np.median(short)),
        float(on.sum() / hot.sum()),
        float(ln[ln > r].sum() / max(ln.sum(), 1)),
    )


def ink_columns(mx, scale):
    """Number of ink columns per 1915 px: peaks of the column ink profile
    (box blur of 3 px at 1915 wide), above 25 percent of the way from its 20th to
    its 95th percentile, at least 12 px (at 1915 wide) apart. Unlike the older
    count in row_pitch_and_columns the separation does not depend on the row pitch
    estimate, so adjacent columns of a dense grid are not merged."""
    prof = mx.mean(0)
    r = max(1, int(round(1.5 / scale)))
    sm = np.convolve(np.pad(prof, r, mode="edge"), np.ones(2 * r + 1) / (2 * r + 1), "valid")
    floor = np.percentile(sm, 20)
    thr = floor + 0.25 * (np.percentile(sm, 95) - floor)
    sep = int(round(12 / scale))
    taken = _separated_peaks(sm, thr, sep)
    return len(taken) * 1915.0 / (len(sm) * scale)


def scanline_parity(img):
    """Mean luma of the even pixel rows over the odd ones (1.0 when no scanline pattern)."""
    lum = img @ np.array([0.299, 0.587, 0.114], np.float32)
    return float(lum[0::2].mean() / max(lum[1::2].mean(), 1e-9))
