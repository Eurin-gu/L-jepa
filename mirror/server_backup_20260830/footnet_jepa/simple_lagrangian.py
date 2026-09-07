"""A deliberately simple back-trajectory Lagrangian footprint proxy.

It is NOT a replacement for STILT/X-STILT (no vertical mixing, no met
preprocessor, crude temporal resolution) but it captures the dominant
transport signal: air at the receptor came from somewhere, and the footprint
should be spread upwind along the trajectory.

The labels are sum-normalized to 1.  This is appropriate for a shape/emulator
ablation, but not for absolute source-receptor sensitivity.  When real STILT
labels are available, switch to unnormalized physical footprints.
"""
import numpy as np
from scipy.interpolate import RegularGridInterpolator

DEG_LAT = 110540.0          # metres per degree of latitude
DEG_LON_AT_EQ = 111320.0    # metres per degree of longitude at the equator


def _mk_interp(lats, lons, field):
    """field: (Nlat, Nlon). Return a RegularGridInterpolator on (lat, lon)."""
    a = np.asarray(field, dtype=float)
    if a.shape != (len(lats), len(lons)):
        raise ValueError(f"wind field shape {a.shape} != (Nlat, Nlon) "
                         f"{(len(lats), len(lons))}")
    return RegularGridInterpolator((lats, lons), a,
                                   bounds_error=False, fill_value=0.0)


def back_trajectory_footprint(lons, lats, u_fields, v_fields, rlon, rlat,
                              npart=600, dt=600.0, hperblock=6,
                              diffusivity=5000.0, seed=0, wind_sampler=None,
                              return_diagnostics=False):
    """
    lons, lats : 1D arrays of the output grid
    u_fields, v_fields : lists of wind grids (Nlat, Nlon), ordered from the
        receptor time (index 0) backwards to t-18h (index len-1).
    rlon, rlat : receptor longitude / latitude.
    ``wind_sampler``, when supplied, is called as ``f(block, lat, lon)`` and
    must return U, V, valid arrays. This lets particles continue through the
    full meteorological domain after leaving the output window.

    Returns a residence-probability shape normalized to sum = 1. With
    ``return_diagnostics=True`` it also returns the fraction of all possible
    particle-time residence captured by the output window.
    """
    lons = np.asarray(lons, float)
    lats = np.asarray(lats, float)
    dlon = lons[1] - lons[0]
    dlat = lats[1] - lats[0]
    nlon, nlat = len(lons), len(lats)

    if wind_sampler is None:
        U = [_mk_interp(lats, lons, u) for u in u_fields]
        V = [_mk_interp(lats, lons, v) for v in v_fields]
    else:
        U = V = None

    npart = int(npart)
    lon = np.full(npart, rlon)
    lat = np.full(npart, rlat)
    rng = np.random.default_rng(seed)

    sigma = np.sqrt(2.0 * diffusivity * dt)          # metres, horizontal diffusion
    subperblock = int(hperblock * 3600.0 / dt)       # substeps per 6 h block

    footprint = np.zeros((nlat, nlon), dtype=np.float64)
    alive = np.ones(npart, dtype=bool)
    n_steps = 0
    lon_edge0 = lons[0] - 0.5 * dlon
    lat_edge0 = lats[0] - 0.5 * dlat

    for block in range(len(u_fields)):
        for _ in range(subperblock):
            # Residence BEFORE advection: the parcel occupies its current cell
            # during this substep.
            ix = np.floor((lon - lon_edge0) / dlon).astype(int)
            iy = np.floor((lat - lat_edge0) / dlat).astype(int)
            ok = (alive & (ix >= 0) & (ix < nlon)
                  & (iy >= 0) & (iy < nlat))
            np.add.at(footprint, (iy[ok], ix[ok]), 1.0)
            n_steps += 1
            if wind_sampler is None:
                pts = np.column_stack([lat, lon])
                u = U[block](pts)
                v = V[block](pts)
                valid = np.isfinite(u) & np.isfinite(v)
            else:
                u, v, valid = wind_sampler(block, lat, lon)
                u = np.asarray(u, dtype=float)
                v = np.asarray(v, dtype=float)
                valid = np.asarray(valid, dtype=bool)
            alive &= valid
            u = np.where(alive, u, 0.0)
            v = np.where(alive, v, 0.0)
            coslat = np.cos(np.radians(lat))
            # advect backward (minus the wind)
            lon = lon - u * dt / (DEG_LON_AT_EQ * coslat)
            lat = lat - v * dt / DEG_LAT
            # horizontal diffusion (random walk)
            lon = lon + np.where(
                alive, rng.normal(0.0, sigma / (DEG_LON_AT_EQ * coslat), npart), 0.0)
            lat = lat + np.where(
                alive, rng.normal(0.0, sigma / DEG_LAT, npart), 0.0)

    s = footprint.sum()
    if s <= 0:
        raise ValueError("trajectory has no residence inside the output window")
    footprint = footprint / s
    diagnostics = {
        "capture_fraction": float(s / (npart * n_steps)),
        "alive_fraction": float(alive.mean()),
        "n_steps": int(n_steps),
    }
    if return_diagnostics:
        return footprint, diagnostics
    return footprint
