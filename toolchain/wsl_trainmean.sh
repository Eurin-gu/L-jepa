#!/usr/bin/env bash
cat > /root/trainmean_eval.py << "PYEOF"
import numpy as np
D = "/mnt/d/lagrangian-jepa-cn/data/datasets"
Xtr = np.load(D + "/formal_hrrr_train_p250_all/y.npy")
mu = Xtr.mean(axis=0)
for vd in ["20160715", "20170517"]:
    yv = np.load(D + "/formal_hrrr_validation_p1000/%s/y.npy" % vd)
    rs=[]; rms=[]
    for s in range(len(yv)):
        a = mu.ravel(); b = yv[s].ravel()
        mk = (a>0)|(b>0)
        if mk.sum()<20: continue
        aa,bb = a[mk], b[mk]
        rs.append(float(np.corrcoef(aa,bb)[0,1]))
        rms.append(float(np.sqrt(((aa-bb)**2).mean())/(bb.mean() or 1.0)))
    print("TRAINMEAN", vd, "r", round(float(np.median(rs)),4), "relRMSE", round(float(np.median(rms)),4), flush=True)
PYEOF
/root/venvs/ml/bin/python /root/trainmean_eval.py 2>&1 | tee /root/trainmean.log