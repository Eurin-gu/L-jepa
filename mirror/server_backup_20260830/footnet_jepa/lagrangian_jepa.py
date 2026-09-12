"""Lagrangian-JEPA prototype.

This is the trajectory-aware counterpart of the generic spatial JEPA in
``models.py``.  It uses a small ensemble of backward trajectories to organise
masked latent prediction along atmospheric transport paths.

Two parts:
  1. ``compute_trajectory_xy`` -- a lightweight trajectory sampler built on the
     same real-HRRR interpolation used by ``data_builder``.  It returns
     receptor-centred normalised (x, y) coordinates along the mean back trajectory.
  2. ``LagrangianJEPA`` -- a JEPA-style model that samples encoder features at
     trajectory points, masks a contiguous trajectory segment, and trains a
     trajectory-relative predictor to reconstruct the masked latent features.

This is a prototype for code/experiment development.  The trajectory source
should later be replaced by STILT/X-STILT ``traj.rds`` when those labels are
available.
"""
from __future__ import annotations

import copy

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from models import visreg_reg

# ---------------------------------------------------------------------------
# Trajectory sampling (prototype)
# ---------------------------------------------------------------------------

def compute_trajectory_xy(snapshot, receptor, met_cache, grid=64,
                          spacing_km=4.0, npart=16, seed=0,
                          backhours=None, record_step_h=None):
    """Return (T, 2) normalised receptor-centred trajectory coordinates.

    The coordinates are in the same local frame as the model input channels:
    x/y are divided by half the domain, so they lie roughly in [-1, 1].

    The mean backward trajectory is integrated with real HRRR winds and
    recorded every ``record_step_h`` hours (default: config TRAJ_RECORD_STEP_H
    = 1 h), giving T = backhours[-1] / record_step_h + 1 points. Winds are
    linearly interpolated in time between adjacent HRRR snapshots; the oldest
    segment holds the last snapshot constant.

    This is a simple mean-trajectory approximation. It does not replace
    STILT trajectories; it is only a prototype source for Lagrangian-JEPA.
    """
    import data_builder as D

    if backhours is None:
        backhours = list(D.C.BACKHOURS)
    else:
        backhours = list(backhours)
    if record_step_h is None:
        record_step_h = float(D.C.TRAJ_RECORD_STEP_H)

    rlat, rlon = receptor
    lats, lons, offsets_km = D.receptor_grid(rlat, rlon, grid, spacing_km)
    half_km = grid * spacing_km / 2.0

    snaps = D.back_snapshots(snapshot, backhours)
    missing = [s for s in snaps if s not in met_cache]
    if missing:
        raise FileNotFoundError(f"missing HRRR snapshots for trajectory: {missing}")

    # Particle state (lon, lat). Start at the receptor.
    lon = np.full(npart, rlon, dtype=np.float64)
    lat = np.full(npart, rlat, dtype=np.float64)
    alive = np.ones(npart, dtype=bool)
    rng = np.random.default_rng(seed)

    dt = D.C.DT
    diffusivity = D.C.DIFFUSIVITY
    sigma = np.sqrt(2.0 * diffusivity * dt)
    deg_lat = 110540.0
    deg_lon_eq = 111320.0

    def wind_at(tau, particle_lat, particle_lon):
        """Time-interpolated wind at elapsed back-hours tau."""
        pxi, pyi = D.latlon_to_grid_xy(particle_lat, particle_lon)
        block = int(np.searchsorted(np.asarray(backhours), tau + 1e-9)) - 1
        block = int(np.clip(block, 0, len(snaps) - 1))
        m0 = met_cache[snaps[block]]
        u0 = D._bilinear(m0["U10M"], pxi, pyi, bounds_error=False)
        v0 = D._bilinear(m0["V10M"], pxi, pyi, bounds_error=False)
        u, v = np.asarray(u0, dtype=float), np.asarray(v0, dtype=float)
        if block + 1 < len(snaps):
            span = backhours[block + 1] - backhours[block]
            w = (tau - backhours[block]) / span
            w = float(np.clip(w, 0.0, 1.0))
            m1 = met_cache[snaps[block + 1]]
            u1 = D._bilinear(m1["U10M"], pxi, pyi, bounds_error=False)
            v1 = D._bilinear(m1["V10M"], pxi, pyi, bounds_error=False)
            u = (1.0 - w) * u + w * np.asarray(u1, dtype=float)
            v = (1.0 - w) * v + w * np.asarray(v1, dtype=float)
        valid = np.isfinite(u) & np.isfinite(v)
        return u, v, valid

    def record_position():
        positions.append((float(np.mean(lon[alive])) if alive.any() else rlon,
                          float(np.mean(lat[alive])) if alive.any() else rlat))

    total_h = backhours[-1]
    substeps_total = int(round(total_h * 3600.0 / dt))
    record_every = max(1, int(round(record_step_h * 3600.0 / dt)))

    positions = [(rlon, rlat)]
    for step in range(substeps_total):
        tau = (step + 0.5) * dt / 3600.0     # substep mid-point back-hours
        u, v, valid = wind_at(min(tau, total_h), lat, lon)
        alive &= valid
        u = np.where(alive, u, 0.0)
        v = np.where(alive, v, 0.0)
        coslat = np.cos(np.radians(lat))
        lon = lon - u * dt / (deg_lon_eq * coslat)
        lat = lat - v * dt / deg_lat
        lon = lon + np.where(alive, rng.normal(0.0, sigma / (deg_lon_eq * coslat), npart), 0.0)
        lat = lat + np.where(alive, rng.normal(0.0, sigma / deg_lat, npart), 0.0)
        if (step + 1) % record_every == 0:
            record_position()

    # Guard against rounding mismatches between record_every and total hours.
    while len(positions) < int(round(total_h / record_step_h)) + 1:
        record_position()

    pos = np.asarray(positions, dtype=np.float64)  # (T, 2) = (lon, lat)
    dlon_km = (pos[:, 0] - rlon) * 111.32 * np.cos(np.radians(rlat))
    dlat_km = (pos[:, 1] - rlat) * 110.54
    xy = np.column_stack([dlon_km, dlat_km]) / half_km
    return xy.astype(np.float32)  # (T, 2) in [-1, 1]-ish local coordinates


