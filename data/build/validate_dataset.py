#!/usr/bin/env python3
"""Independent replica of train_stilt_strict.load_dataset's checks.

Runs the exact validations performed by the project's strict loader
without importing the footnet training stack (which needs torch + the
footnet models/train modules): contract schema/target/label, fingerprint,
samples<->rows alignment, channel count, target shape, finiteness, y>=0,
grid consistency, arrays sha256/shape/dtype, and sample uniqueness.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

N_CHANNELS = 20
SCHEMA_VERSION = 5
TARGET_MODE_PHYSICAL = "stilt_surface_footprint_physical"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def fingerprint(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate(data_dir):
    data_dir = Path(data_dir)
    x_path = data_dir / "x.npy"
    y_path = data_dir / "y.npy"
    meta_path = data_dir / "meta.json"
    if not (x_path.is_file() and y_path.is_file() and meta_path.is_file()):
        raise FileNotFoundError(
            "expected x.npy, y.npy and meta.json in " + str(data_dir))
    x = np.load(x_path).astype(np.float32)
    y = np.load(y_path).astype(np.float32)
    payload = json.load(open(meta_path, encoding="utf-8"))
    contract = payload.get("contract")
    if not isinstance(contract, dict):
        raise ValueError("strict dataset metadata lacks contract")
    if contract.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("strict dataset is not current schema-v5 data")
    if contract.get("target_mode") != TARGET_MODE_PHYSICAL:
        raise ValueError("strict dataset target_mode must be physical_footprint")
    if contract.get("label_source") != "stilt_xstilt":
        raise ValueError("strict dataset label_source must be stilt_xstilt")
    if payload.get("contract_fingerprint") != fingerprint(contract):
        raise ValueError("strict dataset contract fingerprint mismatch")
    samples = payload.get("samples")
    if not isinstance(samples, list) or len(samples) != len(x):
        raise ValueError("metadata rows do not align with input rows")
    if x.ndim != 4 or x.shape[1] != N_CHANNELS:
        raise ValueError("invalid input shape " + str(x.shape))
    if y.shape != (len(x), x.shape[-2], x.shape[-1]):
        raise ValueError("invalid target shape " + str(y.shape))
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(y < 0):
        raise ValueError("dataset contains invalid values")
    if contract.get("grid") != x.shape[-1]:
        raise ValueError("strict dataset grid contract differs from arrays")
    for key in ("inputs", "targets"):
        record = payload.get("arrays", {}).get(key)
        if not isinstance(record, dict):
            raise ValueError("strict dataset metadata lacks arrays." + key)
        path = x_path if key == "inputs" else y_path
        if record.get("sha256") != sha256_file(path):
            raise ValueError("strict dataset " + key + " file hash mismatch")
        arr = x if key == "inputs" else y
        if record.get("shape") != list(arr.shape):
            raise ValueError("strict dataset " + key + " shape fingerprint mismatch")
        if record.get("dtype") != str(arr.dtype):
            raise ValueError("strict dataset " + key + " dtype fingerprint mismatch")
    sim_ids = set()
    receptors = set()
    contents = set()
    for index, sample in enumerate(samples):
        sim_id = str(sample.get("sim_id", ""))
        if not sim_id or sim_id in sim_ids:
            raise ValueError("missing or duplicate sim_id at sample "
                             + str(index) + ": " + str(sim_id))
        sim_ids.add(sim_id)
        receptor = (
            str(sample.get("run_time", sample.get("snapshot", ""))),
            "{:.5f}".format(float(sample.get("latitude", sample.get("lat")))),
            "{:.5f}".format(float(sample.get("longitude", sample.get("lon")))),
            "{:g}".format(float(sample.get("zagl", 5.0))),
        )
        if receptor in receptors:
            raise ValueError("duplicate receptor identity at sample "
                             + str(index) + ": " + str(receptor))
        receptors.add(receptor)
        digest = hashlib.sha256()
        digest.update(x[index].tobytes())
        digest.update(y[index].tobytes())
        content = digest.hexdigest()
        if content in contents:
            raise ValueError("duplicate input/target content at sample "
                             + str(index))
        contents.add(content)
    print("load_dataset replica: PASS")
    print("  x:", x.shape, x.dtype, "| y:", y.shape, y.dtype)
    print("  samples:", len(samples), "| contract grid:", contract.get("grid"),
          "| schema:", contract.get("schema_version"))
    print("  target_mode:", contract.get("target_mode"),
          "| label_source:", contract.get("label_source"))
    print("  unique sim_ids:", len(sim_ids), "| unique receptors:", len(receptors),
          "| unique input/target pairs:", len(contents))
    print("  inputs_sha256:", payload["arrays"]["inputs"]["sha256"])
    print("  targets_sha256:", payload["arrays"]["targets"]["sha256"])
    coverage = np.asarray([float(s["coverage"]) for s in samples])
    footprint_sum = np.asarray([float(s["footprint_sum"]) for s in samples])
    print("  coverage min/mean/max:", float(coverage.min()),
          float(coverage.mean()), float(coverage.max()))
    print("  footprint_sum min/mean/max:", float(footprint_sum.min()),
          float(footprint_sum.mean()), float(footprint_sum.max()))
    return payload


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    args = ap.parse_args()
    validate(args.data)
