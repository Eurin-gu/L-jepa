#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bbox 护栏: 防止"某个区的 CDS 数据被写进另一个区的目录"再次发生.

背景: 2026-09-12 发现 po_valley_italy 目录里有 14 个 cent_valley_CA 的文件,
原因是 cds_harvester v1 硬编码 REGION="po_valley_italy". 该 bug 已由 v2
(按 GRIB bbox 判区) 修复; 本模块是第二道防线 —— 任何写入前后都做 bbox 校验,
不匹配就隔离到 /root/quarantine_badgrib/ 并抛错, 绝不静默留下脏数据.
"""
import os, shutil
import eccodes

QUAR = "/root/quarantine_badgrib"

# 期望 bbox (latmin, latmax, lonmin, lonmax), 对应 era5_batch.area() 的结果
# (receptor bbox 外扩 MARG=6.0, 再按 0.25 deg 网格取整)
REGION_BBOX = {
    "po_valley_italy":   (38.4, 51.9,   2.0,  18.0),
    "north_china_plain": (32.2, 47.0, 108.2, 123.6),
    "so_cal_LA_basin":   (26.0, 41.0, -125.0, -110.0),
    "cent_valley_CA":    (29.0, 45.5, -128.0, -112.8),
    "permian_westTX":    (24.5, 39.0, -109.8, -95.0),
    "co_front_range":    (32.5, 46.6, -112.0, -98.0),
}


def grib_bbox(path):
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
        return (min(la1, la2), max(la1, la2), min(lo1, lo2), max(lo1, lo2))
    except Exception:
        return None


def region_of(path, tol=0.3):
    bb = grib_bbox(path)
    if bb is None:
        return None
    for reg, exp in REGION_BBOX.items():
        if all(abs(bb[i] - exp[i]) < tol for i in range(4)):
            return reg
    return None


def verify_bbox(path, region, tol=0.3):
    """校验 path 的 bbox 是否属于 region. 不匹配则隔离并返回 False."""
    bb = grib_bbox(path)
    exp = REGION_BBOX.get(region)
    if bb is None or exp is None:
        return False
    if all(abs(bb[i] - exp[i]) < tol for i in range(4)):
        return True
    os.makedirs(QUAR, exist_ok=True)
    dst = os.path.join(QUAR, "%s__%s" % (region, os.path.basename(path)))
    try:
        shutil.move(path, dst)
    except Exception:
        pass
    print("[BBOX GUARD] %s 的 bbox=%s 不属于 %s(期望 %s) -> 已隔离 %s"
          % (os.path.basename(path), bb, region, exp, dst), flush=True)
    return False

