"""Build a real-HRRR JEPA-FootNet dataset.

Each sample is a receptor-centred meteorological window plus a 24 h
back-trajectory footprint proxy generated from real HRRR winds.

Receptors:
  * oco2   : sampled from the real OCO-2 sounding manifests (SoCal overpasses)
  * random : uniformly sampled over CONUS with a margin for the output window

The footprint label is produced by `simple_lagrangian.back_trajectory_footprint`
using real U10M/V10M fields.  This is an OSSE/proxy, not a STILT label.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import time

import netCDF4 as nc
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
from simple_lagrangian import back_trajectory_footprint
from provenance import atomic_json, data_contract, fingerprint, source_fingerprint

# ---------------------------------------------------------------------------
# HRRR Lambert Conformal projection (spherical, tangent at 38.5 N)
# ---------------------------------------------------------------------------
_LAT1 = _LAT2 = _LAT0 = 38.5
_LON0 = 262.5                     # = 97.5 W, in 0..360 convention
_A = 6371229.0
_DX = _DY = 3000.0
_NX, _NY = 1799, 1059


def _lcc_fwd(lat, lon):
    p1 = np.radians(_LAT1)
    p0 = np.radians(_LAT0)
    l0 = np.radians(_LON0)
    p = np.radians(lat)
    l = np.radians(np.asarray(lon) % 360.0)
    n = np.sin(p1)
    F = (np.cos(p1) * np.tan(np.pi / 4 + p1 / 2) ** n) / n
    rho = _A * F / np.tan(np.pi / 4 + p / 2) ** n
    rho0 = _A * F / np.tan(np.pi / 4 + p0 / 2) ** n
    th = n * (l - l0)
    return rho * np.sin(th), rho0 - rho * np.cos(th)


def _lcc_inv(x, y):
    p1 = np.radians(_LAT1)
    p0 = np.radians(_LAT0)
    l0 = np.radians(_LON0)
    n = np.sin(p1)
    F = (np.cos(p1) * np.tan(np.pi / 4 + p1 / 2) ** n) / n
    rho0 = _A * F / np.tan(np.pi / 4 + p0 / 2) ** n
    rho = np.sqrt(x * x + (rho0 - y) ** 2)
    th = np.arctan2(x, rho0 - y)
    l = l0 + th / n
    p = 2 * np.arctan((_A * F / rho) ** (1 / n)) - np.pi / 2
    return np.degrees(p), np.degrees(l) % 360.0


def latlon_to_grid_xy(lat, lon):
    sx, sy = _lcc_fwd(lat, lon)
    return sx / _DX + (_NX - 1) / 2.0, sy / _DY + (_NY - 1) / 2.0


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def _parse_snapshot(snapshot: str) -> datetime.datetime:
    stem, hour = snapshot.split(".")
    return datetime.datetime(int(stem[0:4]), int(stem[4:6]), int(stem[6:8]),
                             int(hour.rstrip("zZ")))


def _snapshot_str(dt: datetime.datetime) -> str:
    return dt.strftime("%Y%m%d.%Hz")


def back_snapshots(snapshot: str, backhours=None) -> list[str]:
    backhours = C.BACKHOURS if backhours is None else backhours
    dt = _parse_snapshot(snapshot)
    return [_snapshot_str(dt - datetime.timedelta(hours=h)) for h in backhours]


def load_hrrr_cache(hrrr_dir: str, snapshots=None) -> dict:
    """Load selected HRRR-lite files into memory.

    Loading the whole directory makes a multi-month build consume tens of GB.
    """
    cache = {}
    wanted = None if snapshots is None else set(snapshots)
    files = sorted(os.listdir(hrrr_dir))
    for fn in files:
        if not fn.startswith("hysplit.") or not fn.endswith(".nc"):
            continue
        snapshot = fn.replace("hysplit.", "").replace(".nc", "")
        if wanted is not None and snapshot not in wanted:
            continue
        path = os.path.join(hrrr_dir, fn)
        with nc.Dataset(path) as ds:
            arrs = {}
            for var in ["U10M", "V10M", "PBLH", "PRSS"]:
                a = np.asarray(ds.variables[var])
                arrs[var] = (a[-1] if a.ndim == 3 else a).astype(np.float32)
        cache[snapshot] = arrs
    return cache


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _manifest_utc(value: str, field: str) -> datetime.datetime:
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid meteorology manifest {field}: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"meteorology manifest {field} is not timezone-aware")
    return parsed.astimezone(datetime.timezone.utc)


def _manifest_snapshot(value: str, field: str) -> tuple[str, datetime.datetime]:
    valid = _manifest_utc(value, field)
    return _snapshot_str(valid.replace(tzinfo=None)), valid


def _require_sha256(value, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in value)
    ):
        raise ValueError(f"invalid SHA-256 in meteorology manifest {field}")
    return value.lower()


def load_same_cycle_feature_cache(manifest_path: str, required) -> tuple[dict, dict, dict]:
    """Load verified scheduler features used by the same STILT met sequence."""
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported scheduler meteorology manifest schema")
    strict_alignments = {
        "same_cycle_forecast_realization",
        "same_grib_hourly_analysis_sequence",
    }
    alignment = manifest.get("alignment")
    if alignment not in strict_alignments:
        raise ValueError("meteorology manifest is not strictly source-aligned")
    source_entries = {}
    for source in manifest.get("hour_sources", []):
        snapshot, valid = _manifest_snapshot(
            source.get("valid_time_utc"), "hour_sources.valid_time_utc")
        if snapshot in source_entries:
            raise ValueError(f"duplicate HRRR source valid time: {snapshot}")
        _require_sha256(source.get("sha256"), f"hour_sources[{snapshot}].sha256")
        if source.get("arl_sha256") is not None:
            _require_sha256(
                source["arl_sha256"], f"hour_sources[{snapshot}].arl_sha256")
        try:
            forecast_hour = int(source["forecast_hour"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid HRRR source forecast hour for {snapshot}") from exc
        cycle = _manifest_utc(source.get("cycle_utc"), "hour_sources.cycle_utc")
        if cycle + datetime.timedelta(hours=forecast_hour) != valid:
            raise ValueError(f"HRRR source cycle/forecast mismatch for {snapshot}")
        if alignment == "same_grib_hourly_analysis_sequence" and (
            forecast_hour != 0 or cycle != valid
        ):
            raise ValueError(f"hourly-analysis source is not valid-time f00: {snapshot}")
        source_entries[snapshot] = source
    if not source_entries:
        raise ValueError("meteorology manifest has no HRRR hour_sources")

    artifact_policy = manifest.get("artifact_policy", {})
    if artifact_policy:
        if artifact_policy.get("hourly_arl") and any(
            source.get("arl_sha256") is None for source in source_entries.values()
        ):
            raise ValueError("meteorology manifest lacks hourly ARL SHA-256 receipts")
        if artifact_policy.get("source_grib") == "deleted_after_validation" and any(
            not source.get("source_url") for source in source_entries.values()
        ):
            raise ValueError("deleted HRRR sources lack reproducible source URLs")
        driver = manifest.get("stilt_driver", {})
        _require_sha256(driver.get("sha256"), "stilt_driver.sha256")

    if alignment == "same_cycle_forecast_realization":
        manifest_cycle = _manifest_utc(manifest.get("cycle_utc"), "cycle_utc")
        if any(
            _manifest_utc(source.get("cycle_utc"), "hour_sources.cycle_utc")
            != manifest_cycle
            for source in source_entries.values()
        ):
            raise ValueError("same-cycle manifest contains multiple HRRR cycles")

    entries = {}
    cache = {}
    for item in manifest.get("model_input_features", []):
        snapshot, _ = _manifest_snapshot(
            item.get("valid_time_utc"), "model_input_features.valid_time_utc")
        source = source_entries.get(snapshot)
        if source is None:
            raise ValueError(
                f"model feature {snapshot} has no matching HRRR hour_source")
        feature_source_sha256 = _require_sha256(
            item.get("source_grib_sha256"),
            f"model_input_features[{snapshot}].source_grib_sha256",
        )
        source_sha256 = _require_sha256(
            source.get("sha256"), f"hour_sources[{snapshot}].sha256")
        if feature_source_sha256 != source_sha256:
            raise ValueError(
                f"model feature source GRIB hash mismatch for {snapshot}")
        if item.get("forecast_hour") != source.get("forecast_hour"):
            raise ValueError(
                f"model feature forecast hour differs from HRRR source for {snapshot}")
        feature_cycle = _manifest_utc(
            item.get("cycle_utc"), "model_input_features.cycle_utc")
        source_cycle = _manifest_utc(
            source.get("cycle_utc"), "hour_sources.cycle_utc")
        if feature_cycle != source_cycle:
            raise ValueError(f"model feature cycle differs from HRRR source for {snapshot}")
        path = item["path"]
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        if _sha256_file(path) != item.get("sha256"):
            raise ValueError(f"source-aligned feature hash mismatch: {path}")
        with np.load(path) as data:
            missing = [name for name in ("U10M", "V10M", "PBLH", "PRSS")
                       if name not in data]
            if missing:
                raise ValueError(f"source-aligned feature {path} lacks {missing}")
            fields = {name: np.asarray(data[name], dtype=np.float32)
                      for name in ("U10M", "V10M", "PBLH", "PRSS")}
        shapes = {value.shape for value in fields.values()}
        if len(shapes) != 1 or any(value.ndim != 2 for value in fields.values()):
            raise ValueError(f"invalid source-aligned feature shapes in {path}: {shapes}")
        if any(not np.isfinite(value).all() for value in fields.values()):
            raise ValueError(f"non-finite source-aligned feature values in {path}")
        if snapshot in entries:
            raise ValueError(f"duplicate source-aligned feature valid time: {snapshot}")
        entries[snapshot] = item
        cache[snapshot] = fields
    missing = sorted(set(required).difference(cache))
    if missing:
        raise FileNotFoundError(
            f"meteorology manifest lacks model feature snapshots {missing}")
    return cache, manifest, entries


def _bilinear(field, xi, yi, bounds_error=True):
    ny, nx = field.shape
    xi = np.asarray(xi, dtype=np.float64)
    yi = np.asarray(yi, dtype=np.float64)
    valid = ((xi >= 0.0) & (xi <= nx - 1.0)
             & (yi >= 0.0) & (yi <= ny - 1.0))
    if bounds_error and not np.all(valid):
        raise ValueError(
            f"requested points leave HRRR grid: {np.size(valid) - valid.sum()} "
            f"of {np.size(valid)} out of bounds")
    x0 = np.floor(xi).astype(np.int64)
    y0 = np.floor(yi).astype(np.int64)
    x0 = np.clip(x0, 0, nx - 2)
    y0 = np.clip(y0, 0, ny - 2)
    fx = xi - x0
    fy = yi - y0
    a = field[y0, x0]
    b = field[y0, x0 + 1]
    c = field[y0 + 1, x0]
    d = field[y0 + 1, x0 + 1]
    out = (a * (1 - fx) * (1 - fy) + b * fx * (1 - fy)
           + c * (1 - fx) * fy + d * fx * fy)
    return np.where(valid, out, np.nan)


def load_soundings(date: str):
    """Return (N, 3) array [lat, lon, uncertainty_ppm] from the OCO-2 manifest."""
    path = os.path.join(C.MANIFEST_DIR, f"sounding_manifest_{date}.json")
    with open(path) as fh:
        manifest = json.load(fh)
    return np.asarray(
        [(s["latitude"], s["longitude"], s["xco2_uncertainty_ppm"])
         for s in manifest["soundings"]], dtype=np.float64
    )


def sample_receptors(snapshot: str, n: int, rng, mode: str):
    """Sample receptor (lat, lon) locations."""
    if mode == "oco2":
        date = snapshot[:8]
        snd = load_soundings(date)
        idx = rng.choice(len(snd), size=n, replace=len(snd) < n)
        return [(float(snd[i, 0]), float(snd[i, 1])) for i in idx]
    margin = C.RANDOM_MARGIN_DEG
    lats = rng.uniform(C.LAT_MIN + margin, C.LAT_MAX - margin, n)
    lons = rng.uniform(C.LON_MIN + margin, C.LON_MAX - margin, n)
    return list(zip(lats.tolist(), lons.tolist()))


# ---------------------------------------------------------------------------
# Feature helpers
# ---------------------------------------------------------------------------
def receptor_grid(rlat, rlon, grid, spacing_km):
    """Metric, receptor-centred grid represented by regular lat/lon axes."""
    # Even grids retain a unique receptor pixel at index grid//2. The domain is
    # shifted by half a cell rather than placing the receptor on four boundaries.
    offsets = (np.arange(grid) - grid // 2) * spacing_km
    lats = rlat + offsets / 110.54
    coslat = max(float(np.cos(np.radians(rlat))), 1e-3)
    lons = rlon + offsets / (111.32 * coslat)
    return lats, lons, offsets


def _normalize_met(field, variable_index):
    return ((field - C.MET_OFFSETS[variable_index])
            * C.MET_SCALES[variable_index]).astype(np.float32)


# ---------------------------------------------------------------------------
# Sample construction
# ---------------------------------------------------------------------------
def _assemble_input(snapshot, receptor, met_cache, grid, spacing_km):
    """Build the 20-channel receptor-centred input window (no label)."""
    rlat, rlon = receptor
    lats, lons, offsets_km = receptor_grid(rlat, rlon, grid, spacing_km)
    lon2d, lat2d = np.meshgrid(lons, lats)

    snaps = back_snapshots(snapshot)
    missing = [s for s in snaps if s not in met_cache]
    if missing:
        raise FileNotFoundError(f"Missing backhour HRRR snapshots {missing}")

    xi, yi = latlon_to_grid_xy(lat2d, lon2d)
    met_ch = []
    u_reg, v_reg = [], []
    for s in snaps:
        m = met_cache[s]
        uu = _bilinear(m["U10M"], xi, yi).astype(np.float32)
        vv = _bilinear(m["V10M"], xi, yi).astype(np.float32)
        u_reg.append(uu)
        v_reg.append(vv)
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

    met_stack = np.stack(met_ch, axis=2)             # (grid, grid, 16)
    x = np.concatenate([receptor_query[:, :, None], met_stack,
                        x_coord[:, :, None], y_coord[:, :, None],
                        radius[:, :, None]], axis=2)
    return (np.transpose(x, (2, 0, 1)).astype(np.float32),
            lons, lats, u_reg, v_reg)


def make_sample(snapshot, receptor, met_cache, grid, spacing_km, npart, seed):
    rlat, rlon = receptor
    x, lons, lats, u_reg, v_reg = _assemble_input(
        snapshot, receptor, met_cache, grid, spacing_km)
    wind_snaps = back_snapshots(snapshot)

    def full_domain_wind(block, particle_lat, particle_lon):
        pxi, pyi = latlon_to_grid_xy(particle_lat, particle_lon)
        uu = _bilinear(met_cache[wind_snaps[block]]["U10M"], pxi, pyi,
                       bounds_error=False)
        vv = _bilinear(met_cache[wind_snaps[block]]["V10M"], pxi, pyi,
                       bounds_error=False)
        valid = np.isfinite(uu) & np.isfinite(vv)
        return uu, vv, valid

    y, diagnostics = back_trajectory_footprint(
        lons, lats, u_reg, v_reg, rlon, rlat,
        npart=npart, dt=C.DT, hperblock=C.HPERBLOCK,
        diffusivity=C.DIFFUSIVITY, seed=seed,
        wind_sampler=full_domain_wind, return_diagnostics=True)
    if diagnostics["capture_fraction"] < C.MIN_CAPTURE_FRACTION:
        raise ValueError(
            f"output window captures only {diagnostics['capture_fraction']:.3f} "
            f"of trajectory residence for receptor {(rlat, rlon)}")
    meta = {"snapshot": snapshot, "latitude": rlat, "longitude": rlon,
            **diagnostics}
    return x, y.astype(np.float32), meta


def make_unlabeled_sample(snapshot, receptor, met_cache, grid, spacing_km):
    """Input-only sample for the self-supervised pretraining pool.

    Skips the particle simulation entirely: pretraining never uses labels,
    so unlabeled-pool construction must not pay for them.
    """
    rlat, rlon = receptor
    x, _, _, _, _ = _assemble_input(snapshot, receptor, met_cache, grid,
                                    spacing_km)
    return x, {"snapshot": snapshot, "latitude": rlat, "longitude": rlon}


# ---------------------------------------------------------------------------
# Build / save
# ---------------------------------------------------------------------------
def _sample_seed(snapshot, receptor):
    value = f"{C.RECEPTOR_SEED}|{snapshot}|{receptor[0]:.8f}|{receptor[1]:.8f}"
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:4], "little")


def build(snapshots, n_per_time, grid, npart, rng, mode, out_prefix, met_cache):
    estimated_gb = (len(snapshots) * n_per_time
                    * (C.N_CHANNELS * grid * grid + grid * grid)
                    * np.dtype(np.float32).itemsize * 2.5 / 1e9)
    if estimated_gb > C.MAX_BUILD_RAM_GB:
        raise MemoryError(
            f"{out_prefix} build estimates {estimated_gb:.1f} GB peak RAM, "
            f"above MAX_BUILD_RAM_GB={C.MAX_BUILD_RAM_GB}; use fewer snapshots "
            "per shard or implement a streaming writer")
    all_x, all_y, all_meta = [], [], []
    for snapshot in snapshots:
        recs = sample_receptors(snapshot, n_per_time, rng, mode)
        for i, rec in enumerate(recs):
            x, y, meta = make_sample(snapshot, rec, met_cache,
                                     grid, C.SPACING_KM, npart,
                                     seed=_sample_seed(snapshot, rec))
            all_x.append(x)
            all_y.append(y)
            all_meta.append(meta)
            if (i + 1) % max(1, n_per_time // 5) == 0:
                print(f"  [{snapshot}] {i+1}/{n_per_time} ({time.time():.0f})")
    X = np.stack(all_x).astype(np.float32)
    Y = np.stack(all_y).astype(np.float32)
    os.makedirs(C.OUTDIR, exist_ok=True)
    for suffix, array in (("inputs", X), ("targets", Y)):
        path = os.path.join(C.OUTDIR, f"{out_prefix}_{suffix}.npy")
        tmp = path + ".tmp"
        with open(tmp, "wb") as handle:
            np.save(handle, array)
        os.replace(tmp, path)
    contract = data_contract(grid, npart, mode)
    atomic_json(os.path.join(C.OUTDIR, f"{out_prefix}_meta.json"), {
        "snapshots": snapshots, "n_samples": len(X), "samples": all_meta,
        "contract": contract, "contract_fingerprint": fingerprint(contract),
        "source_fingerprint": source_fingerprint(),
    })
    print(f"[data] saved {len(X)} samples -> {C.OUTDIR}/{out_prefix}_*.npy")
    return X, Y



def build_pretrain_pool(snapshots, n_per_time, grid, rng, mode,
                        met_cache, out_prefix="pretrain"):
    """Build the inputs-only self-supervised pretraining pool.

    No particle simulation runs here: pretraining never consumes labels.
    Writes <out_prefix>_inputs.npy plus metadata for Lagrangian-JEPA
    trajectory construction.
    """
    all_x, all_meta = [], []
    for snapshot in snapshots:
        recs = sample_receptors(snapshot, n_per_time, rng, mode)
        for i, rec in enumerate(recs):
            x, meta = make_unlabeled_sample(
                snapshot, rec, met_cache, grid, C.SPACING_KM)
            all_x.append(x)
            all_meta.append(meta)
            if (i + 1) % max(1, n_per_time // 5) == 0:
                print(f"  [pretrain {snapshot}] {i+1}/{n_per_time}")
    X = np.stack(all_x).astype(np.float32)
    contract = data_contract(grid, 0, mode)   # npart=0: no labels generated
    atomic_json(os.path.join(C.OUTDIR, f"{out_prefix}_meta.json"), {
        "snapshots": snapshots, "n_samples": len(X), "samples": all_meta,
        "inputs_only": True, "contract": contract,
        "contract_fingerprint": fingerprint(contract),
        "source_fingerprint": source_fingerprint(),
    })
    path = os.path.join(C.OUTDIR, f"{out_prefix}_inputs.npy")
    tmp = path + ".tmp"
    with open(tmp, "wb") as handle:
        np.save(handle, X)
    os.replace(tmp, path)
    print(f"[data] saved pretraining pool of {len(X)} inputs -> "
          f"{C.OUTDIR}/{out_prefix}_inputs.npy")
    return X


def build_stilt(manifest_path, grid, out_prefix="train_stilt",
                meteorology_manifest_path=None):
    """Build a dataset whose labels come from uataq/stilt footprints.

    manifest_path: CSV produced by stilt_pipeline/run_batch.py with columns
        sim_id, run_time, lati, long, zagl, foot_nc, traj_rds
    Inputs are built from HRRR-lite exactly like the proxy path; labels are
    resampled physical-unit stilt footprints (read via stilt_io), never
    normalized.
    """
    import csv

    from stilt_io import read_stilt_footprint

    with open(manifest_path) as fh:
        rows = [r for r in csv.DictReader(fh)
                if r.get("foot_nc") and os.path.exists(r["foot_nc"])]
    if not rows:
        raise SystemExit(f"[stilt] no usable rows in {manifest_path}")

    snapshots = sorted({f"{r['run_time'][:4]}{r['run_time'][5:7]}"
                        f"{r['run_time'][8:10]}.{r['run_time'][11:13]}z"
                        for r in rows})
    required = {b for s in snapshots for b in back_snapshots(s)}
    feature_entries = None
    strict_meteorology = None
    driver_hours = None
    driver_sequence_sha256 = None
    if meteorology_manifest_path:
        met_cache, strict_meteorology, feature_entries = \
            load_same_cycle_feature_cache(meteorology_manifest_path, required)
        ordered_sources = sorted(
            strict_meteorology["hour_sources"],
            key=lambda item: _manifest_utc(
                item["valid_time_utc"], "hour_sources.valid_time_utc"),
        )
        driver_hours = [
            {
                "valid_time_utc": _manifest_utc(
                    item["valid_time_utc"], "hour_sources.valid_time_utc"
                ).isoformat().replace("+00:00", "Z"),
                "sha256": item["sha256"],
            }
            for item in ordered_sources
        ]
        driver_receipts = [
            {
                "valid_time_utc": _manifest_utc(
                    item["valid_time_utc"], "hour_sources.valid_time_utc"
                ).isoformat().replace("+00:00", "Z"),
                "sha256": item["sha256"],
                "arl_sha256": item.get("arl_sha256"),
            }
            for item in ordered_sources
        ]
        canonical_driver = json.dumps(
            driver_receipts, sort_keys=True, separators=(",", ":")
        ).encode("ascii")
        driver_sequence_sha256 = hashlib.sha256(canonical_driver).hexdigest()
    else:
        met_cache = load_hrrr_cache(C.HRRR_DIR, required)
    print(f"[stilt] {len(rows)} labelled receptors, "
          f"{len(met_cache)} HRRR snapshots")

    all_x, all_y, all_meta = [], [], []
    skipped = 0
    for i, r in enumerate(rows):
        snapshot = (f"{r['run_time'][:4]}{r['run_time'][5:7]}"
                    f"{r['run_time'][8:10]}.{r['run_time'][11:13]}z")
        receptor = (float(r["lati"]), float(r["long"]))
        try:
            x, _, _, _, _ = _assemble_input(
                snapshot, receptor, met_cache, grid, C.SPACING_KM)
            y, diag = read_stilt_footprint(
                r["foot_nc"], rlat=receptor[0], rlon=receptor[1],
                grid=grid, spacing_km=C.SPACING_KM,
                min_coverage=C.MIN_CAPTURE_FRACTION)
        except (ValueError, FileNotFoundError) as exc:
            print(f"  [skip] {r['sim_id']}: {exc}")
            skipped += 1
            continue
        all_x.append(x)
        all_y.append(y)
        sample_meta = {"snapshot": snapshot, "latitude": receptor[0],
                       "longitude": receptor[1], "sim_id": r["sim_id"],
                       "run_time": r["run_time"],
                       "zagl": float(r["zagl"]),
                       **diag}
        if feature_entries is not None:
            sample_meta["meteorology_features"] = [
                {key: feature_entries[back][key]
                 for key in ("path", "sha256", "forecast_hour",
                             "valid_time_utc", "source_grib_sha256")}
                for back in back_snapshots(snapshot)
            ]
            sample_meta.update({
                "meteorology_driver_sequence_sha256": driver_sequence_sha256,
                "driver_hour_count": len(driver_hours),
                "meteorology_driver_hours": driver_hours,
            })
        all_meta.append(sample_meta)
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(rows)} ({time.time():.0f}s)")
    if not all_x:
        raise SystemExit("[stilt] every row was skipped; nothing saved")

    X = np.stack(all_x).astype(np.float32)
    Y = np.stack(all_y).astype(np.float32)
    os.makedirs(C.OUTDIR, exist_ok=True)
    array_artifacts = {}
    for suffix, array in (("inputs", X), ("targets", Y)):
        path = os.path.join(C.OUTDIR, f"{out_prefix}_{suffix}.npy")
        tmp = path + ".tmp"
        with open(tmp, "wb") as handle:
            np.save(handle, array)
        os.replace(tmp, path)
        array_artifacts[suffix] = {
            "path": os.path.abspath(path),
            "bytes": os.path.getsize(path),
            "sha256": _sha256_file(path),
            "shape": list(array.shape),
            "dtype": str(array.dtype),
        }
    # Without an explicit scheduler meteorology manifest, the footprint driver
    # cannot be proven to be the same HRRR cycle as the model inputs.
    meteorology = {
        "alignment": "valid_time_only_not_same_cycle",
        "model_input_source": "rolling_hrrr_lite_analysis_f00",
        "stilt_driver_source": "external_manifest_unspecified",
    }
    if strict_meteorology is not None:
        meteorology = strict_meteorology
    contract = data_contract(
        grid, 0, C.RECEPTOR_MODE,
        target_mode=C.TARGET_MODE_PHYSICAL,
        label_source="stilt_xstilt",
        meteorology=meteorology,
    )
    atomic_json(os.path.join(C.OUTDIR, f"{out_prefix}_meta.json"), {
        "snapshots": snapshots, "n_samples": len(X), "samples": all_meta,
        "label_source": "stilt_xstilt",
        "manifest": os.path.abspath(manifest_path),
        "meteorology_manifest": (
            os.path.abspath(meteorology_manifest_path)
            if meteorology_manifest_path else None),
        "arrays": array_artifacts,
        "n_skipped": skipped,
        "contract": contract, "contract_fingerprint": fingerprint(contract),
        "source_fingerprint": source_fingerprint(),
    })
    print(f"[stilt] saved {len(X)} samples -> {C.OUTDIR}/{out_prefix}_*.npy "
          f"(skipped {skipped})")
    return X, Y


def discover_snapshots(hrrr_dir=None):
    """Return all HRRR snapshot stems available in HRRR_DIR."""
    hrrr_dir = hrrr_dir or C.HRRR_DIR
    snaps = []
    for fn in sorted(os.listdir(hrrr_dir)):
        if fn.startswith("hysplit.") and fn.endswith(".nc"):
            snaps.append(fn.replace("hysplit.", "").replace(".nc", ""))
    return snaps


def _valid_snapshots(snapshots):
    """Keep only snapshots for which every BACKHOURS file exists."""
    all_snaps = set(discover_snapshots())
    out = []
    for s in snapshots:
        if s not in all_snaps:
            print(f"[warn] snapshot {s} not found, skip")
            continue
        if all(b in all_snaps for b in back_snapshots(s)):
            out.append(s)
        else:
            print(f"[warn] {s} misses a backhour snapshot, skip")
    return out


def select_snapshots():
    """Return (train_snapshots, test_snapshots) according to config."""
    if not C.AUTO_SPLIT:
        train = _valid_snapshots(C.TRAIN_SNAPSHOTS)
        test = _valid_snapshots(C.TEST_SNAPSHOTS)
        return _validate_split(train, test)

    all_snaps = _valid_snapshots(discover_snapshots())
    if not all_snaps:
        return [], []

    if C.TRAIN_MONTHS or C.TEST_MONTHS:
        train = [s for s in all_snaps if s[:6] in C.TRAIN_MONTHS]
        test = [s for s in all_snaps if s[:6] in C.TEST_MONTHS]
        return _validate_split(train, test)

    # Automatic time split: 80% earliest for train, 20% latest for test.
    n = len(all_snaps)
    n_train = max(1, int(n * 0.8))
    return _validate_split(all_snaps[:n_train], all_snaps[n_train:])


def _validate_split(train, test):
    if set(train) & set(test):
        raise ValueError("train and test receptor snapshots overlap")
    train_inputs = {b for s in train for b in back_snapshots(s)}
    test_inputs = {b for s in test for b in back_snapshots(s)}
    overlap = sorted(train_inputs & test_inputs)
    if overlap:
        raise ValueError(
            f"train/test meteorological windows overlap at {overlap}; add a temporal embargo")
    return train, test


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--receptors", choices=["oco2", "random"], default=None)
    ap.add_argument("--label-source", choices=["proxy", "stilt"],
                    default="proxy")
    ap.add_argument("--stilt-manifest",
                    help="run_batch manifest CSV (required with "
                         "--label-source stilt)")
    ap.add_argument(
        "--meteorology-manifest",
        help="scheduler meteorology_manifest.json; required for a dataset "
             "that claims same-cycle HRRR input/label alignment",
    )
    ap.add_argument("--out-prefix", default=None,
                    help="output prefix for --label-source stilt "
                         "(default: <manifest name>)")
    args = ap.parse_args()

    smoke = args.smoke
    mode = args.receptors or C.RECEPTOR_MODE
    if smoke:
        grid = C.SMOKE_GRID
        ntrain = C.SMOKE_N_TRAIN
        ntest = C.SMOKE_N_TEST
        npart = C.SMOKE_NPART
    else:
        grid = C.GRID
        ntrain = C.N_RECEPTORS_PER_TIME_TRAIN
        ntest = C.N_RECEPTORS_PER_TIME_TEST
        npart = C.NPART

    if args.label_source == "stilt":
        if not args.stilt_manifest:
            raise SystemExit("--label-source stilt requires --stilt-manifest")
        grid_size = C.SMOKE_GRID if smoke else C.GRID
        default_prefix = os.path.splitext(
            os.path.basename(args.stilt_manifest))[0].replace("_manifest", "")
        prefix = args.out_prefix or f"{default_prefix}_stilt"
        build_stilt(
            args.stilt_manifest, grid_size, prefix,
            meteorology_manifest_path=args.meteorology_manifest,
        )
        return
    train_snaps, test_snaps = select_snapshots()
    if not train_snaps or not test_snaps:
        raise SystemExit(f"[data] no usable snapshots: train={train_snaps} test={test_snaps}")
    rng = np.random.default_rng(C.RECEPTOR_SEED)
    print(f"[data] mode={mode} grid={grid} npart={npart} "
          f"train_snaps={train_snaps} test_snaps={test_snaps}")
    pretrain_snaps = _valid_snapshots(C.PRETRAIN_EXTRA_SNAPSHOTS)
    required = {b for s in train_snaps + test_snaps + pretrain_snaps
                for b in back_snapshots(s)}
    met_cache = load_hrrr_cache(C.HRRR_DIR, required)
    print(f"[data] loaded {len(met_cache)} required HRRR snapshots")
    build(train_snaps, ntrain, grid, npart, rng, mode, "train", met_cache)
    build(test_snaps, ntest, grid, npart, rng, mode, "test", met_cache)
    if pretrain_snaps:
        build_pretrain_pool(pretrain_snaps, C.N_PRETRAIN_PER_TIME,
                            grid, rng, mode, met_cache)


if __name__ == "__main__":
    main()
