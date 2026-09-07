#!/usr/bin/env bash
set -x
cat > /root/train_pool3.py << "PYEOF"
import numpy as np, torch, json, time
D="/mnt/d/lagrangian-jepa-cn/data/datasets"
Xtr=np.load(D+"/formal_hrrr_train_p250_all/x.npy"); Ytr=np.load(D+"/formal_hrrr_train_p250_all/y.npy")
Xso=np.load(D+"/so_hrrr_20171111/x.npy"); Yso=np.load(D+"/so_hrrr_20171111/y.npy")
Xcv=np.load(D+"/cv_hrrr_20170522/x.npy"); Ycv=np.load(D+"/cv_hrrr_20170522/y.npy")
X=np.concatenate([Xtr,Xso,Xcv],0); Y=np.concatenate([Ytr,Yso,Ycv],0)
mu=Y.mean(0)
class Net(torch.nn.Module):
    def __init__(self):
        super().__init__()
        def blk(i,o,d=0.15): return torch.nn.Sequential(torch.nn.Conv2d(i,o,3,padding=1),torch.nn.BatchNorm2d(o),torch.nn.ReLU(),torch.nn.Dropout2d(d),torch.nn.Conv2d(o,o,3,padding=1),torch.nn.ReLU())
        self.b1=blk(20,40);self.p1=torch.nn.MaxPool2d(2)
        self.b2=blk(40,80);self.p2=torch.nn.MaxPool2d(2)
        self.b3=blk(80,80)
        self.up=torch.nn.Upsample(scale_factor=4, mode="bilinear", align_corners=False)
        self.h=torch.nn.Conv2d(80,1,1)
    def forward(self,x): return self.h(self.up(self.b3(self.p2(self.b2(self.p1(self.b1(x))))))).squeeze(1)
dev="cuda"; m=Net().to(dev)
opt=torch.optim.AdamW(m.parameters(),3e-4,weight_decay=1e-4)
lossf=torch.nn.MSELoss()
Xt=torch.from_numpy(X).float().to(dev); Yt=torch.from_numpy(Y).float().to(dev); mut=torch.from_numpy(mu).float().to(dev)
torch.manual_seed(7); t0=time.time()
for ep in range(90):
    perm=torch.randperm(len(Xt)); tot=0.; nb=0
    for i in range(0,len(Xt),32):
        idx=perm[i:i+32]; opt.zero_grad()
        pred=m(Xt[idx])
        loss=lossf(torch.log1p(mut+pred.clamp(min=-0.999)), torch.log1p(Yt[idx].clamp(min=0)))
        loss.backward(); opt.step(); tot+=float(loss); nb+=1
    if ep%30==0: print("ep",ep,"loss",round(tot/nb,5),flush=True)
print("trained %.0fs"%(time.time()-t0),flush=True)
def ev(pred, ref):
    rs=[];rms=[]
    for s in range(len(ref)):
        a=pred[s].ravel(); b=ref[s].ravel(); mk=(a>0)|(b>0)
        if mk.sum()<20: continue
        aa,bb=a[mk],b[mk]
        rs.append(float(np.corrcoef(aa,bb)[0,1])); rms.append(float(np.sqrt(((aa-bb)**2).mean())/(bb.mean() or 1)))
    return round(float(np.median(rs)),4), round(float(np.median(rms)),4)
res={"epochs":90}
for vd in ["20160715","20170517"]:
    dd=D+"/formal_hrrr_validation_p1000/"+vd
    xv=np.load(dd+"/x.npy"); yv=np.load(dd+"/y.npy")
    with torch.no_grad(): rp=np.expm1(m(torch.from_numpy(xv).float().to(dev)).cpu().numpy())+mu
    r1=ev(rp,yv)
    print("VAL",vd,"residual r",r1[0],"rmse",r1[1],flush=True)
    res[vd]={"residual_r":r1[0],"residual_relRMSE":r1[1]}
json.dump(res,open("/root/pool3_results.json","w"),indent=1)
print("DONE")
PYEOF
/root/venvs/ml/bin/python /root/train_pool3.py 2>&1 | tee /root/train_pool3.log