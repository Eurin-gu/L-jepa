import sys
sys.path.insert(0, "/mnt/d/lagrangian-jepa-cn/mirror/server_backup_20260830/footnet_jepa")
from pathlib import Path
import json
try:
    import train_stilt_strict as T
except Exception as e:
    import traceback
    traceback.print_exc()
    raise SystemExit("IMPORT_FAIL")
ds = T.load_dataset(Path("/mnt/d/lagrangian-jepa-cn/data/datasets/so_hrrr_20171111"))
print("load_dataset (project train_stilt_strict): PASS")
print("x", ds["x"].shape, ds["x"].dtype, "y", ds["y"].shape, ds["y"].dtype)
print("uniqueness", ds["uniqueness"])
print("fingerprints", ds["fingerprints"])
print("sample0", json.dumps(ds["samples"][0], indent=1)[:800])
print("contract fields:", {k: ds["metadata"]["contract"][k] for k in ("schema_version","grid","spacing_km","target_mode","label_source","meteorology")})
