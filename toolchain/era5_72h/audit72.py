import os, json, datetime, importlib.util
from collections import defaultdict
spec = importlib.util.spec_from_file_location("bg", "/root/bbox_guard.py")
bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)
BASE = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d"
REC = "/mnt/d/lagrangian-jepa-cn/data/receptors_v2"
REGS = ["po_valley_italy","north_china_plain","so_cal_LA_basin",
        "cent_valley_CA","permian_westTX","co_front_range"]

def targets(reg):
    d = os.path.join(REC, reg)
    out = set()
    for f in os.listdir(d):
        if f.startswith("receptors_") and f.endswith(".csv"):
            out.add(f.split("_")[1])
    return sorted(out)

def status(reg, day, kind):
    """返回 ok / missing / wrong"""
    p = os.path.join(BASE, reg, "%s_%s.GRIB" % (day, kind))
    if not os.path.exists(p): return "missing", bg.grib_bbox(p)
    bb = bg.grib_bbox(p)
    exp = bg.REGION_BBOX[reg]
    if bb and all(abs(bb[i]-exp[i]) < 0.35 for i in range(4)): return "ok", bb
    return "wrong", bb

print("=== 72h 完整性审计 (按内容, 非文件名) ===")
print("%-20s %5s %6s %6s %6s %6s %6s" % ("region","目标","需天","完整","缺天","错区","月组"))
print("-"*66)
audit = {}; total_missing = 0; total_wrong = 0; total_reqs = 0
for reg in REGS:
    ts = targets(reg)
    need = set()
    for t in ts:
        dt = datetime.datetime.strptime(t, "%Y%m%d")
        for k in range(4):
            need.add((dt - datetime.timedelta(days=k)).strftime("%Y%m%d"))
    ok=set(); miss=set(); wrong=set()
    for day in sorted(need):
        st_pl,_ = status(reg, day, "PL")
        st_sf,_ = status(reg, day, "SFC")
        if "wrong" in (st_pl, st_sf): wrong.add(day)
        elif "missing" in (st_pl, st_sf): miss.add(day)
        else: ok.add(day)
    g = defaultdict(list)
    for day in sorted(miss): g[day[:6]].append(day[6:])
    reqs = len(g)*2
    audit[reg] = {"targets": ts, "need": sorted(need), "ok": sorted(ok),
                  "missing": sorted(miss), "wrong": sorted(wrong),
                  "groups": {k: sorted(v) for k,v in g.items()}}
    total_missing += len(miss); total_wrong += len(wrong); total_reqs += reqs
    print("%-20s %5d %6d %6d %6d %6d %6d" % (reg, len(ts), len(need), len(ok), len(miss), len(wrong), len(g)))
print("-"*66)
print("合计: 缺 %d 天, 错区 %d 天, 需 %d 个 CDS 请求" % (total_missing, total_wrong, total_reqs))
json.dump(audit, open("/root/audit72.json","w"), indent=1)

print()
print("=== 逐区缺口明细 ===")
for reg in REGS:
    a = audit[reg]
    print("[%s] 缺 %d 天" % (reg, len(a["missing"])))
    for k in sorted(a["groups"]): print("    %s: %s" % (k, ",".join(a["groups"][k])))
    if a["wrong"]: print("    !! 错区: %s" % a["wrong"])

print()
print("=== 与当前 plan72.json 对账 ===")
plan = json.load(open("/root/plan72.json"))
for reg in REGS:
    a = audit[reg]
    pm = sorted(plan.get(reg, {}).get("missing", []))
    true_m = a["missing"]
    same = (pm == true_m)
    print("  %-20s plan72=%2d 真实=%2d  %s" % (reg, len(pm), len(true_m), "一致" if same else "不一致!"))
    if not same:
        print("        plan72 多: %s" % sorted(set(pm)-set(true_m)))
        print("        plan72 漏: %s" % sorted(set(true_m)-set(pm)))
