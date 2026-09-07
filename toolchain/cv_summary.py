import numpy as np, math
D = "/mnt/d/lagrangian-jepa-cn/data/datasets/cv_hrrr_20170522"
x = np.load(D + "/x.npy"); y = np.load(D + "/y.npy")
print("x", x.shape, "y", y.shape)
mu = y.mean(axis=0)
print("mean footprint: sum=%.1f max=%.4f nz=%.1f%%" % (mu.sum(), mu.max(), 100*np.mean(mu>0)))
def com(a):
    g = np.arange(a.shape[0])
    aa = a/a.sum()
    return float((aa*g[:,None]).sum()), float((aa*g[None,:]).sum())
cm = com(mu)
print("mean footprint CoM (row,col)≈(%.1f,%.1f), grid center=(64,64)" % cm)
# downsample to 16x16 ascii
s = 8  # 128/16
Z = mu.reshape(16, s, 16, s).sum(axis=(1,3))
mx = Z.max() or 1
sym = " .:-=+*#%@"
print("ensemble-mean footprint (16x16, '.'=0; receptor ~ center rows7-8):")
for i in range(16):
    row = ""
    for k in range(16):
        v = Z[i, k]
        row += sym[min(len(sym)-1, int(9*math.sqrt(v/mx)))]
    print("  " + row)
for s in [0, 25, 60, 90, 119]:
    a = y[s]
    c = com(a)
    print("sample %d: sum=%.1f max=%.4f CoM(%.1f,%.1f) nz=%.0f%%" % (s, a.sum(), a.max(), c[0], c[1], 100*np.mean(a>0)))
