"""Parameter sweep for the look presets. Reference tooling, not part of the gate.

Patches looks.PRESETS in process (nothing is written), renders the gated configuration of
tools/checks/check_film.py with the GPU frames of tools/checks/frame_harness.py, and appends one
JSON line per case to the output file: film_metrics.measure values (halo and edge in px at 1915
wide at any width), measure_reference.geometry values and the names of the film_targets windows
that fail.
Hidden window, one case at a time; never run it beside another GPU job.

    <venv python> -I tools/dev/sweep_look.py <cases.json> <out.jsonl>

A case: dict(name, preset, size=[W, H] (default 1920x1080), dpi=1.0 (the monitor dpi, 1.5 for a
2880x1800 panel at 150 percent), patch={preset key: value}, cfg={settings override}, grain=False
(True adds the ink grain gates).
"""

import json
import os
import sys
import time

import numpy as np

TOOLS = os.path.dirname(os.path.abspath(__file__))
CHECKS = os.path.join(os.path.dirname(TOOLS), "checks")
ROOT = os.path.dirname(os.path.dirname(TOOLS))
for folder in (TOOLS, CHECKS, ROOT):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import check_film as cf
import film_metrics as fm
import frame_harness as fh
import measure_reference as mr
from film_targets import BUCKETS, TIMES

from digital_rain import looks

# Windows that the sweep does not take from film_targets.
BG_GRAIN_WINDOW = (0.0, 1.2)
LEADER_COLS_WINDOW = (0.07, 0.22)
LEADER_H50_WINDOW = (2.5, 8.0)
LEADER_H10_WINDOW = (10.0, 38.0)
PARITY_WINDOW = (0.97, 1.03)


def windows(preset):
    t = cf.TARGETS[preset]
    w = {
        "lit": t["lit"],
        "white_pct": t["white"],
        "hue": t["hue"],
        "glyph_h50": t["h50"],
        "glyph_h10": t["h10"],
        "edge": t["edge"],
    }
    for i, (lo, _hi) in enumerate(BUCKETS):
        w[f"b{lo}"] = t["buckets"][i]
    for c in "rgb":
        w[f"bg_{c}"] = t["bg"][c]
        w[f"bg_grain_{c}"] = BG_GRAIN_WINDOW
    if t["head"]:
        for c in "rgb":
            w[f"head_{c}"] = t["head"][c]
    if t["leader"]:
        w["leader_cols"] = LEADER_COLS_WINDOW
        w["lead_h50"] = LEADER_H50_WINDOW
        w["lead_h10"] = LEADER_H10_WINDOW
    if t["run"]:
        w["run"] = (t["run"], 99.0)
    w["parity"] = PARITY_WINDOW
    return w


def run_case(case, out_path):
    t0 = time.time()
    preset = case["preset"]
    width, height = case.get("size", [1920, 1080])
    dpi = case.get("dpi", 1.0)
    params = looks.PRESETS[preset]
    saved = {k: params[k] for k in case.get("patch", {})}
    params.update(case.get("patch", {}))
    extra = dict(case.get("cfg", {}))
    cfg = cf.owner_cfg(preset, **extra)
    mons = [dict(x=0, y=0, w=width, h=height, dpi=dpi, id="")]
    try:
        frames = fh.gpu_frames(ROOT, cfg, (width, height), TIMES, mons=mons)
        vals, geo = [], []
        for frame in frames:
            cropped = fm.crop(frame)
            vals.append(fm.measure(cropped, fix=1920.0 / width))
            geo.append(mr.geometry(cropped.astype(np.float32), width, height))
        m = {k: float(np.mean([v[k] for v in vals])) for k in vals[0]}
        g = {k: float(np.nanmean([v[k] for v in geo])) for k in geo[0]}
        fails = [k for k, (lo, hi) in windows(preset).items() if not (lo <= m[k] <= hi)]
        res = dict(
            name=case["name"],
            preset=preset,
            size=[width, height],
            dpi=dpi,
            patch=case.get("patch", {}),
            cfg=extra,
            m={k: round(v, 4) for k, v in m.items()},
            g={k: round(v, 4) for k, v in g.items()},
            fails=fails,
        )
        if case.get("grain"):
            res["grain1080"] = round(cf.grain_rel((1920, 1080), "quality", preset), 4)
            res["grain540"] = round(cf.grain_rel((960, 540), "quality", preset), 4)
            grain_ink = params["grain_ink"]
            params["grain_ink"] = 0.0
            res["grain0"] = round(cf.grain_rel((1920, 1080), "quality", preset), 4)
            params["grain_ink"] = grain_ink
        res["secs"] = round(time.time() - t0, 1)
        with open(out_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(res) + "\n")
        print(
            case["name"],
            "fails:",
            fails,
            f"lit {m['lit']:.3f} rows {g['row_pitch']:.1f} colpitch {g['col_pitch']:.1f}"
            f" ink {g['ink_spacing']:.1f} inkc {g['ink_cols']:.0f} stroke {g['stroke']:.1f}"
            f" fill {g['fill']:.2f} long {g['long']:.2f} edge {m['edge']:.2f}"
            f" wp {m['white_pct']:.2f} b40 {m['b40']:.2f} b230 {m['b230']:.2f}"
            f" lc {m['leader_cols']:.2f} lh50 {m['lead_h50']:.1f} h50 {m['glyph_h50']:.1f}"
            f" h10 {m['glyph_h10']:.1f} {res['secs']}s",
            flush=True,
        )
    finally:
        params.update(saved)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    with open(sys.argv[1], encoding="utf-8") as handle:
        cases = json.load(handle)
    for case in cases:
        run_case(case, sys.argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())
