import os, datetime
from collections import defaultdict
BASE = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d"
TARGETS = {
  "po_valley_italy": ["20150211","20150721","20150813","20160115","20160221","20160714","20160909","20170101","20170327","20170421","20171023"],
  "north_china_plain": ["20150301","20150520","20150605","20151103","20160106","20160209","20160310","20160506","20161123","20161216","20170626"],
  "so_cal_LA_basin": ["20150102","20150807","20160217","20160318","20160807","20171111"],
  "cent_valley_CA": ["20150111","20150722","20160222","20160908","20170522","20171118"],
  "permian_westTX": ["20150128","20151013","20160319","20160904","20170308","20171016"],
  "co_front_range": ["20150128","20150911","20160422","20161123","20170612"],
}
grand_missing = 0; grand_reqs = 0
print("%-20s %-6s %-8s %-8s %-8s %-8s" % ("region","目标日","需72h","已有","缺天","缺文件"))
print("-" * 68)
allplan = {}
for reg, dates in TARGETS.items():
    need = set()
    for t in dates:
        dt = datetime.datetime.strptime(t, "%Y%m%d")
        for k in range(4):
            need.add((dt - datetime.timedelta(days=k)).strftime("%Y%m%d"))
    have = set()
    d = os.path.join(BASE, reg)
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.endswith(".GRIB"): have.add(f[:8])
    # 已完整(PL+SFC)的天
    have_full = set()
    import bbox_guard
    for day in have:
        p_pl  = os.path.join(d, day+"_PL.GRIB")
        p_sfc = os.path.join(d, day+"_SFC.GRIB")
        if not (os.path.exists(p_pl) and os.path.exists(p_sfc)):
            continue
        # 内容校验: 体积 + bbox 都必须对
        if os.path.getsize(p_pl) < 20_000_000 or os.path.getsize(p_sfc) < 1_000_000:
            continue
        if bbox_guard.verify_bbox(p_pl, reg) and bbox_guard.verify_bbox(p_sfc, reg):
            have_full.add(day)
    miss = sorted(need - have_full)
    # 按月分组算请求数
    g = defaultdict(list)
    for day in miss: g[day[:6]].append(day[6:])
    reqs = len(g) * 2
    grand_missing += len(miss); grand_reqs += reqs
    allplan[reg] = (miss, g)
    print("%-20s %-6d %-8d %-8d %-8d %-8d" % (reg, len(dates), len(need), len(have_full), len(miss), len(miss)*2))
print("-" * 68)
print("合计: 缺 %d 天 = %d 个文件, 约 %.1f GB" % (grand_missing, grand_missing*2, grand_missing*2*0.0405))
print("预计 CDS 请求: %d 个 (约 %.0f 小时 @50min/请求)" % (grand_reqs, grand_reqs*50/60))
print()
import json
plan = {r: {"missing": m, "groups": {k: v for k, v in g.items()}} for r, (m, g) in allplan.items()}
json.dump(plan, open("/root/plan72.json", "w"), indent=1)
print("计划已存 /root/plan72.json")
print()
for reg, (miss, g) in allplan.items():
    print("%s: %d 天, %d 个月组" % (reg, len(miss), len(g)))
    for k in sorted(g): print("    %s: %s" % (k, ",".join(sorted(g[k]))))
