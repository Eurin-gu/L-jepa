#!/usr/bin/env python3
"""Leakage-resistant Scratch/E-JEPA/L-JEPA protocol for STILT footprints."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import torch

import config as C
from lagrangian_jepa import input_wind_trajectory
from models import (FNO2d, HighResEncoder, HighResPlainUNet,
                    NestedUNetSmall, TemporalUNet)
from provenance import atomic_json, fingerprint, source_fingerprint
from train import (evaluate_model, metrics, set_seed, train_jepa,
                   train_lagrangian_jepa, train_mae, train_supervised)


STRICT_METEOROLOGY_ALIGNMENTS = {
    "same_cycle_forecast_realization",
    "same_grib_hourly_analysis_sequence",
}
SHARED_BACKBONE_ARMS = {"scratch", "e_jepa", "l_jepa", "met_mae"}
ALL_ARMS = SHARED_BACKBONE_ARMS | {"unetpp", "fno", "temporal_unet"}


def _find_array(data_dir: Path, short_name: str, canonical_suffix: str) -> Path:
    direct = data_dir / f"{short_name}.npy"
    if direct.is_file():
        return direct
    matches = sorted(data_dir.glob(f"*_{canonical_suffix}.npy"))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"expected {direct} or one *_{canonical_suffix}.npy in {data_dir}")
    return matches[0]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def validate_array_record(payload: dict, key: str, path: Path,
                          array: np.ndarray) -> None:
    record = payload.get("arrays", {}).get(key)
    if not isinstance(record, dict):
        raise ValueError(f"strict dataset metadata lacks arrays.{key}")
    if record.get("sha256") != sha256_file(path):
        raise ValueError(f"strict dataset {key} file hash mismatch")
    if record.get("shape") != list(array.shape):
        raise ValueError(f"strict dataset {key} shape fingerprint mismatch")
    if record.get("dtype") != str(array.dtype):
        raise ValueError(f"strict dataset {key} dtype fingerprint mismatch")


def validate_unique_samples(samples: list[dict], x: np.ndarray,
                            y: np.ndarray) -> dict[str, int]:
    sim_ids = set()
    receptors = set()
    contents = set()
    for index, sample in enumerate(samples):
        sim_id = str(sample.get("sim_id", ""))
        if not sim_id or sim_id in sim_ids:
            raise ValueError(f"missing or duplicate sim_id at sample {index}: {sim_id!r}")
        sim_ids.add(sim_id)
        receptor = (
            str(sample.get("run_time", sample.get("snapshot", ""))),
            f"{float(sample.get('latitude', sample.get('lat'))):.5f}",
            f"{float(sample.get('longitude', sample.get('lon'))):.5f}",
            f"{float(sample.get('zagl', 5.0)):g}",
        )
        if receptor in receptors:
            raise ValueError(f"duplicate receptor identity at sample {index}: {receptor}")
        receptors.add(receptor)
        digest = hashlib.sha256()
        digest.update(x[index].tobytes())
        digest.update(y[index].tobytes())
        content = digest.hexdigest()
        if content in contents:
            raise ValueError(f"duplicate input/target content at sample {index}")
        contents.add(content)
    return {
        "unique_sim_ids": len(sim_ids),
        "unique_receptors": len(receptors),
        "unique_input_target_pairs": len(contents),
    }


def load_dataset(data_dir: Path) -> dict:
    x_path = _find_array(data_dir, "x", "inputs")
    y_path = _find_array(data_dir, "y", "targets")
    meta_path = data_dir / "meta.json"
    if not meta_path.is_file():
        candidates = sorted(data_dir.glob("*_meta.json"))
        if len(candidates) != 1:
            raise FileNotFoundError(f"expected one metadata JSON in {data_dir}")
        meta_path = candidates[0]
    x = np.load(x_path).astype(np.float32)
    y = np.load(y_path).astype(np.float32)
    with open(meta_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("strict dataset metadata must be an object")
    contract = payload.get("contract")
    if not isinstance(contract, dict):
        raise ValueError("strict dataset metadata lacks contract")
    if contract.get("schema_version") != C.DATA_SCHEMA_VERSION:
        raise ValueError("strict dataset is not current schema-v5 data")
    if contract.get("target_mode") != C.TARGET_MODE_PHYSICAL:
        raise ValueError("strict dataset target_mode must be physical_footprint")
    if contract.get("label_source") != "stilt_xstilt":
        raise ValueError("strict dataset label_source must be stilt_xstilt")
    if payload.get("contract_fingerprint") != fingerprint(contract):
        raise ValueError("strict dataset contract fingerprint mismatch")
    samples = payload.get("samples") if isinstance(payload, dict) else payload
    if not isinstance(samples, list) or len(samples) != len(x):
        raise ValueError("metadata rows do not align with input rows")
    if x.ndim != 4 or x.shape[1] != C.N_CHANNELS:
        raise ValueError(f"invalid input shape {x.shape}")
    if y.shape != (len(x), x.shape[-2], x.shape[-1]):
        raise ValueError(f"invalid target shape {y.shape}")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(y < 0):
        raise ValueError("dataset contains invalid values")
    if contract.get("grid") != x.shape[-1]:
        raise ValueError("strict dataset grid contract differs from arrays")
    validate_array_record(payload, "inputs", x_path, x)
    validate_array_record(payload, "targets", y_path, y)
    uniqueness = validate_unique_samples(samples, x, y)
    trajectory_path = data_dir / "traj.npy"
    trajectory = (np.load(trajectory_path).astype(np.float32)
                  if trajectory_path.is_file() else None)
    if trajectory is not None and (len(trajectory) != len(x)
                                   or trajectory.ndim != 3
                                   or trajectory.shape[-1] != 2):
        raise ValueError(f"trajectory rows do not align: {trajectory.shape}")
    return {
        "x": x, "y": y, "samples": samples, "metadata": payload,
        "paths": {"x": str(x_path), "y": str(y_path),
                  "meta": str(meta_path),
                  "trajectory": str(trajectory_path) if trajectory is not None else None},
        "trajectory": trajectory,
        "uniqueness": uniqueness,
        "fingerprints": {
            "inputs_sha256": payload["arrays"]["inputs"]["sha256"],
            "targets_sha256": payload["arrays"]["targets"]["sha256"],
            "metadata_sha256": sha256_file(meta_path),
        },
    }


def sample_date(sample: dict) -> str:
    return str(sample["snapshot"])[:8]


def geometry_key(sample: dict, block_deg: float = 0.1) -> str:
    latitude = sample.get("latitude", sample.get("lat"))
    longitude = sample.get("longitude", sample.get("lon"))
    if latitude is None or longitude is None:
        raise ValueError("sample metadata lacks receptor latitude/longitude")
    latitude, longitude = float(latitude), float(longitude)
    if block_deg <= 0:
        return f"{latitude:.5f},{longitude:.5f}"
    lat_block = math.floor(latitude / block_deg)
    lon_block = math.floor(longitude / block_deg)
    return f"tile:{block_deg:g}:{lat_block}:{lon_block}"


def _parse_dates(value: str | None) -> list[str] | None:
    return None if value is None else [item for item in value.split(",") if item]


def nested_label_indices(samples: list[dict], indices: np.ndarray,
                         fraction: float, seed: int = 20260828) -> np.ndarray:
    """Select deterministic per-date prefixes so label budgets are nested."""
    if not 0.0 < fraction <= 1.0:
        raise ValueError("label fraction must lie in (0, 1]")
    indices = np.asarray(indices, dtype=np.int64)
    selected = []
    dates = sorted({sample_date(samples[int(index)]) for index in indices})
    for date in dates:
        group = [int(index) for index in indices
                 if sample_date(samples[int(index)]) == date]
        ordered = sorted(group, key=lambda index: hashlib.sha256(
            f"{seed}\0{samples[index]['sim_id']}".encode("utf-8")
        ).digest())
        n_keep = max(1, int(round(fraction * len(ordered))))
        selected.extend(ordered[:n_keep])
    return np.asarray(sorted(selected), dtype=np.int64)


def make_strict_split(samples, train_dates=None, val_dates=None,
                      test_dates=None, geometry_holdout=0.2,
                      geometry_block_deg=0.1, seed=20260824):
    dates = sorted({sample_date(sample) for sample in samples})
    if train_dates is None and val_dates is None and test_dates is None:
        if len(dates) < 4:
            raise ValueError("strict date split needs at least four dates")
        train_dates, val_dates, test_dates = dates[:-3], dates[-3:-2], dates[-2:]
    elif None in (train_dates, val_dates, test_dates):
        raise ValueError("provide train, validation, and test dates together")
    train_dates, val_dates, test_dates = map(set, (train_dates, val_dates, test_dates))
    if train_dates & val_dates or train_dates & test_dates or val_dates & test_dates:
        raise ValueError("train/validation/test dates must be disjoint")
    unknown = (train_dates | val_dates | test_dates).difference(dates)
    if unknown:
        raise ValueError(f"split dates absent from dataset: {sorted(unknown)}")

    geometries = sorted({geometry_key(sample, geometry_block_deg)
                         for sample in samples})
    rng = np.random.RandomState(seed)
    shuffled = np.asarray(geometries, dtype=object)[rng.permutation(len(geometries))]
    if geometry_holdout > 0:
        if not 0 < geometry_holdout < 0.5:
            raise ValueError("geometry_holdout must be 0 or in (0, 0.5)")
        n_each = max(1, int(round(len(geometries) * geometry_holdout)))
        if 2 * n_each >= len(geometries):
            raise ValueError("too few geometries for disjoint train/val/test groups")
        test_geometry = set(shuffled[:n_each])
        val_geometry = set(shuffled[n_each:2 * n_each])
        train_geometry = set(shuffled[2 * n_each:])
    else:
        train_geometry = val_geometry = test_geometry = set(geometries)

    roles = {
        "train": (train_dates, train_geometry),
        "validation": (val_dates, val_geometry),
        "test": (test_dates, test_geometry),
    }
    indices = {}
    for role, (role_dates, role_geometry) in roles.items():
        indices[role] = np.asarray([
            index for index, sample in enumerate(samples)
            if sample_date(sample) in role_dates
            and geometry_key(sample, geometry_block_deg) in role_geometry
        ], dtype=np.int64)
        if not len(indices[role]):
            raise ValueError(f"{role} split is empty")
    if set(indices["train"]) & set(indices["validation"]) \
            or set(indices["train"]) & set(indices["test"]) \
            or set(indices["validation"]) & set(indices["test"]):
        raise AssertionError("split indices overlap")
    feature_sets = {}
    driver_sets = {}
    feature_coverage = True
    driver_coverage = True
    for role, role_indices in indices.items():
        feature_sets[role] = set()
        driver_sets[role] = set()
        for index in role_indices:
            features = samples[int(index)].get("meteorology_features")
            if not features or len(features) != len(C.BACKHOURS):
                feature_coverage = False
            else:
                identities = {
                    (feature.get("valid_time_utc"),
                     feature.get("source_grib_sha256"))
                    for feature in features
                }
                if len(identities) != len(C.BACKHOURS) or any(
                        not valid or not digest for valid, digest in identities):
                    feature_coverage = False
                else:
                    feature_sets[role].update(identities)
            driver_hours = samples[int(index)].get("meteorology_driver_hours")
            if not driver_hours or len(driver_hours) < 25:
                driver_coverage = False
            else:
                identities = {
                    (hour.get("valid_time_utc"), hour.get("sha256"))
                    for hour in driver_hours
                }
                if len(identities) != len(driver_hours) or any(
                        not valid or not digest for valid, digest in identities):
                    driver_coverage = False
                else:
                    driver_sets[role].update(identities)
    feature_overlap = {
        "train_validation": sorted(feature_sets["train"] & feature_sets["validation"]),
        "train_test": sorted(feature_sets["train"] & feature_sets["test"]),
        "validation_test": sorted(
            feature_sets["validation"] & feature_sets["test"]),
    }
    driver_overlap = {
        "train_validation": driver_sets["train"] & driver_sets["validation"],
        "train_test": driver_sets["train"] & driver_sets["test"],
        "validation_test": driver_sets["validation"] & driver_sets["test"],
    }
    return indices, {
        "dates": {role: sorted(role_dates)
                  for role, (role_dates, _) in roles.items()},
        "geometry_counts": {role: len(role_geometry)
                            for role, (_, role_geometry) in roles.items()},
        "geometry_overlap_allowed": geometry_holdout == 0,
        "geometry_holdout_fraction": geometry_holdout,
        "geometry_block_degrees": geometry_block_deg,
        "meteorology_feature_coverage": feature_coverage,
        "meteorology_feature_overlap_counts": {
            key: len(value) for key, value in feature_overlap.items()
        },
        "meteorology_features_disjoint": (
            feature_coverage and not any(feature_overlap.values())
        ),
        "meteorology_driver_coverage": driver_coverage,
        "meteorology_driver_overlap_counts": {
            key: len(value) for key, value in driver_overlap.items()
        },
        "meteorology_drivers_disjoint": (
            driver_coverage and not any(driver_overlap.values())
        ),
        "unused_samples": len(samples) - sum(map(len, indices.values())),
    }


def state_fingerprint(state: dict[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for key, value in sorted(state.items()):
        digest.update(key.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def pretrain_cache_key(dataset: dict, train_indices: np.ndarray, arm: str,
                       seed: int, base: int, epochs: int, batch: int,
                       trajectory_source: str) -> dict:
    return {
        "schema_version": 1,
        "inputs_sha256": dataset["fingerprints"]["inputs_sha256"],
        "train_indices": [int(index) for index in train_indices],
        "arm": arm,
        "seed": int(seed),
        "base": int(base),
        "epochs": int(epochs),
        "batch": int(batch),
        "learning_rate": float(C.LR_JEPA),
        "trajectory_source": trajectory_source if arm == "l_jepa" else None,
        "source_fingerprint": source_fingerprint(),
    }


def load_pretrain_cache(cache_dir: Path | None, key: dict) -> dict | None:
    if cache_dir is None:
        return None
    path = cache_dir / f"{key['arm']}-s{key['seed']}-{fingerprint(key)}.pt"
    if not path.is_file():
        return None
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    if not isinstance(payload, dict) or payload.get("key") != key \
            or not isinstance(payload.get("state_dict"), dict):
        raise ValueError(f"invalid pretraining cache entry: {path}")
    if state_fingerprint(payload["state_dict"]) != payload.get("state_sha256"):
        raise ValueError(f"pretraining cache state hash mismatch: {path}")
    return {**payload, "path": str(path.resolve()), "reused": True}


def save_pretrain_cache(cache_dir: Path | None, key: dict,
                        state: dict[str, torch.Tensor], history) -> dict | None:
    if cache_dir is None:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key['arm']}-s{key['seed']}-{fingerprint(key)}.pt"
    cpu_state = {
        name: value.detach().cpu().clone() for name, value in state.items()
    }
    payload = {
        "key": key,
        "state_dict": cpu_state,
        "state_sha256": state_fingerprint(cpu_state),
        "history": history,
    }
    temporary = Path(str(path) + f".tmp-{os.getpid()}")
    torch.save(payload, temporary)
    os.replace(temporary, path)
    return {**payload, "path": str(path.resolve()), "reused": False}


def run_cached_pretraining(
    arm: str,
    encoder: HighResEncoder,
    dataset: dict,
    train_indices: np.ndarray,
    trajectories: np.ndarray,
    seed: int,
    base: int,
    epochs: int,
    batch: int,
    device: str,
    trajectory_source: str,
    cache_dir: Path | None,
) -> tuple[HighResEncoder, object, dict | None]:
    key = pretrain_cache_key(
        dataset, train_indices, arm, seed, base, epochs, batch,
        trajectory_source)
    cached = load_pretrain_cache(cache_dir, key)
    if cached is not None:
        encoder.load_state_dict(cached["state_dict"])
        return encoder, cached["history"], cached

    set_seed(seed)
    x = dataset["x"]
    if arm == "e_jepa":
        encoder, history = train_jepa(
            encoder, x[train_indices], epochs, C.LR_JEPA, batch, seed,
            device, mask_grid=x.shape[-1] // 4)
    elif arm == "l_jepa":
        encoder, history = train_lagrangian_jepa(
            encoder, x[train_indices], trajectories[train_indices],
            epochs, C.LR_JEPA, batch, seed, device,
            predictor_kind="transformer")
    elif arm == "met_mae":
        encoder, history = train_mae(
            encoder, x[train_indices], epochs, C.LR_JEPA, batch, seed,
            device)
    else:
        raise ValueError(f"arm {arm} has no pretraining objective")
    saved = save_pretrain_cache(cache_dir, key, encoder.state_dict(), history)
    return encoder, history, saved


def initialise_template(seed: int, in_channels: int, base: int,
                        target_mean: float) -> tuple[dict, str]:
    set_seed(seed)
    model = HighResPlainUNet(in_channels=in_channels, base=base)
    initialise_output_bias(model, target_mean)
    state = copy.deepcopy(model.state_dict())
    return state, state_fingerprint(state)


def initialise_output_bias(model: torch.nn.Module, target_mean: float) -> None:
    """Set the final physical-amplitude logit without architecture special cases."""
    bias = math.log(math.expm1(max(target_mean, 1e-8)))
    candidates = [module for module in model.modules()
                  if isinstance(module, torch.nn.Conv2d)
                  and module.out_channels == 1 and module.bias is not None]
    if not candidates:
        raise ValueError(f"{type(model).__name__} has no scalar output bias")
    with torch.no_grad():
        candidates[-1].bias.fill_(bias)


def initialise_arm_model(arm: str, seed: int, in_channels: int, base: int,
                         target_mean: float, shared_state: dict) -> tuple[torch.nn.Module, str]:
    if arm in SHARED_BACKBONE_ARMS:
        model = HighResPlainUNet(in_channels=in_channels, base=base)
        model.load_state_dict(shared_state)
    else:
        set_seed(seed)
        if arm == "unetpp":
            model = NestedUNetSmall(
                num_classes=1, input_channels=in_channels,
                nb_filter=[base * 2**index for index in range(5)],
            )
        elif arm == "fno":
            model = FNO2d(
                in_channels=in_channels, width=max(8, base * 4), modes=12,
                depth=4,
            )
        elif arm == "temporal_unet":
            model = TemporalUNet(
                in_channels=in_channels, base=base, out_channels=1)
        else:
            raise ValueError(f"unknown arm: {arm}")
        initialise_output_bias(model, target_mean)
    return model, state_fingerprint(model.state_dict())


def parameter_counts(model: torch.nn.Module) -> dict[str, int]:
    return {
        "tensor_elements": sum(
            parameter.numel() for parameter in model.parameters()),
        "real_scalars": sum(
            parameter.numel() * (2 if parameter.is_complex() else 1)
            for parameter in model.parameters()),
        "trainable_real_scalars": sum(
            parameter.numel() * (2 if parameter.is_complex() else 1)
            for parameter in model.parameters() if parameter.requires_grad),
    }


def summarize_seed_metrics(seed_results: dict, scope: str = "overall") -> dict:
    output = {}
    arms = sorted(next(iter(seed_results.values())))
    for arm in arms:
        rows = [seed_results[str(seed)][arm]["test"][scope]
                for seed in sorted(map(int, seed_results))]
        output[arm] = {
            key: {"mean": float(np.nanmean([row[key] for row in rows])),
                  "std": float(np.nanstd([row[key] for row in rows]))}
            for key in rows[0] if key != "n_events"
        }
    return output


def paired_date_bootstrap(seed_results: dict, reference="scratch",
                          metric="raw_mse", n_bootstrap=5000,
                          seed=20260828) -> dict:
    seed_keys = sorted(seed_results, key=int)
    arms = sorted(next(iter(seed_results.values())))
    if reference not in arms:
        return {}
    dates = sorted(set.intersection(*[
        set(seed_results[seed_key][arm]["test"]["by_date"])
        for seed_key in seed_keys for arm in arms
    ]))
    if not dates:
        return {}
    rng = np.random.RandomState(seed)
    output = {}
    for arm in arms:
        if arm == reference:
            continue
        delta = np.asarray([
            [seed_results[seed_key][arm]["test"]["by_date"][date][metric]
             - seed_results[seed_key][reference]["test"]["by_date"][date][metric]
             for date in dates]
            for seed_key in seed_keys
        ], dtype=np.float64)
        draws = np.empty(n_bootstrap, dtype=np.float64)
        for index in range(n_bootstrap):
            sampled_seeds = rng.randint(0, len(seed_keys), size=len(seed_keys))
            sampled_dates = rng.randint(0, len(dates), size=len(dates))
            draws[index] = delta[np.ix_(sampled_seeds, sampled_dates)].mean()
        output[arm] = {
            "reference": reference,
            "metric": metric,
            "lower_is_better": True,
            "mean_delta": float(delta.mean()),
            "ci95": [float(np.percentile(draws, 2.5)),
                     float(np.percentile(draws, 97.5))],
            "n_model_seeds": len(seed_keys),
            "n_dates": len(dates),
            "per_date_mean_delta": {
                date: float(delta[:, date_index].mean())
                for date_index, date in enumerate(dates)
            },
        }
    return output


def date_macro_metrics(prediction: np.ndarray, target: np.ndarray,
                       samples: list[dict]) -> dict:
    dates = np.asarray([sample_date(sample) for sample in samples])
    rows = [metrics(prediction[dates == date], target[dates == date])
            for date in sorted(set(dates.tolist()))]
    output = {
        key: float(np.nanmean([row[key] for row in rows]))
        for key in rows[0] if key != "n_events"
    }
    output["n_dates"] = len(rows)
    return output


def formal_test_core(dataset: dict, split: dict, split_meta: dict,
                     alignment: str) -> dict:
    test_indices = [int(index) for index in split["test"]]
    return {
        "dataset_fingerprints": dataset["fingerprints"],
        "test_dates": split_meta["dates"]["test"],
        "test_indices": test_indices,
        "test_sim_ids": [dataset["samples"][index]["sim_id"]
                         for index in test_indices],
        "split_protocol": {
            "geometry_holdout_fraction": split_meta["geometry_holdout_fraction"],
            "geometry_block_degrees": split_meta["geometry_block_degrees"],
            "meteorology_alignment": alignment,
            "meteorology_features_disjoint":
                split_meta["meteorology_features_disjoint"],
            "meteorology_drivers_disjoint":
                split_meta["meteorology_drivers_disjoint"],
        },
    }


def write_exclusive_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def freeze_formal_test(path: Path, core: dict) -> None:
    payload = {
        "schema_version": 1,
        "status": "frozen_before_formal_evaluation",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        **core,
    }
    write_exclusive_json(path, payload)


def verify_and_reserve_formal_test(path: Path, core: dict) -> Path:
    with open(path, encoding="utf-8") as handle:
        frozen = json.load(handle)
    expected = {"schema_version": 1,
                "status": "frozen_before_formal_evaluation", **core}
    actual = {key: frozen.get(key) for key in expected}
    if actual != expected:
        raise ValueError("formal-test manifest differs from current data or split")
    used_path = Path(str(path) + ".used.json")
    write_exclusive_json(used_path, {
        "schema_version": 1,
        "status": "formal_test_consumed",
        "consumed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "formal_test_manifest": str(path.resolve()),
        "formal_test_manifest_sha256": sha256_file(path),
        "source_fingerprint": source_fingerprint(),
    })
    return used_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--train-dates")
    parser.add_argument("--val-dates")
    parser.add_argument("--test-dates")
    parser.add_argument("--geometry-holdout", type=float, default=0.2)
    parser.add_argument("--geometry-block-deg", type=float, default=0.1,
                        help="hold out complete lat/lon tiles, not just exact points")
    parser.add_argument("--trajectory-source",
                        choices=("input_wind", "stilt_privileged"),
                        default="input_wind")
    parser.add_argument("--test-status", choices=("reused", "untouched"),
                        default="reused")
    parser.add_argument("--formal-test-manifest")
    parser.add_argument(
        "--freeze-formal-test-manifest", action="store_true",
        help="create the manifest once and exit without training/evaluation",
    )
    parser.add_argument("--seeds", default="0,1,2,3,4")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--pretrain-epochs", type=int, default=25)
    parser.add_argument("--mass-weight", type=float, default=1.0,
                        help="linear mass-conservation penalty weight (FootNet style)")
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--base", type=int, default=8)
    parser.add_argument("--label-frac", type=float, default=1.0)
    parser.add_argument(
        "--pretrain-cache-dir",
        help="reuse pretraining states across nested label-fraction runs",
    )
    parser.add_argument(
        "--arms",
        default="scratch,e_jepa,l_jepa,met_mae,unetpp,fno,temporal_unet",
    )
    parser.add_argument("--device", default=C.DEVICE)
    args = parser.parse_args()
    if min(args.epochs, args.pretrain_epochs, args.batch, args.base) < 1:
        parser.error("epoch, batch, and base values must be positive")
    if not 0.0 < args.label_frac <= 1.0:
        parser.error("--label-frac must lie in (0, 1]")

    dataset = load_dataset(Path(args.data))
    split, split_meta = make_strict_split(
        dataset["samples"], _parse_dates(args.train_dates),
        _parse_dates(args.val_dates), _parse_dates(args.test_dates),
        args.geometry_holdout, args.geometry_block_deg,
    )
    x, y = dataset["x"], dataset["y"]
    train_idx, val_idx, test_idx = (split["train"], split["validation"],
                                    split["test"])
    supervised_train_idx = nested_label_indices(
        dataset["samples"], train_idx, args.label_frac)
    label_subset = {
        "fraction": args.label_frac,
        "pretraining_samples": len(train_idx),
        "supervised_samples": len(supervised_train_idx),
        "indices": supervised_train_idx.tolist(),
        "sim_ids": [dataset["samples"][int(index)]["sim_id"]
                    for index in supervised_train_idx],
    }
    label_subset["fingerprint"] = fingerprint(label_subset)
    pretrain_cache_dir = (Path(args.pretrain_cache_dir).resolve()
                          if args.pretrain_cache_dir else None)
    trajectories = None
    trajectory_policy = {
        "source": args.trajectory_source,
        "available_at_deployment": args.trajectory_source == "input_wind",
        "derived_from_same_stilt_solve_as_label":
            args.trajectory_source == "stilt_privileged",
    }
    if args.trajectory_source == "input_wind":
        trajectories = input_wind_trajectory(x)
    else:
        trajectories = dataset["trajectory"]
        if trajectories is None:
            raise ValueError("stilt_privileged requires traj.npy")

    metadata = dataset["metadata"] if isinstance(dataset["metadata"], dict) else {}
    meteorology = metadata.get("contract", {}).get("meteorology") or {}
    alignment = meteorology.get("alignment", "unknown_or_legacy_not_same_cycle")
    arms = [item for item in args.arms.split(",") if item]
    unknown_arms = set(arms).difference(ALL_ARMS)
    if unknown_arms or not arms:
        parser.error(f"unknown or empty arms: {sorted(unknown_arms)}")
    try:
        seeds = [int(item) for item in args.seeds.split(",") if item]
    except ValueError as exc:
        parser.error(f"invalid --seeds: {exc}")
    if not seeds or len(seeds) != len(set(seeds)):
        parser.error("--seeds must contain unique integers")
    formal_core = formal_test_core(dataset, split, split_meta, alignment)
    formal_prerequisites = (
        len(split_meta["dates"]["test"]) >= C.MIN_FORMAL_TEST_DATES
        and not split_meta["geometry_overlap_allowed"]
        and split_meta["meteorology_features_disjoint"]
        and split_meta["meteorology_drivers_disjoint"]
        and alignment in STRICT_METEOROLOGY_ALIGNMENTS
        and args.trajectory_source == "input_wind"
        and args.label_frac == 1.0
    )
    if args.freeze_formal_test_manifest:
        if not args.formal_test_manifest:
            parser.error("freezing requires --formal-test-manifest")
        if not formal_prerequisites:
            parser.error("current split does not satisfy formal-test prerequisites")
        freeze_formal_test(Path(args.formal_test_manifest), formal_core)
        print(json.dumps({
            "status": "formal_test_frozen",
            "manifest": str(Path(args.formal_test_manifest).resolve()),
            "test_dates": split_meta["dates"]["test"],
            "test_samples": len(split["test"]),
        }, indent=2))
        return
    formal_usage_marker = None
    if args.test_status == "untouched":
        if not args.formal_test_manifest:
            parser.error("untouched evaluation requires --formal-test-manifest")
        if not formal_prerequisites:
            parser.error("current split does not satisfy formal-test prerequisites")
        formal_usage_marker = verify_and_reserve_formal_test(
            Path(args.formal_test_manifest), formal_core)

    seed_results = {}
    for seed in seeds:
        initial_state, initial_hash = initialise_template(
            seed, x.shape[1], args.base,
            float(y[supervised_train_idx].mean()))
        arm_results = {}
        for arm in arms:
            model, arm_initial_hash = initialise_arm_model(
                arm, seed, x.shape[1], args.base,
                float(y[supervised_train_idx].mean()), initial_state,
            )
            counts = parameter_counts(model)
            pretrain_history = None
            pretrain_cache = None
            if arm in {"e_jepa", "l_jepa", "met_mae"}:
                encoder = HighResEncoder(in_channels=x.shape[1], base=args.base)
                encoder.load_state_dict(model.encoder.state_dict())
                encoder, pretrain_history, pretrain_cache = run_cached_pretraining(
                    arm, encoder, dataset, train_idx, trajectories, seed,
                    args.base, args.pretrain_epochs, args.batch, args.device,
                    args.trajectory_source, pretrain_cache_dir)
                model.encoder.load_state_dict(encoder.state_dict())

            # Every arm receives identical supervised stochastic state, data
            # order, optimizer, budget, decoder initialization, and validation.
            supervised_start_hash = state_fingerprint(model.state_dict())
            supervised_seed = seed + 100_000
            set_seed(supervised_seed)
            model, history = train_supervised(
                model, x[supervised_train_idx], y[supervised_train_idx, None],
                x[val_idx], y[val_idx, None], args.epochs, C.LR,
                args.batch, arm, supervised_seed, args.device,
                                target_mode=C.TARGET_MODE_PHYSICAL,
                mass_weight=args.mass_weight)
            arm_results[arm] = {
                "architecture": type(model).__name__,
                "parameter_count": counts,
                "initial_state_sha256": arm_initial_hash,
                "shared_backbone_initial_sha256": (
                    initial_hash if arm in SHARED_BACKBONE_ARMS else None),
                "supervised_start_state_sha256": supervised_start_hash,
                "pretrain_history": pretrain_history,
                "pretrain_cache": ({
                    "path": pretrain_cache["path"],
                    "state_sha256": pretrain_cache["state_sha256"],
                    "reused": pretrain_cache["reused"],
                } if pretrain_cache is not None else None),
                "supervised_history": history,
                "test": evaluate_model(
                    model, x[test_idx], y[test_idx, None], args.batch,
                    args.device, [dataset["samples"][i] for i in test_idx],
                    target_mode=C.TARGET_MODE_PHYSICAL),
            }
        seed_results[str(seed)] = arm_results

    zero_prediction = np.zeros_like(y[test_idx])
    mean_prediction = np.broadcast_to(
        y[supervised_train_idx].mean(axis=0), y[test_idx].shape).copy()
    baselines = {
        "zero": metrics(zero_prediction, y[test_idx]),
        "train_mean": metrics(mean_prediction, y[test_idx]),
    }
    test_samples = [dataset["samples"][int(index)] for index in test_idx]
    baseline_date_macro = {
        "zero": date_macro_metrics(zero_prediction, y[test_idx], test_samples),
        "train_mean": date_macro_metrics(mean_prediction, y[test_idx], test_samples),
    }
    summary = summarize_seed_metrics(seed_results)
    date_macro_summary = summarize_seed_metrics(seed_results, "date_macro")
    paired_date_deltas = paired_date_bootstrap(seed_results)
    baseline_mse = baselines["train_mean"]["raw_mse"]
    baseline_date_macro_mse = baseline_date_macro["train_mean"]["raw_mse"]
    baseline_gate_overall = {
        arm: values["raw_mse"]["mean"] < baseline_mse
        for arm, values in summary.items()
    }
    baseline_gate = {
        arm: values["raw_mse"]["mean"] < baseline_date_macro_mse
        for arm, values in date_macro_summary.items()
    }
    formal_eligible = (
        args.test_status == "untouched"
        and formal_prerequisites
        and formal_usage_marker is not None
    )
    result = {
        "protocol_version": 2,
        "data_paths": dataset["paths"],
        "data_fingerprints": dataset["fingerprints"],
        "deduplication": dataset["uniqueness"],
        "source_fingerprint": source_fingerprint(),
        "split": split_meta,
        "split_indices": {key: value.tolist() for key, value in split.items()},
        "label_subset": label_subset,
        "meteorology_alignment": alignment,
        "trajectory_policy": trajectory_policy,
        "test_status": args.test_status,
        "formal_test_manifest": (
            str(Path(args.formal_test_manifest).resolve())
            if args.formal_test_manifest else None),
        "formal_test_usage_marker": (
            str(formal_usage_marker.resolve()) if formal_usage_marker else None),
        "capacity_protocol": "canonical_architectures_not_parameter_matched",
        "experiment_config": {
            "arms": arms,
            "seeds": seeds,
            "epochs": args.epochs,
            "pretrain_epochs": args.pretrain_epochs,
            "batch": args.batch,
            "base": args.base,
            "label_fraction": args.label_frac,
            "pretrain_cache_dir": (
                str(pretrain_cache_dir) if pretrain_cache_dir else None),
        },
        "formal_eligible": formal_eligible,
        "formal_blockers": [] if formal_eligible else [
            "current test is exploratory/reused, has fewer than five dates, "
            "or lacks strict same-cycle/geometry/meteorology/deployment alignment"],
        "baselines": baselines,
        "baseline_date_macro": baseline_date_macro,
        "baseline_gate_train_mean_date_macro": baseline_gate,
        "baseline_gate_train_mean_receptor_weighted": baseline_gate_overall,
        "seeds": seed_results,
        "summary": summary,
        "date_macro_summary": date_macro_summary,
        "paired_date_raw_mse_vs_scratch": paired_date_deltas,
    }
    atomic_json(args.out, result)
    print(json.dumps({
        "formal_eligible": formal_eligible,
        "split_sizes": {key: len(value) for key, value in split.items()},
        "train_mean_raw_mse": baseline_mse,
        "train_mean_date_macro_raw_mse": baseline_date_macro_mse,
        "baseline_gate": baseline_gate,
        "summary": summary,
    }, indent=2))


if __name__ == "__main__":
    main()
