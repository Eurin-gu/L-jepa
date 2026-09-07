#!/usr/bin/env python3
"""Select quality-controlled, diverse OCO-2 receptors for STILT."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np


RECEPTOR_FIELDS = ("run_time", "lati", "long", "zagl")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: str, value: dict) -> None:
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def maximin_sample(indices, lat, lon, times, n, seed, time_weight=1.0):
    """Return source indices in deterministic space-time maximin order."""
    indices = np.asarray(indices, dtype=np.int64)
    if n >= len(indices):
        return indices.copy()
    if n < 1 or time_weight < 0:
        raise ValueError("n must be positive and time_weight must be non-negative")

    selected_lat = np.asarray(lat[indices], dtype=np.float64)
    selected_lon = np.asarray(lon[indices], dtype=np.float64)
    selected_time = np.asarray(times[indices], dtype=np.float64)
    mean_latitude = float(selected_lat.mean())
    north_km = (selected_lat - mean_latitude) * 110.54
    east_km = ((selected_lon - selected_lon.mean()) * 111.32
               * max(float(np.cos(np.radians(mean_latitude))), 1e-3))
    spatial_span = max(float(np.ptp(north_km)), float(np.ptp(east_km)), 1e-12)
    time_span = max(float(np.ptp(selected_time)), 1e-12)
    coordinates = np.column_stack([
        east_km / spatial_span,
        north_km / spatial_span,
        time_weight * (selected_time - selected_time.min()) / time_span,
    ])

    rng = np.random.default_rng(seed)
    first = int(rng.integers(len(indices)))
    chosen = np.zeros(len(indices), dtype=bool)
    chosen[first] = True
    order = [first]
    minimum_distance = ((coordinates - coordinates[first]) ** 2).sum(axis=1)
    minimum_distance[first] = -1.0
    for _ in range(1, n):
        next_index = int(np.argmax(minimum_distance))
        chosen[next_index] = True
        order.append(next_index)
        distance = ((coordinates - coordinates[next_index]) ** 2).sum(axis=1)
        minimum_distance = np.minimum(minimum_distance, distance)
        minimum_distance[chosen] = -1.0
    return indices[np.asarray(order, dtype=np.int64)]


def sample_indices(indices, lat, lon, times, n, seed, strategy, time_weight):
    if strategy == "maximin":
        return maximin_sample(indices, lat, lon, times, n, seed, time_weight)
    if strategy == "random":
        rng = np.random.default_rng(seed)
        return rng.choice(indices, size=min(n, len(indices)), replace=False)
    raise ValueError(f"unknown receptor sampling strategy: {strategy}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lite", required=True, help="OCO-2 Lite .nc4 path")
    parser.add_argument("--n", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20260822)
    parser.add_argument("--sampling-strategy", choices=("maximin", "random"),
                        default="maximin")
    parser.add_argument(
        "--time-weight", type=float, default=1.0,
        help="relative weight of normalized overpass time in maximin distance",
    )
    parser.add_argument("--lat-min", type=float, default=32.0)
    parser.add_argument("--lat-max", type=float, default=35.0)
    parser.add_argument("--lon-min", type=float, default=-119.0)
    parser.add_argument("--lon-max", type=float, default=-116.0)
    parser.add_argument("--zagl", type=float, default=5.0,
                        help="receptor height above ground [m]")
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--provenance-out",
        help="default: <out>.provenance.json",
    )
    args = parser.parse_args()
    if args.n < 1 or args.time_weight < 0:
        parser.error("--n must be positive and --time-weight non-negative")
    if args.lat_min > args.lat_max or args.lon_min > args.lon_max:
        parser.error("bounding-box minima must not exceed maxima")

    import netCDF4 as nc

    source_path = os.path.abspath(args.lite)
    with nc.Dataset(source_path) as dataset:
        required = {
            "latitude", "longitude", "xco2", "time",
            "xco2_quality_flag", "sounding_id",
        }
        missing = required.difference(dataset.variables)
        if missing:
            raise SystemExit(f"OCO-2 Lite file lacks variables: {sorted(missing)}")
        lat = np.ma.asarray(dataset.variables["latitude"][:]).filled(np.nan).astype(float)
        lon = np.ma.asarray(dataset.variables["longitude"][:]).filled(np.nan).astype(float)
        xco2 = np.ma.asarray(dataset.variables["xco2"][:]).filled(np.nan).astype(float)
        times = np.ma.asarray(dataset.variables["time"][:]).filled(np.nan).astype(float)
        quality = np.ma.asarray(
            dataset.variables["xco2_quality_flag"][:]).filled(-1).astype(np.int16)
        sounding_id = np.ma.asarray(
            dataset.variables["sounding_id"][:]).filled(0).astype(np.uint64)
        time_variable = dataset.variables["time"]
        time_units = time_variable.units
        calendar = getattr(time_variable, "calendar", "standard")

    lengths = {len(value) for value in
               (lat, lon, xco2, times, quality, sounding_id)}
    if len(lengths) != 1:
        raise SystemExit("OCO-2 variables have inconsistent sounding dimensions")
    finite = np.isfinite(lat) & np.isfinite(lon) & np.isfinite(xco2) & np.isfinite(times)
    quality_good = finite & (quality == 0)
    xco2_good = quality_good & (xco2 > 350.0) & (xco2 < 450.0)
    inside = (xco2_good
              & (lat >= args.lat_min) & (lat <= args.lat_max)
              & (lon >= args.lon_min) & (lon <= args.lon_max))
    candidates = np.flatnonzero(inside)
    if len(candidates) == 0:
        raise SystemExit("no quality-flag-zero soundings inside the bounding box")

    selection_order = sample_indices(
        candidates, lat, lon, times, args.n, args.seed,
        args.sampling_strategy, args.time_weight,
    )
    selection_rank = {int(index): rank for rank, index in enumerate(selection_order)}
    csv_order = sorted(map(int, selection_order), key=lambda index: (times[index], index))
    decoded = nc.num2date(
        times[csv_order], units=time_units, calendar=calendar,
        only_use_cftime_datetimes=False,
    )

    rows = []
    selected_provenance = []
    seen_rows = set()
    for index, stamp in zip(csv_order, decoded):
        timestamp = stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        row = {
            "run_time": timestamp,
            "lati": f"{lat[index]:.5f}",
            "long": f"{lon[index]:.5f}",
            "zagl": f"{args.zagl:g}",
        }
        identity = tuple(row[field] for field in RECEPTOR_FIELDS)
        if identity in seen_rows:
            raise RuntimeError(
                "selected soundings collapse to a duplicate STILT receptor after formatting")
        seen_rows.add(identity)
        rows.append(row)
        selected_provenance.append({
            "csv_row": len(rows) - 1,
            "selection_rank": selection_rank[index],
            "source_index": index,
            "sounding_id": str(int(sounding_id[index])),
            "run_time": timestamp,
            "latitude": float(lat[index]),
            "longitude": float(lon[index]),
            "xco2_ppm": float(xco2[index]),
        })

    output_path = os.path.abspath(args.out)
    provenance_path = os.path.abspath(
        args.provenance_out or output_path + ".provenance.json")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(provenance_path).parent.mkdir(parents=True, exist_ok=True)
    temporary_csv = output_path + ".tmp"
    with open(temporary_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECEPTOR_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary_csv, output_path)

    provenance = {
        "schema_version": 1,
        "source": {
            "path": source_path,
            "bytes": os.path.getsize(source_path),
            "sha256": sha256_file(source_path),
        },
        "quality_control": {
            "required_flag": "xco2_quality_flag == 0",
            "xco2_ppm_range_exclusive": [350.0, 450.0],
            "bounding_box_inclusive": {
                "latitude": [args.lat_min, args.lat_max],
                "longitude": [args.lon_min, args.lon_max],
            },
            "counts": {
                "source": len(lat),
                "finite": int(finite.sum()),
                "quality_flag_zero": int(quality_good.sum()),
                "xco2_range": int(xco2_good.sum()),
                "candidates_in_box": len(candidates),
            },
        },
        "sampling": {
            "strategy": args.sampling_strategy,
            "seed": args.seed,
            "requested": args.n,
            "selected": len(rows),
            "time_weight": args.time_weight,
            "space_coordinates": "local_east_north_km_scaled_by_common_spatial_span",
            "time_coordinate": "source_time_scaled_to_unit_span",
        },
        "output": {
            "path": output_path,
            "sha256": sha256_file(output_path),
            "receptor_height_agl_m": args.zagl,
        },
        "selected_soundings": selected_provenance,
    }
    atomic_json(provenance_path, provenance)
    print(
        f"[receptors] wrote {len(rows)} QC/maximin receptors -> {output_path}; "
        f"provenance -> {provenance_path}")


if __name__ == "__main__":
    main()
