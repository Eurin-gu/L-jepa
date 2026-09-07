
import eccodes, collections, os
p = "/mnt/d/lagrangian-jepa-cn/met_cache/hrrr_20171111/2017111114.grib2"
def get(m, k):
    try: return eccodes.codes_get(m, k)
    except Exception: return "<NA>"
counts = collections.Counter()
first = {}
def key_of(m):
    return tuple(str(get(m, k)) for k in ("shortName","paramId","typeOfLevel","level"))
f = open(p, "rb")
msgs = 0
while True:
    m = eccodes.codes_new_from_file(f, eccodes.CODES_PRODUCT_GRIB)
    if m is None: break
    msgs += 1
    k = key_of(m)
    counts[k] += 1
    if len(first) < 2:
        first[k] = {kk: get(m, kk) for kk in ["gridType","Nx","Ny","DxInMetres","DyInMetres","latin1","latin2","laD","loV","iScansNegatively","jScansPositively","jPointsAreConsecutive","numberOfDataPoints","latitudeOfFirstGridPointInDegrees","longitudeOfFirstGridPointInDegrees","latitudeOfLastGridPointInDegrees","longitudeOfLastGridPointInDegrees","latitudeOfSouthernPoleInDegrees","longitudeOfSouthernPoleInDegrees"]}
    eccodes.codes_release(m)
f.close()
print("total messages:", msgs)
for k, n in sorted(counts.items()):
    print(n, k)
print("=== grid info ===")
for k, info in first.items():
    print("KEY", k)
    for kk, v in info.items(): print("   ", kk, "=", v)
