"""Image metrics of the film look gates (tools/checks/check_film.py).

Everything here is a pure function of an HxWx3 uint8 (or float) frame, so the gate script only
holds frame rendering, windows and reporting. Pixel distances are scaled to 1915 px wide, the
width of the Blu-ray stills the windows were measured on (design/film-reference.md).

measure         one cropped frame: lit share, tone buckets, near-white share, leader columns,
                background, hue, halo, edge rise, ink columns, stroke fill, grain, parity
clarity_*       glyph peaks, ink boxes and leader colours on the frame resampled to 1915 wide
followup_*      leader openness, column clustering and 2.39:1 band leader columns
"""

import colorsys

import imgmeasure as pix
import numpy as np
from film_targets import BUCKETS, SCALE
from numpy.lib.stride_tricks import sliding_window_view
from PIL import Image


def luma(img):
    a = img.astype(np.float32)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def row_pitches(img):
    """Glyph row pitch per 240 x 270 px tile: the brightest 30 percent of columns averaged into
    a vertical luma profile, first autocorrelation peak above 0.15 between 8 and 200 px. Tiles
    whose column-mean luma never reaches 8 are skipped."""
    y = luma(img)
    height, width = y.shape
    out = []
    for ty in range(0, height - 269, 270):
        for tx in range(0, width - 239, 240):
            tile = y[ty : ty + 270, tx : tx + 240]
            col_mean = tile.mean(0)
            if col_mean.max() < 8:
                continue
            cols = np.argsort(col_mean)[-max(1, int(0.3 * 240)) :]
            prof = tile[:, cols].mean(1)
            prof = prof - prof.mean()
            if not prof.any():
                continue
            ac = np.correlate(prof, prof, "full")[269:]
            ac = ac / ac[0]
            for lag in range(8, 201):
                if ac[lag] > 0.15 and ac[lag] >= ac[lag - 1] and ac[lag] >= ac[lag + 1]:
                    out.append(lag)
                    break
    return out


def crop(img):
    """Drop the top 10 percent of rows (the frame's first rain rows are not settled)."""
    return img[int(round(img.shape[0] * 0.1)) :]


def halo(mx, ink, nmax):
    dist = pix.distance_rings(ink, nmax)
    prof = [
        float(np.median(mx[dist == d])) if (dist == d).any() else 0.0 for d in range(0, nmax + 1)
    ]
    floor = float(np.median(mx[mx < 25])) if (mx < 25).any() else 0.0
    peak = prof[0]
    norm = [(v - floor) / max(peak - floor, 1) for v in prof]
    d50 = next((d for d, v in enumerate(norm) if v < 0.5), nmax)
    d10 = next((d for d, v in enumerate(norm) if v < 0.1), nmax)
    return d50 * SCALE, d10 * SCALE


def edge_rise(mx):
    g = mx
    gx = np.abs(np.diff(g, axis=1))[:-1, :]
    gy = np.abs(np.diff(g, axis=0))[:, :-1]
    grad = np.maximum(gx, gy)
    hot = (mx > 120)[:-1, :-1]
    edge = pix.dilate(mx > 120, 2)[:-1, :-1] & ~hot | hot
    local_max = np.maximum.reduce(
        [np.roll(np.roll(g, i, 0), j, 1) for i in (-3, 0, 3) for j in (-3, 0, 3)]
    )[:-1, :-1]
    sel = edge & (local_max > 150)
    width = (local_max[sel] - 20) / np.maximum(np.percentile(grad[sel], 90), 1)
    return float(np.median(width) * 0.8 * SCALE)


def lit_run(mx, lit, rp, cp):
    """Median vertical run of lit pixels along ink columns, in rows (see
    design/film-reference-reloaded.md): the estimate of measure_reference.still."""
    if not np.isfinite(rp) or rp <= 0:
        return 0.0
    w = max(1, int(cp * 0.15))
    br = max(1, int(rp * 0.35))
    prof = mx.mean(0)
    runs = []
    for x in np.where(prof > np.percentile(prof, 70))[0][:: max(1, int(cp))]:
        col = lit[:, max(0, x - w) : x + w + 1].any(-1).astype(np.float32)
        col = pix.box(col[:, None], br)[:, 0] > 0.0
        n = 0
        for v in list(col) + [False]:
            if v:
                n += 1
            elif n:
                runs.append(n / rp)
                n = 0
    runs = [r for r in runs if r > 1.5]
    return float(np.median(runs)) if runs else 0.0


