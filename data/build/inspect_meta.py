
import json
base = "/mnt/d/lagrangian-jepa-cn/mirror/server_backup_20260830/footnet_jepa/data"
for name in ["prod_test_merged","strict_2024_all","prod_all_v5"]:
    p = base + "/%s/meta.json" % name
    d = json.load(open(p, encoding="utf-8"))
    print("="*20, name)
    print("top-level keys:", list(d.keys()))
    for k in d:
        if k != "samples":
            v = d[k]
            if isinstance(v, (dict, list)):
                s = json.dumps(v, ensure_ascii=False)[:500]
            else:
                s = str(v)[:200]
            print(" ", k, "=", s)
    s0 = (d.get("samples") or [None])[0]
    if isinstance(s0, dict):
        print("  sample[0] keys:", list(s0.keys()))
        print("  sample[0] =", json.dumps(s0, ensure_ascii=False)[:1200])
    else:
        print("  samples:", type(d.get("samples")), (len(d.get("samples")) if isinstance(d.get("samples"), list) else None))
