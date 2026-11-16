"""Platform-neutral helpers of osapi (pure Python, no OS calls)."""

APP_NAME = "MatrixRain"  # folder name for settings and state on every platform


def monitor_signature(mons):
    return tuple(
        (m["x"], m["y"], m["w"], m["h"], round(m["dpi"], 2), m.get("id", "")) for m in mons
    )


def virtual_bounds(mons):
    x = min(m["x"] for m in mons)
    y = min(m["y"] for m in mons)
    w = max(m["x"] + m["w"] for m in mons) - x
    h = max(m["y"] + m["h"] for m in mons) - y
    return x, y, w, h


MIN_DPI_SCALE, MAX_DPI_SCALE = 0.75, 3.0
MIN_REFRESH_HZ, MAX_REFRESH_HZ = 24, 500


def clamp_dpi(scale):
    """The display scale limited to the range the renderers are tuned for."""
    return min(MAX_DPI_SCALE, max(MIN_DPI_SCALE, scale))


def dedupe_ids(mons):
    """Give repeated monitor ids a |2, |3 suffix in list order; returns `mons`."""
    seen = {}
    for mon in mons:
        seen[mon["id"]] = count = seen.get(mon["id"], 0) + 1
        if count > 1:
            mon["id"] += f"|{count}"
    return mons


def valid_refresh_rate(hz, default):
    """`hz` when it is a plausible refresh rate, otherwise `default`."""
    return hz if MIN_REFRESH_HZ <= hz <= MAX_REFRESH_HZ else default
