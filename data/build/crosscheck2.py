import eccodes, numpy as np, json
p = "/mnt/d/lagrangian-jepa-cn/met_cache/hrrr_20171111/2017111120.grib2"
meta = json.load(open("/mnt/d/lagrangian-jepa-cn/data/datasets/so_hrrr_20171111/meta.json"))
rlat = meta["samples"][0]["latitude"]; rlon = meta["samples"][0]["longitude"]
x = np.load("/mnt/d/lagrangian-jepa-cn/data/datasets/so_hrrr_20171111/x.npy")
print("assembler U10M at receptor pixel (db formula):", float(x[0,1,64,64])/0.1)

_LAT1=_LAT0=38.5; _LON0=262.5; _A=6371229.0
def fwd(lat, lon):
    p1=np.radians(_LAT1); p0=np.radians(_LAT0); l0=np.radians(_LON0)
    p=np.radians(np.asarray(lat,dtype=float)); l=np.radians(np.asarray(lon,dtype=float)%360.0)
    n=np.sin(p1); F=(np.cos(p1)*np.tan(np.pi/4+p1/2)**n)/n
    rho=_A*F/np.tan(np.pi/4+p/2)**n; rho0=_A*F/np.tan(np.pi/4+p0/2)**n; th=n*(l-l0)
    return rho*np.sin(th), rho0-rho*np.cos(th)
sx0, sy0 = fwd(21.138123, 237.280472)   # native file cell (0,0)
sxr, syr = fwd(rlat, rlon)
nx = 1799; ny = 1059
fx = (sxr - sx0)/3000.0
fy = (syr - sy0)/3000.0
print("native fractional cell of receptor:", fx, fy, "(in bounds:", 0<=fx<=nx-1 and 0<=fy<=ny-1, ")")
f = open(p, "rb")
vals = None
while True:
    m = eccodes.codes_new_from_file(f, eccodes.CODES_PRODUCT_GRIB)
    if m is None: break
    sh = eccodes.codes_get(m,"shortName"); tl = eccodes.codes_get(m,"typeOfLevel"); lv = eccodes.codes_get(m,"level")
    if (sh,tl,lv)==("10u","heightAboveGround",10):
        vals = np.asarray(eccodes.codes_get_values(m), dtype=np.float64).reshape(ny, nx)
        eccodes.codes_release(m); break
    eccodes.codes_release(m)
f.close()
def bil(field, xf, yf):
    x0 = int(np.floor(xf)); y0 = int(np.floor(yf))
    x0 = min(max(x0,0), nx-2); y0 = min(max(y0,0), ny-2)
    ax = xf-x0; ay = yf-y0
    a=field[y0,x0]; b=field[y0,x0+1]; c=field[y0+1,x0]; d=field[y0+1,x0+1]
    return a*(1-ax)*(1-ay)+b*ax*(1-ay)+c*(1-ax)*ay+d*ax*ay
vnat = bil(vals, fx, fy)
print("native-grid bilinear U10M at receptor:", float(vnat))
print("difference vs db formula:", float(vnat - x[0,1,64,64]/0.1))
# also do db-formula direct at receptor for cross check (should equal ~ch1 value)
def fwd_grid(lat, lon):
    sx, sy = fwd(lat, lon)
    return sx/3000.0 + (nx-1)/2.0, sy/3000.0 + (ny-1)/2.0
gx, gy = fwd_grid(rlat, rlon)
print("db fractional cell of receptor:", gx, gy)
print("db bilinear:", float(bil(vals, gx, gy)))
