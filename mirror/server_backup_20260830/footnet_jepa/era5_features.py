"""ERA5 feature extractor for the global multi-region dataset line.

Reads the per-day ERA5 feature caches produced by era5_met_cache.py
(era5_cache/{date}.npz, flat keys "{snapshot}_{VAR}" with snapshot
"YYYYMMDD.HHz", VAR in U10M/V10M/PBLH/PRSS, fields south->north on the
native 0.25 deg regular_ll grid) and assembles the 20-channel
receptor-centred input window used by data_builder for the HRRR line.

The receptor grid is metric (128x128 @ 4 km); ERA5 fields are bilinearly
interpolated in lat/lon space (no LCC projection needed, unlike HRRR).
"""
import os
import numpy as np

KM_PER_DEG_LAT = 110.54
KM_PER_DEG_LON_EQ = 111.32

MET_OFFSETS = [0.0, 0.0, 1000.0, 90000.0]
MET_SCALES = [0.1, 0.1, 1e-3, 1e-4]
VARS = ["U10M", "V10M", "PBLH", "PRSS"]
BACKHOURS = [0, 6, 12, 18]

CACHE_DIR = "/root/autodl-tmp/era5_cache"
_cache = {}


def load_era5_cache(date):
    if date in _cache:
        return _cache[date]
    p = os.path.join(CACHE_DIR, date + ".npz")
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    d = np.load(p)
    _cache[date] = d
    return d


def _parse_snapshot(snapshot):
    stem, hour = snapshot.split(".")
    return (int(stem[0:4]), int(stem[4:6]), int(stem[6:8]), int(hour.rstrip("zZ")))


def _snapshot_str(y, m, d, h):
    return "%04d%02d%02d.%02dz" % (y, m, d, h)


def back_snapshots(snapshot, backhours=None):
    backhours = BACKHOURS if backhours is None else backhours
    import datetime as _dt
    y, m, d, h = _parse_snapshot(snapshot)
    dt = _dt.datetime(y, m, d, h)
    return [_snapshot_str((dt - _dt.timedelta(hours=b)).year,
                          (dt - _dt.timedelta(hours=b)).month,
                          (dt - _dt.timedelta(hours=b)).day,
                          (dt - _dt.timedelta(hours=b)).hour) for b in backhours]


def _bilinear_latlon(field, src_lat, src_lon, q_lat, q_lon):
    """Bilinear sample field(ny, nx) (lat ascending, lon ascending) at (q_lat,
    q_lon); NaN outside domain."""
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
    cc = field[y0c + 1, x0c]
    d = field[y0c + 1, x0c + 1]
    out = (a * (1 - fx) * (1 - fy) + b * fx * (1 - fy)
           + cc * (1 - fx) * fy + d * fx * fy)
    return np.where(valid, out, np.nan)


def _receptor_grid(rlat, rlon, grid, spacing_km):
    offsets = (np.arange(grid) - grid // 2) * spacing_km
    lats = rlat + offsets / KM_PER_DEG_LAT
    coslat = max(float(np.cos(np.radians(rlat))), 1e-3)
    lons = rlon + offsets / (KM_PER_DEG_LON_EQ * coslat)
    return lats, lons, offsets


def _normalize(field, var_idx):
    return ((field - MET_OFFSETS[var_idx]) * MET_SCALES[var_idx]).astype(np.float32)


def assemble_input(snapshot, receptor, cache=None, grid=128, spacing_km=4.0):
    """Build the 20-channel input window (same layout as the HRRR line)."""
    rlat, rlon = receptor
    lats, lons, offsets_km = _receptor_grid(rlat, rlon, grid, spacing_km)
    snaps = back_snapshots(snapshot)
    date = snapshot[:8]
    c = cache if cache is not None else load_era5_cache(date)
    met_ch = []
    for s in snaps:
        base = s + "_"
        for vi, var in enumerate(VARS):
            key = base + var
            if key not in c.files:
                raise FileNotFoundError("ERA5 cache missing " + key + " for " + s)
            fld = c[key]
            lat_ax = c[base + var + "_lat"]
            lon0 = float(c[base + var + "_lon0"])
            di = float(c[base + var + "_di"])
            lon_ax = lon0 + di * np.arange(fld.shape[1])
            lon2d, lat2d = np.meshgrid(lons, lats)
            val = _bilinear_latlon(fld, lat_ax, lon_ax,
                                   lat2d.ravel(), lon2d.ravel()).reshape(grid, grid)
            met_ch.append(_normalize(val, vi))

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
    return np.transpose(x, (2, 0, 1)).astype(np.float32), lons, lats


if __name__ == "__main__":
    import sys
    snapshot = sys.argv[1] if len(sys.argv) > 1 else "20240401.21z"
    rlat = float(sys.argv[2]) if len(sys.argv) > 2 else 33.99921
    rlon = float(sys.argv[3]) if len(sys.argv) > 3 else -118.13158
    x, lons, lats = assemble_input(snapshot, (rlat, rlon))
    print("input shape:", x.shape)
    print("channel 0 (receptor) sum:", x[0].sum())
    print("U10M ch1 mean/std:", round(float(x[1].mean()), 4), round(float(x[1].std()), 4))
    print("PBLH ch9 mean:", round(float(x[9].mean()), 4))
    print("PRSS ch11 mean:", round(float(x[11].mean()), 4))
    print("OK")
