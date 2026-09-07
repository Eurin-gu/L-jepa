#!/usr/bin/env bash
set -x
/root/venvs/cds/bin/pip install -q gcsfs zarr xarray 2>&1 | tail -2
cat > /root/arco_recon.py << "PYEOF"
import gcsfs, time, xarray as xr
fs = gcsfs.GCSFileSystem(anon=True)
day = "gcp-public-data-arco-era5/raw/date-variable-pressure_level/2017/10/22"
ls = fs.ls(day, detail=False)
print("day items:", len(ls))
for x in ls[:20]: print("  ", x)
# try open one var
import os
cand = [x for x in ls if x.endswith(".zarr") or "zarr" in x]
print("zarr cand:", cand[:5])
for p in (cand[:1] if cand else ls[:1]):
    t0=time.time()
    try:
        store = fs.get_mapper(p)
        ds = xr.open_zarr(store, consolidated=False)
        print("opened", p, "%.1fs" % (time.time()-t0))
        print("dims:", dict(ds.sizes))
        print("coords:", list(ds.coords))
        print("vars:", list(ds.data_vars)[:6])
        for v in list(ds.data_vars)[:1]:
            print("var", v, "shape", ds[v].shape, "dtype", ds[v].dtype)
        ds.close()
    except Exception as e:
        print("open ERR", str(e)[:250])