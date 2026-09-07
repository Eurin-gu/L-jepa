#!/usr/bin/env python3
"""Extract FootNet surface features from a scheduler HRRR wrfprs subset.

The source GRIB is the exact forecast realization converted to ARL for STILT.
Keeping these four native-grid fields makes model inputs and label meteorology
share one HRRR cycle instead of mixing forecast ARL with rolling f00 analyses.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import numpy as np


FIELD_NAMES = ("U10M", "V10M", "PBLH", "PRSS")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _matches(message, field: str) -> bool:
    short = str(getattr(message, "shortName", "")).lower()
    name = str(getattr(message, "name", "")).lower()
    level = int(getattr(message, "level", -1))
    level_type = str(getattr(message, "typeOfLevel", "")).lower()
    if field == "U10M":
        return ((short in {"10u", "u", "ugrd"} or "u component" in name)
                and level == 10 and "heightaboveground" in level_type)
    if field == "V10M":
        return ((short in {"10v", "v", "vgrd"} or "v component" in name)
                and level == 10 and "heightaboveground" in level_type)
    if field == "PBLH":
        return (short in {"hpbl", "blh", "pblh"}
                or "boundary layer height" in name)
    if field == "PRSS":
        return ((short in {"sp", "pres", "prss"} or "surface pressure" in name)
                and ("surface" in level_type or level == 0))
    raise KeyError(field)


def select_feature_messages(messages) -> dict[str, object]:
    selected = {}
    for message in messages:
        for field in FIELD_NAMES:
            if field not in selected and _matches(message, field):
                selected[field] = message
    missing = [field for field in FIELD_NAMES if field not in selected]
    if missing:
        raise ValueError(f"GRIB lacks required model fields: {missing}")
    return selected


def message_valid_time(message) -> dt.datetime:
    valid = getattr(message, "validDate", None)
    if valid is None:
        date = int(message.validityDate)
        time = int(message.validityTime)
        valid = dt.datetime.strptime(f"{date:08d}{time:04d}", "%Y%m%d%H%M")
    if valid.tzinfo is None:
        valid = valid.replace(tzinfo=dt.timezone.utc)
    return valid.astimezone(dt.timezone.utc)


def extract(grib_path: Path, output_path: Path, cycle: dt.datetime,
            forecast_hour: int) -> dict:
    import pygrib

    with pygrib.open(str(grib_path)) as handle:
        selected = select_feature_messages(list(handle))
    arrays = {
        field: np.asarray(message.values, dtype=np.float32)
        for field, message in selected.items()
    }
    shapes = {array.shape for array in arrays.values()}
    if len(shapes) != 1 or any(array.ndim != 2 for array in arrays.values()):
        raise ValueError(f"feature fields have incompatible shapes: {shapes}")
    if any(not np.isfinite(array).all() for array in arrays.values()):
        raise ValueError("feature fields contain non-finite values")

    expected_valid = cycle + dt.timedelta(hours=forecast_hour)
    actual_times = {message_valid_time(message) for message in selected.values()}
    if actual_times != {expected_valid}:
        raise ValueError(
            f"GRIB valid times {sorted(actual_times)} != expected {expected_valid}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with open(temporary, "wb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, output_path)

    source_sha = sha256_file(grib_path)
    metadata = {
        "schema_version": 1,
        "cycle_utc": cycle.isoformat().replace("+00:00", "Z"),
        "forecast_hour": int(forecast_hour),
        "valid_time_utc": expected_valid.isoformat().replace("+00:00", "Z"),
        "path": str(output_path.resolve()),
        "sha256": sha256_file(output_path),
        "bytes": output_path.stat().st_size,
        "shape": list(next(iter(shapes))),
        "fields": list(FIELD_NAMES),
        "source_grib_path": str(grib_path.resolve()),
        "source_grib_sha256": source_sha,
    }
    sidecar = output_path.with_suffix(output_path.suffix + ".json")
    temporary_sidecar = sidecar.with_suffix(sidecar.suffix + ".tmp")
    with open(temporary_sidecar, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary_sidecar, sidecar)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grib", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cycle", required=True, help="ISO-8601 UTC cycle")
    parser.add_argument("--forecast-hour", required=True, type=int)
    args = parser.parse_args()
    cycle = dt.datetime.fromisoformat(args.cycle.replace("Z", "+00:00"))
    if cycle.tzinfo is None:
        parser.error("--cycle must include a timezone")
    cycle = cycle.astimezone(dt.timezone.utc)
    if not 0 <= args.forecast_hour <= 48:
        parser.error("--forecast-hour must be in [0, 48]")
    metadata = extract(
        Path(args.grib).resolve(), Path(args.out).resolve(), cycle,
        args.forecast_hour,
    )
    print(json.dumps(metadata, sort_keys=True))


if __name__ == "__main__":
    main()
