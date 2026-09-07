"""Stable data and source fingerprints used to reject stale experiment files."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import config as C


def data_contract(grid: int, npart: int, mode: str, *,
                  target_mode: str | None = None,
                  label_source: str | None = None,
                  meteorology: dict | None = None) -> dict:
    """Build a complete, explicit dataset contract.

    Callers that ingest external labels must pass the target, label, and
    meteorology provenance explicitly.  In particular, temporarily mutating
    config globals can create a contract whose top-level metadata disagrees
    with its fingerprinted contents.
    """
    target_mode = C.TARGET_MODE if target_mode is None else target_mode
    label_source = C.LABEL_SOURCE if label_source is None else label_source
    return {
        "schema_version": C.DATA_SCHEMA_VERSION,
        "grid": int(grid),
        "spacing_km": float(C.SPACING_KM),
        "grid_origin": "receptor_at_index_grid_div_2",
        "backhours": list(C.BACKHOURS),
        "hperblock": float(C.HPERBLOCK),
        "dt_seconds": float(C.DT),
        "diffusivity_m2_s": float(C.DIFFUSIVITY),
        "npart": int(npart),
        "receptor_mode": mode,
        "feature_layout": [
            "receptor_impulse",
            "4x[U10M,V10M,PBLH,PRSS]",
            "local_x_over_half_domain",
            "local_y_over_half_domain",
            "radius_over_half_domain",
        ],
        "met_offsets": list(C.MET_OFFSETS),
        "met_scales": list(C.MET_SCALES),
        "target_mode": target_mode,
        "label_source": label_source,
        "meteorology": meteorology,
        "minimum_capture_fraction": float(C.MIN_CAPTURE_FRACTION),
        "random_receptor_bounds": (
            [C.LAT_MIN, C.LAT_MAX, C.LON_MIN, C.LON_MAX, C.RANDOM_MARGIN_DEG]
            if mode == "random" else None),
    }


def fingerprint(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_fingerprint(root: str | None = None) -> str:
    root_path = Path(root or C.ROOT)
    digest = hashlib.sha256()
    for path in sorted(root_path.glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def atomic_json(path: str, payload: dict) -> None:
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
