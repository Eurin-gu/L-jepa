import argparse
import sys
from pathlib import Path

sys.path.insert(0, "/mnt/d/lagrangian-jepa-cn/mirror/server_backup_20260830/footnet_jepa")
import train_stilt_strict as T  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True)
args = ap.parse_args()
ds = T.load_dataset(Path(args.data))
print("load_dataset PASS")
print("x", ds["x"].shape, ds["x"].dtype, "y", ds["y"].shape, ds["y"].dtype)
print("uniqueness", ds["uniqueness"])
print("fingerprints", ds["fingerprints"])
