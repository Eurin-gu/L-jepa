#!/usr/bin/env python3
"""Local dataset assembler for JEPA-FootNet (schema v5, physical STILT labels).

Mirrors the semantics of the server pipeline:

  * data_builder._assemble_input (HRRR Lambert-conformal latlon_to_grid_xy,
    bilinear sampling on a receptor-centred 128x128 @ 4 km regular lat/lon
    grid, MET_OFFSETS / MET_SCALES normalisation, 20 channel layout,
    BACKHOURS = [0, 6, 12, 18]);
  * stilt_io.read_stilt_footprint (resample <sim>_foot.nc footprint to the
    receptor-centred metric grid; physical units preserved; NaN-outside-domain
    filled with 0; coverage diagnostic; min_coverage gate);
  * provenance.data_contract / fingerprint / source_fingerprint / atomic_json
    conventions so the output passes train_stilt_strict.load_dataset.

Inputs
------
  --manifest   run_batch CSV with columns
               sim_id,run_time,lati,long,zagl,foot_nc,traj_rds
  --features   per-date feature descriptor JSON (see make_source).
  --out        output directory (x.npy / y.npy / meta.json written here).

The descriptor JSON is the "每日期一个 json: 快照时刻列表 + 每快照的
U10M/V10M/PBLH/PRSS 读取配置" called for by the design; the actual read
functions live in feature_sources.py (declarative dispatch by source_type).
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feature_sources as FS

# ---------------------------------------------------------------------------
# schema-v5 / config constants (copied; do not import footnet_jepa)
# ---------------------------------------------------------------------------
DATA_SCHEMA_VERSION = 5
GRID = 128
SPACING_KM = 4.0
BACKHOURS = [0, 6, 12, 18]
N_MET = 4
N_CHANNELS = 1 + N_MET * len(BACKHOURS) + 3          # 20
MET_OFFSETS = [0.0, 0.0, 1000.0, 90000.0]
MET_SCALES = [0.1, 0.1, 1e-3, 1e-4]
HPERBLOCK = 6.0
DT_SECONDS = 600.0
DIFFUSIVITY = 5000.0
RECEPTOR_MODE = "oco2"                                 # manifest-driven receptors
MIN_CAPTURE_FRACTION = 0.80                            # config.MIN_CAPTURE_FRACTION
TARGET_MODE_PHYSICAL = "stilt_surface_footprint_physical"
LABEL_SOURCE = "stilt_xstilt"
MET_KEYS = ["U10M", "V10M", "PBLH", "PRSS"]

KM_PER_DEG_LAT = 110.54
KM_PER_DEG_LON_EQ = 111.32

# HRRR Lambert conformal projection (data_builder).
_LAT1 = _LAT2 = _LAT0 = 38.5
_LON0 = 262.5
_A = 6371229.0
_DX = _DY = 3000.0
_NX, _NY = 1799, 1059


def _lcc_fwd(lat, lon):
    p1 = np.radians(_LAT1)
    p0 = np.radians(_LAT0)
    l0 = np.radians(_LON0)
    p = np.radians(np.asarray(lat, dtype=np.float64))
    l = np.radians(np.asarray(lon, dtype=np.float64) % 360.0)
    n = np.sin(p1)
    F = (np.cos(p1) * np.tan(np.pi / 4 + p1 / 2) ** n) / n
    rho = _A * F / np.tan(np.pi / 4 + p / 2) ** n
    rho0 = _A * F / np.tan(np.pi / 4 + p0 / 2) ** n
    th = n * (l - l0)
    return rho * np.sin(th), rho0 - rho * np.cos(th)


# Equirectangular grid metadata for ERA5 etc. (filled by main when --grid-type equirect)
EQ = {"dlon": 0.25, "dlat": 0.25, "lon0": None, "lat_first": None, "north_first": True}

def latlon_to_grid_xy_equirect(lat, lon):
    lon = np.asarray(lon, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    xi = (lon - EQ["lon0"]) / EQ["dlon"]
    if EQ["north_first"]:
        yi = (EQ["lat_first"] - lat) / EQ["dlat"]
    else:
        yi = (lat - EQ["lat_first"]) / EQ["dlat"]
    return xi, yi

def probe_era5_grid(source, snapshots):
    """Read grid metadata from the first available ERA5 day grib message."""
    import eccodes
    for s in snapshots:
        p = source.snapshot_file(s)
        if not os.path.isfile(p):
            continue
        with open(p, "rb") as fh:
            g = eccodes.codes_grib_new_from_file(fh)
        if g is None:
            continue
        try:
            EQ["dlon"] = float(eccodes.codes_get(g, "iDirectionIncrementInDegrees"))
            EQ["dlat"] = float(eccodes.codes_get(g, "jDirectionIncrementInDegrees"))
            EQ["lon0"] = float(eccodes.codes_get(g, "longitudeOfFirstGridPointInDegrees"))
            EQ["lat_first"] = float(eccodes.codes_get(g, "latitudeOfFirstGridPointInDegrees"))
            nx = int(eccodes.codes_get(g, "Nx"))
            ny = int(eccodes.codes_get(g, "Ny"))
            lat_last = float(eccodes.codes_get(g, "latitudeOfLastGridPointInDegrees"))
            EQ["north_first"] = lat_first_gt_last(EQ["lat_first"], lat_last)
        finally:
            eccodes.codes_release(g)
        return True
    return False

def lat_first_gt_last(first, last):
    return float(first) > float(last)

def latlon_to_grid_xy(lat, lon):
    if EQ["lon0"] is not None:
        return latlon_to_grid_xy_equirect(lat, lon)
    sx, sy = _lcc_fwd(lat, lon)
    return sx / _DX + (_NX - 1) / 2.0, sy / _DY + (_NY - 1) / 2.0


def receptor_grid(rlat, rlon, grid=GRID, spacing_km=SPACING_KM):
    """Metric receptor-centred grid represented by regular lat/lon axes."""
    offsets = (np.arange(grid) - grid // 2) * spacing_km
    lats = rlat + offsets / KM_PER_DEG_LAT
    coslat = max(float(math.cos(math.radians(rlat))), 1e-3)
    lons = rlon + offsets / (KM_PER_DEG_LON_EQ * coslat)
    return lats, lons, offsets


def _bilinear(field, xi, yi, bounds_error=True):
    """Identical behaviour to data_builder._bilinear."""
    ny, nx = field.shape
    xi = np.asarray(xi, dtype=np.float64)
    yi = np.asarray(yi, dtype=np.float64)
    valid = ((xi >= 0.0) & (xi <= nx - 1.0)
             & (yi >= 0.0) & (yi <= ny - 1.0))
    if bounds_error and not np.all(valid):
        raise ValueError(
            "requested points leave HRRR grid: {} of {} out of bounds".format(
                int(np.size(valid) - valid.sum()), int(np.size(valid))))
    x0 = np.clip(np.floor(xi).astype(np.int64), 0, nx - 2)
    y0 = np.clip(np.floor(yi).astype(np.int64), 0, ny - 2)
    fx = xi - x0
    fy = yi - y0
    a = field[y0, x0]
    b = field[y0, x0 + 1]
    c = field[y0 + 1, x0]
    d = field[y0 + 1, x0 + 1]
    out = (a * (1 - fx) * (1 - fy) + b * fx * (1 - fy)
           + c * (1 - fx) * fy + d * fx * fy)
    return np.where(valid, out, np.nan)


def _normalize_met(field, variable_index):
    return ((field - MET_OFFSETS[variable_index])
            * MET_SCALES[variable_index]).astype(np.float32)


def snapshot_of_run_time(run_time):
    return (run_time[:4] + run_time[5:7] + run_time[8:10]
            + "." + run_time[11:13] + "z")


def back_snapshots(snapshot):
    dt = datetime.datetime(int(snapshot[0:4]), int(snapshot[4:6]),
                           int(snapshot[6:8]), int(snapshot[9:11]))
    return [ (dt - datetime.timedelta(hours=h)).strftime("%Y%m%d.%Hz")
             for h in BACKHOURS ]


# ---------------------------------------------------------------------------
# STILT footprint label (semantics of stilt_io.read_stilt_footprint)
# ---------------------------------------------------------------------------
def _fp_bilinear(field, src_lat, src_lon, q_lat, q_lon):
    """stilt_io._bilinear: bilinear sample with np.interp; NaN outside."""
    ny, nx = field.shape
    fi = np.interp(q_lon, src_lon, np.arange(nx), left=np.nan, right=np.nan)
    fj = np.interp(q_lat, src_lat, np.arange(ny), left=np.nan, right=np.nan)
    inside = np.isfinite(fi) & np.isfinite(fj)
    fi = np.where(inside, fi, 0.0)
    fj = np.where(inside, fj, 0.0)
    x0 = np.floor(fi).astype(np.int64)
    y0 = np.floor(fj).astype(np.int64)
    valid = inside & (x0 >= 0) & (x0 <= nx - 2) & (y0 >= 0) & (y0 <= ny - 2)
    x0c = np.clip(x0, 0, nx - 2)
    y0c = np.clip(y0, 0, ny - 2)
    fx = fi - x0c
    fy = fj - y0c
    a = field[y0c, x0c]
    b = field[y0c, x0c + 1]
    c = field[y0c + 1, x0c]
    d = field[y0c + 1, x0c + 1]
    out = (a * (1 - fx) * (1 - fy) + b * fx * (1 - fy)
           + c * (1 - fx) * fy + d * fx * fy)
    return np.where(valid, out, np.nan)


def read_stilt_footprint(foot_nc_path, rlat, rlon, grid=GRID,
                         spacing_km=SPACING_KM, min_coverage=MIN_CAPTURE_FRACTION):
    """stilt_io.read_stilt_footprint equivalent (physical units preserved)."""
    import netCDF4 as nc

    with nc.Dataset(foot_nc_path) as ds:
        lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
        lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
        foot = np.asarray(ds.variables["foot"][:], dtype=np.float64)
    if foot.ndim == 3:
        foot = foot.sum(axis=0)
    if lat[0] > lat[-1]:
        lat = lat[::-1]
        foot = foot[::-1, :]
    if lon[0] > lon[-1]:
        lon = lon[::-1]
        foot = foot[:, ::-1]
    offsets_km = (np.arange(grid) - grid // 2) * spacing_km
    q_lats = rlat + offsets_km / KM_PER_DEG_LAT
    coslat = max(float(math.cos(math.radians(rlat))), 1e-3)
    q_lons = rlon + offsets_km / (KM_PER_DEG_LON_EQ * coslat)
    lon_g, lat_g = np.meshgrid(q_lons, q_lats)
    y = _fp_bilinear(foot.astype(np.float64), lat, lon,
                     lat_g.ravel(), lon_g.ravel()).reshape(grid, grid)
    coverage = float(np.isfinite(y).mean())
    if coverage < min_coverage:
        raise ValueError(
            "footprint {} covers only {:.3f} of the {}x{} window ({:.2f} "
            "required); expand the stilt domain or shorten the horizon".format(
                os.path.basename(foot_nc_path), coverage, grid, grid,
                min_coverage))
    y = np.where(np.isfinite(y), y, 0.0)
    diagnostics = {
        "coverage": coverage,
        "source_grid": [int(foot.shape[0]), int(foot.shape[1])],
        "footprint_sum": float(np.nansum(y)),
        "units": "stilt_surface_sensitivity",
    }
    return y.astype(np.float32), diagnostics


# ---------------------------------------------------------------------------
# Sample assembly
# ---------------------------------------------------------------------------
def assemble_input(snapshot, receptor, met_cache, grid=GRID, spacing_km=SPACING_KM):
    """data_builder._assemble_input equivalent: (20, grid, grid) float32."""
    rlat, rlon = receptor
    lats, lons, offsets_km = receptor_grid(rlat, rlon, grid, spacing_km)
    lon2d, lat2d = np.meshgrid(lons, lats)
    snaps = back_snapshots(snapshot)
    missing = [s for s in snaps if s not in met_cache]
    if missing:
        raise FileNotFoundError("Missing backhour HRRR snapshots "
                                + str(missing))
    xi, yi = latlon_to_grid_xy(lat2d, lon2d)
    met_ch = []
    for s in snaps:
        m = met_cache[s]
        uu = _bilinear(m["U10M"], xi, yi).astype(np.float32)
        vv = _bilinear(m["V10M"], xi, yi).astype(np.float32)
        met_ch.append(_normalize_met(uu, 0))
        met_ch.append(_normalize_met(vv, 1))
        met_ch.append(_normalize_met(_bilinear(m["PBLH"], xi, yi), 2))
        met_ch.append(_normalize_met(_bilinear(m["PRSS"], xi, yi), 3))
    receptor_query = np.zeros((grid, grid), dtype=np.float32)
    receptor_query[grid // 2, grid // 2] = 1.0
    x_km, y_km = np.meshgrid(offsets_km, offsets_km)
    half_km = grid * spacing_km / 2.0
    x_coord = (x_km / half_km).astype(np.float32)
    y_coord = (y_km / half_km).astype(np.float32)
    radius = (np.hypot(x_km, y_km) / half_km).astype(np.float32)
    met_stack = np.stack(met_ch, axis=2)
    x = np.concatenate([receptor_query[:, :, None], met_stack,
                        x_coord[:, :, None], y_coord[:, :, None],
                        radius[:, :, None]], axis=2)
    return np.transpose(x, (2, 0, 1)).astype(np.float32)


# ---------------------------------------------------------------------------
# Provenance (provenance.py equivalents)
# ---------------------------------------------------------------------------
def data_contract(met_receipts=None):
    if met_receipts:
        alignment = "same_cycle_" + met_receipts.get("cycle_mode", "f00")
        driver = met_receipts.get("driver_source", "local_manifest_receipts")
    else:
        alignment = "valid_time_only_not_same_cycle"
        driver = "external_manifest_unspecified"
    meteorology = {
        "alignment": alignment,
        "model_input_source": "rolling_hrrr_lite_analysis_f00",
        "stilt_driver_source": driver,
    }
    return {
        "schema_version": DATA_SCHEMA_VERSION,
        "grid": int(GRID),
        "spacing_km": float(SPACING_KM),
        "grid_origin": "receptor_at_index_grid_div_2",
        "backhours": list(BACKHOURS),
        "hperblock": float(HPERBLOCK),
        "dt_seconds": float(DT_SECONDS),
        "diffusivity_m2_s": float(DIFFUSIVITY),
        "npart": 0,
        "receptor_mode": RECEPTOR_MODE,
        "feature_layout": [
            "receptor_impulse",
            "4x[U10M,V10M,PBLH,PRSS]",
            "local_x_over_half_domain",
            "local_y_over_half_domain",
            "radius_over_half_domain",
        ],
        "met_offsets": list(MET_OFFSETS),
        "met_scales": list(MET_SCALES),
        "target_mode": TARGET_MODE_PHYSICAL,
        "label_source": LABEL_SOURCE,
        "meteorology": meteorology,
        "minimum_capture_fraction": float(MIN_CAPTURE_FRACTION),
        "random_receptor_bounds": None,
    }


def fingerprint(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_fingerprint(root):
    digest = hashlib.sha256()
    for path in sorted(os.path.join(root, n) for n in os.listdir(root)):
        if not (os.path.isfile(path) and path.endswith(".py")):
            continue
        name = os.path.basename(path)
        digest.update(name.encode("utf-8"))
        with open(path, "rb") as fh:
            digest.update(fh.read())
    return digest.hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(16 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path, payload):
    def json_safe(value):
        if isinstance(value, dict):
            return {key: json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [json_safe(item) for item in value]
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value

    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(json_safe(payload), handle, indent=2, sort_keys=True,
                  allow_nan=False)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Path handling (accept Windows or POSIX paths)
# ---------------------------------------------------------------------------
def norm_path(path):
    if path.startswith("/"):
        return path
    drive = path[0].upper()
    rest = path[2:].replace("\\", "/")
    return "/mnt/" + drive.lower() + rest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--features", required=True,
                    help="per-date feature descriptor JSON")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-coverage", type=float, default=MIN_CAPTURE_FRACTION)
    ap.add_argument("--footnet-root", default=None,
                    help="footnet_jepa code dir used for source_fingerprint")
    ap.add_argument("--limit", type=int, default=None,
                    help="restrict to the first N manifest rows (smoke test)")
    ap.add_argument("--grid-type", default="hrrr_lcc",
                    choices=["hrrr_lcc", "equirect"],
                    help="feature grid projection (equirect for ERA5)")
    ap.add_argument("--met-receipts", default=None,
                    help="JSON with per-snapshot met receipts (cycle_mode/driver_source/files)")
    args = ap.parse_args()

    manifest_path = norm_path(args.manifest)
    out_dir = norm_path(args.out)
    with open(norm_path(args.features), encoding="utf-8") as fh:
        feature_desc = json.load(fh)
    source = FS.make_source(feature_desc)

    with open(manifest_path, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r.get("foot_nc") and os.path.exists(r["foot_nc"])]
    if not rows:
        raise SystemExit("[assemble] no usable rows in " + manifest_path)
    if args.limit is not None:
        rows = rows[:args.limit]
    snapshots = sorted({snapshot_of_run_time(r["run_time"]) for r in rows})
    required = sorted({b for s in snapshots for b in back_snapshots(s)})
    print("[assemble] manifest rows:", len(rows), "snapshots:", snapshots)
    print("[assemble] required feature snapshots:", required)
    for s in required:
        p = source.snapshot_file(s)
        print("[assemble]   feature file:", os.path.exists(p), p)
    if args.grid_type == "equirect":
        if not probe_era5_grid(source, required):
            raise SystemExit("[assemble] could not probe equirect grid")
        print("[assemble] equirect grid:", EQ)

    t0 = time.time()
    met_cache = {}
    for s in required:
        met_cache[s] = source.read_snapshot(s, MET_KEYS)
        info = {k: (v.shape, v.dtype, float(v.mean()))
                for k, v in met_cache[s].items()}
        print("[assemble] loaded", s, info, "({:.1f}s)".format(time.time() - t0))

    X = np.zeros((len(rows), N_CHANNELS, GRID, GRID), dtype=np.float32)
    Y = np.zeros((len(rows), GRID, GRID), dtype=np.float32)
    all_meta = []
    skipped = 0
    kept = 0
    for i, r in enumerate(rows):
        snapshot = snapshot_of_run_time(r["run_time"])
        receptor = (float(r["lati"]), float(r["long"]))
        sim_id = r["sim_id"]
        try:
            x = assemble_input(snapshot, receptor, met_cache, GRID, SPACING_KM)
            y, diag = read_stilt_footprint(
                r["foot_nc"], rlat=receptor[0], rlon=receptor[1],
                grid=GRID, spacing_km=SPACING_KM,
                min_coverage=args.min_coverage)
        except (ValueError, FileNotFoundError, KeyError) as exc:
            print("[assemble]   [skip]", sim_id, ":", exc)
            skipped += 1
            continue
        X[kept] = x
        Y[kept] = y
        sample_meta = {"snapshot": snapshot, "latitude": receptor[0],
                       "longitude": receptor[1], "sim_id": sim_id,
                       "run_time": r["run_time"], "zagl": float(r["zagl"]),
                       **diag}
        all_meta.append(sample_meta)
        kept += 1
        if (i + 1) % 20 == 0:
            print("[assemble]  {}/{} kept={} skip={} ({:.1f}s)".format(
                i + 1, len(rows), kept, skipped, time.time() - t0))
    if kept == 0:
        raise SystemExit("[assemble] every row was skipped; nothing saved")
    X = X[:kept]
    Y = Y[:kept]
    if not (np.isfinite(X).all() and np.isfinite(Y).all() and (Y >= 0).all()):
        raise SystemExit("[assemble] invalid values in built arrays")

    os.makedirs(out_dir, exist_ok=True)
    array_artifacts = {}
    for suffix, array in (("inputs", X), ("targets", Y)):
        path = os.path.join(out_dir, "x.npy" if suffix == "inputs" else "y.npy")
        tmp = path + ".tmp"
        with open(tmp, "wb") as handle:
            np.save(handle, array)
        os.replace(tmp, path)
        array_artifacts[suffix] = {
            "path": os.path.abspath(path),
            "bytes": os.path.getsize(path),
            "sha256": sha256_file(path),
            "shape": list(array.shape),
            "dtype": str(array.dtype),
        }

    met_receipts = None
    if args.met_receipts:
        with open(norm_path(args.met_receipts), encoding="utf-8") as mf:
            met_receipts = json.load(mf)
    contract = data_contract(met_receipts=met_receipts)
    footnet_root = norm_path(args.footnet_root) if args.footnet_root else None
    payload = {
        "snapshots": snapshots,
        "n_samples": kept,
        "samples": all_meta,
        "label_source": LABEL_SOURCE,
        "manifest": os.path.abspath(manifest_path),
        "meteorology_manifest": met_receipts,
        "arrays": array_artifacts,
        "n_skipped": skipped,
        "contract": contract,
        "contract_fingerprint": fingerprint(contract),
        "source_fingerprint": (source_fingerprint(footnet_root)
                               if footnet_root else None),
    }
    atomic_json(os.path.join(out_dir, "meta.json"), payload)
    print("[assemble] saved {} samples -> {} (skip {}) ({:.1f}s)".format(
        kept, out_dir, skipped, time.time() - t0))
    print(json.dumps({"n_samples": kept, "n_skipped": skipped,
                      "arrays": {k: v["shape"] for k, v in array_artifacts.items()}},
                     indent=2))


if __name__ == "__main__":
    main()
