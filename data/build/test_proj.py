import numpy as np
def log(f, s):
    f.write(s + "\n"); print(s)
f = open("/mnt/d/lagrangian-jepa-cn/data/build/test_proj.log", "w")
_LAT1=_LAT2=_LAT0=38.5; _LON0=262.5; _A=6371229.0; _DX=_DY=3000.0; _NX,_NY=1799,1059
def _lcc_fwd(lat, lon):
    p1=np.radians(_LAT1); p0=np.radians(_LAT0); l0=np.radians(_LON0)
    p=np.radians(np.asarray(lat,dtype=float)); l=np.radians(np.asarray(lon,dtype=float)%360.0)
    n=np.sin(p1); F=(np.cos(p1)*np.tan(np.pi/4+p1/2)**n)/n
    rho=_A*F/np.tan(np.pi/4+p/2)**n; rho0=_A*F/np.tan(np.pi/4+p0/2)**n; th=n*(l-l0)
    return rho*np.sin(th), rho0-rho*np.cos(th)
def latlon_to_grid_xy(lat,lon):
    sx,sy=_lcc_fwd(lat,lon); return sx/_DX+(_NX-1)/2.0, sy/_DY+(_NY-1)/2.0
lat1, lon1 = 21.138123, 237.280472
x, y = latlon_to_grid_xy(lat1, lon1)
log(f, "first grib point -> grid xy (expect ~ (0,0)): %.4f %.4f" % (x, y))
def _lcc_inv(x, y):
    p1=np.radians(_LAT1); p0=np.radians(_LAT0); l0=np.radians(_LON0)
    n=np.sin(p1); F=(np.cos(p1)*np.tan(np.pi/4+p1/2)**n)/n
    rho0=_A*F/np.tan(np.pi/4+p0/2)**n
    sx=(x-(_NX-1)/2.0)*_DX; sy=(y-(_NY-1)/2.0)*_DY
    rho=np.sqrt(sx*sx+(rho0-sy)**2); th=np.arctan2(sx,rho0-sy)
    l=l0+th/n; p=2*np.arctan((_A*F/rho)**(1/n))-np.pi/2
    return np.degrees(p), np.degrees(l)%360.0
log(f, "grid (0,0)-> %.5f %.5f" % _lcc_inv(0,0))
log(f, "grid (1798,1058)-> %.5f %.5f" % _lcc_inv(1798,1058))
log(f, "grid (899,529)-> %.5f %.5f" % _lcc_inv(899,529))
log(f, "grid (899.5,529.0)-> %.5f %.5f" % _lcc_inv(899.5,529))
f.close()
print("done")
