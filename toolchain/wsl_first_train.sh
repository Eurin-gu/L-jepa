#!/usr/bin/env bash
set -x
cat > /root/first_train.py << "PYEOF"
import numpy as np, torch, time, json, csv, os, glob
D = "/mnt/d/lagrangian-jepa-cn/data/datasets"
X = np.load(D + "/formal_hrrr_train_p250_all/x.npy"); Y = np.load(D + "/formal_hrrr_train_p250_all/y.npy")
print("train", X.shape, Y.shape, flush=True)
dev = "cuda"
class Net(torch.nn.Module):
    def __init__(self):
        super().__init__()
        def blk(i,o): return torch.nn.Sequential(torch.nn.Conv2d(i,o,3,padding=1), torch.nn.BatchNorm2d(o), torch.nn.ReLU(), torch.nn.Conv2d(o,o,3,padding=1), torch.nn.ReLU())
        self.b1 = blk(20,32); self.p1 = torch.nn.MaxPool2d(2)
        self.b2 = blk(32,64); self.p2 = torch.nn.MaxPool2d(2)
        self.b3 = blk(64,64)
        self.up = torch.nn.Upsample(scale_factor=4, mode="bilinear", align_corners=False)
        self.h = torch.nn.Conv2d(64,1,1)
    def forward(self,x):
        x = self.up(self.b3(self.p2(self.b2(self.p1(self.b1(x))))))
        return self.h(x).squeeze(1)
m = Net().to(dev)
opt = torch.optim.Adam(m.parameters(), 2e-4)
lossf = torch.nn.MSELoss()
Xt = torch.from_numpy(X).float().to(dev); Yt = torch.from_numpy(Y).float().to(dev)
t0 = time.time()
torch.manual_seed(1)
for ep in range(25):
    perm = torch.randperm(len(Xt))
    tot = 0.0; nb = 0
    for i in range(0, len(Xt), 32):
        idx = perm[i:i+32]
        opt.zero_grad()
        loss = lossf(m(Xt[idx]), Yt[idx])
        loss.backward(); opt.step()
        tot += float(loss); nb += 1
    if ep % 5 == 0 or ep == 24: print("ep", ep, "loss", round(tot/nb,6), flush=True)
print("TRAINED %.0fs" % (time.time()-t0), flush=True)
# evaluate on validation dates (p1000 labels)
rows = []
for vd in ["20160715", "20170517"]:
    dd = D + "/formal_hrrr_validation_p1000/" + vd
    xv = np.load(dd + "/x.npy"); yv = np.load(dd + "/y.npy")
    with torch.no_grad():
        pv = m(torch.from_numpy(xv).float().to(dev)).cpu().numpy()
    rs = []; rms = []
    for s in range(len(yv)):
        a = pv[s].ravel(); b = yv[s].ravel()
        mk = (a > 0) | (b > 0)
        if mk.sum() < 20: continue
        aa, bb = a[mk], b[mk]
        rs.append(float(np.corrcoef(aa, bb)[0,1]))
        den = bb.mean() or 1.0
        rms.append(float(np.sqrt(((aa-bb)**2).mean())/den))
    med_r = float(np.median(rs)); med_rmse = float(np.median(rms))
    rows.append({"val_date": vd, "n": len(yv), "pearson_r_median": round(med_r,4), "relRMSE_median": round(med_rmse,4)})
    print("VAL", vd, "r", round(med_r,4), "relRMSE", round(med_rmse,4), flush=True)
with open("/root/first_train_results.json","w") as f: json.dump({"epochs":25,"rows":rows}, f, indent=1)
print("DONE", flush=True)
PYEOF
/root/venvs/ml/bin/python /root/first_train.py 2>&1 | tee /root/first_train.log