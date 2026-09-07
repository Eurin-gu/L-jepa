import eccodes, collections
p = "/root/era5_grib/po_20171023_SFC.GRIB"
counts = collections.Counter()
with open(p, "rb") as f:
    while True:
        m = eccodes.codes_new_from_file(f, eccodes.CODES_PRODUCT_GRIB)
        if m is None: break
        try:
            counts[(eccodes.codes_get(m,"shortName"), eccodes.codes_get(m,"paramId"),
                    eccodes.codes_get(m,"typeOfLevel"), eccodes.codes_get(m,"level"))] += 1
        except Exception:
            counts[("??","??","??","??")] += 1
        eccodes.codes_release(m)
with open("/mnt/d/lagrangian-jepa-cn/data/build/inspect_era5sfc.log","w") as log:
    log.write("total messages: %d\n" % sum(counts.values()))
    for k, n in sorted(counts.items()):
        log.write("%d %s\n" % (n, k))
print("done")
