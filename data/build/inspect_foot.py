
import netCDF4 as nc, numpy as np
p = "/root/work/stilt/out/by-id/hrrr-so-20171111-p250_20171111T204641Z_4e47e91dcaf0/hrrr-so-20171111-p250_20171111T204641Z_4e47e91dcaf0_foot.nc"
ds = nc.Dataset(p)
print("=== foot.nc dims ===")
for k,v in ds.dimensions.items(): print(" dim", k, len(v))
print("=== vars ===")
for k,v in ds.variables.items():
    print(" var", k, v.dimensions, v.shape, getattr(v,'units',None))
    if k in ("time","lat","lon"):
        a = np.asarray(v[:])
        print("   ", k, "first/last:", a[0], a[-1], "min/max:", np.nanmin(a), np.nanmax(a))
f = np.asarray(ds.variables["foot"][:])
print("foot shape", f.shape, "dtype", f.dtype, "sum", float(np.nansum(f)), "min/max", float(np.nanmin(f)), float(np.nanmax(f)))
ds.close()
# also the po smoke (ERA5) footprint for later
p2 = "/root/work/stilt/out/by-id/era5-po-20171023-smoke_20171023T120449Z_3571cc857fc8/era5-po-20171023-smoke_20171023T120449Z_3571cc857fc8_foot.nc"
ds2 = nc.Dataset(p2)
print("=== po foot.nc dims ===")
for k,v in ds2.dimensions.items(): print(" dim", k, len(v))
for k,v in ds2.variables.items():
    print(" var", k, v.dimensions, v.shape, getattr(v,'units',None))
    if k in ("time","lat","lon"):
        a = np.asarray(v[:]); print("   ", k, "first/last:", a[0], a[-1])
ds2.close()
