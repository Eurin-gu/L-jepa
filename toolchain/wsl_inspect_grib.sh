#!/usr/bin/env bash
/root/venvs/cds/bin/python - << "PY"
import eccodes, collections
p = "/mnt/c/Users/Yuki/Downloads/ae6c2bebd8e7b7804b1a986bc1dafd32.grib"
import os
print("exists", os.path.exists(p), "MB", round(os.path.getsize(p)/1e6,2) if os.path.exists(p) else 0)
n = 0; dates = collections.Counter(); shn = collections.Counter(); levs = set()
with open(p, "rb") as f:
    while True:
        try: gid = eccodes.codes_grib_new_from_file(f)
        except Exception: break
        if gid is None: break
        n += 1
        try:
            dates[eccodes.codes_get(gid,"dataDate")] += 1
            shn[eccodes.codes_get(gid,"shortName")] += 1
            lt = eccodes.codes_get(gid,"typeOfLevel")
            lv = eccodes.codes_get(gid,"level") if lt != "surface" else 0
            if lt in ("isobaricInhPa","isobaricInPa"): levs.add(int(lv))
        except Exception: pass
        eccodes.codes_release(gid)
print("messages:", n)
print("dates:", dict(dates))
print("shortnames:", dict(shn))
print("nlevs:", len(levs), sorted(list(levs))[:12], "...", sorted(list(levs))[-6:])
PY