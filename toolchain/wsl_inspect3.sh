#!/usr/bin/env bash
/root/venvs/cds/bin/python - << "PY"
import eccodes
p = "/mnt/c/Users/Yuki/Downloads/9a62d3ecc94adde0c46f3d8fbea5ec95.grib"
times = set()
with open(p,"rb") as f:
    for i in range(400):
        try: gid = eccodes.codes_grib_new_from_file(f)
        except Exception: break
        if gid is None: break
        try: times.add((eccodes.codes_get(gid,"dataDate"), eccodes.codes_get(gid,"dataTime")))
        except Exception: pass
        eccodes.codes_release(gid)
print("times:", sorted(times))
PY