# ---------------------------------------------------------------------------
# Canonical trajectory cache (single implementation; used by train.py and
# train_lagrangian_jepa.py)
# ---------------------------------------------------------------------------

def build_trajectory_cache(samples, grid, npart):
    """Precompute normalised trajectory coordinates for metadata dicts.

    samples: iterable of metadata dicts with snapshot / latitude / longitude
    keys (e.g. entries of a data_builder *_meta.json "samples" list).

    Returns an (N, T, 2) float32 array aligned with the input order.
    """
    import data_builder as D

    samples = list(samples)
    snapshots = sorted({s["snapshot"] for s in samples})
    required = {b for s in snapshots for b in D.back_snapshots(s)}
    met_cache = D.load_hrrr_cache(D.C.HRRR_DIR, required)
    out = []
    for sample in samples:
        seed = D._sample_seed(sample["snapshot"],
                              (sample["latitude"], sample["longitude"]))
        out.append(compute_trajectory_xy(
            sample["snapshot"], (sample["latitude"], sample["longitude"]),
            met_cache, grid=grid, spacing_km=D.C.SPACING_KM,
            npart=npart, seed=seed))
    return np.stack(out).astype(np.float32)


# ---------------------------------------------------------------------------
# Fake-trajectory controls (F1-F3) for the L-JEPA causality audit.
#
#   F1 reverse: integrate (-u, -v). Path length identical, direction reversed.
#   F2 perp:    integrate (-v,  u). 90-degree-rotated wind -> geometric tube
#               that crosses (not follows) the true footprint bright band.
#   F3 random:  per-sample fixed heading theta with step size = true speed,
#               i.e. a straight tube of the same length as the wind skeleton
#               but with no physical advection direction.
#
# These change ONLY how the tube is drawn.  The model, the segment-mask rule,
# the mask length, and the supervised budget stay identical to the true
# input-wind arm (see train_stilt_strict / planning pre-registration).
# ---------------------------------------------------------------------------
TRAJ_TRANSFORMS = ("none", "reverse", "perp", "random_heading")


