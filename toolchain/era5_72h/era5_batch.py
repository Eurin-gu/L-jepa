#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch ERA5 fetch: ONE CDS request per (region, year-month) per kind.

Instead of one request per (day, PL/SFC) -- which queued 136 requests for the
US regions -- this asks CDS for all needed days of a month at once, then
splits the multi-day GRIB into the per-day files the pipeline expects
(<YYYYMMDD>_PL.GRIB / <YYYYMMDD>_SFC.GRIB).

Why: CDS queue latency dominates. Fewer, larger requests => far less waiting.
"""
import os, sys, time, datetime, signal, cdsapi, eccodes

OUT = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d"
MARG = 6.0
PL_V = ["geopotential", "temperature", "u_component_of_wind",
        "v_component_of_wind", "vertical_velocity", "relative_humidity"]
PL_L = [str(x) for x in [1000,975,950,925,900,875,850,825,800,775,750,700,650,
        600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,
        10,7,5,3,2,1]]
SF_V = ["2m_temperature", "10m_v_component_of_wind", "10m_u_component_of_wind",
        "total_cloud_cover", "surface_pressure", "2m_dewpoint_temperature",
        "boundary_layer_height", "convective_available_potential_energy",
        "geopotential"]
REGIONS = {
  "po_valley_italy": (44.4, 45.9, 8.0, 12.2),
  "north_china_plain": (38.2, 41.0, 114.2, 117.6),
  "so_cal_LA_basin": (32.0, 35.0, -119.0, -116.0),
  "cent_valley_CA": (35.0, 39.5, -122.0, -118.8),
  "permian_westTX": (30.5, 33.0, -103.8, -101.0),
  "co_front_range": (38.5, 40.6, -106.0, -104.0),
}
# minimum plausible sizes (bytes) to consider a per-day file complete
MIN_SIZE = {"PL": 20_000_000, "SFC": 1_000_000}
FETCH_TIMEOUT_S = 28800

class _Timeout(Exception):
    pass

def _alarm(signum, frame):
    raise _Timeout()

GRID_MODE = os.environ.get("ERA5_GRID_MODE", "anchored")   # anchored | native


def _snap_out(v, step=0.25):
    import math
    return math.ceil(v / step - 1e-9) * step


def _snap_in(v, step=0.25):
    import math
    return math.floor(v / step + 1e-9) * step


def _grid_sig(path):
    try:
        with open(path, "rb") as f:
            g = eccodes.codes_grib_new_from_file(f)
        if g is None:
            return None
        try:
            return tuple(round(float(eccodes.codes_get(g, k)), 3) for k in (
                "Ni", "Nj", "latitudeOfFirstGridPointInDegrees",
                "longitudeOfFirstGridPointInDegrees",
                "latitudeOfLastGridPointInDegrees",
                "longitudeOfLastGridPointInDegrees"))
        finally:
            eccodes.codes_release(g)
    except Exception:
        return None


def _check_grid_consistency(out_dir, region, kind, days):
    import glob, bbox_guard
    new = [os.path.join(out_dir, "%s_%s.GRIB" % (d, kind)) for d in days]
    newsig = None
    for fp in new:
        if os.path.exists(fp):
            newsig = _grid_sig(fp); break
    if newsig is None:
        return
    for fp in sorted(glob.glob(os.path.join(out_dir, "*_%s.GRIB" % kind))):
        if fp in new:
            continue
        old = _grid_sig(fp)
        if old is None:
            continue
        if old != newsig:
            os.makedirs(bbox_guard.QUAR, exist_ok=True)
            for f2 in new:
                if os.path.exists(f2):
                    try:
                        os.replace(f2, os.path.join(bbox_guard.QUAR, "GRIDMIX_%s_%s" % (region, os.path.basename(f2))))
                    except Exception:
                        pass
            raise RuntimeError("GRID guard: %s/%s new grid %s != existing %s" % (region, kind, newsig, old))
        return


def area(region):
    s, n, w, e = REGIONS[region]
    a = [n + MARG, w - MARG, s - MARG, e + MARG]
    if GRID_MODE == "native":
        a = [round(_snap_out(a[0]), 4), round(_snap_in(a[1]), 4),
             round(_snap_in(a[2]), 4), round(_snap_out(a[3]), 4)]
    return a

def needed_days(dates):
    days = set()
    for d in dates:
        dt = datetime.datetime.strptime(d, "%Y%m%d")
        days.add((dt - datetime.timedelta(days=1)).strftime("%Y%m%d"))
        days.add(d)
    return sorted(days)

def group_by_month(days):
    g = {}
    for day in days:
        g.setdefault(day[:6], []).append(day[6:])
    return g

def day_file(region, day, kind):
    return os.path.join(OUT, region, "%s_%s.GRIB" % (day, kind))

def day_ok(region, day, kind):
    p = day_file(region, day, kind)
    return os.path.exists(p) and os.path.getsize(p) >= MIN_SIZE[kind]

def split_grib(src, region, kind):
    """Split multi-day GRIB into per-day files. Returns sorted list of days written."""
    out_dir = os.path.join(OUT, region)
    os.makedirs(out_dir, exist_ok=True)
    handles = {}
    written = set()
    with open(src, "rb") as f:
        while True:
            gid = eccodes.codes_grib_new_from_file(f)
            if gid is None:
                break
            try:
                d = int(eccodes.codes_get(gid, "dataDate"))
            except Exception:
                eccodes.codes_release(gid)
                continue
            key = "%08d" % d
            h = handles.get(key)
            if h is None:
                h = open(os.path.join(out_dir, "%s_%s.GRIB" % (key, kind)), "wb")
                handles[key] = h
            eccodes.codes_write(gid, h)
            written.add(key)
            eccodes.codes_release(gid)
    for h in handles.values():
        h.close()
    _check_grid_consistency(out_dir, region, kind, sorted(written))
    # --- bbox 护栏: 绝不把错误区域的数据留在本区目录 ---
    import bbox_guard
    bad = [d for d in sorted(written)
           if not bbox_guard.verify_bbox(os.path.join(out_dir, "%s_%s.GRIB" % (d, kind)), region)]
    if bad:
        raise RuntimeError("BBOX GUARD: %s/%s 收到不属于本区的数据: %s" % (region, kind, bad))
    return sorted(written)

def fetch_group(c, region, ym, ddays, kind, ar, tmpdir):
    y, mth = ym[:4], ym[4:6]
    common = {"product_type": "reanalysis", "year": y, "month": mth,
              "day": sorted(set(ddays)),
              "time": ["%02d:00" % h for h in range(24)],
              "area": ar, "data_format": "grib",
              "download_format": "unarchived", "grid": [0.25, 0.25]}
    if kind == "PL":
        ds = "reanalysis-era5-pressure-levels"
        req = dict(common, variable=PL_V, pressure_level=PL_L)
    else:
        ds = "reanalysis-era5-single-levels"
        req = dict(common, variable=SF_V)
    tmp = os.path.join(tmpdir, "%s_%s_%s.grib" % (region, ym, kind))
    t0 = time.time()
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(FETCH_TIMEOUT_S)
    try:
        c.retrieve(ds, req, tmp)
    finally:
        signal.alarm(0)
    ok_days = split_grib(tmp, region, kind)
    size = os.path.getsize(tmp)
    os.remove(tmp)
    print("[%s] %s %s: %d days in %.0fs (%.1f MB) -> %s"
          % (region, ym, kind, len(ok_days), time.time() - t0, size / 1e6,
             ",".join(d for d in ok_days if d[6:] in ddays)), flush=True)
    return True

def run_region(region, dates):
    c = cdsapi.Client()
    ar = area(region)
    days = needed_days(dates)
    gs = group_by_month(days)
    tmpdir = "/tmp/era5_batch"
    os.makedirs(tmpdir, exist_ok=True)
    print("[%s] %d days in %d month-groups" % (region, len(days), len(gs)), flush=True)
    for ym in sorted(gs):
        ddays = sorted(set(gs[ym]))
        for kind in ("PL", "SFC"):
            full_days = ["%s%s" % (ym, dd) for dd in ddays]
            if all(day_ok(region, d, kind) for d in full_days):
                print("[%s] %s %s already complete" % (region, ym, kind), flush=True)
                continue
            rejects = 0
            for attempt in range(6):
                try:
                    fetch_group(c, region, ym, ddays, kind, ar, tmpdir)
                    break
                except _Timeout:
                    print("[%s] %s %s TIMEOUT %ds, retry %d"
                          % (region, ym, kind, FETCH_TIMEOUT_S, attempt + 1), flush=True)
                    time.sleep(120)
                except Exception as e:
                    msg = str(e)
                    low = msg.lower()
                    if "reject" in low or "limited" in low or "queued" in low:
                        rejects += 1
                        if rejects >= 2:
                            # do NOT storm CDS: exit and let era5_guard.py resume later
                            print("[%s] %s %s RATE-LIMITED twice -> aborting, guard will resume"
                                  % (region, ym, kind), flush=True)
                            raise SystemExit(3)
                        print("[%s] %s %s RATE-LIMITED, one long backoff (1800s)"
                              % (region, ym, kind), flush=True)
                        time.sleep(1800)
                    else:
                        print("[%s] %s %s FAIL %s (retry %d)"
                              % (region, ym, kind, msg[:180], attempt + 1), flush=True)
                        time.sleep(60)
    print("[%s] DONE" % region, flush=True)

US = {
  "so_cal_LA_basin": ["20150102","20150807","20160217","20160318","20160807","20171111"],
  "cent_valley_CA": ["20150111","20150722","20160222","20160908","20170522","20171118"],
  "permian_westTX": ["20150128","20151013","20160319","20160904","20170308","20171016"],
  "co_front_range": ["20150128","20150911","20160422","20161123","20170612"],
}

if __name__ == "__main__":
    # CDS rejects jobs when too many are queued at once (measured: 4 parallel
    # regions x PL+SFC => "The job has been rejected / Number queued ...").
    # So run STRICTLY SERIALLY: exactly one request in the CDS queue at a time,
    # each request carrying a whole month-group of days.
    targets = sys.argv[1:] or sorted(US)
    print("[mode] serial, one CDS request at a time; regions=%s" % ",".join(targets), flush=True)
    for reg in targets:
        while True:
            try:
                run_region(reg, US[reg])
                break
            except Exception as e:
                print("[%s] region-level FAIL %s -- retry in 300s" % (reg, str(e)[:200]), flush=True)
                time.sleep(300)
    print("ERA5 BATCH ALL DONE", flush=True)