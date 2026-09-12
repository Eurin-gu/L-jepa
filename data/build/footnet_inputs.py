#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FootNet-aligned input builder.

Reproduces FootNet v3 input layout (from nd349/FootNet SurfaceFootNet.py):

  Surface (24 ch):
    1) Gaussian plume (t0), z-standardised                     1
    2) U10,V10,PBLH,PRSS x [0,6,12,18,24]h                    20
    3) binary plume mask (comb_plume >= 0.08)                  1
    4) great-circle distance from receptor (km)                1
    5) exp(0.01 * dist)                                        1
  Column (49 ch): plume + 9 met vars x 5 times + same context  49
"""
import numpy as np

SURFACE_SCALES = [10.0, 10.0, 0.001, 0.001]
COLUMN_SCALES  = [10.0, 10.0, 0.001, 0.001, 1.0, 1.0, 1.0, 1.0, 0.01]
BACKHOURS = [0, 6, 12, 18, 24]
R_EARTH_KM = 6371.0


def gaussian_plume(lon2d, lat2d, f_lon, f_lat, uu, vv, res_deg):
    """Exact port of FootNet SurfaceFootNet.GaussianPlume.

    uu, vv are scalars (domain-mean wind components), as FootNet averages
    the wind field before calling this.
    """
    wspd = np.sqrt(uu ** 2 + vv ** 2)
    wdir = np.arctan2(vv, uu)
    aA, aB, wA, wB = 104.0, 213.0, 6.0, 2.0
    a = (wspd - wA) / (wB - wA) * (aB - aA) + aA
    a = min(max(a, aA), aB)
    x0 = 1e3
    xx = (lon2d - f_lon) / res_deg * 1e3
    yy = (lat2d - f_lat) / res_deg * 1e3
    r = np.sqrt(xx ** 2 + yy ** 2)
    phi = np.arctan2(yy, xx) - wdir
    lx = r * np.cos(phi)
    ly = r * np.sin(phi)
    sig = np.where(lx > 0, a * np.power(np.maximum(lx, 0.0) / x0, 0.894), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        c = 1.0 / (sig * wspd) * np.exp(-0.5 * (ly / sig) ** 2)
    return np.where(np.isfinite(c), c, 0.0)


def move_upstream(lat, lon, uu, vv, hours):
    """Displace a receptor upstream by wind over `hours` (FootNet moves the
    source backward along the wind for each successive backhour)."""
    d_km = np.hypot(uu, vv) * hours * 3600.0 / 1000.0
    if d_km <= 0:
        return lat, lon
    denom = np.hypot(uu, vv)
    ux, uy = -uu / denom, -vv / denom
    dlat = uy * d_km / 110.54
    dlon = ux * d_km / (111.32 * max(np.cos(np.radians(lat)), 1e-3))
    return lat + dlat, lon + dlon


def plume_channels(lons2d, lats2d, r_lat, r_lon, u_list, v_list, res_deg):
    """Return (gp_first_z, comb_mask): z-standardised t0 plume + binarised mask."""
    lat, lon = r_lat, r_lon
    plumes = []
    for uu, vv in zip(u_list, v_list):
        p = gaussian_plume(lons2d, lats2d, lon, lat, -uu, -vv, res_deg)
        plumes.append(p)
        lat, lon = move_upstream(lat, lon, uu, vv, 6.0)
    gp_separate = np.array(plumes)
    comb = gp_separate.sum(axis=0)
    first = gp_separate[0]
    mu, sd = np.nanmean(first), np.nanstd(first)
    gp_first_z = (first - mu) / sd if sd > 0 else np.zeros_like(first)
    return gp_first_z, np.where(comb >= 0.08, 1.0, 0.0)


def great_circle_km(r_lat, r_lon, lats2d, lons2d):
    """Great-circle distance from receptor to every grid point, km."""
    p1 = np.radians(r_lat)
    p2 = np.radians(lats2d)
    dl = np.radians(lons2d - r_lon)
    a = np.sin((p2 - p1) / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0) ** 2
    return 2.0 * R_EARTH_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def assemble_footnet_input(met_by_backhour, lons2d, lats2d, r_lat, r_lon,
                           res_deg, mode="surface", met_order=None):
    """Assemble a FootNet-layout tensor (C,H,W) float32.

    met_by_backhour: {backhour: {var: 2-D array}}
    mode: surface -> 24 ch ; column -> 49 ch
    """
    if mode == "surface":
        met_order = met_order or ["U10M", "V10M", "PBLH", "PRSS"]
        scales = SURFACE_SCALES
    else:
        met_order = met_order or ["U10M", "V10M", "PBLH", "PRSS",
                                  "U850", "V850", "U500", "V500", "T850"]
        scales = COLUMN_SCALES
    u_list = [float(np.nanmean(met_by_backhour[h]["U10M"])) for h in BACKHOURS]
    v_list = [float(np.nanmean(met_by_backhour[h]["V10M"])) for h in BACKHOURS]
    gp_first, mask = plume_channels(lons2d, lats2d, r_lat, r_lon,
                                    u_list, v_list, res_deg)
    dist = great_circle_km(r_lat, r_lon, lats2d, lons2d)
    chans = [gp_first]
    for h in BACKHOURS:
        for vi, var in enumerate(met_order):
            chans.append(met_by_backhour[h][var] * scales[vi])   # FootNet multiplies
    chans.append(mask)
    chans.append(dist)
    chans.append(np.exp(0.01 * dist))
    return np.stack(chans, axis=0).astype(np.float32)