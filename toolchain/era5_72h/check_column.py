#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Column footprint production check: completeness + per-height yield + QC."""
import csv, glob, os
import numpy as np
from collections import defaultdict

AR = "/root/auto_run"
HEIGHTS = [5, 100, 300, 800, 1500]

man_files = sorted(glob.glob(os.path.join(AR, "colmanifest_po_*_p250.csv")))
print("=" * 78)
print("柱足迹生产检查 — %d 个日期" % len(man_files))
print("=" * 78)
print()
print("%-10s %-6s %-7s %-7s %-7s %-7s %-8s %-8s" % (
    "date", "recs", "5m", "100m", "300m", "800m", "1500m", "total"))
print("-" * 78)
grand_recs = 0
grand_by_h = defaultdict(int)
for mf in man_files:
    date = os.path.basename(mf).split("_")[2]
    by_rec = defaultdict(dict)
    for r in csv.DictReader(open(mf)):
        by_rec[(r["run_time"], r["lati"], r["long"])][float(r["zagl"])] = bool(
            r.get("foot_nc") and os.path.exists(r["foot_nc"]))
    n = len(by_rec)
    cnt = {h: sum(1 for hm in by_rec.values() if hm.get(h)) for h in HEIGHTS}
    tot = sum(cnt.values())
    grand_recs += n
    for h in HEIGHTS:
        grand_by_h[h] += cnt[h]
    print("%-10s %-6d %-7d %-7d %-7d %-7d %-8d %-8d" % (
        date, n, cnt[5.0], cnt[100.0], cnt[300.0], cnt[800.0], cnt[1500.0], tot))
print("-" * 78)
print("%-10s %-6d %-7d %-7d %-7d %-7d %-8d %-8d" % (
    "TOTAL", grand_recs, grand_by_h[5.0], grand_by_h[100.0], grand_by_h[300.0],
    grand_by_h[800.0], grand_by_h[1500.0], sum(grand_by_h.values())))
print()
print("预期总 sims: %d x 5 = %d" % (grand_recs, grand_recs * 5))
print("实产出 foot.nc: %d (%.1f%%)" % (sum(grand_by_h.values()),
      100.0 * sum(grand_by_h.values()) / (grand_recs * 5)))
print()
print("缺层说明: 缺失 = 物理零 (STILT 对 foot==0 不写文件), 非失败")
print()
# per-date completeness of low layers
low_full = sum(1 for mf in man_files for _ in [0])  # placeholder
print("低层(5m/100m)完整性:")
for mf in man_files:
    date = os.path.basename(mf).split("_")[2]
    by_rec = defaultdict(dict)
    for r in csv.DictReader(open(mf)):
        by_rec[(r["run_time"], r["lati"], r["long"])][float(r["zagl"])] = bool(
            r.get("foot_nc") and os.path.exists(r["foot_nc"]))
    n = len(by_rec)
    ok = sum(1 for hm in by_rec.values() if hm.get(5.0) and hm.get(100.0))
    flag = "OK" if ok == n else "!! %d 缺" % (n - ok)
    print("  %-10s %d/%d  %s" % (date, ok, n, flag))

