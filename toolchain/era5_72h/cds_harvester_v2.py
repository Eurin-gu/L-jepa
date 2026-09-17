#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CDS 快速收割器 v2 — 修复区域判定 bug.

v1 硬编码 REGION="po_valley_italy", 导致所有区的数据都被拆进 po 目录.
v2 从下载文件的 GRIB bbox 自动判定区域 (job 详情不含区域字段).

机制: /results 返回 JSON 内含对象存储 href, 直接 HTTP GET (77MB/45s),
绕过 cdsapi 的慢速轮询. 实测比轮询快一个数量级.
"""
import json, urllib.request, os, sys, time
import importlib.util
spec = importlib.util.spec_from_file_location("eb", "/root/era5_batch.py")
eb = importlib.util.module_from_spec(spec); spec.loader.exec_module(eb)

DONE_FILE = "/root/harvested_v2.txt"
TMP = "/root/cds_harvest"
cfg = dict(l.split(":", 1) for l in open("/root/.cdsapirc").read().strip().splitlines() if ":" in l)
URL = cfg["url"].strip(); KEY = cfg["key"].strip()

REGION_BBOX = {
    "po_valley_italy":   (38.4, 51.9, 2.0, 18.2),
    "north_china_plain": (32.2, 47.0, 108.2, 123.6),
    "so_cal_LA_basin":   (26.0, 41.0, -125.0, -110.0),
    "cent_valley_CA":    (29.0, 45.5, -128.0, -112.8),
    "permian_westTX":    (24.5, 39.0, -109.8, -95.0),
    "co_front_range":    (32.5, 46.6, -112.0, -98.0),
}


def api(path, timeout=60):
    req = urllib.request.Request(URL + path)
    req.add_header("PRIVATE-TOKEN", KEY)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def region_from_grib(path):
    """Infer region from the GRIB bounding box."""
    import eccodes
    try:
        with open(path, "rb") as f:
            g = eccodes.codes_grib_new_from_file(f)
        if g is None:
            return None
        try:
            la1 = float(eccodes.codes_get(g, "latitudeOfFirstGridPointInDegrees"))
            la2 = float(eccodes.codes_get(g, "latitudeOfLastGridPointInDegrees"))
            lo1 = float(eccodes.codes_get(g, "longitudeOfFirstGridPointInDegrees"))
            lo2 = float(eccodes.codes_get(g, "longitudeOfLastGridPointInDegrees"))
        finally:
            eccodes.codes_release(g)
        s, n = min(la1, la2), max(la1, la2)
        w, e = min(lo1, lo2), max(lo1, lo2)
        for reg, (rs, rn, rw, re_) in REGION_BBOX.items():
            if abs(s-rs) < 0.3 and abs(n-rn) < 0.3 and abs(w-rw) < 0.3 and abs(e-re_) < 0.3:
                return reg
    except Exception:
        return None
    return None


def harvested():
    if not os.path.exists(DONE_FILE): return set()
    return set(l.strip() for l in open(DONE_FILE) if l.strip())


def mark(jid):
    with open(DONE_FILE, "a") as fh:
        fh.write(jid + chr(10))


def harvest(jid):
    meta = api("/retrieve/v1/jobs/" + jid + "/results")
    asset = meta.get("asset", {}).get("value", {})
    href = asset.get("href")
    if not href:
        return False
    os.makedirs(TMP, exist_ok=True)
    out = os.path.join(TMP, "job_%s.grib" % jid[:8])
    t0 = time.time()
    req = urllib.request.Request(href)
    req.add_header("PRIVATE-TOKEN", KEY)
    with urllib.request.urlopen(req, timeout=1800) as r, open(out, "wb") as fh:
        total = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk: break
            fh.write(chunk); total += len(chunk)
    # 2026-09-12: CDS 偶尔返回 3 KB 的"假成功"结果 (GRIB 头在但无有效场),
    # 会导致收割器每轮重复下载+报错. 低于 100 KB 一律判为损坏, 标记跳过;
    # 真正的补救是下载器重新请求 (have() 会发现文件缺失).
    if total < 100_000:
        print("  [%s] 结果仅 %d 字节 (损坏/空), 跳过; 由下载器重新请求" % (jid[:8], total), flush=True)
        try: os.remove(out)
        except Exception: pass
        mark(jid)
        return False
    kind = "PL" if total > 10_000_000 else "SFC"
    reg = region_from_grib(out)
    if reg is None:
        print("  [%s] %s %.1fMB 无法判定区域, 保留以备人工检查: %s" % (jid[:8], kind, total/1e6, out), flush=True)
        # 不 mark: 等人工处理后重跑
        return False
    written = eb.split_grib(out, reg, kind)
    os.remove(out)
    import bbox_guard
    for d in written:
        bbox_guard.verify_bbox(os.path.join(eb.OUT, reg, "%s_%s.GRIB" % (d, kind)), reg)
    print("  [%s] %s %.1fMB %.0fs -> [%s] %s" % (jid[:8], kind, total/1e6, time.time()-t0, reg, written), flush=True)
    mark(jid)
    return True


def main():
    once = "--once" in sys.argv
    print("HARVESTER v2 START (region auto-detected from GRIB bbox)", flush=True)
    while True:
        try:
            jobs = api("/retrieve/v1/jobs?limit=100").get("jobs", [])
        except Exception as e:
            print("  api error: %s" % str(e)[:100], flush=True)
            time.sleep(120); continue
        done = harvested()
        n = 0
        for j in jobs:
            jid = j.get("jobID")
            if not jid or jid in done: continue
            if j.get("status") == "successful":
                try:
                    if harvest(jid): n += 1
                except Exception as e:
                    # 2026-09-12: 不在失败时 mark —— 否则一次网络抖动就把这个 job
                    # 永久标记为已处理, 数据静默丢失. 下一轮会重试.
                    print("  harvest %s failed (下一轮重试): %s" % (jid[:8], str(e)[:120]), flush=True)
        if n:
            print("  收割 %d 个 job" % n, flush=True)
        if once: break
        time.sleep(180)


if __name__ == "__main__":
    main()