def apply_trajectory_transform(u, v, transform, rng=None):
    """Return (u2, v2) with the requested direction control.

    u, v : (B, T) centre winds, already de-normalised to m/s.
    transform : none | reverse | perp | random_heading.
    rng : np.random.Generator used only by random_heading (one fixed theta
          per sample, constant along the trajectory).
    """
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    if transform == "none":
        return u, v
    if transform == "reverse":
        return -u, -v
    if transform == "perp":
        return -v, u
    if transform == "random_heading":
        if rng is None:
            rng = np.random.default_rng(0)
        theta = rng.uniform(0.0, 2.0 * np.pi, size=u.shape[0])
        speed = np.hypot(u, v)                 # (B, T) keeps tube length aligned
        ct = np.cos(theta)[:, None]
        st = np.sin(theta)[:, None]
        return speed * ct, speed * st
    raise ValueError("unknown trajectory transform: " + str(transform))


def input_wind_trajectory(inputs, backhours=None, step_h=None,
                          spacing_km=None, transform="none", seed=0):
    """Derive a deployment-available mean trajectory from FootNet inputs.

    This deliberately uses only the normalized U10M/V10M channels already
    presented to the encoder.  It is therefore suitable for the primary
    L-JEPA arm, unlike a STILT particle trajectory produced by the same solve
    as the downstream footprint label.

    transform applies one of the F1-F3 direction controls (see module docs)
    to the centre wind *before* integration; the numerical integration and
    the returned coordinate frame are unchanged.  seed is used only when
    transform == "random_heading".
    """
    import config as C

    values = np.asarray(inputs, dtype=np.float32)
    if values.ndim != 4 or values.shape[1] != C.N_CHANNELS:
        raise ValueError(
            f"expected FootNet inputs (N,{C.N_CHANNELS},H,W), got {values.shape}")
    if values.shape[-2] != values.shape[-1]:
        raise ValueError("input-wind trajectory requires a square local grid")
    backhours = np.asarray(C.BACKHOURS if backhours is None else backhours,
                           dtype=np.float64)
    step_h = float(C.TRAJ_RECORD_STEP_H if step_h is None else step_h)
    spacing_km = float(C.SPACING_KM if spacing_km is None else spacing_km)
    if len(backhours) < 2 or backhours[0] != 0 or np.any(np.diff(backhours) <= 0):
        raise ValueError("backhours must start at 0 and increase strictly")
    if step_h <= 0:
        raise ValueError("step_h must be positive")

    center = values.shape[-1] // 2
    u = np.stack([
        values[:, 1 + 4 * index, center, center] / C.MET_SCALES[0]
        + C.MET_OFFSETS[0]
        for index in range(len(backhours))
    ], axis=1).astype(np.float64)
    v = np.stack([
        values[:, 2 + 4 * index, center, center] / C.MET_SCALES[1]
        + C.MET_OFFSETS[1]
        for index in range(len(backhours))
    ], axis=1).astype(np.float64)

    if transform not in TRAJ_TRANSFORMS:
        raise ValueError("unknown trajectory transform: " + str(transform))
    if transform != "none":
        rng = (np.random.default_rng(seed) if transform == "random_heading"
               else None)
        u, v = apply_trajectory_transform(u, v, transform, rng=rng)

    total_h = float(backhours[-1])
    times = np.arange(0.0, total_h + 0.5 * step_h, step_h)
    if times[-1] < total_h:
        times = np.append(times, total_h)
    positions = np.zeros((len(values), len(times), 2), dtype=np.float64)
    half_km = values.shape[-1] * spacing_km / 2.0
    for index in range(1, len(times)):
        midpoint = 0.5 * (times[index - 1] + times[index])
        block = int(np.searchsorted(backhours, midpoint, side="right") - 1)
        block = min(max(block, 0), len(backhours) - 2)
        weight = (midpoint - backhours[block]) / (
            backhours[block + 1] - backhours[block])
        u_mid = (1.0 - weight) * u[:, block] + weight * u[:, block + 1]
        v_mid = (1.0 - weight) * v[:, block] + weight * v[:, block + 1]
        elapsed_seconds = (times[index] - times[index - 1]) * 3600.0
        positions[:, index, 0] = (
            positions[:, index - 1, 0] - u_mid * elapsed_seconds / 1000.0 / half_km)
        positions[:, index, 1] = (
            positions[:, index - 1, 1] - v_mid * elapsed_seconds / 1000.0 / half_km)
    return positions.astype(np.float32)