def bucket_hue_drift(img):
    """Median hue of the 80-120 bucket minus that of the 200-230 bucket (degrees)."""
    a = img.astype(np.float32)
    mx = a.max(-1)
    out = []
    for lo, hi in ((80, 120), (200, 230)):
        sel = a[(mx >= lo) & (mx < hi)]
        sel = sel[:: max(1, len(sel) // 20000)]
        out.append(float(np.median([colorsys.rgb_to_hsv(*(c / 255.0))[0] * 360 for c in sel])))
    return out[0] - out[1]


def measure(img, bg_mode="distance", fix=1.0):
    """The gate values of one cropped frame. bg_mode "dark" takes the
    background from pixels with max channel under 25, as measure_reference does."""
    a = img.astype(np.float32)
    mx = a.max(-1)
    lit = mx > pix.LIT
    n_lit = max(int(lit.sum()), 1)
    out = dict(lit=float(lit.mean()))
    for lo, hi in BUCKETS:
        out[f"b{lo}"] = float(((mx >= lo) & (mx < hi)).sum() / n_lit)
    white = a.min(-1) > pix.WHITE
    out["white_pct"] = float(white.sum() / n_lit * 100)
    out["leader_cols"] = float(white.any(0).sum() / max(int(lit.any(0).sum()), 1))
    top = a[mx >= np.percentile(mx, 99.5)].mean(0)
    for i, c in enumerate("rgb"):
        out[f"head_{c}"] = float(top[i])
    bgm = (mx < 25) if bg_mode == "dark" else ~pix.dilate(lit, int(round(25 / SCALE)))
    if bgm.sum() < 1000:  # dense frame: no pixel is 25 px from ink
        bgm = mx < 25
    if bgm.sum() < 1000:
        bgm = np.zeros_like(bgm)
        med = np.array([np.nan] * 3)
    else:
        med = np.median(a[bgm], 0)
    for i, c in enumerate("rgb"):
        out[f"bg_{c}"] = float(med[i])
    lit_px = a[lit]
    hs = np.array(
        [
            colorsys.rgb_to_hsv(*(c / 255.0))[0] * 360
            for c in lit_px[:: max(1, len(lit_px) // 20000)]
        ]
    )
    out["hue"] = float(np.median(hs))
    lo_px, hi_px = max(4, int(8 / SCALE)), int(60 / SCALE)
    rp, _n, cp = pix.row_pitch_and_columns(mx, lo_px, hi_px)
    if not np.isfinite(cp):
        cp = 24.5 / SCALE
    out["run"] = lit_run(mx, lit, rp, cp)
    nmax = int(max(cp, 10) * 1.5)
    out["nmax"] = float(nmax)
    out["glyph_h50"], out["glyph_h10"] = halo(mx, mx > 200, nmax)
    out["lead_h50"], out["lead_h10"] = halo(mx, white, nmax)
    out["edge"] = edge_rise(mx)
    for k in ("glyph_h50", "glyph_h10", "lead_h50", "lead_h10", "edge"):
        out[k] *= fix  # 1920 / W, so px at any width are px at 1915 wide
    sc = 1915.0 / img.shape[1]
    out["ink_cols"] = float(pix.ink_columns(mx, sc))
    out["fill"] = float(pix.stroke_width(mx, sc)[1])
    res = [a[..., c] - pix.box(a[..., c], 3) for c in range(3)]
    for i, c in enumerate("rgb"):
        out[f"bg_grain_{c}"] = float(res[i][bgm].std()) if bgm.any() else 0.0
    out["parity"] = pix.scanline_parity(a)
    return out


# Clarity metrics: the frame is resampled to 1915 px wide (PIL BOX), glyph
# peaks are the local maxima of the max channel over a 21 x 15 window above 41, ink boxes
# are the 0.5 P connected region inside 53 x 37 px (boxes touching the window or under
# 14 x 10 dropped), leader core and ring colours come from near-white (min channel above
# 180) pixels, the band is the 200 to 239 non-white pixels.
WIDTH_1915 = 1915  # Blu-ray width of design/film-reference.md; every window is in px of it
PEAK_FLOOR = 41  # every lit glyph (max channel > 40) is a glyph peak
PEAK_WINDOW = (21, 15)  # peak suppression window, px at 1915 wide (about one glyph cell)
BOX_WINDOW = (26, 18)  # half size of the ink box search window
MIN_BOX = (14, 10)  # smallest ink box (h, w) counted: whole glyphs, not bars and dots
BRIDGE_GAPS = True  # bridge 1 to 2 px gaps inside a glyph (False: plain 8-connectivity)


def to_1915_wide(img):
    """HxWx3 uint8 -> float32 array resampled to 1915 px wide."""
    h, w = img.shape[:2]
    if w == WIDTH_1915:
        return img.astype(np.float32)
    im = Image.fromarray(img)
    im = im.resize((WIDTH_1915, max(1, round(h * WIDTH_1915 / w))), Image.BOX)
    return np.asarray(im).astype(np.float32)


def max_filter(a, ry, rx):
    p = np.pad(a, ((ry, ry), (0, 0)), mode="constant", constant_values=-1)
    a1 = sliding_window_view(p, 2 * ry + 1, axis=0).max(-1)
    p = np.pad(a1, ((0, 0), (rx, rx)), mode="constant", constant_values=-1)
    return sliding_window_view(p, 2 * rx + 1, axis=1).max(-1)


def glyph_peaks(mx, scale=1.0, floor=None):
    floor = PEAK_FLOOR if floor is None else floor
    ry, rx = max(1, round(PEAK_WINDOW[0] / 2 * scale)), max(1, round(PEAK_WINDOW[1] / 2 * scale))
    h, w = mx.shape
    # deterministic tie breaker so a flat plateau gives one peak
    tb = (np.arange(h)[:, None] * 0.37 + np.arange(w)[None, :] * 0.11) % 1.0 * 1e-3
    m = mx + tb
    mf = max_filter(m, ry, rx)
    ys, xs = np.nonzero((m >= mf) & (mx > floor))
    return ys, xs, mx[ys, xs]


def ink_box(mx, y, x, peak):
    hy, hx = BOX_WINDOW
    y0, y1 = max(0, y - hy), min(mx.shape[0], y + hy + 1)
    x0, x1 = max(0, x - hx), min(mx.shape[1], x + hx + 1)
    win = mx[y0:y1, x0:x1]
    mask = win >= 0.5 * peak
    bridge = pix.dilate(mask, square=True) if BRIDGE_GAPS else mask
    comp = np.zeros_like(mask)
    comp[y - y0, x - x0] = True
    for _ in range(200):
        nxt = pix.dilate(comp, square=True) & bridge
        if (nxt == comp).all():
            break
        comp = nxt
    comp &= mask
    ys, xs = np.nonzero(comp)
    if len(ys) == 0:
        return None
    by0, by1, bx0, bx1 = ys.min(), ys.max(), xs.min(), xs.max()
    if by0 == 0 or bx0 == 0 or by1 == win.shape[0] - 1 or bx1 == win.shape[1] - 1:
        return None
    b = win[by0 : by1 + 1, bx0 : bx1 + 1]
    return dict(
        h=int(by1 - by0 + 1),
        w=int(bx1 - bx0 + 1),
        y0=int(y0 + by0),
        x0=int(x0 + bx0),
        dark=float((b < 0.3 * peak).mean()),
        fill=float((b >= 0.5 * peak).mean()),
    )


def leader_colours(a, mx, lit):
    out = {}
    white = a.min(-1) > pix.WHITE
    out["white_pct"] = float(white.sum() / max(int(lit.sum()), 1) * 100)
    out["core_rgb"] = [float(v) for v in np.median(a[white], 0)] if white.sum() > 20 else None
    if white.sum() > 20:
        d = np.full(mx.shape, 99, np.int16)
        cur = white
        d[cur] = 0
        for k in range(1, 6):
            nxt = pix.dilate(cur, square=True)
            d[nxt & ~cur] = k
            cur = nxt
        ring = (d >= 2) & (d <= 5) & lit
        out["ring_rgb"] = [float(v) for v in np.median(a[ring], 0)] if ring.sum() > 20 else None
    else:
        out["ring_rgb"] = None
    band = (mx >= 200) & (mx < 240) & ~white
    top = (mx >= 240) & ~white
    out["band_rgb"] = [float(v) for v in np.median(a[band], 0)] if band.sum() > 50 else None
    out["top_rgb"] = [float(v) for v in np.median(a[top], 0)] if top.sum() > 50 else None
    far = lit.copy()
    for _ in range(25):
        far = pix.dilate(far, square=True)
    bgm = ~far
    if bgm.sum() < 1000:
        bgm = mx < 25
    out["bg_rgb"] = [float(v) for v in np.median(a[bgm], 0)] if bgm.sum() >= 1000 else None
    return out


def clarity_measure(img, full=True, scale=1.0):
    """img: HxWx3 uint8 at any width (resampled to 1915 unless scale given for gifs)."""
    a = to_1915_wide(img) if scale == 1.0 else img.astype(np.float32)
    mx = a.max(-1)
    lit = mx > pix.LIT
    ys, xs, pv = glyph_peaks(mx, scale)
    out = dict(n_peaks=int(len(pv)), lit=float(lit.mean()))
    out["peak200"] = float((pv > 200).mean()) if len(pv) else float("nan")
    out["peak_lt150"] = float((pv < 150).mean()) if len(pv) else float("nan")
    if full:
        boxes = []
        seen = set()
        n_bright = 0
        for y, x, peak in zip(ys, xs, pv, strict=True):
            if peak <= 200:
                continue
            n_bright += 1
            b = ink_box(mx, int(y), int(x), float(peak))
            if b is not None and b["h"] >= MIN_BOX[0] and b["w"] >= MIN_BOX[1]:
                key = (b["y0"], b["x0"], b["h"], b["w"])
                if key not in seen:
                    seen.add(key)
                    boxes.append(b)
        out["n_bright"] = n_bright
        out["n_boxes"] = len(boxes)
        for k in ("dark", "fill", "h", "w"):
            out[{"fill": "fillb", "h": "box_h", "w": "box_w"}.get(k, k)] = (
                float(np.median([b[k] for b in boxes])) if boxes else float("nan")
            )
        out["aspect"] = (
            float(np.median([b["h"] / b["w"] for b in boxes])) if boxes else float("nan")
        )
    out.update(leader_colours(a, mx, lit))
    return out


def clarity_values(frames, m):
    """The clarity gate values (means over the gated times; colours are medians over the
    times, as in the stills sweep) for cropped frames. `m` is the mean of
    measure() over the same frames."""
    ts = [clarity_measure(f) for f in frames]
    mean = {
        k: float(np.nanmean([x[k] for x in ts]))
        for k in ("dark", "aspect", "peak_lt150", "peak200")
    }

    def med(k):
        arr = [x[k] for x in ts if x[k] is not None]
        return [float(v) for v in np.median(arr, 0)] if arr else None

    core, ring, band = med("core_rgb"), med("ring_rgb"), med("band_rgb")
    core = core or [0.0, 0.0, 0.0]
    ring = ring or [0.0, 1.0, 0.0]  # no leader found: fails the ring gates
    band = band or [0.0, 1.0, 0.0]
    return dict(
        dark=mean["dark"],
        aspect=mean["aspect"],
        lt150=mean["peak_lt150"],
        p200=mean["peak200"],
        core_mean=sum(core) / 3,
        core_b_r=core[2] - core[0],
        ring_r_g=ring[0] / ring[1],
        ring_b_g=ring[2] / ring[1],
        band_sat=1 - min(band) / max(band),
        bg_gx=m["bg_g"] - max(m["bg_r"], m["bg_b"]),
    )


COLUMN_BIN_PX = 25.5  # about one film column at 1915 px wide
DOT_RUN_Y = 64  # ink dot spectra: 64 px runs along y, 16 px runs along x
DOT_RUN_X = 16
DOT_PITCH_PX = 2.6667  # display px at dpi 1.0 (the ink_dots pitch of film_1999)


def ink_residual(a):
    """Green minus its 5 x 5 box mean (the ink texture residual)."""
    g = a[..., 1]
    k = 5
    p = np.pad(g, k // 2, mode="edge")
    c = np.pad(np.cumsum(np.cumsum(p, 0), 1), ((1, 0), (1, 0)))
    return g - (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def residual_spectrum(r, ink, axis, run):
    """Mean power spectrum of the residual over ink runs of run px along `axis` (0: y, 1: x)."""
    if axis == 1:
        r, ink = r.T, ink.T
    height, width = r.shape
    power, n, win = np.zeros(run // 2 + 1), 0, np.hanning(run)
    for x in range(0, width, 2):
        col, ic = r[:, x], ink[:, x]
        for y in range(0, height - run, run // 2):
            if ic[y : y + run].all():
                v = col[y : y + run]
                power += np.abs(np.fft.rfft((v - v.mean()) * win)) ** 2
                n += 1
    return power / max(n, 1), n


def ink_dots(img, pitch):
    """Peak prominence of the ink residual spectrum at the bin of `pitch` px (peak power over
    the mean of the bins two either side), per axis, for one native frame."""
    a = img.astype(np.float32)
    r, ink = ink_residual(a), a.max(-1) > 120
    out = {}
    for ax, lab, run in ((0, "y", DOT_RUN_Y), (1, "x", DOT_RUN_X)):
        power, n = residual_spectrum(r, ink, ax, run)
        k = int(round(run / pitch))
        if n and 2 <= k < len(power) - 2:
            out[f"dot_{lab}"] = float(power[k] / (0.5 * (power[k - 2] + power[k + 2])))
        else:
            out[f"dot_{lab}"] = float("nan")
    return out


def label_components(mask):
    """4-connected labels of a sparse mask (no scipy)."""
    lab = np.zeros(mask.shape, np.int32)
    ys, xs = np.nonzero(mask)
    n = 0
    height, width = mask.shape
    for y0, x0 in zip(ys, xs, strict=True):
        if lab[y0, x0]:
            continue
        n += 1
        st = [(y0, x0)]
        lab[y0, x0] = n
        while st:
            y, x = st.pop()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < height and 0 <= xx < width and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n
                    st.append((yy, xx))
    return lab, n


def leader_openness(a, min_h=12, min_w=8):
    """Leader openness: near-white (min channel above 180) groups by a 2 px dilation; a
    leader is a group whose near-white box is at least 12 x 8 px (h x w). `open` is the share
    of the pixels inside the inscribed ellipse (semi-axes 0.45 h, 0.45 w) that are not
    near-white; medians over leaders."""
    mn = a.min(-1)
    white = mn > pix.WHITE
    lab, n = label_components(pix.dilate(white, 2, square=True))
    out = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero((lab == i) & white)
        if len(ys) == 0:
            continue
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        h, w = y1 - y0 + 1, x1 - x0 + 1
        if h < min_h or w < min_w:
            continue
        yy, xx = np.mgrid[y0 : y1 + 1, x0 : x1 + 1]
        cy, cx = (y0 + y1) / 2, (x0 + x1) / 2
        ell = ((yy - cy) / (0.45 * h)) ** 2 + ((xx - cx) / (0.45 * w)) ** 2 <= 1.0
        inner = mn[y0 : y1 + 1, x0 : x1 + 1][ell]
        out.append(
            dict(
                h=int(h),
                w=int(w),
                open=float((inner <= pix.WHITE).mean()),
                fill=float(len(ys) / (h * w)),
            )
        )
    res = dict(n_lead=len(out))
    for k in ("open", "fill", "h", "w"):
        res[f"lead_{k}"] = float(np.median([o[k] for o in out])) if out else float("nan")
    return res


def column_gaps(a, lit_thr=60, row_share=0.10, bin_px=COLUMN_BIN_PX):
    """Clustering: lit is max channel above 60; bins of 25.5 px (about one film column); a bin
    is lit when at least 10 percent of rows hold a lit pixel in it; gaps are runs of unlit bins
    with a lit bin on both sides; means over 3 bin phases (0, 8.5, 17 px)."""
    lit = a.max(-1) > lit_thr
    width = lit.shape[1]
    res = []
    for ph in (0.0, bin_px / 3, 2 * bin_px / 3):
        edges = np.arange(ph, width + 1e-6, bin_px)
        cols = []
        for x0, x1 in zip(edges[:-1], edges[1:], strict=True):
            sl = lit[:, int(round(x0)) : int(round(x1))]
            if sl.shape[1] == 0:
                continue
            cols.append(sl.any(1).mean() >= row_share)
        cols = np.array(cols, bool)
        runs, cur, seen = [], 0, False
        for v in cols:
            if v:
                if seen and cur:
                    runs.append(cur)
                seen, cur = True, 0
            else:
                cur += 1
        res.append(
            dict(
                lit_bins=float(cols.mean()),
                gap_mean=float(np.mean(runs)) if runs else 0.0,
                gap_max=float(max(runs)) if runs else 0.0,
            )
        )
    return {k: float(np.mean([r[k] for r in res])) for k in res[0]}


def band_239(a):
    """Leader columns (lc239) and near-white percent on 1915 x 801 bands, the shape of the
    2.39:1 stills: the top and the bottom band of the frame, averaged."""
    h = int(round(WIDTH_1915 / 2.39))
    out = []
    for y0 in sorted({0, max(0, a.shape[0] - h)}):
        b = a[y0 : y0 + h]
        lit = b.max(-1) > pix.LIT
        white = b.min(-1) > pix.WHITE
        out.append(
            (
                white.any(0).sum() / max(int(lit.any(0).sum()), 1),
                white.sum() / max(int(lit.sum()), 1) * 100,
            )
        )
    return dict(
        lc239=float(np.mean([o[0] for o in out])), wp239=float(np.mean([o[1] for o in out]))
    )


def followup_measure(crop_img):
    """The follow-up values of one cropped monitor frame (uint8 HxWx3)."""
    a = to_1915_wide(crop_img)
    out = leader_openness(a)
    out.update(band_239(a))
    g = column_gaps(a)
    out.update(g)
    out["open"] = out["lead_open"]
    out["ci"] = g["gap_mean"] * g["lit_bins"]
    return out


def monitor_values(frames, mons, dpi=1.0):
    """Per monitor, each metric is the mean over the gated times; returns the per-monitor
    list and the mean over the monitors. `frames` are grid frames, `mons` the monitor rects.
    The dot peak is read at the bin of the dot pitch scaled by the monitor dpi (the shader
    scales it per monitor)."""
    seeds = []
    for mon in mons:
        rows = slice(mon["y"], mon["y"] + mon["h"])
        cols = slice(mon["x"], mon["x"] + mon["w"])
        crops = [crop(f[rows, cols]) for f in frames]
        vals = [followup_measure(c) for c in crops]
        s = {k: float(np.nanmean([v[k] for v in vals])) for k in ("open", "ci", "lc239")}
        s["wp"] = float(np.mean([measure(c, fix=1920.0 / mon["w"])["white_pct"] for c in crops]))
        d = [ink_dots(c, DOT_PITCH_PX * mon["dpi"]) for c in crops]
        s["dot_y"] = float(np.nanmean([x["dot_y"] for x in d]))
        s["dot_x"] = float(np.nanmean([x["dot_x"] for x in d]))
        seeds.append(s)
    return seeds, {k: float(np.mean([s[k] for s in seeds])) for k in seeds[0]}
