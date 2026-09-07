"""Minimal GenGHG training smoke.

This is a first step toward real STILT-label experiments using the GenGHG
benchmark.  It uses a small fully-convolutional net that maps
    x: (112, 24, 24)  ->  y: (1, 192, 192)
and trains with MSE.  It is intentionally simple; replace with the full
five-arm JEPA/MAE protocol once the data is on Autodl.

Usage:
    python3 train_genghg.py --root /path/to/genghg_small --epochs 3
"""
from __future__ import annotations

import argparse
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from genghg_loader import GenGHGDataset, build_manifest


class SimpleGenGHGNet(nn.Module):
    """Small conv encoder-decoder: 24x24 input -> 192x192 output."""

    def __init__(self, in_channels=112, base=32):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(in_channels, base, 3, padding=1),
            nn.BatchNorm2d(base), nn.ReLU(inplace=True),
            nn.Conv2d(base, base * 2, 3, padding=1),
            nn.BatchNorm2d(base * 2), nn.ReLU(inplace=True),
            nn.Conv2d(base * 2, base * 4, 3, padding=1),
            nn.BatchNorm2d(base * 4), nn.ReLU(inplace=True),
        )
        self.head = nn.Sequential(
            nn.Conv2d(base * 4, base * 2, 3, padding=1),
            nn.BatchNorm2d(base * 2), nn.ReLU(inplace=True),
            nn.Conv2d(base * 2, 1, 1),
        )

    def forward(self, x):
        h = self.encoder(x)               # (B,128,24,24)
        y = F.interpolate(h, size=(192, 192), mode="bilinear", align_corners=False)
        y = self.head(y)                  # (B,1,192,192)
        return y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    manifest = build_manifest(args.root, limit=args.limit)
    if not manifest:
        raise SystemExit(f"no .pt samples under {args.root}")
    dataset = GenGHGDataset(manifest)
    loader = torch.utils.data.DataLoader(
        dataset, batch_size=args.batch_size, shuffle=True,
        collate_fn=lambda batch: (
            torch.stack([b[0] for b in batch]),
            torch.stack([b[1] for b in batch]),
            [b[2] for b in batch],
        ))
    print(f"[genghg] {len(manifest)} samples, grid x=24 y=192")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SimpleGenGHGNet().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    for epoch in range(1, args.epochs + 1):
        model.train()
        total = 0.0
        for x, y, _ in loader:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            pred = model(x)
            loss = loss_fn(pred, y)
            loss.backward()
            opt.step()
            total += loss.item() * len(x)
        print(f"[genghg] epoch {epoch}/{args.epochs} loss {total/len(manifest):.6f}")


if __name__ == "__main__":
    main()
