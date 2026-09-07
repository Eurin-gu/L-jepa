#!/usr/bin/env bash
p=/mnt/c/Users/Yuki/Downloads/9a62d3ecc94adde0c46f3d8fbea5ec95.grib
ls -la $p 2>/dev/null || echo missing
/root/venvs/cds/bin/python - << "PY"
import eccodes, collections, os
p = "/mnt/c/Users/Yuki/Downloads/9a62d3ecc94adde0c46f3d8fbea5ec95.grib"
if not os.path.exists(p): raise SystemExit("missing")
print("MB", round(os.path.getsize(p)/1e6,1))
n=0; dates=collections.Counter(); shn=collections.Counter(); levs=set(); surf=0
with open(p,"rb") as f:
    while True:
        try: gid=eccodes.codes_grib_new_from_file(f)
        except Exception: break
        if gid is None: break
        n+=1
        try:
            dates[eccodes.codes_get(gid,"dataDate")]+=1
            sn=eccodes.codes_get(gid,"shortName")
            shn[sn]+=1
            lt=eccodes.codes_get(gid,"typeOfLevel")
            if lt=="isobaricInhPa": levs.add(int(eccodes.codes_get(gid,"level")))
            else: surf+=1
        except Exception: pass
        eccodes.codes_release(gid)
print("messages", n)
print("dates", dict(dates))
print("shortnames", dict(shn))
print("nlevs", len(levs), "surface_msgs", surf)
PY