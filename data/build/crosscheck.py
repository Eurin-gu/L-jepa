import eccodes, numpy as np, json
p = "/mnt/d/lagrangian-jepa-cn/met_cache/hrrr_20171111/2017111120.grib2"
meta = json.load(open("/mnt/d/lagrangian-jepa-cn/data/datasets/so_hrrr_20171111/meta.json"))
rlat = meta["samples"][0]["latitude"]; rlon = meta["samples"][0]["longitude"]
x = np.load("/mnt/d/lagrangian-jepa-cn/data/datasets/so_hrrr_20171111/x.npy")
# channel 1 = U10M@t0 normalized *0.1 ; sample pixel value near receptor row64 col64
print("assembler U10M at receptor pixel (from x ch1):", float(x[0,1,64,64])/0.1)
f = open(p, "rb")
vals = None; lats = None; lons = None; nx = ny = None
while True:
    m = eccodes.codes_new_from_file(f, eccodes.CODES_PRODUCT_GRIB)
    if m is None: break
    sh = eccodes.codes_get(m, "shortName"); tl = eccodes.codes_get(m, "typeOfLevel"); lv = eccodes.codes_get(m, "level")
    if (sh, tl, lv) == ("10u", "heightAboveGround", 10):
        vals = np.asarray(eccodes.codes_get_values(m), dtype=np.float64)
        nx = int(eccodes.codes_get(m, "Nx")); ny = int(eccodes.codes_get(m, "Ny"))
        try:
            lats = np.asarray(eccodes.codes_get_array(m, "latitudes"))
            lons = np.asarray(eccodes.codes_get_array(m, "longitudes"))
        except Exception as e:
            lats = lons = None
        eccodes.codes_release(m)
        break
    eccodes.codes_release(m)
f.close()
vals = vals.reshape(ny, nx)
def bilin(field, lon, lat, qlat, qlon):
    fi = np.interp(qlon, lon, np.arange(nx), left=np.nan, right=np.nan)
    fj = np.interp(qlat, lat, np.arange(ny), left=np.nan, right=np.nan)
    inside = np.isfinite(fi) & np.isfinite(fj)
    fi = np.where(inside, fi, 0); fj = np.where(inside, fj, 0)
    x0 = np.floor(fi).astype(int); y0 = np.floor(fj).astype(int)
    valid = inside & (x0>=0) & (x0<=nx-2) & (y0>=0) & (y0<=ny-2)
    x0 = np.clip(x0,0,nx-2); y0 = np.clip(y0,0,ny-2)
    fx = fi-x0; fy = fj-y0
    a=field[y0,x0]; b=field[y0,x0+1]; c=field[y0+1,x0]; d=field[y0+1,x0+1]
    out = a*(1-fx)*(1-fy)+b*fx*(1-fy)+c*(1-fx)*fy+d*fx*fy
    return np.where(valid, out, np.nan)
if lats is not None:
    print("native coords available; lat at (0,0),(ny-1,nx-1):", lats[0], lats[-1])
    L = lats.reshape(ny,nx); O = lons.reshape(ny,nx)
    row = np.unique(L[:,0]); col = np.unique(O[0,:])
    v_native = bilin(vals, col, row, rlat, rlon)
    print("native-grid bilinear U10M at receptor:", float(v_native))
else:
    print("latitudes key not available")
# also show assembler-derived value at the true native cell coordinate: value from x at fractional index (row,col of receptor in db space)
print("done")