# ---------------------------------------------------------------------------
# Trajectory-relative predictor
# ---------------------------------------------------------------------------

class TrajectoryPredictor(nn.Module):
    """Predict masked trajectory features from visible trajectory features.

    A lightweight attention module: each query (masked trajectory point)
    attends to all visible trajectory points by coordinate distance.
    """

    def __init__(self, latent_ch: int, hidden: int = 128, scale: float = 1.0):
        super().__init__()
        self.scale = float(scale)
        self.pos_embed = nn.Sequential(
            nn.Linear(2, hidden),
            nn.ReLU(inplace=True),
            nn.Linear(hidden, latent_ch),
        )
        self.mlp = nn.Sequential(
            nn.Linear(latent_ch * 2, hidden),
            nn.ReLU(inplace=True),
            nn.Linear(hidden, latent_ch),
        )

    def forward(self, visible_feats, visible_xy, query_xy,
                visible_valid=None, query_valid=None):
        """Batched distance attention.

        visible_feats: (B, Tv, C)   visible_xy: (B, Tv, 2)
        query_xy:      (B, Tq, 2)
        visible_valid / query_valid: optional (B, Tv) / (B, Tq) bool masks
        marking real (non-padded) positions; padded keys are excluded from the
        attention and padded queries are still processed but can be discarded.
        """
        diff = query_xy[:, :, None, :] - visible_xy[:, None, :, :]  # (B,Tq,Tv,2)
        dist2 = (diff ** 2).sum(-1) / (self.scale ** 2 + 1e-6)       # (B,Tq,Tv)
        if visible_valid is not None:
            key_mask = visible_valid[:, None, :].expand_as(dist2)
            dist2 = dist2.masked_fill(~key_mask, float("inf"))
        attn = torch.softmax(-dist2, dim=-1)
        attn = torch.nan_to_num(attn, nan=0.0)     # all-padded rows -> zeros
        context = torch.einsum("bqv,bvc->bqc", attn, visible_feats)  # (B,Tq,C)
        pos = self.pos_embed(query_xy)                                # (B,Tq,C)
        out = self.mlp(torch.cat([context, pos], dim=-1))
        if query_valid is not None:
            return out * query_valid.unsqueeze(-1).to(out.dtype)
        return out


