
import json
p = "/mnt/d/lagrangian-jepa-cn/mirror/server_backup_20260830/footnet_jepa/data/strict_jul05_apr02/meta.json"
d = json.load(open(p, encoding="utf-8"))
print("keys:", list(d.keys()))
print("snapshots:", d.get("snapshots"))
print("n_samples:", d.get("n_samples"))
print("arrays:", json.dumps(d.get("arrays"), indent=1)[:800])
print("contract:", json.dumps(d.get("contract"), indent=1)[:2000])
print("contract_fingerprint:", d.get("contract_fingerprint"))
print("label_source:", d.get("label_source"), "| manifest:", d.get("manifest"), "| n_skipped:", d.get("n_skipped"))
print("source_fingerprint present:", "source_fingerprint" in d)
s0 = d["samples"][0]
print("sample keys:", list(s0.keys()))
print("sample0:", json.dumps(s0, indent=1)[:2500])
print("n samples:", len(d["samples"]))
