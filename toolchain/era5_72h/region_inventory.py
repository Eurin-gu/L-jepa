import os, datetime
BASE = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d"
REC = "/mnt/d/lagrangian-jepa-cn/data/receptors_v2"
REGS = ["po_valley_italy","north_china_plain","so_cal_LA_basin","cent_valley_CA","permian_westTX","co_front_range"]
def targets(reg):
    return sorted(f.split("_")[1] for f in os.listdir(os.path.join(REC,reg))
                  if f.startswith("receptors_") and f.endswith(".csv"))
print("=== 6 区权威状态 (目标日 -> 4 天窗口 -> PL+SFC) ===")
print("%-20s %5s %5s %6s %7s %7s" % ("region","目标日","天数","应有文件","实有","缺"))
T_n=T_d=T_f=T_h=0
detail = {}
for reg in REGS:
    ts = targets(reg); need=set()
    for t in ts:
        dt = datetime.datetime.strptime(t,"%Y%m%d")
        for k in range(4): need.add((dt - datetime.timedelta(days=k)).strftime("%Y%m%d"))
    d = os.path.join(BASE,reg)
    have = 0; miss_days=[]
    for day in sorted(need):
        a = os.path.exists(os.path.join(d, day+"_PL.GRIB"))
        b = os.path.exists(os.path.join(d, day+"_SFC.GRIB"))
        if a and b: have += 2
        else: miss_days.append(day)
    tot = len(need)*2
    print("%-20s %5d %5d %6d %7d %7d" % (reg, len(ts), len(need), tot, have, tot-have))
    T_n+=len(ts); T_d+=len(need); T_f+=tot; T_h+=have
    detail[reg] = miss_days
print("%-20s %5d %5d %6d %7d %7d" % ("合计", T_n, T_d, T_f, T_h, T_f-T_h))
print()
for reg in REGS:
    md = detail[reg]
    print("[%s] 缺 %d 天: %s" % (reg, len(md), " ".join(md) if md else "无"))
print()
print("=== co_front_range 目录实际内容 ===")
d = os.path.join(BASE,"co_front_range")
for f in sorted(os.listdir(d)): print("   ", f)
