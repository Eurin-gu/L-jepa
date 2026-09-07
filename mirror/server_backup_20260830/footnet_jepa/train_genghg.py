"""GenGHG four-arm benchmark: Scratch / Met-MAE / Eulerian-JEPA / train-mean.

This script trains and evaluates a footprint emulator on GenGHG `.pt` files.
It uses real STILT footprint labels (y) and GFS meteorological inputs (x).

The five-arm protocol in the paper plan additionally includes Lagrangian-JEPA.
That arm needs particle trajectories (`traj.rds` or equivalent); the GenGHG
benchmark files only contain `x` and `y`, so this script deliberately does NOT
fake Lagrangian-JEPA. Once real trajectories are available, add the fifth arm
by pretraining `GenGHGEncoder` with `LagrangianJEPA` and then fine-tuning the
same `GenGHGNet`.

Usage:
    python3 train_genghg.py --root /path/to/genghg --epochs 1 --limit 32 --seeds 0
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
from genghg_loader import GenGHGDataset, build_manifest, train_val_test_split_by_city
from models import visreg_reg

# ---------------------------------------------------------------------------
# Small conv encoder for 24x24 GFS inputs.
# ---------------------------------------------------------------------------

class GenGHGEncoder(nn.Module):
    """Encode a 112x24x24 condition into a 6x6 latent map."""

    def __init__(self, in_channels=112, base=64):
        super().__init__()
        self.c0 = nn.Sequential(
            nn.Conv2d(in_channels, base, 3, padding=1),
            nn.BatchNorm2d(base), nn.ReLU(inplace=True))
        self.d1 = nn.Sequential(
            nn.Conv2d(base, base * 2, 3, stride=2, padding=1),
            nn.BatchNorm2d(base * 2), nn.ReLU(inplace=True))   # 12x12
        self.d2 = nn.Sequential(
            nn.Conv2d(base * 2, base * 4, 3, stride=2, padding=1),
            nn.BatchNorm2d(base * 4), nn.ReLU(inplace=True))   # 6x6
        self.latent_ch = base * 4

    def forward(self, x):
        x = self.c0(x)
        s1 = self.d1(x)
        latent = self.d2(s1)
        return latent, (x, s1)


class GenGHGDecoder(nn.Module):
    """Decode a 6x6 latent map to a 192x192 footprint."""

    def __init__(self, latent_ch, base=64, out_channels=1):
        super().__init__()
        self.up1 = nn.Sequential(
            nn.Conv2d(latent_ch, base * 2, 3, padding=1),
            nn.BatchNorm2d(base * 2), nn.ReLU(inplace=True))   # 6x6
        self.up2 = nn.Sequential(
            nn.Conv2d(base * 2, base, 3, padding=1),
            nn.BatchNorm2d(base), nn.ReLU(inplace=True))       # 12x12
        self.head = nn.Sequential(
            nn.Conv2d(base, base, 3, padding=1),
            nn.BatchNorm2d(base), nn.ReLU(inplace=True),
            nn.Conv2d(base, out_channels, 1))

    def forward(self, latent, skips):
        s0, s1 = skips
        x = self.up1(latent)                       # 6x6
        x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)
        x = self.up2(x + s1)                       # 12x12 + skip
        x = F.interpolate(x, size=(192, 192), mode="bilinear", align_corners=False)
        x = x + F.interpolate(s0, size=(192, 192), mode="bilinear", align_corners=False)
        return self.head(x)


class GenGHGNet(nn.Module):
    """Shared supervised model for all arms."""

    def __init__(self, in_channels=112, base=64):
        super().__init__()
        self.encoder = GenGHGEncoder(in_channels, base)
        self.decoder = GenGHGDecoder(self.encoder.latent_ch, base)

    def forward(self, x):
        latent, skips = self.encoder(x)
        return self.decoder(latent, skips)


# ---------------------------------------------------------------------------
# Pretext models (all pretrain only the GenGHGEncoder)
# ---------------------------------------------------------------------------

class GenGHGMAE(nn.Module):
    """Masked reconstruction of the 24x24 meteorological input."""

    def __init__(self, encoder, latent_ch, base=64, in_channels=112,
                 mask_frac=0.4):
        super().__init__()
        self.encoder = encoder
        self.mask_frac = float(mask_frac)
        self.decoder = nn.Sequential(
            nn.Conv2d(latent_ch, base * 2, 3, padding=1),
            nn.BatchNorm2d(base * 2), nn.ReLU(inplace=True),
            nn.ConvTranspose2d(base * 2, base, 4, stride=2, padding=1),
            nn.BatchNorm2d(base), nn.ReLU(inplace=True),
            nn.ConvTranspose2d(base, in_channels, 4, stride=2, padding=1))

    def forward(self, x):
        B, C, H, W = x.shape
        # Patch-mask the 24x24 input with square 4x4 blocks.
        patch = 4
        gh, gw = H // patch, W // patch
        mask = torch.zeros(B, 1, gh, gw, device=x.device)
        for i in range(B):
            side = max(1, int(round(self.mask_frac * min(gh, gw))))
            r0 = int(torch.randint(0, gh - side + 1, (), device=x.device))
            c0 = int(torch.randint(0, gw - side + 1, (), device=x.device))
            mask[i, 0, r0:r0 + side, c0:c0 + side] = 1.0
        mask_up = F.interpolate(mask, size=(H, W), mode="nearest")
        masked_x = x * (1.0 - mask_up)
        latent, _ = self.encoder(masked_x)
        recon = self.decoder(latent)
        return recon, x, mask_up

    def loss(self, recon, target, mask_up):
        diff = (recon - target) ** 2
        masked = (diff * mask_up).sum() / mask_up.sum().clamp_min(1)
        full = diff.mean()
        return masked + full


class GenGHGJEPA(nn.Module):
    """Masked latent prediction on the 6x6 encoder grid (Eulerian-JEPA)."""

    def __init__(self, encoder, latent_ch, ema_decay=0.996,
                 mask_frac_min=0.3, mask_frac_max=0.6):
        super().__init__()
        self.online = encoder
        import copy
        self.target = copy.deepcopy(encoder)
        for p in self.target.parameters():
            p.requires_grad_(False)
        self.predictor = nn.Sequential(
            nn.Conv2d(latent_ch, latent_ch, 3, padding=1),
            nn.BatchNorm2d(latent_ch), nn.ReLU(inplace=True),
            nn.Conv2d(latent_ch, latent_ch, 3, padding=1))
        self.ema_decay = ema_decay
        self.mask_frac_min = mask_frac_min
        self.mask_frac_max = mask_frac_max

    @torch.no_grad()
    def _ema_update(self):
        with torch.no_grad():
            for po, pt in zip(self.online.parameters(), self.target.parameters()):
                pt.data.mul_(self.ema_decay).add_(po.data, alpha=1 - self.ema_decay)
            for bo, bt in zip(self.online.buffers(), self.target.buffers()):
                bt.data.copy_(bo.data)

    def forward(self, x):
        B, _, H, W = x.shape
        gh, gw = H // 4, W // 4   # encoder downsample total factor 4
        mask = torch.zeros(B, 1, gh, gw, device=x.device)
        for i in range(B):
            frac = float(torch.empty((), device=x.device).uniform_(
                self.mask_frac_min, self.mask_frac_max))
            side = max(1, int(round(frac * min(gh, gw))))
            side = min(side, min(gh, gw) - 1)
            r0 = int(torch.randint(0, gh - side + 1, (), device=x.device))
            c0 = int(torch.randint(0, gw - side + 1, (), device=x.device))
            mask[i, 0, r0:r0 + side, c0:c0 + side] = 1.0
        mask_up = F.interpolate(mask, size=(H, W), mode="nearest")
        masked_x = x * (1.0 - mask_up)

        online_latent, _ = self.online(masked_x)
        pred = self.predictor(online_latent)

        target_training = self.target.training
        self.target.eval()
        with torch.no_grad():
            target_latent, _ = self.target(x)
        self.target.train(target_training)

        pred_n = F.normalize(pred, dim=1)
        target_n = F.normalize(target_latent, dim=1)
        cell = F.smooth_l1_loss(pred_n, target_n, reduction="none").mean(dim=1)
        latent_loss = (cell * mask[:, 0]).sum() / mask.sum().clamp_min(1)

        # Anti-collapse regulariser.
        c = online_latent.permute(0, 2, 3, 1).reshape(-1, online_latent.shape[1])
        scale, shape, center = visreg_reg(c, n_slices=128)
        reg = scale + shape + center
        return latent_loss + 0.5 * reg, latent_loss


# ---------------------------------------------------------------------------
# Training utilities
# ---------------------------------------------------------------------------

def make_loader(dataset, batch, shuffle=True, seed=0):
    def collate(batch):
        x = torch.stack([b[0] for b in batch])
        y = torch.stack([b[1] for b in batch])
        meta = [b[2] for b in batch]
        return x, y, meta
    return torch.utils.data.DataLoader(
        dataset, batch_size=batch, shuffle=shuffle,
        generator=torch.Generator().manual_seed(seed), collate_fn=collate)


def train_supervised(model, loader, val_loader, epochs, lr, device, name, seed):
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    best_val, best_state = float("inf"), None
    history = []
    for epoch in range(epochs):
        model.train()
        total, n = 0.0, 0
        for x, y, _ in loader:
            x, y = x.to(device), y.to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(x), y)
            loss.backward()
            opt.step()
            total += loss.item() * len(x); n += len(x)
        model.eval()
        val_total, val_n = 0.0, 0
        with torch.no_grad():
            for x, y, _ in val_loader:
                x, y = x.to(device), y.to(device)
                val_total += loss_fn(model(x), y).item() * len(x)
                val_n += len(x)
        val_loss = val_total / max(val_n, 1)
        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        history.append((total / n, val_loss))
        print(f"  [{name}] ep {epoch+1}/{epochs} train {total/n:.6f} val {val_loss:.6f}")
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, history


def evaluate_mse(model, loader, device):
    model.eval()
    preds, tgts = [], []
    with torch.no_grad():
        for x, y, _ in loader:
            x, y = x.to(device), y.to(device)
            preds.append(model(x).cpu())
            tgts.append(y.cpu())
    p = torch.cat(preds).numpy()
    t = torch.cat(tgts).numpy()
    return {"mse": float(np.mean((p - t) ** 2)),
            "mae": float(np.mean(np.abs(p - t))),
            "n": len(t)}


def pretrain_mae(encoder, loader, epochs, lr, device, seed):
    model = GenGHGMAE(encoder, encoder.latent_ch, in_channels=112)
    model.to(device)
    opt = torch.optim.Adam(list(model.encoder.parameters()) +
                           list(model.decoder.parameters()), lr=lr)
    for epoch in range(epochs):
        model.train()
        total, n = 0.0, 0
        for x, _, _ in loader:
            x = x.to(device)
            opt.zero_grad(set_to_none=True)
            recon, target, mask = model(x)
            loss = model.loss(recon, target, mask)
            loss.backward(); opt.step()
            total += loss.item() * len(x); n += len(x)
        print(f"  [mae] ep {epoch+1}/{epochs} loss {total/n:.6f}")
    return model.encoder


def pretrain_jepa(encoder, loader, epochs, lr, device, seed):
    model = GenGHGJEPA(encoder, encoder.latent_ch)
    model.to(device)
    opt = torch.optim.Adam(list(model.online.parameters()) +
                           list(model.predictor.parameters()), lr=lr)
    for epoch in range(epochs):
        model.train()
        total, n = 0.0, 0
        for x, _, _ in loader:
            x = x.to(device)
            opt.zero_grad(set_to_none=True)
            loss, _ = model(x)
            loss.backward(); opt.step(); model._ema_update()
            total += loss.item() * len(x); n += len(x)
        print(f"  [jepa] ep {epoch+1}/{epochs} loss {total/n:.6f}")
    return model.online


def set_seed(seed):
    import random
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--pretrain-epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.2)
    ap.add_argument("--run-id", default="genghg-ablation")
    args = ap.parse_args()

    device = C.DEVICE
    print(f"[genghg] device={device}")

    manifest = build_manifest(args.root)
    if args.limit and len(manifest) > args.limit:
        # Stratified sample by city so a small smoke still sees multiple cities.
        by_city = {}
        for item in manifest:
            by_city.setdefault(item["city"], []).append(item)
        cities = sorted(by_city)
        rng = np.random.RandomState(0)
        per_city = max(2, args.limit // max(len(cities), 1))
        sampled = []
        for city in cities:
            idx = rng.choice(len(by_city[city]), size=min(per_city, len(by_city[city])),
                             replace=False)
            sampled.extend(by_city[city][i] for i in idx)
        rng.shuffle(sampled)
        manifest = sampled[:args.limit]
    if len(manifest) < 3:
        raise SystemExit("need at least 3 samples")
    # Use a city-level split when possible, otherwise a simple random split.
    split = None
    try:
        split = train_val_test_split_by_city(
            manifest, val_frac=args.val_frac, test_frac=args.test_frac)
    except ValueError:
        split = None
    if not split or not split["train"] or not split["val"] or not split["test"]:
        rng = np.random.RandomState(0)
        order = rng.permutation(len(manifest))
        n_val = max(1, int(args.val_frac * len(manifest)))
        n_test = max(1, int(args.test_frac * len(manifest)))
        n_train = max(1, len(manifest) - n_val - n_test)
        split = {
            "train": [manifest[i] for i in order[:n_train]],
            "val": [manifest[i] for i in order[n_train:n_train + n_val]],
            "test": [manifest[i] for i in order[n_train + n_val:]],
        }
    print("[genghg] split:", {k: len(v) for k, v in split.items()})

    train_ds = GenGHGDataset(split["train"])
    val_ds = GenGHGDataset(split["val"])
    test_ds = GenGHGDataset(split["test"])
    train_loader = make_loader(train_ds, args.batch_size, True, 0)
    val_loader = make_loader(val_ds, args.batch_size, False, 0)
    test_loader = make_loader(test_ds, args.batch_size, False, 0)

    seeds = [int(s) for s in args.seeds.split(",")]
    results = {}
    for seed in seeds:
        print(f"\n=== seed {seed} ===")
        set_seed(seed)

        # train-mean baseline
        ysum = None; ycount = 0
        for _, y, _ in train_loader:
            if ysum is None:
                ysum = y.sum(dim=0, keepdim=True).cpu().numpy()
            else:
                ysum += y.sum(dim=0, keepdim=True).cpu().numpy()
            ycount += len(y)
        ymean = ysum / ycount
        mean_pred = torch.from_numpy(np.repeat(ymean, len(test_ds), axis=0))
        ytest = torch.cat([y for _, y, _ in test_loader])
        results.setdefault("train_mean", {"mse": float(np.mean((mean_pred.numpy() - ytest.numpy()) ** 2))})

        # Scratch
        print("=== Scratch ===")
        scratch = GenGHGNet()
        scratch, hist = train_supervised(
            scratch, train_loader, val_loader, args.epochs, 1e-3, device, "scratch", seed)
        results.setdefault("scratch", []).append(
            {"mse": evaluate_mse(scratch, test_loader, device)["mse"],
             "history": hist})

        # Met-MAE
        print("=== Met-MAE ===")
        encoder = GenGHGEncoder()
        encoder = pretrain_mae(encoder, train_loader, args.pretrain_epochs, 1e-3,
                               device, seed)
        mae_net = GenGHGNet()
        mae_net.encoder.load_state_dict(encoder.state_dict())
        mae_net, hist = train_supervised(
            mae_net, train_loader, val_loader, args.epochs, 1e-3, device, "mae", seed)
        results.setdefault("met_mae", []).append(
            {"mse": evaluate_mse(mae_net, test_loader, device)["mse"],
             "history": hist})

        # Eulerian-JEPA
        print("=== Eulerian-JEPA ===")
        encoder = GenGHGEncoder()
        encoder = pretrain_jepa(encoder, train_loader, args.pretrain_epochs, 3e-4,
                                device, seed)
        jepa_net = GenGHGNet()
        jepa_net.encoder.load_state_dict(encoder.state_dict())
        jepa_net, hist = train_supervised(
            jepa_net, train_loader, val_loader, args.epochs, 1e-3, device, "eulerian-jepa", seed)
        results.setdefault("eulerian_jepa", []).append(
            {"mse": evaluate_mse(jepa_net, test_loader, device)["mse"],
             "history": hist})

        print("[genghg] seed done:", results)

    out = os.path.join(C.RESULTS, args.run_id)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "genghg_ablation.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"[saved] {out}/genghg_ablation.json")


if __name__ == "__main__":
    main()