class TransformerTrajectoryPredictor(nn.Module):
    """Stronger predictor: self-attention over visible trajectory tokens + distance attention to queries."""

    def __init__(self, latent_ch: int, hidden: int = 128, nhead: int = 4,
                 num_layers: int = 2, scale: float = 1.0):
        super().__init__()
        self.scale = float(scale)
        self.pos_embed = nn.Sequential(
            nn.Linear(2, hidden), nn.ReLU(inplace=True), nn.Linear(hidden, latent_ch))
        self.query_embed = nn.Sequential(
            nn.Linear(2, hidden), nn.ReLU(inplace=True), nn.Linear(hidden, latent_ch))
        layer = nn.TransformerEncoderLayer(
            d_model=latent_ch, nhead=nhead, dim_feedforward=hidden,
            batch_first=True, dropout=0.1)
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)
        self.mlp = nn.Sequential(
            nn.Linear(latent_ch * 2, hidden), nn.ReLU(inplace=True),
            nn.Linear(hidden, latent_ch))

    def forward(self, visible_feats, visible_xy, query_xy,
                visible_valid=None, query_valid=None):
        B, Tv, C = visible_feats.shape
        tokens = visible_feats + self.pos_embed(visible_xy)
        src_key_padding_mask = None
        if visible_valid is not None:
            src_key_padding_mask = ~visible_valid
        encoded = self.encoder(tokens, src_key_padding_mask=src_key_padding_mask)

        # Distance attention from each query to all encoded visible points.
        diff = query_xy[:, :, None, :] - visible_xy[:, None, :, :]  # (B,Tq,Tv,2)
        dist2 = (diff ** 2).sum(-1) / (self.scale ** 2 + 1e-6)
        if visible_valid is not None:
            key_mask = visible_valid[:, None, :].expand_as(dist2)
            dist2 = dist2.masked_fill(~key_mask, float("inf"))
        attn = torch.softmax(-dist2, dim=-1)
        attn = torch.nan_to_num(attn, nan=0.0)
        context = torch.einsum("bqv,bvc->bqc", attn, encoded)  # (B,Tq,C)
        q = self.query_embed(query_xy)
        out = self.mlp(torch.cat([context, q], dim=-1))
        if query_valid is not None:
            out = out * query_valid.unsqueeze(-1).to(out.dtype)
        return out


# ---------------------------------------------------------------------------
# Lagrangian-JEPA
# ---------------------------------------------------------------------------

