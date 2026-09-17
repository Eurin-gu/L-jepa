import os, json, datetime, glob
import numpy as np
D = "/mnt/d/lagrangian-jepa-cn"

print("=" * 78)
print("1. ERA5 气象 (met_cache/era5d/<区>)  —— 按内容判定, 需 PL+SFC 都在")
REC = os.path.join(D, "data/receptors_v2")
REGS = ["po_valley_italy","north_china_plain","so_cal_LA_basin","cent_valley_CA","permian_westTX","co_front_range"]
tot_need = tot_ok = 0
for reg in REGS:
    ts = set(f.split("_")[1] for f in os.listdir(os.path.join(REC,reg)) if f.startswith("receptors_") and f.endswith(".csv"))
    need = set()
    for t in ts:
        dt = datetime.datetime.strptime(t, "%Y%m%d")
        for k in range(4): need.add((dt - datetime.timedelta(days=k)).strftime("%Y%m%d"))
    d = os.path.join(D, "met_cache/era5d", reg)
    npl = len(glob.glob(os.path.join(d,"*_PL.GRIB"))); nsf = len(glob.glob(os.path.join(d,"*_SFC.GRIB")))
    ok = sum(1 for day in need if os.path.exists(os.path.join(d,day+"_PL.GRIB")) and os.path.exists(os.path.join(d,day+"_SFC.GRIB")))
    tot_need += len(need); tot_ok += ok
    print("  %-20s 目标日 %2d | 需 %2d 天 | 齐备 %2d | 缺 %2d | 磁盘 %d PL + %d SFC" % (reg, len(ts), len(need), ok, len(need)-ok, npl, nsf))
print("  %-20s 合计 %d/%d 天齐备, 缺 %d" % ("", tot_ok, tot_need, tot_need-tot_ok))

print()
print("=" * 78)
print("2. ARL (STILT 直接输入)")
MD = "/root/met_era5"
if os.path.isdir(MD):
    for r in sorted(os.listdir(MD)):
        p = os.path.join(MD, r)
        if os.path.isdir(p):
            fs = [f for f in os.listdir(p) if not f.endswith((".nc",".grib",".idx"))]
            sz = sum(os.path.getsize(os.path.join(p,f)) for f in fs)
            print("  %-22s %3d 天  %.2f GB" % (r, len(fs), sz/1e9))
else: print("  (无)")

print()
print("=" * 78)
print("3. 已建数据集 (data/datasets/*)")
DS = os.path.join(D, "data/datasets")
if os.path.isdir(DS):
    for name in sorted(os.listdir(DS)):
        p = os.path.join(DS, name)
        if not os.path.isdir(p): continue
        # 顶层有 x.npy 还是一个日期一个子目录
        if os.path.exists(os.path.join(p,"x.npy")):
            try:
                x = np.load(os.path.join(p,"x.npy"), mmap_mode="r"); y = np.load(os.path.join(p,"y.npy"), mmap_mode="r")
                print("  %-34s x%s y%s  (样本 %d)" % (name, x.shape, y.shape, x.shape[0]))
            except Exception as e: print("  %-34s 读取失败 %s" % (name, str(e)[:60]))
        else:
            subs = sorted(os.listdir(p))
            n = 0
            for s in subs:
                xf = os.path.join(p,s,"x.npy")
                if os.path.exists(xf):
                    try: n += np.load(xf, mmap_mode="r").shape[0]
                    except Exception: pass
            print("  %-34s %d 个日期子目录, 合计 %d 样本" % (name, len(subs), n))

print()
print("=" * 78)
print("4. 受体 (data/receptors_v2)")
for reg in REGS:
    p = os.path.join(REC, reg)
    cs = glob.glob(os.path.join(p, "receptors_*.csv"))
    ds = sorted(f.split("_")[1] for f in cs)
    nrec = 0
    if cs:
        try: nrec = sum(1 for _ in open(cs[0])) - 1
        except Exception: pass
    print("  %-20s %2d 个日期, 每日期 %d 受体" % (reg, len(ds), nrec))

print()
print("=" * 78)
print("5. 柱足迹 (column footprints)")
for p in ["/root/colfoot", os.path.join(D,"data/build/smoke_out")]:
    if os.path.isdir(p):
        n = len(glob.glob(os.path.join(p,"*.npz")))
        print("  %-40s %d 个 .npz" % (p, n))

print()
print("=" * 78)
print("6. 磁盘")
import shutil
for p in ["/mnt/d/lagrangian-jepa-cn", "/root", "/home/yuki/ljepa"]:
    if os.path.exists(p):
        t, u, f = shutil.disk_usage(p)
        print("  %-28s 挂载点剩余 %.1f GB / 共 %.1f GB" % (p, f/1e9, t/1e9))
