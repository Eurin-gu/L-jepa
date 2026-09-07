"""Re-evaluate provenance-aware checkpoints on the held-out split."""
import argparse
import glob
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
from models import PlainUNet
from provenance import atomic_json, source_fingerprint
from train import _baseline, evaluate_model, load_data


def latest_run_dir():
    path = os.path.join(C.RESULTS, "LATEST")
    if not os.path.exists(path):
        raise FileNotFoundError("no results/LATEST; run train.py first or pass --run-dir")
    with open(path, encoding="utf-8") as handle:
        return os.path.join(C.RESULTS, handle.read().strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir")
    args = parser.parse_args()
    run_dir = os.path.abspath(args.run_dir or latest_run_dir())
    _, test_data = load_data()
    data_fp = test_data["meta"]["contract_fingerprint"]
    results = {}
    paths = sorted(glob.glob(os.path.join(run_dir, "model_*_seed*.pt")))
    if not paths:
        raise FileNotFoundError(f"no provenance-aware checkpoints in {run_dir}")
    for path in paths:
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        if checkpoint.get("data_fingerprint") != data_fp:
            raise RuntimeError(f"checkpoint/data contract mismatch: {path}")
        arm = checkpoint["arm"]
        seed = int(checkpoint["seed"])
        model = (_baseline(checkpoint["smoke"]) if arm == "baseline"
                 else PlainUNet(in_channels=C.N_CHANNELS, base=checkpoint["base"]))
        model.load_state_dict(checkpoint["state_dict"])
        model.to(C.DEVICE)
        result = evaluate_model(
            model, test_data["x"], test_data["y"], C.BATCH_SIZE, C.DEVICE,
            test_data["meta"]["samples"])
        results.setdefault(str(seed), {})[arm] = result
        print(f"seed={seed} {arm}: {result['overall']}")
    atomic_json(os.path.join(run_dir, "evaluation.json"), {
        "run_dir": run_dir, "data_fingerprint": data_fp,
        "current_source_fingerprint": source_fingerprint(), "results": results,
    })


if __name__ == "__main__":
    main()
