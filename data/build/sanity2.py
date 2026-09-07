import numpy as np, json
base = "/mnt/d/lagrangian-jepa-cn/data/datasets/so_hrrr_20171111"
x = np.load(base + "/x.npy"); y = np.load(base + "/y.npy")
meta = json.load(open(base + "/meta.json"))
s0 = meta["samples"][0]
# label shape: where is footprint mass vs receptor (center=64,64)
yy = y[0]
print("y0 argmax at", np.unravel_index(np.argmax(yy), yy.shape), "max", float(yy.max()))
com = np.array(np.unravel_index(np.arange(yy.size), yy.shape)).T
wsum = yy.sum()
com_rc = np.sum(yy[:, :, None] * com.reshape(128,128,2), axis=(0,1)) / wsum
print("y0 centre-of-mass (row,col):", com_rc, "-> offset from centre:", com_rc - np.array([64.0,64.0]))
print("y0 footprint outside central 40x40 frac:", 1.0 - yy[44:84,44:84].sum()/wsum)
# receptor is inland west of coast; wind at 20z from grib? check U channel mean signs by backhour
for bi in range(4):
    u = x[0, 1+4*bi]; v = x[0, 2+4*bi]
    print("backhour", bi, "mean U_norm", float(u.mean()), "V_norm", float(v.mean()))
# channel layout spot checks
print("ch1..4 (t0) means:", [float(x[0,1+i].mean()) for i in range(4)])
print("ch5..8 (t-6) means:", [float(x[0,5+i].mean()) for i in range(4)])
print("ch17 row center all -1..1 finite", bool(np.isfinite(x[0,17]).all()))
print("radius at corners:", float(x[0,19,0,0]), float(x[0,19,0,-1]))
# 20 channel spatial consistency: impulse col at x index 64 all channels finite
print("finite x all", bool(np.isfinite(x).all()))
print("meta n_samples", meta["n_samples"], "meta samples len", len(meta["samples"]))
print("arrays paths:", meta["arrays"]["inputs"]["path"], meta["arrays"]["targets"]["path"])
print("snapshots:", meta["snapshots"], "label_source:", meta["label_source"])
print("source_fingerprint:", (meta.get("source_fingerprint") or "")[:16])
