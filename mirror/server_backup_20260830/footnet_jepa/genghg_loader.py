"""Loader for the GenGHG v1.0 benchmark (Zenodo 21053452).

Each `.pt` file contains:
    x: Tensor[C=112, Hx=24, Wx=24]  -- GFS meteorological conditions
    y: Tensor[1, Hy=192, Wy=192]    -- STILT surface footprint

Channel layout (see `parsing_pt_to_nc.py`):
    2 distance channels
    + 5 time steps (0,-6,-12,-18,-24h)
      * surface: U10M,V10M,WS,WD,PRSS,PBLH,reverseGPM
      * 5 pressure levels: UWND,VWND,reverseGPM

This module provides:
    - parse_sample_name()
    - load_pt()
    - build_manifest()
    - train_val_test_split_by_city()
    - GenGHGDataset (torch Dataset)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

# Channel names in the exact order used by the official parsing script.
PRESSURE_TAGS = ["surface", "925hpa", "850hpa", "700hpa", "600hpa", "500hpa"]
SURFACE_VARS = ["U10M", "V10M", "WS", "WD", "PRSS", "PBLH", "reverseGPM"]
HIGHLEVEL_VARS = ["UWND", "VWND", "reverseGPM"]
TIME_TAGS = ["h", "h-6", "h-12", "h-18", "h-24"]


def condition_names() -> list[str]:
    names = ["dist_linear", "dist_exp"]
    for time_tag in TIME_TAGS:
        for pressure_tag in PRESSURE_TAGS:
            var_names = SURFACE_VARS if pressure_tag == "surface" else HIGHLEVEL_VARS
            for var_name in var_names:
                names.append(f"{time_tag}_{pressure_tag}_{var_name}")
    return names


def parse_sample_name(path) -> tuple[str | None, str | None, float | None, float | None]:
    """Parse 'City_YYYYMMDDHHMM_lon_lat.pt' -> (city, datetime, lon, lat)."""
    stem = Path(path).stem
    parts = stem.split("_")
    if len(parts) < 4:
        return None, None, None, None
    try:
        lon = float(parts[-2])
        lat = float(parts[-1])
    except ValueError:
        return None, None, None, None
    city = "_".join(parts[:-3])
    return city, parts[-3], lon, lat


def load_pt(path) -> dict:
    obj = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(obj, dict) or "x" not in obj or "y" not in obj:
        raise ValueError(f"{path} must contain dict with 'x' and 'y'")
    x = obj["x"].float()
    y = obj["y"].float()
    if y.ndim == 2:
        y = y.unsqueeze(0)
    if x.ndim != 3 or y.ndim != 3 or y.shape[0] != 1:
        raise ValueError(f"unexpected shapes x={tuple(x.shape)} y={tuple(y.shape)}")
    return {"x": x, "y": y}


def build_manifest(root, split=None, limit=None) -> list[dict]:
    """Return a list of sample dicts with metadata.

    Args:
        root: directory containing split subdirs (train/val/test) or .pt files.
        split: optional subdir name to restrict to.
        limit: optional max number of samples to return.
    """
    root = Path(root)
    if split:
        roots = [root / split]
    else:
        roots = [root] if root.is_dir() else [root.parent]
    # If the root contains split subdirectories (train/val/test), search them.
    if root.is_dir():
        subdirs = sorted([d for d in root.iterdir() if d.is_dir()])
        if subdirs:
            roots = subdirs
    samples = []
    for base in roots:
        if not base.is_dir():
            continue
        for pt in sorted(base.glob("*.pt")):
            city, datetime_str, lon, lat = parse_sample_name(pt)
            if city is None:
                continue
            samples.append({
                "path": str(pt),
                "city": city,
                "datetime": datetime_str,
                "lon": lon,
                "lat": lat,
                "split": base.name,
            })
            if limit and len(samples) >= limit:
                return samples
    return samples


def train_val_test_split_by_city(manifest, val_cities=None, test_cities=None,
                                 val_frac=0.1, test_frac=0.2, seed=0):
    """Split by city so a held-out city is never seen in training.

    If val_cities/test_cities are given, use them; otherwise split unique
    cities randomly with a fixed seed.
    """
    cities = sorted({s["city"] for s in manifest})
    rng = np.random.default_rng(seed)
    if test_cities is None:
        test_cities = set(rng.choice(cities, size=max(1, int(test_frac * len(cities))),
                                     replace=False).tolist())
    remaining = [c for c in cities if c not in test_cities]
    if val_cities is None:
        n_val = max(1, int(val_frac * len(remaining)))
        val_cities = set(rng.choice(remaining, size=n_val, replace=False).tolist())
    train_cities = [c for c in remaining if c not in val_cities]

    out = {"train": [], "val": [], "test": []}
    for s in manifest:
        if s["city"] in test_cities:
            out["test"].append(s)
        elif s["city"] in val_cities:
            out["val"].append(s)
        elif s["city"] in train_cities:
            out["train"].append(s)
    return out


class GenGHGDataset(Dataset):
    def __init__(self, samples, transform=None):
        self.samples = samples
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        data = load_pt(sample["path"])
        x, y = data["x"], data["y"]
        if self.transform is not None:
            x, y = self.transform(x, y)
        return x, y, sample


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="GenGHG root directory (contains train/val/test)")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    manifest = build_manifest(args.root, limit=args.limit)
    print(f"found {len(manifest)} samples")
    if manifest:
        print("example:", json.dumps(manifest[0], indent=2))
        try:
            split = train_val_test_split_by_city(manifest)
            print({k: len(v) for k, v in split.items()})
        except ValueError as exc:
            print("split skipped (need at least 2 cities):", exc)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(manifest, fh, indent=2)
