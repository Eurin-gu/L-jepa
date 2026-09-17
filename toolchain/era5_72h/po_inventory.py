import os, datetime, importlib.util
spec = importlib.util.spec_from_file_location("bg", "/root/bbox_guard.py")
bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)
BASE = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d"
REC = "/mnt/d/lagrangian-jepa-cn/data/receptors_v2"
reg = "po_valley_italy"
ts = sorted(f.split("_")[1] for f in os.listdir(os.path.join(REC,reg))
            if f.startswith("receptors_") and f.endswith(".csv"))
need = set()
for t in ts:
    dt = datetime.datetime.strptime(t, "%Y%m%d")
    for k in range(4): need.add((dt - datetime.timedelta(days=k)).strftime("%Y%m%d"))
d = os.path.join(BASE, reg)
print("=== po 逐日权威清单 (目标 %d 天 = %d 文件) ===" % (len(need), len(need)*2))
print("%-10s %-5s %-5s %-6s %-6s" % ("日期","PL","SFC","PL大小","SFC大小"))
full = 0; part = 0; none_ = 0
for day in sorted(need):
    pl = os.path.join(d, day+"_PL.GRIB"); sf = os.path.join(d, day+"_SFC.GRIB")
    e_pl = os.path.exists(pl); e_sf = os.path.exists(sf)
    sp = os.path.getsize(pl)/1e6 if e_pl else 0; ss = os.path.getsize(sf)/1e6 if e_sf else 0
    mark = ""
    if e_pl and e_sf: full += 1; mark = "OK"
    elif e_pl or e_sf: part += 1; mark = "** 只有一半 **"
    else: none_ += 1; mark = "缺失"
    print("%-10s %-5s %-5s %-6.1f %-6.1f  %s" % (day, "有" if e_pl else "-", "有" if e_sf else "-", sp, ss, mark))
print()
print("完整 %d 天, 缺一半 %d 天, 全缺 %d 天 -> 已有 %d/%d 文件" % (full, part, none_, (full*2+part), len(need)*2))
print()
print("=== 目录里的非 .GRIB 文件 (干扰项) ===")
for f in sorted(os.listdir(d)):
    if not f.endswith(".GRIB"):
        print("   %-40s %.2f MB" % (f, os.path.getsize(os.path.join(d,f))/1e6))
print()
print("=== 收割器反复报 0.0MB 的 job ===")
hd = "/root/cds_harvest"
for f in sorted(os.listdir(hd)) if os.path.isdir(hd) else []:
    p = os.path.join(hd,f)
    print("   %-40s %.3f MB" % (f, os.path.getsize(p)/1e6))
