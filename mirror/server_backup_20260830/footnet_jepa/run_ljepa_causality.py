#!/usr/bin/env python3
"""L-JEPA causality audit (fake-trajectory controls) -- Go/No-Go driver.

Arms: scratch, met_mae, met_tubular, lj_true, lj_reverse, lj_perp, lj_rand.
All arms share dates, seeds, encoder/decoder init, pretrain & supervised
budget; only the trajectory (or mask structure) differs, so the date-level
finetune gap between lj_true and lj_perp / lj_rand is the causal signal.

Usage:
  python3 run_ljepa_causality.py --data <dir> --epochs 40 \
      --pretrain-epochs 25 --seeds 0,1,2
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
from models import HighResEncoder, HighResPlainUNet
from lagrangian_jepa import input_wind_trajectory
from provenance import atomic_json
from train import (set_seed, train_supervised, train_mae,
                   train_lagrangian_jepa, evaluate_model)
from train_stilt_strict import initialise_output_bias

ALL_ARMS = ("scratch", "met_mae", "met_tubular",
            "lj_true", "lj_reverse", "lj_perp", "lj_rand")


def load_dataset(data_dir: Path) -> dict:
    import train_stilt_strict as TSS
    return TSS.load_dataset(data_dir)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--pretrain-epochs", type=int, default=25)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--base", type=int, default=16)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--arms", default=",".join(ALL_ARMS))
    ap.add_argument("--device", default=C.DEVICE)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    arms = [a for a in args.arms.split(",") if a]
    unknown = set(arms) - set(ALL_ARMS)
    if unknown:
        ap.error("unknown arms: " + str(sorted(unknown)))
    seeds = [int(s) for s in args.seeds.split(",") if s]
    dataset = load_dataset(args.data)
    x, y = dataset["x"], dataset["y"]
    samples = dataset["samples"]
    print("[causality] data=%s x=%s y=%s samples=%d"
          % (args.data, x.shape, y.shape, len(samples)))
    dates = sorted({str(s["snapshot"])[:8] for s in samples})
    if len(dates) < 2:
        raise SystemExit("need >=2 distinct dates for date-level eval")
    val_date = dates[0]
    train_dates = dates[1:]
    tr_idx = np.array([i for i, s in enumerate(samples)
                       if str(s["snapshot"])[:8] in train_dates])
    va_idx = np.array([i for i, s in enumerate(samples)
                       if str(s["snapshot"])[:8] == val_date])
    print("[causality] train dates=%s n=%d | val date=%s n=%d"
          % (train_dates, len(tr_idx), val_date, len(va_idx)))
    if len(tr_idx) < 32 or len(va_idx) < 32:
        raise SystemExit("train/val too small for meaningful audit")
    traj_cache = {}
    for transform, label in (("none", "lj_true"), ("reverse", "lj_reverse"),
                             ("perp", "lj_perp"),
                             ("random_heading", "lj_rand")):
        traj_cache[label] = input_wind_trajectory(
            x, transform=transform, seed=0)
    y_target = y[:, None]
    meta_va = [samples[int(i)] for i in va_idx]
    out_dir = Path(args.out) if args.out else Path("causality_results")
    out_dir.mkdir(parents=True, exist_ok=True)
    all_rows = []
    done_pairs = set()
    resume_file = out_dir / ("causality_%s.json" % val_date)
    if resume_file.is_file():
        try:
            prior = json.load(open(resume_file))
            all_rows = list(prior.get("rows", []))
            done_pairs = {(r["seed"], r["arm"]) for r in all_rows}
            print("[causality] resume: %d rows already done" % len(all_rows))
        except Exception as exc:
            print("[causality] resume read failed, starting fresh:", exc)
    for seed in seeds:
        for arm in arms:
            if (seed, arm) in done_pairs:
                print("[causality] skip seed=%d arm=%s (done)" % (seed, arm))
                continue
            set_seed(seed)
            encoder = HighResEncoder(in_channels=x.shape[1], base=args.base)
            if arm == "scratch":
                pass
            elif arm == "met_mae":
                encoder, _ = train_mae(encoder, x[tr_idx], args.pretrain_epochs,
                                       C.LR_JEPA, args.batch, seed, args.device)
            elif arm == "met_tubular":
                from train import train_tubular_mae
                encoder, _ = train_tubular_mae(encoder, x[tr_idx],
                                               args.pretrain_epochs, C.LR_JEPA,
                                               args.batch, seed, args.device)
            else:
                traj = traj_cache[arm]
                encoder, _ = train_lagrangian_jepa(
                    encoder, x[tr_idx], traj[tr_idx], args.pretrain_epochs,
                    C.LR_JEPA, args.batch, seed, args.device,
                    predictor_kind="transformer")
            model = HighResPlainUNet(in_channels=x.shape[1], base=args.base)
            model.encoder.load_state_dict(encoder.state_dict())
            set_seed(seed + 100_000)
            initialise_output_bias(model, float(y[tr_idx].mean()))
            model, _ = train_supervised(
                model, x[tr_idx], y_target[tr_idx], x[va_idx], y_target[va_idx],
                args.epochs, C.LR, args.batch, "%s-s%d" % (arm, seed),
                seed + 100_000, args.device,
                target_mode=C.TARGET_MODE_PHYSICAL,
                mass_weight=getattr(C, "MASS_WEIGHT", 1.0))
            result = evaluate_model(
                model, x[va_idx], y_target[va_idx], batch=args.batch,
                device=args.device, sample_meta=meta_va,
                target_mode=C.TARGET_MODE_PHYSICAL)
            dm = result["date_macro"]
            row = {"seed": seed, "arm": arm, "val_date": val_date,
                   "n_val": int(len(va_idx)),
                   "r_date_macro": dm.get("pearson", float("nan")),
                   "relRMSE_date_macro": dm.get("raw_rmse",
                                                 float("nan")),
                   "rmse_date_macro": dm.get("rmse", float("nan")),
                   "overall_r": result["overall"].get("pearson",
                                                      float("nan"))}
            all_rows.append(row)
            print("[causality] seed=%d arm=%s r=%.4f relRMSE=%.3f"
                  % (seed, arm, row["r_date_macro"],
                     row["relRMSE_date_macro"]), flush=True)
    payload = {"dataset": str(args.data), "val_date": val_date,
               "arms": arms, "seeds": seeds, "rows": all_rows}
    out = str(out_dir / ("causality_%s.json" % val_date))
    atomic_json(out, payload)
    print("[causality] saved", out)


if __name__ == "__main__":
    main()