class LagrangianJEPA(nn.Module):
    """Masked latent prediction along backward trajectories.

    The online encoder sees the full meteorological input (the masking is done
    in trajectory space rather than input space).  The target encoder is an EMA
    copy and provides supervision features at all trajectory points.
    """

    def __init__(self, encoder, latent_ch: int, ema_decay: float = 0.996,
                 seg_frac_min: float = 0.2, seg_frac_max: float = 0.6,
                 reg_mode: str = "visreg", reg_slices: int = 256,
                 hidden: int = 128, predictor_kind: str = "distance"):
        super().__init__()
        self.online = encoder
        self.target = copy.deepcopy(encoder)
        for p in self.target.parameters():
            p.requires_grad_(False)
        if predictor_kind == "transformer":
            self.predictor = TransformerTrajectoryPredictor(
                latent_ch, hidden=hidden)
        else:
            self.predictor = TrajectoryPredictor(latent_ch, hidden=hidden)
        self.ema_decay = ema_decay
        self.latent_ch = latent_ch
        self.seg_frac_min = float(seg_frac_min)
        self.seg_frac_max = float(seg_frac_max)
        assert reg_mode in ("visreg", "sigreg")
        self.reg_mode = reg_mode
        self.reg_slices = reg_slices

    @torch.no_grad()
    def _ema_update(self):
        with torch.no_grad():
            for po, pt in zip(self.online.parameters(), self.target.parameters()):
                pt.data.mul_(self.ema_decay).add_(po.data, alpha=1 - self.ema_decay)
            for bo, bt in zip(self.online.buffers(), self.target.buffers()):
                bt.data.copy_(bo.data)

    @staticmethod
    def _sample_features(latent, xy):
        """Bilinear sample latent features at normalised (x, y) trajectory points.

        latent: (B, C, H, W)
        xy:     (B, T, 2), x east / y north normalised by half-domain.
        Returns (B, T, C).
        """
        B, C, H, W = latent.shape
        x = xy[..., 0]         # east -> increasing longitude / array column
        # data_builder and stilt_io both store rows south-to-north, so north is
        # the positive grid_sample y direction (row 0 maps to -1).
        y = xy[..., 1]         # north -> increasing latitude / array row
        grid = torch.stack([x, y], dim=-1).clamp(-1.0, 1.0)  # (B,T,2)
        grid = grid.unsqueeze(1).to(latent.dtype)            # (B,1,T,2)
        sampled = F.grid_sample(
            latent, grid, mode="bilinear", padding_mode="border", align_corners=True)
        return sampled[:, :, 0, :].transpose(1, 2)           # (B,T,C)

    def _make_segment_mask(self, T: int, B: int, device):
        """Return a boolean visible mask of shape (B, T). True = visible.

        The masked segment length is shared across the batch so all samples
        have the same number of query points. Each sample gets a random
        start position.
        """
        frac = float(torch.empty((), device=device).uniform_(
            self.seg_frac_min, self.seg_frac_max))
        length = max(1, int(round(frac * T)))
        length = min(length, T - 1)
        starts = torch.randint(0, T - length + 1, (B,), device=device)
        rows = torch.arange(T, device=device).unsqueeze(0)           # (1,T)
        masked = ((rows >= starts[:, None]) & (rows < starts[:, None] + length))
        return ~masked

    def forward(self, x, traj_xy):
        if traj_xy.ndim != 3 or traj_xy.shape[0] != x.shape[0] or traj_xy.shape[-1] != 2:
            raise ValueError(
                f"trajectory must have shape (B,T,2), got {tuple(traj_xy.shape)} "
                f"for input batch {x.shape[0]}")
        if not torch.isfinite(traj_xy).all():
            raise ValueError("trajectory contains non-finite coordinates")
        B, T, _ = traj_xy.shape
        if T < 2:
            raise ValueError("trajectory must contain at least two points")
        # BatchNorm in the EMA target must not update independently of the
        # online encoder. The target is a deterministic teacher for this step.
        target_training = self.target.training
        self.target.eval()
        with torch.no_grad():
            target_latent = self.target(x)[0].detach()
        self.target.train(target_training)
        online_latent = self.online(x)[0]

        online_feats = self._sample_features(online_latent, traj_xy)   # (B,T,C)
        target_feats = self._sample_features(target_latent, traj_xy)   # (B,T,C)

        visible_mask = self._make_segment_mask(T, B, x.device)         # (B,T)
        query_mask = ~visible_mask                                     # (B,T)

        # Batched prediction: every position queries all visible positions;
        # masked-out queries are zeroed by the predictor via query_valid and
        # discarded below. All samples share the same masked segment length,
        # so the gather stays rectangular.
        pred_all = self.predictor(
            online_feats, traj_xy, traj_xy,
            visible_valid=visible_mask, query_valid=query_mask)        # (B,T,C)
        q_rows, q_cols = torch.nonzero(query_mask, as_tuple=True)
        n_query = int(query_mask.sum(dim=1).max().item())
        pred = pred_all[q_rows, q_cols].view(B, n_query, -1)           # (B,L,C)
        tgt = target_feats[q_rows, q_cols].view(B, n_query, -1)        # (B,L,C)

        # Normalise features over channels before the loss.
        pred_n = F.normalize(pred, dim=-1)
        tgt_n = F.normalize(tgt, dim=-1)
        masked_loss = F.smooth_l1_loss(pred_n, tgt_n)

        # Anti-collapse regulariser on the online latent.
        c = online_latent.permute(0, 2, 3, 1).reshape(-1, online_latent.shape[1])
        if self.reg_mode == "visreg":
            scale, shape, center = visreg_reg(c, n_slices=self.reg_slices)
            reg = scale + shape + center
        else:
            from models import sigreg_reg
            reg = sigreg_reg(c, n_slices=self.reg_slices)

        return masked_loss + 0.5 * reg, masked_loss


# ---------------------------------------------------------------------------
# Demo / smoke
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from models import Encoder

    torch.manual_seed(0)
    encoder = Encoder(in_channels=20, base=4)
    model = LagrangianJEPA(encoder, encoder.latent_ch, hidden=32)
    x = torch.randn(2, 20, 64, 64)
    traj = torch.randn(2, 5, 2)
    loss, masked = model(x, traj)
    print("lagrangian-jepa loss:", loss.item(), "masked:", masked.item())
