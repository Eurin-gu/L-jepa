#!/usr/bin/env bash
set -x
cat > /root/train_smoke.py << "PYEOF"
import numpy as np, torch, time
X = np.load("/mnt/d/lagrangian-jepa-cn/data/datasets/so_hrrr_20171111/x.npy")
Y = np.load("/mnt/d/lagrangian-jepa-cn/data/datasets/so_hrrr_20171111/y.npy")
print("X", X.shape, X.dtype, "Y", Y.shape, Y.dtype, flush=True)
dev = "cuda" if torch.cuda.is_available() else "cpu"
print("device", dev, flush=True)
X = torch.from_numpy(X).float().to(dev)
Y = torch.from_numpy(Y).float().to(dev)
class Net(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.e = torch.nn.Sequential(torch.nn.Conv2d(20,16,3,padding=1), torch.nn.ReLU(),
                                    torch.nn.Conv2d(16,16,3,padding=1), torch.nn.ReLU(),
                                    torch.nn.Conv2d(16,8,3,padding=1), torch.nn.ReLU())
        self.h = torch.nn.Conv2d(8,1,1)
    def forward(self,x): return self.h(self.e(x)).squeeze(1)
m = Net().to(dev)
opt = torch.optim.Adam(m.parameters(), 1e-3)
lossf = torch.nn.MSELoss()
t0=time.time()
for step in range(40):
    opt.zero_grad()
    idx = torch.randperm(len(X))[:16].to(dev)
    loss = lossf(m(X[idx]), Y[idx])
    loss.backward(); opt.step()
    if step%10==0: print("step", step, "loss", float(loss), flush=True)
print("SMOKE OK time %.1fs" % (time.time()-t0), flush=True)
PYEOF
/root/venvs/ml/bin/python /root/train_smoke.py 2>&1 | tee /root/train_smoke.log