import numpy as np, json, os
base = "/mnt/d/lagrangian-jepa-cn/data/datasets/formal_hrrr_formal_test_p1000/20160318"
meta = json.load(open(base + "/meta.json"))
x = np.load(base + "/x.npy"); y = np.load(base + "/y.npy")
log = open("/mnt/d/lagrangian-jepa-cn/data/build/probe_20160318.log","w")
def w(s): log.write(s+"\n"); print(s)
w("sample0: lat %.5f lon %.5f sim %s coverage %.4f footprint_sum %.3f source_grid %s" % (
    meta["samples"][0]["latitude"], meta["samples"][0]["longitude"], meta["samples"][0]["sim_id"],
    meta["samples"][0]["coverage"], meta["samples"][0]["footprint_sum"], meta["samples"][0]["source_grid"]))
# label focus
yy = y[0]; ii = np.unravel_index(np.argmax(yy), yy.shape)
w("y0 argmax (row,col)=%s val=%.4f" % (ii, float(yy[ii])))
# cross-check ch1 (U10M@t0) receptor pixel vs direct npz bilinear
mf = "/mnt/d/lagrangian-jepa-cn/reuse_stilt/server_backup_20260830/hrrr_stilt_production_v1/formal_test_p1000/20160318/model_features/a2016031821_f00.npz"
z = np.load(mf); u10 = z["U10M"]; z.close()
rlat = meta["samples"][0]["latitude"]; rlon = meta["samples"][0]["longitude"]
p1=np.radians(38.5); p0=np.radians(38.5); l0=np.radians(262.5); A=6371229.0
def fwd(lat, lon):
    p=np.radians(np.asarray(lat,dtype=float)); l=np.radians(np.asarray(lon,dtype=float)%360.0)
    n=np.sin(p1); F=(np.cos(p1)*np.tan(np.pi/4+p1/2)**n)/n
    rho=A*F/np.tan(np.pi/4+p/2)**n; rho0=A*F/np.tan(np.pi/4+p0/2)**n; th=n*(l-l0)
    return rho*np.sin(th), rho0-rho*np.cos(th)
nx, ny = 1799, 1059
def togrid(lat, lon):
    sx, sy = fwd(lat, lon)
    return sx/3000.0+(nx-1)/2.0, sy/3000.0+(ny-1)/2.0
gx, gy = togrid(rlat, rlon)
x0=int(np.floor(gx)); y0=int(np.floor(gy)); x0c=min(max(x0,0),nx-2); y0c=min(max(y0,0),ny-2)
fx=gx-x0c; fy=gy-y0c
a=u10[y0c,x0c]; b=u10[y0c,x0c+1]; c=u10[y0c+1,x0c]; d=u10[y0c+1,x0c+1]
db = a*(1-fx)*(1-fy)+b*fx*(1-fy)+c*(1-fx)*fy+d*fx*fy
w("receptor db-cell (%.3f,%.3f) direct npz U10M=%.5f vs x ch1=%.5f  diff=%.2e" % (
    gx, gy, float(db), float(x[0,1,64,64])/0.1, float(db - x[0,1,64,64]/0.1)))
# domain statistics over all samples: finite, label sums, channel means per backhour t0
w("finite x/y all: %s %s  y>=0: %s" % (bool(np.isfinite(x).all()), bool(np.isfinite(y).all()), bool((y>=0).all())))
w("per-channel-1..4 (t0 U,V,PBLH,PRSS normalized) means over samples: %s" %
  [float(x[:,1+i].mean()) for i in range(4)])
log.close()
