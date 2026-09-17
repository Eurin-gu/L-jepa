#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""柱足迹全链路检查 (生产完整性 + 质量 + 合成产物).

用法: /root/venvs/cds/bin/python /root/check_column_full.py
"""
import csv, glob, os
import numpy as np
from collections import defaultdict

AR = "/root/auto_run"
OUT = "/root/colfoot"
HEIGHTS = [5, 100, 300, 800, 1500]

print("=" * 80)
print("柱足迹全链路检查")
print("=" * 80)

# ---------- 1. 生产完整性 ----------
man_files = sorted(glob.glob(os.path.join(AR, "colmanifest_po_*_p250.csv")))
print("\n【1】生产完整性")
print("  日期数: %d/11" % len(man_files))
print()
print("  %-10s %-6s %-6s %-6s %-6s %-6s %-6s" % ("date", "recs", "5m", "100m", "300m", "800m", "1500m"))
print("  " + "-" * 54)
grand = defaultdict(int)
nrec = 0
for mf in man_files:
    date = os.path.basename(mf).split("_")[2]
    by_rec = defaultdict(dict)
    for r in csv.DictReader(open(mf)):
        by_rec[(r["run_time"], r["lati"], r["long"])][float(r["zagl"])] = bool(
            r.get("foot_nc") and os.path.exists(r["foot_nc"]))
    n = len(by_rec); nrec += n
    c = {h: sum(1 for hm in by_rec.values() if hm.get(h)) for h in HEIGHTS}
    for h in HEIGHTS: grand[h] += c[h]
    print("  %-10s %-6d %-6d %-6d %-6d %-6d %-6d" % (
        date, n, c[5.0], c[100.0], c[300.0], c[800.0], c[1500.0]))
print("  " + "-" * 54)
print("  %-10s %-6d %-6d %-6d %-6d %-6d %-6d" % (
    "TOTAL", nrec, grand[5.0], grand[100.0], grand[300.0], grand[800.0], grand[1500.0]))
tot_out = sum(grand.values())
print("\n  foot.nc 产出: %d / %d (%.1f%%)" % (tot_out, nrec * 5, 100.0 * tot_out / (nrec * 5)))
print("  缺失 = 物理零 (STILT 对 foot==0 不写文件)，非运行失败")

# ---------- 2. 合成产物 ----------
print("\n【2】合成产物")
summ = os.path.join(OUT, "column_summary.csv")
npz = glob.glob(os.path.join(OUT, "col_*.npz"))
print("  合成足迹文件: %d 个" % len(npz))
if os.path.exists(summ):
    rows = list(csv.DictReader(open(summ)))
    print("  汇总记录: %d 条" % len(rows))
    rs = np.array([float(r["r_col_vs_surf"]) for r in rows if r["r_col_vs_surf"] not in ("", "nan")])
    lp = np.array([int(r["layers_present"]) for r in rows])
    print("  r(柱, 地表) 中位: %.3f" % np.nanmedian(rs))
    print("  r < 0.9 比例:   %.0f%%" % (100 * np.nanmean(rs < 0.9)))
    print("  层数分布: %s" % dict(zip(*np.unique(lp, return_counts=True))))
    # per-date
    print("\n  按日期的 r(柱,地表) 中位:")
    byd = defaultdict(list)
    for r in rows:
        if r["r_col_vs_surf"] not in ("", "nan"):
            byd[r["date"]].append(float(r["r_col_vs_surf"]))
    for d in sorted(byd):
        v = np.array(byd[d])
        print("    %s  n=%-4d r_med=%.3f" % (d, len(v), np.nanmedian(v)))
else:
    print("  尚未合成 (运行 /root/compose_column.py)")

print("\n" + "=" * 80)

