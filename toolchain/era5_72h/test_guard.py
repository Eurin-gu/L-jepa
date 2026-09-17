import importlib.util, os, shutil, sys, tempfile
spec = importlib.util.spec_from_file_location("eb", "/root/era5_batch.py")
eb = importlib.util.module_from_spec(spec); spec.loader.exec_module(eb)
spec2 = importlib.util.spec_from_file_location("bg", "/root/bbox_guard.py")
bg = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(bg)

print("=== 护栏单元测试 ===")
tmp = tempfile.mkdtemp(prefix="guardtest_")
eb.OUT = tmp

# 场景 A: 把 cent_valley 的数据按 po 写入 -> 必须被拦下
src = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d/cent_valley_CA/20150719_PL.GRIB"
print("源文件(cent_valley):", bg.region_of(src))
try:
    eb.split_grib(src, "po_valley_italy", "PL")
    print("❌ 场景A 未被拦下 —— 护栏失效!")
except RuntimeError as e:
    print("✅ 场景A 已拦下:", str(e)[:110])
leftover = os.listdir(os.path.join(tmp, "po_valley_italy")) if os.path.isdir(os.path.join(tmp,"po_valley_italy")) else []
print("   po 目录残留文件:", leftover)

# 场景 B: 同一份数据按正确区域(cent_valley)写入 -> 必须通过
try:
    w = eb.split_grib(src, "cent_valley_CA", "PL")
    print("✅ 场景B 正确放行, 写入:", w)
except RuntimeError as e:
    print("❌ 场景B 误报:", e)

# 场景 C: 直接对已存在的错区文件调用 verify_bbox
dst = os.path.join(tmp, "po_valley_italy", "20150719_PL.GRIB")
os.makedirs(os.path.dirname(dst), exist_ok=True)
shutil.copy2(src, dst)
ok = bg.verify_bbox(dst, "po_valley_italy")
print("   场景C verify_bbox(错区)=%s (期望 False), 文件是否仍存在=%s (期望 False)" % (ok, os.path.exists(dst)))

shutil.rmtree(tmp, ignore_errors=True)
print()
print("=== 隔离区最终内容 ===")
for f in sorted(os.listdir("/root/quarantine_badgrib")): print("  ", f)
