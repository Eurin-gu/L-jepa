"""Prototype training script for Lagrangian-JEPA pretraining.

This is a code prototype, not a final experimental arm.  It uses the current
HRRR-based proxy trajectories from ``lagrangian_jepa.compute_trajectory_xy``.
Once STILT/X-STILT ``traj.rds`` is available, replace the trajectory source
with real trajectories while keeping the same Lagrangian-JEPA model.

Usage:
    python3 train_lagrangian_jepa.py --smoke
    python3 train_lagrangian_jepa.py --epochs 10
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import data_builder as D
from lagrangian_jepa import LagrangianJEPA, build_trajectory_cache
from models import Encoder
from provenance import atomic_json, fingerprint, source_fingerprint
from train import set_seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--run-id")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    import train as T
    train_data, _ = T.load_data()

    # Match the supervised/ordinary-JEPA protocol: pretraining sees only the
    # training-date samples. Using validation inputs is an optional transductive
    # setting and must not happen silently.
    train_idx, _, pretrain_scope = T.train_validation_indices(train_data["meta"])
    x_train = train_data["x"][train_idx]
    meta = train_data["meta"]
    grid = x_train.shape[-1]
    npart = C.SMOKE_NPART if args.smoke else min(C.NPART, 64)
    epochs = args.epochs or (C.SMOKE_EPOCHS_JEPA if args.smoke else C.EPOCHS_JEPA)
    batch = C.SMOKE_BATCH if args.smoke else C.BATCH_SIZE
    base = 4 if args.smoke else 16

    print(f"[lagrangian] grid={grid} samples={len(x_train)} npart={npart} epochs={epochs}")
    traj_all = build_trajectory_cache(meta["samples"], grid, npart)
    traj = traj_all[train_idx]
    print(f"[lagrangian] trajectory cache {traj_all.shape}; pretrain subset {traj.shape}")

    seed = C.SEEDS[0] if args.seed is None else args.seed
    set_seed(seed)
    encoder = Encoder(in_channels=C.N_CHANNELS, base=base)
    model = LagrangianJEPA(encoder, encoder.latent_ch,
                           ema_decay=C.EMA_DECAY,
                           reg_mode=C.JEPA_REG_MODE,
                           reg_slices=C.JEPA_REG_SLICES)
    device = C.DEVICE
    model.to(device)
    optimizer = torch.optim.Adam(
        list(model.online.parameters()) + list(model.predictor.parameters()),
        lr=C.LR_JEPA)

    dataset = torch.utils.data.TensorDataset(
        torch.from_numpy(x_train), torch.from_numpy(traj))
    loader = torch.utils.data.DataLoader(
        dataset, batch_size=batch, shuffle=True,
        generator=torch.Generator().manual_seed(seed))

    run_id = args.run_id or dt.datetime.now().strftime("lagrangian-%Y%m%dT%H%M%S")
    run_dir = os.path.join(C.RESULTS, run_id)
    if os.path.exists(run_dir) and os.listdir(run_dir):
        raise FileExistsError(f"refusing to overwrite non-empty run directory {run_dir}")
    os.makedirs(run_dir, exist_ok=True)

    contract = meta.get("contract", {})
    run_meta = {
        "run_id": run_id, "seed": seed, "epochs": epochs,
        "grid": grid, "npart": npart, "batch": batch,
        "data_contract": contract,
        "data_fingerprint": meta.get("contract_fingerprint"),
        "source_fingerprint": source_fingerprint(),
        "trajectory_source": "simple_lagrangian_proxy_mean_trajectory",
        "pretrain_scope": pretrain_scope,
        "n_pretrain_samples": len(x_train),
        "formal_inference_allowed": False,
    }
    atomic_json(os.path.join(run_dir, "run.json"), run_meta)

    for epoch in range(1, epochs + 1):
        model.train()
        total, count = 0.0, 0
        for xb, tb in loader:
            xb, tb = xb.to(device), tb.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss, _ = model(xb, tb)
            loss.backward()
            optimizer.step()
            model._ema_update()
            total += loss.item() * len(xb)
            count += len(xb)
        msg = f"[lagrangian] epoch {epoch}/{epochs} loss {total/count:.4f}"
        print(msg)
        with open(os.path.join(run_dir, "log.txt"), "a") as fh:
            fh.write(msg + "\n")

    torch.save({"state_dict": encoder.state_dict(), **run_meta},
               os.path.join(run_dir, "encoder_lagrangian_jepa.pt"))
    atomic_json(os.path.join(run_dir, "run.json"), {**run_meta, "completed": True})
    print(f"[saved] {run_dir}/encoder_lagrangian_jepa.pt")


if __name__ == "__main__":
    main()
