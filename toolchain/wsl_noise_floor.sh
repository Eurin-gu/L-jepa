#!/usr/bin/env bash
set -x
cat > /root/noise_floor.py << "PYEOF"
import csv, netCDF4 as nc, numpy as np, os
MA = "/root/auto_run/manifest_so_sb_a2.csv"
MB = "/root/auto_run/manifest_so_sb_b2.csv"
MP = "/root/stilt_out/manifest_20171111_p250.csv"
def load(m):
    d = {}
    with open(m) as fh:
        for r in csv.DictReader(fh):
            key = (r["run_time"], round(float(r["lati"]),5), round(float(r["long"]),5))
            d[key] = r
    return d
def arr(p):
    ds = nc.Dataset(p); v = np.asarray(ds.variables["foot"][0]).astype(np.float64); ds.close()
    return np.nan_to_num(v)
A = load(MA); B = load(MB); P = load(MP)
common = sorted(set(A) & set(B))
print("common A∩B receptors:", len(common))
def metrics(x, y):
    m = (x>0)|(y>0)
    if m.sum() < 10: return None
    xv, yv = x[m], y[m]
    r = float(np.corrcoef(xv, yv)[0,1])
    denom = yv.mean() if yv.mean() > 0 else 1.0
    rmse_rel = float(np.sqrt(((xv-yv)**2).mean())/denom)
    ov = float(np.minimum(xv, yv).sum()/max(xv.max(), 1e-12))
    return r, rmse_rel, ov
import statistics
rs=[]; rms=[]; ovs=[]
for k in common:
    ra, rb = A[k], B[k]
    va = arr(ra["foot_nc"]); vb = arr(rb["foot_nc"])
    m = metrics(va, vb)
    if m: rs.append(m[0]); rms.append(m[1]); ovs.append(m[2])
print("SPLIT-HALF p500a vs p500b  n=%d" % len(rs))
print("  pearson r  : median %.4f  mean %.4f" % (statistics.median(rs), statistics.mean(rs)))
print("  relRMSE    : median %.4f  mean %.4f" % (statistics.median(rms), statistics.mean(rms)))
# pooled vs p250 on common where p250 exists
pk = [k for k in common if k in P]
rs2=[]; rms2=[]
for k in pk:
    va = arr(A[k]["foot_nc"]); vb = arr(B[k]["foot_nc"]); vp = arr(P[k]["foot_nc"])
    vpool = (va+vb)/2.0
    m = metrics(vpool, vp)
    if m: rs2.append(m[0]); rms2.append(m[1])
print("POOLED(p1000-like) vs p250  n=%d" % len(rs2))
print("  pearson r  : median %.4f  mean %.4f" % (statistics.median(rs2), statistics.mean(rs2)))
print("  relRMSE    : median %.4f" % statistics.median(rms2))
PYEOF
/root/venvs/cds/bin/python /root/noise_floor.py 2>&1 | tee /root/noise_floor.log