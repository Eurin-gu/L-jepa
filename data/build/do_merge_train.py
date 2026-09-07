import sys, json
sys.path.insert(0, "/mnt/d/lagrangian-jepa-cn/data/build")
import run_arm_build as R
dates = ["20160428","20160523","20160615","20160901","20161021","20170314",
         "20170429","20170611","20171006","20171118"]
out_dir, n, arrays = R.merge_train(dates)
print("merged:", out_dir, "n=", n)
print(json.dumps(arrays, indent=2))
