import eccodes, os
BASE = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d"
EXPECT = {
  "po_valley_italy":   (38.4, 51.9,   2.0,  18.2),
  "north_china_plain": (32.2, 47.0, 108.2, 123.6),
  "so_cal_LA_basin":   (26.0, 41.0,-125.0,-110.0),
  "cent_valley_CA":    (29.0, 45.5,-128.0,-112.8),
  "permian_westTX":    (24.5, 39.0,-109.8, -95.0),
  "co_front_range":    (32.5, 46.6,-112.0, -98.0),
}
def bbox(p):
    try:
        with open(p, "rb") as f:
            g = eccodes.codes_grib_new_from_file(f)
        if g is None: return None
        try:
            la1=float(eccodes.codes_get(g,"latitudeOfFirstGridPointInDegrees"))
            la2=float(eccodes.codes_get(g,"latitudeOfLastGridPointInDegrees"))
            lo1=float(eccodes.codes_get(g,"longitudeOfFirstGridPointInDegrees"))
            lo2=float(eccodes.codes_get(g,"longitudeOfLastGridPointInDegrees"))
        finally: eccodes.codes_release(g)
        return (min(la1,la2), max(la1,la2), min(lo1,lo2), max(lo1,lo2))
    except Exception: return None

print("=== 全 6 区 bbox 污染扫描 ===")
print()
total_bad = 0
for reg, exp in EXPECT.items():
    d = os.path.join(BASE, reg)
    if not os.path.isdir(d): continue
    files = sorted(f for f in os.listdir(d) if f.endswith(".GRIB"))
    bad = []
    for f in files:
        bb = bbox(os.path.join(d, f))
        if bb is None: continue
        if not (abs(bb[0]-exp[0])<0.3 and abs(bb[1]-exp[1])<0.3 and abs(bb[2]-exp[2])<0.3 and abs(bb[3]-exp[3])<0.3):
            bad.append((f, bb))
    total_bad += len(bad)
    mark = "OK" if not bad else "污染 %d" % len(bad)
    print("  %-20s %3d 文件  %s" % (reg, len(files), mark))
    for f, bb in bad:
        print("       %-24s bbox=%.1f..%.1f, %.1f..%.1f" % (f, bb[0], bb[1], bb[2], bb[3]))
print()
print("合计污染文件: %d" % total_bad)
