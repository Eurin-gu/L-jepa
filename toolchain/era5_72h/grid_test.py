import importlib.util, os, shutil, tempfile
os.environ["ERA5_GRID_MODE"] = "anchored"
spec = importlib.util.spec_from_file_location("eb", "/root/era5_batch.py")
eb = importlib.util.module_from_spec(spec); spec.loader.exec_module(eb)
tmp = tempfile.mkdtemp(prefix="gridtest_"); eb.OUT = tmp
B = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d"
d = os.path.join(tmp, "po_valley_italy"); os.makedirs(d, exist_ok=True)
shutil.copy2(os.path.join(B,"po_valley_italy","20150208_PL.GRIB"), os.path.join(d,"20150208_PL.GRIB"))
print("  po 参考网格:", eb._grid_sig(os.path.join(d,"20150208_PL.GRIB")))
print("  cent_valley 网格:", eb._grid_sig(os.path.join(B,"cent_valley_CA","20150719_PL.GRIB")))
try:
    eb.split_grib(os.path.join(B,"cent_valley_CA","20150719_PL.GRIB"), "po_valley_italy", "PL")
    print("  FAIL: 未被拦下, 护栏失效")
except RuntimeError as e:
    print("  OK: 已拦下 ->", str(e)[:110])
left = sorted(f for f in os.listdir(d) if f.endswith(".GRIB"))
print("  po 目录残留:", left)
# 反向: 同网格应放行
try:
    w = eb.split_grib(os.path.join(B,"po_valley_italy","20150209_PL.GRIB"), "po_valley_italy", "PL")
    print("  OK: 同网格放行", w)
except RuntimeError as e:
    print("  FAIL: 同网格被误拦 ->", str(e)[:110])
shutil.rmtree(tmp, ignore_errors=True)