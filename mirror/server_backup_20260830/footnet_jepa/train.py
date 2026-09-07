"""Train fair scratch and JEPA footprint-shape emulators.

The current proxy target is a sum-normalized trajectory residence distribution,
not a physical-unit STILT footprint. Models therefore emit spatial logits and
are trained as probability distributions. Physical-amplitude prediction must
use a separate, explicitly versioned target contract once STILT labels exist.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import random
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
from models import Encoder, JEPA, MeteorologyMAE, NestedUNetSmall, PlainUNet
from lagrangian_jepa import LagrangianJEPA, build_trajectory_cache
from provenance import atomic_json, data_contract, fingerprint, source_fingerprint


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def spatial_probability(logits: torch.Tensor) -> torch.Tensor:
    """Convert (B,1,H,W) logits to non-negative unit-mass maps."""
    if logits.ndim != 4 or logits.shape[1] != 1:
        raise ValueError(f"expected (B,1,H,W) logits, got {tuple(logits.shape)}")
    flat = torch.softmax(logits.flatten(1), dim=1)
    return flat.view_as(logits)


def physical_amplitude(logits: torch.Tensor) -> torch.Tensor:
    """Convert (B,1,H,W) logits to a non-negative physical-amplitude map.

    Used only with TARGET_MODE_PHYSICAL. Softplus keeps the output strictly
    non-negative by construction; no normalization is applied so the learned
    amplitude retains its physical units.
    """
    if logits.ndim != 4 or logits.shape[1] != 1:
        raise ValueError(f"expected (B,1,H,W) logits, got {tuple(logits.shape)}")
    return F.softplus(logits)


def model_output(model, xb, target_mode: str):
    """Apply the output transform matching the label contract."""
    logits = model(xb)
    return spatial_probability(logits) if target_mode == C.TARGET_MODE_SHAPE \
        else physical_amplitude(logits)


class FootprintShapeLoss(nn.Module):
    """Distribution cross-entropy plus total-variation shape mismatch."""

    def __init__(self, shape_weight: float = 1.0):
        super().__init__()
        self.shape_weight = float(shape_weight)

    def forward(self, logits: torch.Tensor, target: torch.Tensor):
        if target.shape != logits.shape:
            raise ValueError(f"target {target.shape} != logits {logits.shape}")
        target = target.clamp_min(0.0)
        target = target / target.sum(dim=(2, 3), keepdim=True).clamp_min(1e-12)
        log_prob = F.log_softmax(logits.flatten(1), dim=1)
        cross_entropy = -(target.flatten(1) * log_prob).sum(dim=1).mean()
        probability = spatial_probability(logits)
        total_variation = 0.5 * (probability - target).abs().sum(dim=(1, 2, 3)).mean()
        return cross_entropy + self.shape_weight * total_variation, cross_entropy


class FootprintAmplitudeLoss(nn.Module):
    """Loss for TARGET_MODE_PHYSICAL STILT footprints.

    The amplitude head is softplus(logits), i.e. non-negative by construction
    and never renormalized, so physical units survive the training signal:

      * amplitude term: mean L1 between log1p predictions and log1p targets
        (log space tames the heavy-tailed footprint magnitudes),
      * mass term: L1 between log1p total footprint masses,
      * shape term: cross-entropy between the normalized prediction and
        normalized target, so distributional shape is still supervised.
    """

    def __init__(self, shape_weight: float = 1.0, mass_weight: float = 1.0):
        super().__init__()
        self.shape_weight = float(shape_weight)
        self.mass_weight = float(mass_weight)

    def forward(self, logits: torch.Tensor, target: torch.Tensor):
        if target.shape != logits.shape:
            raise ValueError(f"target {target.shape} != logits {logits.shape}")
        target = target.clamp_min(0.0)
        amplitude = F.softplus(logits)
        pixel_error = (torch.log1p(amplitude) - torch.log1p(target)).abs().mean()
        pred_mass = amplitude.flatten(1).sum(dim=1)
        target_mass = target.flatten(1).sum(dim=1)
        mass_error = (torch.log1p(pred_mass) - torch.log1p(target_mass)).abs().mean()
        # FootNet-style linear relative mass conservation penalty
        mass_conservation = ((pred_mass - target_mass).abs()
                             / target_mass.clamp_min(1e-8)).mean()
        norm_target = target / target.sum(dim=(2, 3), keepdim=True).clamp_min(1e-12)
        log_prob = F.log_softmax(logits.flatten(1), dim=1)
        cross_entropy = -(norm_target.flatten(1) * log_prob).sum(dim=1).mean()
        target_entropy = -(norm_target.flatten(1)
                           * torch.log(norm_target.flatten(1).clamp_min(1e-12)))\
            .sum(dim=1).mean()
        shape_kl = cross_entropy - target_entropy
        amplitude_error = (pixel_error + mass_error
                          + self.mass_weight * mass_conservation)
        return amplitude_error + self.shape_weight * shape_kl, amplitude_error


def make_criterion(target_mode: str, mass_weight: float = 1.0):
    if target_mode not in (C.TARGET_MODE_SHAPE, C.TARGET_MODE_PHYSICAL):
        raise ValueError(f"unknown target mode: {target_mode}")
    return (FootprintShapeLoss(C.SHAPE_MULTISCALE_WEIGHT)
            if target_mode == C.TARGET_MODE_SHAPE
            else FootprintAmplitudeLoss(C.SHAPE_MULTISCALE_WEIGHT,
                                        mass_weight=mass_weight))


def _read_metadata(split: str) -> dict:
    path = os.path.join(C.OUTDIR, f"{split}_meta.json")
    with open(path, encoding="utf-8") as handle:
        meta = json.load(handle)
    contract = meta.get("contract", {})
    if contract.get("schema_version") != C.DATA_SCHEMA_VERSION:
        raise RuntimeError(
            f"{split} data schema {contract.get('schema_version')} is stale; "
            "rerun data_builder.py")
    if contract.get("target_mode") != C.TARGET_MODE:
        raise RuntimeError(
            f"{split} target mode {contract.get('target_mode')} != {C.TARGET_MODE}")
    expected = data_contract(
        contract["grid"], contract["npart"], contract["receptor_mode"],
        target_mode=contract.get("target_mode"),
        label_source=contract.get("label_source"),
        meteorology=contract.get("meteorology"),
    )
    if meta.get("contract_fingerprint") != fingerprint(expected):
        raise RuntimeError(
            f"{split} data contract no longer matches config.py; rerun data_builder.py")
    return meta


def load_data() -> tuple[dict, dict]:
    datasets = []
    for split in ("train", "test"):
        meta = _read_metadata(split)
        x = np.load(os.path.join(C.OUTDIR, f"{split}_inputs.npy")).astype(np.float32)
        y = np.load(os.path.join(C.OUTDIR, f"{split}_targets.npy")).astype(np.float32)
        if x.ndim != 4 or x.shape[1] != C.N_CHANNELS or y.shape != (len(x), *x.shape[-2:]):
            raise RuntimeError(f"invalid {split} array shapes: X={x.shape}, Y={y.shape}")
        if not np.isfinite(x).all() or not np.isfinite(y).all():
            raise RuntimeError(f"{split} arrays contain non-finite values")
        if np.any(y < 0):
            raise RuntimeError(f"{split} targets contain negative values")
        target_mode = meta["contract"]["target_mode"]
        if target_mode == C.TARGET_MODE_SHAPE:
            sums = y.sum(axis=(1, 2))
            if not np.allclose(sums, 1.0, atol=2e-5):
                raise RuntimeError(f"{split} targets violate probability contract")
        elif target_mode == C.TARGET_MODE_PHYSICAL:
            pass  # physical-unit footprints: no normalization contract
        else:
            raise RuntimeError(
                f"{split} declares unknown target mode {target_mode}; "
                "update config.TARGET_MODE and rerun data_builder.py")
        if len(meta.get("samples", [])) != len(x):
            raise RuntimeError(f"{split} metadata/sample length mismatch")
        datasets.append({"x": x, "y": y[:, None], "meta": meta,
                         "target_mode": target_mode})
    if datasets[0]["meta"]["contract_fingerprint"] != datasets[1]["meta"]["contract_fingerprint"]:
        raise RuntimeError("train and test were built with different data contracts")
    return datasets[0], datasets[1]



def train_validation_indices(meta: dict) -> tuple[np.ndarray, np.ndarray, str]:
    samples = meta["samples"]
    dates = np.asarray([s["snapshot"][:8] for s in samples])
    unique = sorted(set(dates.tolist()))
    if len(unique) >= 2:
        n_val_groups = max(1, int(np.ceil(0.2 * len(unique))))
        val_groups = set(unique[-n_val_groups:])
        val = np.flatnonzero(np.isin(dates, list(val_groups)))
        train = np.flatnonzero(~np.isin(dates, list(val_groups)))
        scope = "held_out_date"
    else:
        order = np.random.RandomState(0).permutation(len(samples))
        n_val = max(1, int(np.ceil(0.2 * len(samples))))
        val, train = order[:n_val], order[n_val:]
        scope = "same_snapshot_receptor_holdout"
    if not len(train) or not len(val):
        raise RuntimeError("training and validation splits must both be non-empty")
    return train, val, scope


def stratified_label_indices(samples, indices, frac, seed):
    """Deterministically pick a per-date stratified subset of labeled samples.

    Every date keeps max(1, round(frac * n_date)) samples so a reduced label
    budget never deletes an entire weather situation.
    """
    indices = np.asarray(sorted(int(i) for i in indices))
    if frac >= 1.0:
        return indices
    if not (0.0 < frac <= 1.0):
        raise ValueError(f"label fraction must be in (0, 1], got {frac}")
    rng = np.random.RandomState(seed)
    dates = np.asarray([samples[i]["snapshot"][:8] for i in indices])
    keep = []
    for date in sorted(set(dates.tolist())):
        group = indices[dates == date]
        n_keep = max(1, int(round(frac * len(group))))
        keep.extend(rng.choice(group, size=n_keep, replace=False).tolist())
    return np.asarray(sorted(keep))


def load_pretrain_pool():
    """Load the inputs-only self-supervised pool, if data_builder built one.

    Returns (inputs, sample_metas); (None, None) when no pool exists, which
    keeps smoke runs working without extra snapshots.
    """
    x_path = os.path.join(C.OUTDIR, "pretrain_inputs.npy")
    m_path = os.path.join(C.OUTDIR, "pretrain_meta.json")
    if not (os.path.exists(x_path) and os.path.exists(m_path)):
        return None, None
    x = np.load(x_path).astype(np.float32)
    if x.ndim != 4 or x.shape[1] != C.N_CHANNELS:
        raise RuntimeError(f"invalid pretraining pool shape {x.shape}")
    with open(m_path, encoding="utf-8") as handle:
        meta = json.load(handle)
    if not meta.get("inputs_only"):
        raise RuntimeError("pretrain_meta.json is missing inputs_only=true")
    contract = meta.get("contract", {})
    expected = data_contract(
        contract.get("grid", x.shape[-1]),
        contract.get("npart", 0),
        contract.get("receptor_mode", C.RECEPTOR_MODE),
        target_mode=contract.get("target_mode"),
        label_source=contract.get("label_source"),
        meteorology=contract.get("meteorology"),
    )
    if meta.get("contract_fingerprint") != fingerprint(expected):
        raise RuntimeError("pretrain pool data contract no longer matches config.py")
    if len(meta.get("samples", [])) != len(x):
        raise RuntimeError("pretraining pool metadata/sample length mismatch")
    return x, meta["samples"]


def make_loader(x, y, batch, shuffle=True, seed=0):
    dataset = torch.utils.data.TensorDataset(torch.from_numpy(x), torch.from_numpy(y))
    generator = torch.Generator().manual_seed(seed)
    return torch.utils.data.DataLoader(
        dataset, batch_size=batch, shuffle=shuffle, generator=generator)


def _pearson(a, b):
    if np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def metrics(pred, target, spacing_km=C.SPACING_KM):
    """Return means of per-event metrics; events never cancel each other."""
    pred = np.asarray(pred, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    if pred.shape != target.shape or pred.ndim != 3:
        raise ValueError(f"expected matching (N,H,W), got {pred.shape}, {target.shape}")
    rows = []
    yy, xx = np.indices(pred.shape[1:])
    for p, t in zip(pred, target):
        p = np.clip(p, 0.0, None); t = np.clip(t, 0.0, None)
        raw_error = (p - t) ** 2
        positive = t > 0
        p_mass, t_mass = p.sum(), t.sum()
        mass_error = abs(p_mass - t_mass) / max(t_mass, 1e-15)
        raw_mse = float(raw_error.mean())
        positive_mse = (float(raw_error[positive].mean())
                        if positive.any() else float("nan"))
        target_weighted_mse = float(
            (raw_error * t).sum() / max(t_mass, 1e-15))
        mass_absolute_error = float(abs(p_mass - t_mass))
        has_predicted_mass = p_mass > 1e-15
        raw_rmse = float(np.sqrt(raw_mse))
        p /= max(p_mass, 1e-15); t /= max(t_mass, 1e-15)
        midpoint = 0.5 * (p + t)
        js = (0.5 * (
            np.sum(np.where(p > 0, p * np.log(np.maximum(p, 1e-15) / np.maximum(midpoint, 1e-15)), 0.0))
            + np.sum(np.where(t > 0, t * np.log(np.maximum(t, 1e-15) / np.maximum(midpoint, 1e-15)), 0.0)))
              if has_predicted_mass and t_mass > 1e-15 else float("nan"))
        py, px = np.array([(p * yy).sum(), (p * xx).sum()])
        ty, tx = np.array([(t * yy).sum(), (t * xx).sum()])
        pp = np.unravel_index(np.argmax(p), p.shape)
        tp = np.unravel_index(np.argmax(t), t.shape)
        rows.append({
            "pearson": _pearson(p.ravel(), t.ravel()),
            "raw_mse": raw_mse,
            "positive_cell_mse": positive_mse,
            "target_weighted_mse": target_weighted_mse,
            "raw_rmse": raw_rmse,
            "shape_rmse": float(np.sqrt(np.mean((p - t) ** 2))),
            "js_divergence": float(js),
            "overlap": float(np.minimum(p, t).sum()),
            "mass_error": float(mass_error),
            "mass_absolute_error": mass_absolute_error,
            "center_distance_km": (
                float(np.hypot(px - tx, py - ty) * spacing_km)
                if has_predicted_mass else float("nan")),
            "peak_distance_km": (
                float(np.hypot(pp[1] - tp[1], pp[0] - tp[0]) * spacing_km)
                if has_predicted_mass else float("nan")),
        })
    keys = rows[0]
    result = {}
    for key in keys:
        values = np.asarray([row[key] for row in rows], dtype=float)
        result[key] = (float(np.nanmean(values)) if np.isfinite(values).any()
                       else float("nan"))
    result["n_events"] = len(rows)
    return result


def evaluate_model(model, x, y, batch=8, device="cpu", sample_meta=None,
                   target_mode=C.TARGET_MODE_SHAPE):
    model.eval()
    predictions = []
    with torch.no_grad():
        for start in range(0, len(x), batch):
            xb = torch.from_numpy(x[start:start + batch]).to(device)
            out = model_output(model, xb, target_mode)
            predictions.append(out.cpu().numpy()[:, 0])
    pred = np.concatenate(predictions)
    target = y[:, 0]
    result = {"overall": metrics(pred, target)}
    if sample_meta:
        snapshots = np.asarray([item["snapshot"] for item in sample_meta])
        result["by_snapshot"] = {}
        for snapshot in sorted(set(snapshots.tolist())):
            keep = snapshots == snapshot
            result["by_snapshot"][snapshot] = metrics(pred[keep], target[keep])
        dates = np.asarray([str(item["snapshot"])[:8] for item in sample_meta])
        result["by_date"] = {}
        for date in sorted(set(dates.tolist())):
            keep = dates == date
            result["by_date"][date] = metrics(pred[keep], target[keep])
        rows = list(result["by_date"].values())
        result["date_macro"] = {
            key: float(np.nanmean([row[key] for row in rows]))
            for key in rows[0] if key != "n_events"
        }
        result["date_macro"]["n_dates"] = len(rows)
    return result


def validation_loss(model, x, y, criterion, batch, device):
    model.eval()
    values = []
    with torch.no_grad():
        for start in range(0, len(x), batch):
            xb = torch.from_numpy(x[start:start + batch]).to(device)
            yb = torch.from_numpy(y[start:start + batch]).to(device)
            values.append((criterion(model(xb), yb)[0].item(), len(xb)))
    return sum(v * n for v, n in values) / sum(n for _, n in values)


def train_supervised(model, xtr, ytr, xval, yval, epochs, lr, batch,
                     name, seed, device="cpu", target_mode=C.TARGET_MODE_SHAPE,
                     mass_weight: float = 1.0):
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = make_criterion(target_mode, mass_weight=mass_weight)
    loader = make_loader(xtr, ytr, batch, seed=seed)
    best, best_state, history = float("inf"), None, []
    started = time.time()
    for epoch in range(epochs):
        model.train(); total = 0.0; count = 0
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss, _ = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            total += loss.item() * len(xb); count += len(xb)
        val = validation_loss(model, xval, yval, criterion, batch, device)
        train_mean = total / count
        history.append({"epoch": epoch + 1, "train_loss": train_mean, "val_loss": val})
        if val < best:
            best = val
            best_state = {key: value.detach().cpu().clone()
                          for key, value in model.state_dict().items()}
        if (epoch + 1) % max(1, epochs // 5) == 0 or epoch == 0:
            print(f"  [{name}] ep {epoch+1}/{epochs} train {train_mean:.4f} "
                  f"val {val:.4f} ({time.time()-started:.0f}s)")
    model.load_state_dict(best_state)
    return model, history


def train_jepa(encoder, x_unlabeled, epochs, lr, batch, seed, device="cpu",
               mask_grid=None):
    jepa = JEPA(
        encoder, latent_ch=encoder.latent_ch, mask_grid=mask_grid,
        ema_decay=C.EMA_DECAY,
        reg_mode=C.JEPA_REG_MODE, reg_slices=C.JEPA_REG_SLICES,
        mask_frac_min=C.MASK_FRAC_MIN, mask_frac_max=C.MASK_FRAC_MAX)
    jepa.to(device)
    optimizer = torch.optim.Adam(
        list(jepa.online.parameters()) + list(jepa.predictor.parameters()), lr=lr)
    dummy = np.zeros((len(x_unlabeled), 1), dtype=np.float32)
    loader = make_loader(x_unlabeled, dummy, batch, seed=seed)
    history = []
    for epoch in range(epochs):
        jepa.online.train(); jepa.target.train(); jepa.predictor.train()
        total = 0.0; count = 0
        for xb, _ in loader:
            xb = xb.to(device)
            optimizer.zero_grad(set_to_none=True)
            pred, target, mask, context = jepa(xb)
            loss = jepa.loss(pred, target, mask, context, C.JEPA_REG_WEIGHT)
            loss.backward(); optimizer.step(); jepa._ema_update()
            total += loss.item() * len(xb); count += len(xb)
        history.append({"epoch": epoch + 1, "loss": total / count})
        if (epoch + 1) % max(1, epochs // 5) == 0 or epoch == 0:
            print(f"  [jepa] ep {epoch+1}/{epochs} loss {total/count:.4f}")
    return jepa.online, history


def train_mae(encoder, x_unlabeled, epochs, lr, batch, seed, device="cpu",
              mask_fraction=0.5):
    """Pretrain the shared encoder by reconstructing masked input patches."""
    if len(x_unlabeled) == 0:
        raise ValueError("Met-MAE pretraining requires at least one input")
    base = encoder.c0.conv1.out_channels
    model = MeteorologyMAE(
        encoder, in_channels=x_unlabeled.shape[1], base=base,
        mask_fraction=mask_fraction,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    dummy = np.zeros((len(x_unlabeled), 1), dtype=np.float32)
    loader = make_loader(x_unlabeled, dummy, batch, seed=seed)
    history = []
    for epoch in range(epochs):
        model.train()
        total = 0.0
        count = 0
        for xb, _ in loader:
            xb = xb.to(device)
            optimizer.zero_grad(set_to_none=True)
            reconstruction, mask = model(xb)
            loss = model.loss(reconstruction, xb, mask)
            loss.backward()
            optimizer.step()
            total += loss.item() * len(xb)
            count += len(xb)
        history.append({"epoch": epoch + 1, "loss": total / count})
        if (epoch + 1) % max(1, epochs // 5) == 0 or epoch == 0:
            print(f"  [met-mae] ep {epoch+1}/{epochs} loss {total/count:.4f}")
    return model.encoder, history



def train_lagrangian_jepa(encoder, x_unlabeled, traj, epochs, lr, batch, seed,
                          device="cpu", predictor_kind="distance"):
    """Pretrain an encoder with Lagrangian-JEPA on trajectory features."""
    model = LagrangianJEPA(
        encoder, latent_ch=encoder.latent_ch, ema_decay=C.EMA_DECAY,
        reg_mode=C.JEPA_REG_MODE, reg_slices=C.JEPA_REG_SLICES,
        predictor_kind=predictor_kind)
    model.to(device)
    optimizer = torch.optim.Adam(
        list(model.online.parameters()) + list(model.predictor.parameters()), lr=lr)
    dataset = torch.utils.data.TensorDataset(
        torch.from_numpy(x_unlabeled), torch.from_numpy(traj))
    loader = torch.utils.data.DataLoader(
        dataset, batch_size=batch, shuffle=True,
        generator=torch.Generator().manual_seed(seed))
    history = []
    for epoch in range(epochs):
        model.online.train(); model.target.train(); model.predictor.train()
        total = 0.0; count = 0
        for xb, tb in loader:
            xb, tb = xb.to(device), tb.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss, _ = model(xb, tb)
            loss.backward(); optimizer.step(); model._ema_update()
            total += loss.item() * len(xb); count += len(xb)
        history.append({"epoch": epoch + 1, "loss": total / count})
        if (epoch + 1) % max(1, epochs // 5) == 0 or epoch == 0:
            print(f"  [lagrangian-jepa] ep {epoch+1}/{epochs} loss {total/count:.4f}")
    return model.online, history


def _baseline(smoke):
    widths = [4, 8, 16, 32, 64] if smoke else [8, 16, 32, 64, 128]
    return NestedUNetSmall(num_classes=1, input_channels=C.N_CHANNELS, nb_filter=widths)


def _checkpoint(model, arm, seed, base, smoke, data_fp):
    return {
        "state_dict": model.state_dict(), "arm": arm, "seed": seed,
        "base": base, "smoke": smoke, "data_fingerprint": data_fp,
        "source_fingerprint": source_fingerprint(),
    }


def _mean_seed_metrics(seed_results):
    summary = {}
    first = next(iter(seed_results.values()))
    arms = [key for key in first if key != "history"]
    for arm in arms:
        rows = [value[arm]["test"]["overall"] for value in seed_results.values()]
        keys = [key for key in rows[0] if key != "n_events"]
        summary[arm] = {
            key: {"mean": float(np.mean([row[key] for row in rows])),
                  "std_across_seeds": float(np.std([row[key] for row in rows], ddof=0))}
            for key in keys
        }
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--seeds", help="comma-separated integer seeds")
    parser.add_argument("--label-frac", type=float, default=1.0,
                        help="fraction of supervised labels used for "
                             "fine-tuning; pretraining still sees all inputs")
    parser.add_argument("--with-lagrangian", action="store_true",
                        help="also train the Lagrangian-JEPA prototype arm")
    args = parser.parse_args()

    train_data, test_data = load_data()
    train_idx, val_idx, validation_scope = train_validation_indices(train_data["meta"])

    # Pretraining pool: every training-split input. Fine-tuning labels are a
    # stratified subset (--label-frac); the pool is never label-restricted.
    x_pool = train_data["x"][train_idx]
    y_pool = train_data["y"][train_idx]
    labeled_idx = stratified_label_indices(
        train_data["meta"]["samples"], train_idx, args.label_frac,
        C.RECEPTOR_SEED)
    x_train = train_data["x"][labeled_idx]
    y_train = train_data["y"][labeled_idx]
    print(f"[labels] fine-tuning on {len(x_train)}/{len(x_pool)} labeled "
          f"samples (frac={args.label_frac:g})")

    # Optional inputs-only extra pool from data_builder --pretrain-snapshots.
    x_extra, meta_extra = load_pretrain_pool()
    pretrain_samples = [train_data["meta"]["samples"][i] for i in train_idx]
    if x_extra is not None:
        if x_extra.shape[-2:] != x_pool.shape[-2:]:
            raise RuntimeError(
                f"pretraining pool grid {x_extra.shape[-2:]} != data grid "
                f"{x_pool.shape[-2:]}")
        x_pretrain = np.concatenate([x_pool, x_extra], axis=0)
        pretrain_samples.extend(meta_extra)
        print(f"[pretrain] pool = {len(x_pool)} train inputs + "
              f"{len(x_extra)} unlabeled extras = {len(x_pretrain)}")
    else:
        x_pretrain = x_pool
        print(f"[pretrain] pool = {len(x_pool)} train inputs (no extra pool)")
    pretrain_pool_size = len(x_pretrain)

    x_val, y_val = train_data["x"][val_idx], train_data["y"][val_idx]
    traj_train = None
    if args.with_lagrangian:
        npart = C.SMOKE_NPART if args.smoke else min(C.NPART, 64)
        traj_train = build_trajectory_cache(
            pretrain_samples, train_data["x"].shape[-1], npart)
        if len(traj_train) != len(x_pretrain):
            raise RuntimeError(
                f"trajectory cache length {len(traj_train)} != pretraining "
                f"pool size {len(x_pretrain)}")
        print(f"[trajectory] cached {traj_train.shape}")
    seeds = ([int(value) for value in args.seeds.split(",")]
             if args.seeds else (C.SEEDS[:1] if args.smoke else C.SEEDS))
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique")
    epochs_sup = C.SMOKE_EPOCHS_SUP if args.smoke else C.EPOCHS_SUPERVISED
    epochs_jepa = C.SMOKE_EPOCHS_JEPA if args.smoke else C.EPOCHS_JEPA
    batch = C.SMOKE_BATCH if args.smoke else C.BATCH_SIZE
    base = 4 if args.smoke else 16
    run_id = args.run_id or dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = os.path.join(C.RESULTS, run_id)
    if os.path.exists(run_dir) and os.listdir(run_dir):
        raise FileExistsError(f"refusing to overwrite non-empty run directory {run_dir}")
    os.makedirs(run_dir, exist_ok=True)
    device = C.DEVICE
    print(f"[run] {run_id} device={device} seeds={seeds} validation={validation_scope}")

    all_results = {}
    data_fp = train_data["meta"]["contract_fingerprint"]
    target_mode = train_data["target_mode"]
    print(f"[run] target_mode={target_mode} label_source={C.LABEL_SOURCE}")
    mean_shape = y_train[:, 0].mean(axis=0)
    if target_mode == C.TARGET_MODE_SHAPE:
        mean_shape = mean_shape / mean_shape.sum()
        mean_description = "same normalized mean training footprint for every receptor"
    else:
        mean_description = "unnormalized mean training footprint amplitude"
    mean_prediction = np.repeat(mean_shape[None], len(test_data["x"]), axis=0)
    zero_parameter_references = {
        "train_mean_shape": {
            "overall": metrics(mean_prediction, test_data["y"][:, 0]),
            "description": mean_description,
        }
    }
    for seed in seeds:
        print(f"\n=== seed {seed}: baseline ===")
        set_seed(seed)
        baseline = _baseline(args.smoke)
        baseline, baseline_history = train_supervised(
            baseline, x_train, y_train, x_val, y_val, epochs_sup, C.LR,
            batch, "baseline", seed + 1000, device,
            target_mode=target_mode)

        set_seed(seed)
        initial_plain = PlainUNet(in_channels=C.N_CHANNELS, base=base)
        initial_state = copy.deepcopy(initial_plain.state_dict())

        print(f"\n=== seed {seed}: scratch ===")
        scratch = PlainUNet(in_channels=C.N_CHANNELS, base=base)
        scratch.load_state_dict(initial_state)
        scratch, scratch_history = train_supervised(
            scratch, x_train, y_train, x_val, y_val, epochs_sup, C.LR,
            batch, "scratch", seed + 2000, device,
            target_mode=target_mode)

        print(f"\n=== seed {seed}: JEPA + identical decoder initialization ===")
        encoder = Encoder(in_channels=C.N_CHANNELS, base=base)
        encoder.load_state_dict(initial_plain.encoder.state_dict())
        set_seed(seed + 3000)
        encoder, jepa_history = train_jepa(
            encoder, x_pretrain, epochs_jepa, C.LR_JEPA, batch, seed + 3000,
            device)
        jepa = PlainUNet(in_channels=C.N_CHANNELS, base=base)
        jepa.load_state_dict(initial_state)
        jepa.encoder.load_state_dict(encoder.state_dict())
        jepa, finetune_history = train_supervised(
            jepa, x_train, y_train, x_val, y_val, epochs_sup, C.LR,
            batch, "jepa", seed + 2000, device,
            target_mode=target_mode)

        models = {"baseline": baseline, "scratch": scratch, "jepa": jepa}
        histories = {"baseline": baseline_history, "scratch": scratch_history,
                     "jepa_pretrain": jepa_history, "jepa_finetune": finetune_history}
        if args.with_lagrangian:
            print(f"\n=== seed {seed}: Lagrangian-JEPA + identical decoder initialization ===")
            lag_encoder = Encoder(in_channels=C.N_CHANNELS, base=base)
            lag_encoder.load_state_dict(initial_plain.encoder.state_dict())
            set_seed(seed + 4000)
            lag_encoder, lag_history = train_lagrangian_jepa(
                lag_encoder, x_pretrain, traj_train, epochs_jepa, C.LR_JEPA,
                batch, seed + 4000, device)
            lag_jepa = PlainUNet(in_channels=C.N_CHANNELS, base=base)
            lag_jepa.load_state_dict(initial_state)
            lag_jepa.encoder.load_state_dict(lag_encoder.state_dict())
            lag_jepa, lag_finetune_history = train_supervised(
                lag_jepa, x_train, y_train, x_val, y_val, epochs_sup, C.LR,
                batch, "lagrangian-jepa", seed + 2000, device,
                target_mode=target_mode)
            models["lagrangian_jepa"] = lag_jepa
            histories["lagrangian_jepa_pretrain"] = lag_history
            histories["lagrangian_jepa_finetune"] = lag_finetune_history
        seed_result = {"history": histories}
        for arm, model in models.items():
            seed_result[arm] = {
                "validation": evaluate_model(
                    model, x_val, y_val, batch, device,
                    [train_data["meta"]["samples"][i] for i in val_idx],
                    target_mode=target_mode),
                "test": evaluate_model(
                    model, test_data["x"], test_data["y"], batch, device,
                    test_data["meta"]["samples"], target_mode=target_mode),
                "n_parameters": sum(p.numel() for p in model.parameters()),
            }
            path = os.path.join(run_dir, f"model_{arm}_seed{seed}.pt")
            torch.save(_checkpoint(model, arm, seed, base, args.smoke, data_fp), path)
            print(f"  {arm} test: {seed_result[arm]['test']['overall']}")
        all_results[str(seed)] = seed_result

    payload = {
        "run_id": run_id, "smoke": args.smoke, "seeds": seeds,
        "validation_scope": validation_scope,
        "target_mode": target_mode,
        "label_source": C.LABEL_SOURCE,
        "pretrain_pool_size": int(pretrain_pool_size),
        "supervised_label_fraction": float(args.label_frac),
        "independent_test_snapshots": sorted(set(
            item["snapshot"] for item in test_data["meta"]["samples"])),
        "data_contract": train_data["meta"]["contract"],
        "data_fingerprint": data_fp,
        "source_fingerprint": source_fingerprint(),
        "results_by_seed": all_results,
        "summary": _mean_seed_metrics(all_results),
        "zero_parameter_references": zero_parameter_references,
        "formal_inference_allowed": (
            not args.smoke and len(set(item["snapshot"][:8]
                                       for item in test_data["meta"]["samples"]))
            >= C.MIN_FORMAL_TEST_DATES),
        "formal_inference_reason": (
            f"requires a non-smoke run with at least {C.MIN_FORMAL_TEST_DATES} "
            "independent held-out meteorological dates; receptors from one field "
            "are not independent weather samples"),
    }
    atomic_json(os.path.join(run_dir, "results.json"), payload)
    with open(os.path.join(C.RESULTS, "LATEST"), "w", encoding="utf-8") as handle:
        handle.write(run_id + "\n")
    print(f"\n[saved] {run_dir}")


if __name__ == "__main__":
    main()
