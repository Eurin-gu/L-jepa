#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Composite PBL column footprints from the 5-height runs (v2).

IMPORTANT: STILT writes no foot.nc when the footprint is identically zero
(simulation_step.r returns early with 'No non-zero footprint values found').
Verified: 30/30 missing high-altitude outputs on 20150211 carry that warning.
So a missing layer means foot == 0 (physical), NOT a failed run -- treat it as
a zero layer and keep the receptor (v1 wrongly dropped 25% of samples).

F_col = sum_z w_z * F_z / sum(F_z),  w_z = dp(z) over exp-atmosphere
"""
import csv, glob, os
import numpy as np
import netCDF4 as nc
from collections import defaultdict

AR = "/root/auto_run"
OUTDIR = "/root/colfoot"
HEIGHTS = [5, 100, 300, 800, 1500]

def weights(hs):
    def p(z): return 1013.25 * np.exp(-z / 8000.0)
    b = [0.0]
    for i in range(len(hs) - 1):
        b.append(0.5 * (hs[i] + hs[i + 1]))
    b.append(hs[-1] + 0.5 * (hs[-1] - hs[-2]))
    w = np.array([p(b[i]) - p(b[i + 1]) for i in range(len(hs))])
    return w / w.sum()

W = weights(HEIGHTS)

def load_foot(path):
    d = nc.Dataset(path)
    f = np.array(d.variables["foot"][:], dtype=np.float64)
    lat = np.array(d.variables["lat"][:]); lon = np.array(d.variables["lon"][:])
    d.close()
    if f.ndim == 3: f = f.sum(axis=0)
    return np.squeeze(f), lat, lon

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print("weights:", " ".join("%.4f" % x for x in W), flush=True)
    summary = []
    for mf in sorted(glob.glob(os.path.join(AR, "colmanifest_po_*_p250.csv"))):
        date = os.path.basename(mf).split("_")[2]
        by_rec = defaultdict(dict)
        for r in csv.DictReader(open(mf)):
            by_rec[(r["run_time"], r["lati"], r["long"])][float(r["zagl"])] = r.get("foot_nc") or ""
        n_done = 0
        for key, hmap in by_rec.items():
            feet = {}
            lat = lon = None
            shape = None
            present = 0
            for h in HEIGHTS:
                p = hmap.get(h) or ""
                if p and os.path.exists(p):
                    f, la, lo = load_foot(p)
                    if shape is None: shape = f.shape; lat, lon = la, lo
                    if f.shape != shape:
                        f = None
                    else:
                        present += 1
                else:
                    f = None
                feet[h] = f
            if shape is None:
                continue
            col = np.zeros(shape, dtype=np.float64)
            for h, w in zip(HEIGHTS, W):
                f = feet[h]
                if f is None:
                    continue                      # physical zero layer
                s = f.sum()
                if s > 0:
                    col += w * (f / s)
            # deterministic name: Python hash() is randomised per process,
            # which made re-runs pile up duplicate .npz files
            _lat = ("%.4f" % float(key[1])).replace(".", "p").replace("-", "m")
            _lon = ("%.4f" % float(key[2])).replace(".", "p").replace("-", "m")
            out = os.path.join(OUTDIR, "col_%s_%s_%s.npz" % (date, _lat, _lon))
            np.savez_compressed(out, foot=col.astype(np.float32), lat=lat, lon=lon,
                                heights=np.array(HEIGHTS), weights=W, run_time=key[0],
                                layers_present=present)
            surf = feet[5.0]
            r = float(np.corrcoef(col.ravel(), surf.ravel())[0, 1]) if (surf is not None and col.std() > 0 and surf.std() > 0) else np.nan
            summary.append({"date": date, "lat": key[1], "lon": key[2],
                            "layers_present": present, "col_sum": float(col.sum()),
                            "surf_sum": float(surf.sum()) if surf is not None else np.nan,
                            "r_col_vs_surf": r})
            n_done += 1
        print("[%s] composited %d receptors" % (date, n_done), flush=True)
    if summary:
        csvp = os.path.join(OUTDIR, "column_summary.csv")
        with open(csvp, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(summary[0].keys()))
            w.writeheader(); w.writerows(summary)
        rs = np.array([s["r_col_vs_surf"] for s in summary], dtype=float)
        lp = np.array([s["layers_present"] for s in summary])
        print("summary ->", csvp, "n =", len(summary), flush=True)
        print("  r(col, surf) median = %.3f" % np.nanmedian(rs), flush=True)
        print("  layers_present distribution:", dict(zip(*np.unique(lp, return_counts=True))), flush=True)
        print("  fraction r < 0.9: %.0f%%" % (100 * np.nanmean(rs < 0.9)), flush=True)
    print("COMPOSITE DONE", flush=True)

if __name__ == "__main__":
    main()