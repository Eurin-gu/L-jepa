import eccodes, numpy as np
want = {("10u","heightAboveGround",10):"U10M", ("10v","heightAboveGround",10):"V10M",
        ("blh","surface",0):"PBLH", ("sp","surface",0):"PRSS"}
with open("/mnt/d/lagrangian-jepa-cn/data/build/inspect_vars.log","w") as log:
    for fn in ["2017111102.grib2","2017111108.grib2","2017111114.grib2","2017111120.grib2"]:
        p = "/mnt/d/lagrangian-jepa-cn/met_cache/hrrr_20171111/" + fn
        f = open(p,"rb")
        log.write("-- file " + fn + "\n")
        while True:
            try:
                m = eccodes.codes_new_from_file(f, eccodes.CODES_PRODUCT_GRIB)
            except Exception:
                continue
            if m is None: break
            try:
                sh = eccodes.codes_get(m,"shortName"); tl = eccodes.codes_get(m,"typeOfLevel"); lv = eccodes.codes_get(m,"level")
                if (sh,tl,lv) in want:
                    arr = np.asarray(eccodes.codes_get_values(m), dtype=np.float64)
                    log.write("%s (%s,%s,%s) unit=%s n=%d min=%.4f max=%.4f mean=%.4f dataDate=%s dataTime=%s step=%s\n" % (
                        want[(sh,tl,lv)], sh, tl, lv, eccodes.codes_get(m,"units"), arr.size,
                        float(np.nanmin(arr)), float(np.nanmax(arr)), float(np.nanmean(arr)),
                        eccodes.codes_get(m,"dataDate"), eccodes.codes_get(m,"dataTime"), eccodes.codes_get(m,"stepRange")))
            except Exception as e:
                log.write("ERR %s\n" % e)
            finally:
                eccodes.codes_release(m)
        f.close()
print("done")
