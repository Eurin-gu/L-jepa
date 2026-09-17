import eccodes, os, collections
BASE = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d"

def profile(path):
    """统计一个 GRIB 文件: 消息数, 不同 dataDate, 不同 dataTime(小时), 变量数"""
    dates = collections.Counter(); times = collections.Counter()
    vars_ = set(); levels = set(); n = 0
    with open(path, "rb") as f:
        while True:
            g = eccodes.codes_grib_new_from_file(f)
            if g is None: break
            n += 1
            try:
                dates[int(eccodes.codes_get(g,"dataDate"))] += 1
                times[int(eccodes.codes_get(g,"dataTime"))//100] += 1
                vars_.add(eccodes.codes_get(g,"shortName"))
                try: levels.add(int(eccodes.codes_get(g,"level")))
                except Exception: pass
            except Exception: pass
            eccodes.codes_release(g)
    return n, dict(sorted(dates.items())), dict(sorted(times.items())), len(vars_), len(levels)

SAMPLES = [
  ("po_valley_italy","20150718","PL"), ("po_valley_italy","20160218","PL"),
  ("po_valley_italy","20171023","PL"),
  ("po_valley_italy","20150718","SFC"), ("po_valley_itality" if False else "po_valley_italy","20171023","SFC"),
  ("cent_valley_CA","20150719","PL"),   ("cent_valley_CA","20160906","PL"),
  ("north_china_plain","20150301","PL"),("so_cal_LA_basin","20171111","PL"),
]
print("=== 每个日文件里实际有多少个时次 ===")
print("%-20s %-9s %-4s %7s  %-28s %-24s %5s %5s" % ("region","day","kind","消息数","日期分布","小时分布","变量","层数"))
for reg, day, kind in SAMPLES:
    p = os.path.join(BASE, reg, "%s_%s.GRIB" % (day, kind))
    if not os.path.exists(p):
        print("%-20s %-9s %-4s  (不存在)" % (reg, day, kind)); continue
    n, d, t, nv, nl = profile(p)
    print("%-20s %-9s %-4s %7d  %-28s %-24s %5d %5d" % (reg, day, kind, n, str(d)[:27], str(t)[:23], nv, nl))
