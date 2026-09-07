"""Readers converting uataq/stilt outputs into FootNet training tensors.

* ``read_stilt_footprint`` -- ingest <sim>_foot.nc (lon/lat/time/foot) and
  resample onto the receptor-centred metric grid used by ``data_builder``
  (default 128 x 128 @ 4 km). Physical units are PRESERVED; nothing is
  silently renormalized. Diagnostics report how much of the target window
  is covered by the simulation domain.

* ``stilt_traj_to_xy`` -- convert <sim>_traj.rds into the (T, 2) normalised
  receptor-centred trajectory coordinates consumed by Lagrangian-JEPA's
  trajectory cache. Reading .rds shells out to Rscript once per file; results
  are cached as .npz next to the caller's cache directory.
"""
from __future__ import annotations

import os
import subprocess
import tempfile

import numpy as np

KM_PER_DEG_LAT = 110.54
KM_PER_DEG_LON_EQ = 111.32


def _bilinear(field, src_lat, src_lon, q_lat, q_lon):
    """Bilinear sample field(ny, nx) at (q_lat, q_lon); NaN outside domain."""
    ny, nx = field.shape
    fi = np.interp(q_lon, src_lon, np.arange(nx), left=np.nan, right=np.nan)
    fj = np.interp(q_lat, src_lat, np.arange(ny), left=np.nan, right=np.nan)
    inside = np.isfinite(fi) & np.isfinite(fj)
    # neutralise out-of-domain entries before integer casting
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


def read_stilt_footprint(foot_nc_path, rlat, rlon, grid=128, spacing_km=4.0,
                         min_coverage=0.95):
    """Resample a stilt footprint onto the receptor-centred metric grid.

    Returns (y, diagnostics): y is (grid, grid) float32 with physical units
    and NaN outside the simulation domain; diagnostics includes the fraction
    of target cells covered by the source grid. Raises ValueError when
    coverage falls below ``min_coverage`` so callers never train on a label
    whose window mostly fell outside the simulation domain.
    """
    import netCDF4 as nc

    with nc.Dataset(foot_nc_path) as ds:
        lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
        lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
        foot = np.asarray(ds.variables["foot"][:], dtype=np.float64)
    if foot.ndim == 3:                      # (time, ny, nx) -> integrate time
        foot = foot.sum(axis=0)
    if lat[0] > lat[-1]:                    # store south->north
        lat = lat[::-1]
        foot = foot[::-1, :]
    if lon[0] > lon[-1]:
        lon = lon[::-1]
        foot = foot[:, ::-1]

    offsets_km = (np.arange(grid) - grid // 2) * spacing_km
    q_lats = rlat + offsets_km / KM_PER_DEG_LAT
    coslat = max(float(np.cos(np.radians(rlat))), 1e-3)
    q_lons = rlon + offsets_km / (KM_PER_DEG_LON_EQ * coslat)
    lon_g, lat_g = np.meshgrid(q_lons, q_lats)

    y = _bilinear(foot.astype(np.float64), lat, lon,
                  lat_g.ravel(), lon_g.ravel()).reshape(grid, grid)
    coverage = float(np.isfinite(y).mean())
    if coverage < min_coverage:
        raise ValueError(
            f"footprint {os.path.basename(foot_nc_path)} covers only "
            f"{coverage:.3f} of the {grid}x{grid} window "
            f"({min_coverage:.2f} required); expand the stilt domain or "
            "shorten the horizon")
    # Outside the simulation domain there was no simulated influence: fill
    # with 0 so labels are directly trainable (footprints are non-negative).
    y = np.where(np.isfinite(y), y, 0.0)
    diagnostics = {
        "coverage": coverage,
        "source_grid": [int(foot.shape[0]), int(foot.shape[1])],
        "footprint_sum": float(np.nansum(y)),
        "units": "stilt_surface_sensitivity",
    }
    return y.astype(np.float32), diagnostics


_R_TRAJ_DUMP = r"""
args <- commandArgs(trailingOnly = TRUE)
obj <- readRDS(args[[1]])
# uataq/stilt writes a list(file, receptor, particle, params); the trajectory
# table lives in $particle. Older/plain layouts are data.frames already.
if (is.list(obj) && !is.data.frame(obj) && !is.null(obj$particle)) {
  df <- as.data.frame(obj$particle)
} else {
  df <- as.data.frame(obj)
}
write.csv(df, args[[2]], row.names = FALSE)
"""


def _dump_traj_csv(traj_rds_path: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False) as fh:
        fh.write(_R_TRAJ_DUMP)
        script = fh.name
    csv_path = traj_rds_path + ".csv"
    proc = subprocess.run(
        ["Rscript", script, traj_rds_path, csv_path],
        capture_output=True, text=True, timeout=300)
    os.unlink(script)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[:500])
    return csv_path


