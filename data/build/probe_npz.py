import numpy as np, json, os
base = "/mnt/d/lagrangian-jepa-cn/reuse_stilt/server_backup_20260830/hrrr_stilt_production_v1"
log = open("/mnt/d/lagrangian-jepa-cn/data/build/npz_probe.log","w")
for rel in ["train_p250/20160428/model_features/a2016042820_f00.npz",
            "train_p250/20170314/model_features/a2017031421_f00.npz",
            "formal_test_p1000/20160318/model_features/a2016031821_f00.npz"]:
    p = base + "/" + rel
    z = np.load(p)
    log.write("== " + rel + "\n")
    for k in z.files:
        a = z[k]
        log.write("  %s shape=%s dtype=%s finite=%s min=%.4f max=%.4f mean=%.4f\n" % (
            k, a.shape, a.dtype, bool(np.isfinite(a).all()),
            float(np.nanmin(a)), float(np.nanmax(a)), float(np.nanmean(a))))
    z.close()
    jp = p + ".json"
    if os.path.exists(jp):
        d = json.load(open(jp))
        log.write("  json: %s\n" % json.dumps(d)[:700])
log.close()
print("done")
