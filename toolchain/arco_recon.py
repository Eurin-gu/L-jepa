import gcsfs, time, xarray as xr
fs = gcsfs.GCSFileSystem(anon=True)
day = "gcp-public-data-arco-era5/raw/date-variable-pressure_level/2017/10/22"
ls = fs.ls(day, detail=False)
print("day items:", len(ls))
for x in ls[:25]: print("  ", x)
cand = [x for x in ls if "zarr" in x or x.endswith("/")]
for p in (cand[:2] if cand else ls[:2]):
    t0 = time.time()
    try:
        ds = xr.open_zarr(fs.get_mapper(p), consolidated=False)
        print("opened", p, "%.1fs" % (time.time()-t0))
        print("dims:", dict(ds.sizes))
        print("coords:", list(ds.coords)[:8])
        print("vars:", list(ds.data_vars)[:8])
        for v in list(ds.data_vars)[:2]:
            print("  var", v, ds[v].shape, ds[v].dtype)
        ds.close()
    except Exception as e:
        print("open ERR", p, str(e)[:220])