#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一 72h: 按 plan72.json 补下所有区的额外天数.

按 (区, 年月) 分组批量请求 (PL/SFC 各一个请求), 串行提交避免 CDS 限流,
跳过已存在的文件 (可断点续跑).
"""
import json, os, time, sys, cdsapi
import importlib.util
spec = importlib.util.spec_from_file_location("eb", "/root/era5_batch.py")
eb = importlib.util.module_from_spec(spec); spec.loader.exec_module(eb)

PLAN = json.load(open("/root/plan72.json"))
BASE = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d"
TMP = "/tmp/era5_72all"
os.makedirs(TMP, exist_ok=True)

def have(reg, day, kind):
    """体积达标 **且** bbox 属于本区 才算已有.
    2026-09-12: 原来只查体积, 错区文件(44MB)骗过了它 -> 缺口被掩盖成 0."""
    p = os.path.join(BASE, reg, "%s_%s.GRIB" % (day, kind))
    if not (os.path.exists(p) and os.path.getsize(p) >= (20_000_000 if kind == "PL" else 1_000_000)):
        return False
    import bbox_guard
    return bbox_guard.verify_bbox(p, reg)


def queue_busy():
    """CDS 上处于 accepted/running 的 job 数 (占免费额度).
    2026-09-13: 实测 CDS 队列延迟可 >5 小时, 免费额度只容很少排队.
    队列非空时继续投递只会得到 rejected, 所以必须等它排空."""
    import urllib.request
    cfg = dict(l.split(":", 1) for l in open("/root/.cdsapirc").read().strip().splitlines() if ":" in l)
    req = urllib.request.Request(cfg["url"].strip() + "/retrieve/v1/jobs?limit=100")
    req.add_header("PRIVATE-TOKEN", cfg["key"].strip())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            jobs = json.load(r).get("jobs", [])
        return sum(1 for j in jobs if j.get("status") in ("accepted", "running"))
    except Exception:
        return -1   # 查询失败时按"未知"处理, 不阻塞



def _single_instance():
    """2026-09-13: 之前出现过 3 个 era5_guard + 1 个下载器同时抢 CDS 额度.
    用 flock 保证同一时刻只有一个下载器在跑 (重复启动会直接退出)."""
    import fcntl
    global _LOCK_FH
    _LOCK_FH = open("/root/era5_72all.lock", "w")
    try:
        fcntl.flock(_LOCK_FH, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[单实例锁] 已有 era5_72all 在运行, 本次退出", flush=True)
        raise SystemExit(0)


def main():
    c = cdsapi.Client()
    total_req = 0; done_req = 0; skipped = 0
    # 2026-09-12: po 有 7 天被 v1 收割器写入了 cent_valley 的错误数据,
    # 已隔离并加入 plan72. 提到队首优先修复, 避免排在 100h 之后.
    ORDER = ["po_valley_italy"] + [r for r in sorted(PLAN) if r != "po_valley_italy"]
    for reg in ORDER:
        groups = PLAN[reg]["groups"]
        if not groups:
            print("[%s] 无缺口, 跳过" % reg, flush=True); continue
        ar = eb.area(reg)
        print("[%s] %d 个月组" % (reg, len(groups)), flush=True)
        for ym in sorted(groups):
            days = groups[ym]
            for kind in ("PL", "SFC"):
                full = ["%s%s" % (ym, d) for d in days]
                missing = [d for d in full if not have(reg, d, kind)]
                if not missing:
                    skipped += 1
                    continue
                total_req += 1
                need_days = sorted(set(d[6:] for d in missing))
                for attempt in range(1, 400):
                    nb = queue_busy()
                    if nb > 0:
                        print("    [%s] %s %s: CDS 队列有 %d 个 job 排队中, 等15分再投 (避免被拒)"
                              % (reg, ym, kind, nb), flush=True)
                        time.sleep(900)
                        continue
                    try:
                        eb.fetch_group(c, reg, ym, need_days, kind, ar, TMP)
                        done_req += 1
                        print("    [%s] %s %s OK (缺 %d 天)" % (reg, ym, kind, len(need_days)), flush=True)
                        break
                    except Exception as e:
                        msg = str(e); low = msg.lower()
                        if "reject" in low or "limited" in low or "queued" in low:
                            print("    [%s] %s %s 限流, 等10分 (第%d次)" % (reg, ym, kind, attempt), flush=True)
                            time.sleep(600)
                        else:
                            print("    [%s] %s %s FAIL %s (第%d次)" % (reg, ym, kind, msg[:100], attempt), flush=True)
                            time.sleep(180)
    print("\n72H ALL DONE: 完成 %d 请求, 跳过 %d" % (done_req, skipped), flush=True)

if __name__ == "__main__":
    _single_instance()
    main()

