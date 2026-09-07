#!/usr/bin/env bash
set -x
/root/venvs/cds/bin/pip install -q netCDF4 2>&1 | tail -1
/root/venvs/cds/bin/python - << "PY"
import netCDF4 as nc
import numpy as np
p = "/root/work/stilt/out/by-id/hrrr-so-20171111-smoke2_20171111T204641Z_4e47e91dcaf0/hrrr-so-20171111-smoke2_20171111T204641Z_4e47e91dcaf0_foot.nc"
ds = nc.Dataset(p)
print("dims:", {k: len(v) for k, v in ds.dimensions.items()})
print("vars:", list(ds.variables.keys()))
for vn in list(ds.variables)[:6]:
    a = np.asarray(ds.variables[vn][:])
    print(vn, a.shape, a.dtype, "sum", float(np.nansum(a)) if a.dtype.kind=="f" else "")
ds.close()
PY