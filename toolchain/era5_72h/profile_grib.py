import eccodes, collections, os
BASE = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d/po_valley_italy"
def profile(path, label):
    print("=" * 78)
    print("%s  %s  (%.1f MB)" % (label, os.path.basename(path), os.path.getsize(path)/1e6))
    vars_ = {}; levels = set(); times = set(); dates = set()
    grid = {}; ed = set(); gridtype = set(); tlev = set()
    n = 0
    with open(path, "rb") as f:
        while True:
            g = eccodes.codes_grib_new_from_file(f)
            if g is None: break
            n += 1
            try:
                sn = eccodes.codes_get(g, "shortName")
                nm = eccodes.codes_get(g, "name")
                un = eccodes.codes_get(g, "units")
                pid = eccodes.codes_get(g, "paramId")
                tl = eccodes.codes_get(g, "typeOfLevel")
                tlev.add(tl)
                vars_.setdefault(sn, (nm, un, pid, tl))
                levels.add(eccodes.codes_get(g, "level"))
                times.add(eccodes.codes_get(g, "dataTime"))
                dates.add(eccodes.codes_get(g, "dataDate"))
                ed.add(eccodes.codes_get(g, "edition"))
                gridtype.add(eccodes.codes_get(g, "gridType"))
                for k in ("Ni","Nj","iDirectionIncrementInDegrees","jDirectionIncrementInDegrees"):
                    if k not in grid:
                        try: grid[k] = eccodes.codes_get(g, k)
                        except Exception: pass
                if "la1" not in grid:
                    for k in ("latitudeOfFirstGridPointInDegrees","latitudeOfLastGridPointInDegrees",
                              "longitudeOfFirstGridPointInDegrees","longitudeOfLastGridPointInDegrees"):
                        try: grid[k] = round(float(eccodes.codes_get(g,k)),2)
                        except Exception: pass
            except Exception: pass
            eccodes.codes_release(g)
    print("  消息数 %d | GRIB edition %s | gridType %s" % (n, sorted(ed), sorted(gridtype)))
    print("  grid: %s" % grid)
    print("  日期 %s | 时次数 %d (%s..%s)" % (sorted(dates), len(times), min(times), max(times)))
    print("  typeOfLevel: %s" % sorted(tlev))
    print("  层数 %d" % len(levels))
    if len(levels) <= 40: print("  层: %s" % sorted(levels, reverse=True))
    print("  变量 %d 个:" % len(vars_))
    for sn, (nm, un, pid, tl) in sorted(vars_.items()):
        print("     %-8s paramId=%-5s %-34s [%s]  %s" % (sn, pid, nm[:34], un, tl))

profile(os.path.join(BASE, "20171023_PL.GRIB"), "压力层 PL")
profile(os.path.join(BASE, "20171023_SFC.GRIB"), "单层 SFC")