def _xy_from_table(hours_back, longs, latis, rlat, rlon, half_km,
                   backhours=(0, 6, 12, 18)):
    """Pure conversion: stilt trajectory table -> mean (T, 2) xy.

    Many particles share each backward time; group by rounded hour and take
    the mean lon/lat, so the result is one receptor-centred coordinate per
    time step, matching Lagrangian-JEPA's trajectory convention.
    """
    hours_back = np.asarray(hours_back, dtype=float)
    keep = hours_back <= (max(backhours) + 1e-6)
    hours = hours_back[keep]
    longs = np.asarray(longs)[keep]
    latis = np.asarray(latis)[keep]

    # Round to nearest 0.5 h to aggregate particles from the same release.
    bins = np.round(hours * 2.0) / 2.0
    out = []
    for h in np.unique(bins):
        m = bins == h
        out.append((h, float(np.mean(longs[m])), float(np.mean(latis[m]))))
    out.sort(key=lambda row: row[0])
    h, lon_m, lat_m = zip(*out)
    dlon_km = (np.asarray(lon_m) - rlon) * \
        KM_PER_DEG_LON_EQ * np.cos(np.radians(rlat))
    dlat_km = (np.asarray(lat_m) - rlat) * KM_PER_DEG_LAT
    xy = np.column_stack([dlon_km / half_km, dlat_km / half_km])
    return xy.astype(np.float32)


def stilt_traj_to_xy(traj_rds_path, rlat, rlon, half_km,
                     cache_dir=None, backhours=(0, 6, 12, 18)):
    """Convert stilt traj.rds to Lagrangian-JEPA (T, 2) coordinates.

    Coordinates are receptor-centred, divided by ``half_km``, matching
    ``compute_trajectory_xy``'s convention (x east, y north). Rows are
    ordered from the receptor time backwards; only rows within
    ``max(backhours)`` are kept. Results are cached as .npz beside the rds
    (or in ``cache_dir``) keyed by mtime so repeated builds skip R.
    """
    cache_key = (f"{os.path.basename(traj_rds_path)}."
                 f"{int(os.path.getmtime(traj_rds_path))}.xy.npz")
    cache_path = os.path.join(cache_dir or os.path.dirname(traj_rds_path),
                              cache_key)
    if os.path.exists(cache_path):
        with np.load(cache_path) as z:
            xy = z["xy"]
    else:
        import pandas as pd
        csv_path = _dump_traj_csv(traj_rds_path)
        try:
            df = pd.read_csv(csv_path)
        finally:
            os.unlink(csv_path)
        hours_back = -np.asarray(df["time"], dtype=float) / 60.0
        xy = _xy_from_table(hours_back, np.asarray(df["long"], dtype=float),
                            np.asarray(df["lati"], dtype=float),
                            rlat, rlon, half_km, backhours=backhours)
        np.savez_compressed(cache_path, xy=xy)
    if len(xy) < 2:
        raise ValueError(
            f"{os.path.basename(traj_rds_path)} has fewer than two backward "
            "points inside the requested horizon")
    return xy
