"""Network architectures for the footprint-emulator ablation.

* NestedUNetSmall : the paper's U-Net++ (nested skip connections), scaled to
  CPU-friendly filter widths -> "paper method" baseline.
* Encoder / Decoder : a plain U-Net-style encoder + decoder.  The encoder is
  the shared JEPA backbone; Decoder is the supervised footprint head.  The
  same (Encoder + Decoder) model trained from scratch is the ablation control.
"""
import copy

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# ----------------------------------------------------------------------------
# Anti-collapse regularizers for JEPA pretraining.
#
# VICReg-style variance/covariance terms were previously computed on the
# *detached EMA target* latent, which carries no gradient (see the project
# audit, section 3.3) -- they were dead code.  The regularizers below are
# applied to the ONLINE context latent instead, and come from the two
# successors of VICReg:
#   * SIGReg  -- Sketched Isotropic Gaussian Regularization (LeJEPA,
#                Balestriero & LeCun, arXiv:2511.08544): Epps-Pulley
#                normality statistic on random 1-D slices.
#   * VISReg  -- Variance-Invariance-Sketching Regularization (Wu,
#                Balestriero & Levine, arXiv:2606.02572): keeps VICReg's
#                variance (scale) term but replaces the second-order
#                covariance term with a Sliced-Wasserstein sketch of the
#                full distribution shape; robust gradients under collapse.
# ----------------------------------------------------------------------------
_QUANTILE_CACHE = {}


def _random_unit_slices(dim, n_slices, device):
    """n_slices random unit-norm directions in R^dim (Cramer-Wold slicing)."""
    w = torch.randn(dim, n_slices, device=device)
    return w / (w.norm(dim=0, keepdim=True) + 1e-12)


def _gaussian_quantiles(n, device):
    """Mid-point quantiles q_i = Phi^-1((i+0.5)/n) of the standard normal."""
    key = (n, str(device))
    q = _QUANTILE_CACHE.get(key)
    if q is None:
        p = (torch.arange(n, device=device, dtype=torch.float32) + 0.5) / n
        q = (torch.erfinv(2.0 * p - 1.0) * (2.0 ** 0.5)).detach()
        _QUANTILE_CACHE[key] = q
    return q


def visreg_reg(z, n_slices=256):
    """VISReg scale/shape/center terms on embeddings z (N, D) WITH gradient.

    Returns (scale, shape, center) scalars (paper eqs. 1, 5, 6).
    """
    mu = z.mean(dim=0)                          # (D,) batch mean
    z_hat = z - mu                              # centered
    sigma = z_hat.std(dim=0, correction=0)      # stable for small batches

    # scale: squared variance hinge (gradient stays nonzero under collapse)
    scale = (1.0 - sigma).square().mean()

    # shape: sliced 2-Wasserstein to the standard normal on the
    # scale-normalized embeddings; stop-gradient on sigma decouples the
    # shape and scale objectives (paper eq. 2)
    z_tilde = z_hat / (sigma.detach() + 1e-4)
    proj = z_tilde @ _random_unit_slices(z.shape[1], n_slices, z.device)
    proj_sorted = proj.sort(dim=0).values       # (N, K)
    q = _gaussian_quantiles(z.shape[0], z.device).unsqueeze(1)
    shape = (proj_sorted - q).square().mean()

    # center: pull the batch mean toward the origin
    center = mu.square().mean()
    return scale, shape, center


def sigreg_reg(z, n_slices=256, t_max=3.0, n_points=17):
    """SIGReg: Epps-Pulley normality statistic on random 1-D slices.

    SIGReg couples scale and shape (standardized embeddings), unlike VISReg.
    Implementation follows the official lejepa EppsPulley test (trapezoid).
    """
    n = z.shape[0]
    z_std = ((z - z.mean(dim=0))
             / (z.std(dim=0, correction=0) + 1e-4))
    proj = z_std @ _random_unit_slices(z.shape[1], n_slices, z.device)  # (N,K)

    t = torch.linspace(0.0, t_max, n_points, device=z.device)
    dt = t_max / (n_points - 1)
    weights = torch.full((n_points,), 2.0 * dt, device=z.device)
    weights[0] = weights[-1] = dt
    phi = torch.exp(-t.square() / 2.0)

    xt = proj.unsqueeze(-1) * t                 # (N, K, P)
    cos_mean = torch.cos(xt).mean(dim=0)
    sin_mean = torch.sin(xt).mean(dim=0)
    err = (cos_mean - phi).square() + sin_mean.square()
    return (err @ (weights * phi)).mean() * n


class VGGBlock(nn.Module):
    """Two 3x3 convs + BN + ReLU (same building block as the repo)."""

    def __init__(self, in_channels, middle_channels, out_channels):
        super().__init__()
        self.relu = nn.ReLU(inplace=True)
        self.conv1 = nn.Conv2d(in_channels, middle_channels, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(middle_channels)
        self.conv2 = nn.Conv2d(middle_channels, out_channels, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(out_channels)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.conv2(x)
        x = self.bn2(x)
        x = self.relu(x)
        return x


class NestedUNetSmall(nn.Module):
    """Faithful (but small) U-Net++: nb_filter configurable, 5 down stages."""

    def __init__(self, num_classes=1, input_channels=20, nb_filter=None, deep_supervision=False):
        super().__init__()
        if nb_filter is None:
            nb_filter = [16, 32, 64, 128, 256]
        self.nb_filter = nb_filter
        self.deep_supervision = deep_supervision
        self.pool = nn.MaxPool2d(2, 2)
        self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)

        n = nb_filter
        self.conv0_0 = VGGBlock(input_channels, n[0], n[0])
        self.conv1_0 = VGGBlock(n[0], n[1], n[1])
        self.conv2_0 = VGGBlock(n[1], n[2], n[2])
        self.conv3_0 = VGGBlock(n[2], n[3], n[3])
        self.conv4_0 = VGGBlock(n[3], n[4], n[4])

        self.conv0_1 = VGGBlock(n[0] + n[1], n[0], n[0])
        self.conv1_1 = VGGBlock(n[1] + n[2], n[1], n[1])
        self.conv2_1 = VGGBlock(n[2] + n[3], n[2], n[2])
        self.conv3_1 = VGGBlock(n[3] + n[4], n[3], n[3])

        self.conv0_2 = VGGBlock(n[0] * 2 + n[1], n[0], n[0])
        self.conv1_2 = VGGBlock(n[1] * 2 + n[2], n[1], n[1])
        self.conv2_2 = VGGBlock(n[2] * 2 + n[3], n[2], n[2])

        self.conv0_3 = VGGBlock(n[0] * 3 + n[1], n[0], n[0])
        self.conv1_3 = VGGBlock(n[1] * 3 + n[2], n[1], n[1])

        self.conv0_4 = VGGBlock(n[0] * 4 + n[1], n[0], n[0])

        if deep_supervision:
            self.finals = nn.ModuleList(
                [nn.Conv2d(n[0], num_classes, 1) for _ in range(4)])
        else:
            self.final = nn.Conv2d(n[0], num_classes, 1)

    def forward(self, x):
        n = self.nb_filter
        x0_0 = self.conv0_0(x)
        x1_0 = self.conv1_0(self.pool(x0_0))
        x0_1 = self.conv0_1(torch.cat([x0_0, self.up(x1_0)], 1))

        x2_0 = self.conv2_0(self.pool(x1_0))
        x1_1 = self.conv1_1(torch.cat([x1_0, self.up(x2_0)], 1))
        x0_2 = self.conv0_2(torch.cat([x0_0, x0_1, self.up(x1_1)], 1))

        x3_0 = self.conv3_0(self.pool(x2_0))
        x2_1 = self.conv2_1(torch.cat([x2_0, self.up(x3_0)], 1))
        x1_2 = self.conv1_2(torch.cat([x1_0, x1_1, self.up(x2_1)], 1))
        x0_3 = self.conv0_3(torch.cat([x0_0, x0_1, x0_2, self.up(x1_2)], 1))

        x4_0 = self.conv4_0(self.pool(x3_0))
        x3_1 = self.conv3_1(torch.cat([x3_0, self.up(x4_0)], 1))
        x2_2 = self.conv2_2(torch.cat([x2_0, x2_1, self.up(x3_1)], 1))
        x1_3 = self.conv1_3(torch.cat([x1_0, x1_1, x1_2, self.up(x2_2)], 1))
        x0_4 = self.conv0_4(torch.cat([x0_0, x0_1, x0_2, x0_3, self.up(x1_3)], 1))

        if self.deep_supervision:
            return [f(x0_i) for f, x0_i in zip(self.finals, [x0_1, x0_2, x0_3, x0_4])]
        return self.final(x0_4)


class Encoder(nn.Module):
    """Plain U-Net encoder -> (deep latent, skip features). Shared JEPA backbone."""

    def __init__(self, in_channels=20, base=16):
        super().__init__()
        n = [base * 2 ** i for i in range(5)]        # 16, 32, 64, 128, 256
        self.pool = nn.MaxPool2d(2, 2)
        self.c0 = VGGBlock(in_channels, n[0], n[0])
        self.c1 = VGGBlock(n[0], n[1], n[1])
        self.c2 = VGGBlock(n[1], n[2], n[2])
        self.c3 = VGGBlock(n[2], n[3], n[3])
        self.c4 = VGGBlock(n[3], n[4], n[4])
        self.latent_ch = n[4]

    def forward(self, x):
        s0 = self.c0(x)                    # 400
        s1 = self.c1(self.pool(s0))        # 200
        s2 = self.c2(self.pool(s1))        # 100
        s3 = self.c3(self.pool(s2))        # 50
        s4 = self.c4(self.pool(s3))        # 25
        return s4, [s0, s1, s2, s3]


class Decoder(nn.Module):
    """Plain U-Net decoder that consumes Encoder's latent + skips."""

    def __init__(self, base=16, out_channels=1):
        super().__init__()
        n = [base * 2 ** i for i in range(5)]        # 16,32,64,128,256
        self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
        self.d3 = VGGBlock(n[4] + n[3], n[3], n[3])   # 256+128 -> 128 at 50
        self.d2 = VGGBlock(n[3] + n[2], n[2], n[2])   # 128+64  -> 64 at 100
        self.d1 = VGGBlock(n[2] + n[1], n[1], n[1])   # 64+32   -> 32 at 200
        self.d0 = VGGBlock(n[1] + n[0], n[0], n[0])   # 32+16   -> 16 at 400
        self.final = nn.Conv2d(n[0], out_channels, 1)

    def forward(self, latent, skips):
        s0, s1, s2, s3 = skips
        x = self.up(latent)                       # 25 -> 50
        x = self.d3(torch.cat([x, s3], 1))
        x = self.up(x)                            # 50 -> 100
        x = self.d2(torch.cat([x, s2], 1))
        x = self.up(x)                            # 100 -> 200
        x = self.d1(torch.cat([x, s1], 1))
        x = self.up(x)                            # 200 -> 400
        x = self.d0(torch.cat([x, s0], 1))
        return self.final(x)


class PlainUNet(nn.Module):
    """Encoder + Decoder. The JEPA backbone + supervised head (and scratch control)."""

    def __init__(self, in_channels=20, base=16, out_channels=1):
        super().__init__()
        self.encoder = Encoder(in_channels, base)
        self.decoder = Decoder(base, out_channels)

    def forward(self, x):
        latent, skips = self.encoder(x)
        return self.decoder(latent, skips)


# ----------------------------------------------------------------------------
# JEPA pretraining (conv-based masked latent-patch prediction)
# ----------------------------------------------------------------------------

class HighResEncoder(nn.Module):
    """Encoder with stride 4 (two downsamplings) for higher latent resolution.

    64x64 input -> 16x16 latent; 128x128 -> 32x32 latent.
    """
    def __init__(self, in_channels=20, base=16):
        super().__init__()
        n = [base * 2 ** i for i in range(3)]   # 16,32,64
        self.pool = nn.MaxPool2d(2, 2)
        self.c0 = VGGBlock(in_channels, n[0], n[0])
        self.c1 = VGGBlock(n[0], n[1], n[1])
        self.c2 = VGGBlock(n[1], n[2], n[2])
        self.latent_ch = n[2]

    def forward(self, x):
        s0 = self.c0(x)
        s1 = self.c1(self.pool(s0))
        s2 = self.c2(self.pool(s1))
        return s2, [s0, s1]


class HighResDecoder(nn.Module):
    """Decoder for HighResEncoder: 16x16 latent -> 64x64 output."""
    def __init__(self, latent_ch, base=16, out_channels=1):
        super().__init__()
        n = [base * 2 ** i for i in range(3)]   # 16,32,64
        self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
        self.d1 = VGGBlock(n[2] + n[1], n[1], n[1])
        self.d0 = VGGBlock(n[1] + n[0], n[0], n[0])
        self.final = nn.Conv2d(n[0], out_channels, 1)

    def forward(self, latent, skips):
        s0, s1 = skips
        x = self.up(latent)
        x = self.d1(torch.cat([x, s1], 1))
        x = self.up(x)
        x = self.d0(torch.cat([x, s0], 1))
        return self.final(x)


class HighResPlainUNet(nn.Module):
    """Plain U-Net with high-resolution latent (stride 4)."""
    def __init__(self, in_channels=20, base=16, out_channels=1):
        super().__init__()
        self.encoder = HighResEncoder(in_channels, base)
        self.decoder = HighResDecoder(self.encoder.latent_ch, base, out_channels)

    def forward(self, x):
        latent, skips = self.encoder(x)
        return self.decoder(latent, skips)


class MeteorologyMAE(nn.Module):
    """Masked autoencoder whose reconstruction objective is meteorology only."""

    def __init__(self, encoder, in_channels=20, base=16, mask_fraction=0.5):
        super().__init__()
        self.encoder = encoder
        self.decoder = HighResDecoder(
            encoder.latent_ch, base=base, out_channels=in_channels)
        if not 0.0 < mask_fraction < 1.0:
            raise ValueError("mask_fraction must lie in (0, 1)")
        self.mask_fraction = float(mask_fraction)

    def make_mask(self, x):
        batch, _, height, width = x.shape
        if height % 4 or width % 4:
            raise ValueError("MeteorologyMAE input must be divisible by 4")
        gh, gw = height // 4, width // 4
        n_mask = max(1, min(gh * gw - 1, round(self.mask_fraction * gh * gw)))
        scores = torch.rand(batch, gh * gw, device=x.device)
        chosen = scores.topk(n_mask, dim=1).indices
        mask = torch.zeros(batch, gh * gw, device=x.device, dtype=x.dtype)
        mask.scatter_(1, chosen, 1.0)
        mask = mask.view(batch, 1, gh, gw)
        return F.interpolate(mask, size=(height, width), mode="nearest")

    def forward(self, x):
        mask = self.make_mask(x)
        # Query/static channels remain visible. Reconstructing them would turn
        # the baseline into an easy coordinate-inpainting task rather than a
        # meteorology representation objective.
        masked = x.clone()
        masked[:, 1:17] = masked[:, 1:17] * (1.0 - mask)
        latent, skips = self.encoder(masked)
        reconstruction = self.decoder(latent, skips)
        return reconstruction, mask

    @staticmethod
    def loss(reconstruction, target, mask):
        if target.shape[1] != 20 or reconstruction.shape != target.shape:
            raise ValueError("MeteorologyMAE requires matching 20-channel tensors")
        error = (reconstruction[:, 1:17] - target[:, 1:17]).square()
        return (error * mask).sum() / (mask.sum() * 16).clamp_min(1)


class MeteorologyTubularMAE(MeteorologyMAE):
    """Met-MAE control whose mask is a straight *tube* through the receptor.

    This is the structural control for the L-JEPA causality audit: the mask
    is a contiguous corridor (same coarse block count and tube geometry as
    the Lagrangian arm) but its orientation is a per-sample random heading,
    NOT the wind-inflow direction.  If a micro-finetune advantage of the
    true input-wind L-JEPA arm persists over this control, the advantage is
    attributable to masking along the real inflow rather than to "masking
    any equal-length tube through the receptor" (see pre-registration).

    mask_fraction is interpreted on the coarse 4x-downsampled grid exactly
    like MeteorologyMAE so the two controls mask comparable areas.
    """

    def __init__(self, encoder, in_channels=20, base=16, mask_fraction=0.5,
                 tube_radius=1, seed=0):
        super().__init__(encoder, in_channels=in_channels, base=base,
                         mask_fraction=mask_fraction)
        self.tube_radius = int(tube_radius)          # coarse-grid half-width
        self._rng = np.random.default_rng(seed)

    def make_mask(self, x):
        batch, _, height, width = x.shape
        if height % 4 or width % 4:
            raise ValueError("MeteorologyTubularMAE input must be divisible by 4")
        gh, gw = height // 4, width // 4
        n_mask = max(1, min(gh * gw - 1,
                           round(self.mask_fraction * gh * gw)))
        device = x.device
        # per-sample random heading through the coarse-grid centre
        thetas = self._rng.uniform(0.0, 2.0 * np.pi, size=batch)
        coarse = np.zeros((batch, gh, gw), dtype=np.float64)
        cy, cx = gh / 2.0, gw / 2.0
        r = np.hypot(gh, gw) / 2.0 + self.tube_radius  # cover the domain
        for b in range(batch):
            t = thetas[b]
            dx, dy = np.cos(t), np.sin(t)
            yy, xx = np.mgrid[0:gh, 0:gw]
            # signed distance from the receptor-centre line
            dist = np.abs((xx - cx) * dy - (yy - cy) * dx)
            on_tube = dist <= self.tube_radius + 0.5
            # keep only a mask_fraction-length window along the ray so the
            # masked cell count matches MeteorologyMAE; window is centred
            # on the receptor so the tube always passes through the centre
            along = (xx - cx) * dx + (yy - cy) * dy
            half = np.sqrt(n_mask / max(1.0, on_tube.sum() / max(1, gh * gw)))
            window = np.abs(along) <= (gh * half) / 2.0 * 0.0 + 1e9
            sel = on_tube & window
            coarse[b][sel] = 1.0
        # enforce the same masked-cell budget as the random-block control
        flat = coarse.reshape(batch, -1)
        budget = n_mask
        for b in range(batch):
            idx = np.where(flat[b] > 0)[0]
            if len(idx) > budget:
                keep = idx[:budget]
                flat[b][idx[budget:]] = 0.0
        mask = coarse.reshape(batch, 1, gh, gw)
        mask = torch.from_numpy(mask).to(device=device, dtype=x.dtype)
        return F.interpolate(mask, size=(height, width), mode="nearest")


class SpectralConv2d(nn.Module):
    """Truncated Fourier convolution used by FNO2d."""

    def __init__(self, in_channels, out_channels, modes=12):
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.modes = int(modes)
        scale = 1.0 / max(1, in_channels * out_channels)
        shape = (in_channels, out_channels, self.modes, self.modes)
        self.weight_positive = nn.Parameter(
            scale * torch.randn(*shape, dtype=torch.cfloat))
        self.weight_negative = nn.Parameter(
            scale * torch.randn(*shape, dtype=torch.cfloat))

    @staticmethod
    def multiply(values, weights):
        return torch.einsum("bixy,ioxy->boxy", values, weights)

    def forward(self, x):
        batch, _, height, width = x.shape
        if min(height, width) < 2:
            raise ValueError("SpectralConv2d spatial dimensions must be at least 2")
        transformed = torch.fft.rfft2(x, norm="ortho")
        output = torch.zeros(
            batch, self.out_channels, height, width // 2 + 1,
            dtype=transformed.dtype, device=x.device)
        modes_y = min(self.modes, height // 2)
        modes_x = min(self.modes, width // 2 + 1)
        output[:, :, :modes_y, :modes_x] = self.multiply(
            transformed[:, :, :modes_y, :modes_x],
            self.weight_positive[:, :, :modes_y, :modes_x])
        output[:, :, -modes_y:, :modes_x] = self.multiply(
            transformed[:, :, -modes_y:, :modes_x],
            self.weight_negative[:, :, :modes_y, :modes_x])
        return torch.fft.irfft2(
            output, s=(height, width), norm="ortho")


class FNOBlock(nn.Module):
    def __init__(self, width, modes):
        super().__init__()
        self.spectral = SpectralConv2d(width, width, modes)
        self.local = nn.Conv2d(width, width, 1)
        self.norm = nn.GroupNorm(1, width)

    def forward(self, x):
        return F.gelu(self.norm(self.spectral(x) + self.local(x)))


class FNO2d(nn.Module):
    """Fourier Neural Operator baseline for full-field footprint emulation."""

    def __init__(self, in_channels=20, width=32, modes=12, depth=4):
        super().__init__()
        self.lift = nn.Conv2d(in_channels, width, 1)
        self.blocks = nn.ModuleList(
            [FNOBlock(width, modes) for _ in range(depth)])
        self.projection = nn.Sequential(
            nn.Conv2d(width, width, 1), nn.GELU(), nn.Conv2d(width, 1, 1))

    def forward(self, x):
        x = self.lift(x)
        for block in self.blocks:
            x = block(x)
        return self.projection(x)


class TemporalUNet(nn.Module):
    """Explicitly encode the four meteorological times before spatial U-Net."""

    def __init__(self, in_channels=20, base=16, out_channels=1):
        super().__init__()
        if in_channels != 20:
            raise ValueError("TemporalUNet requires the 20-channel schema-v5 layout")
        self.temporal = nn.Sequential(
            nn.Conv3d(4, base, 3, padding=1),
            nn.BatchNorm3d(base), nn.GELU(),
            nn.Conv3d(base, base, 3, padding=1),
            nn.BatchNorm3d(base), nn.GELU(),
        )
        self.time_logits = nn.Parameter(torch.zeros(4))
        self.spatial = HighResPlainUNet(
            in_channels=base + 4, base=base, out_channels=out_channels)

    def forward(self, x):
        batch, _, height, width = x.shape
        meteorology = x[:, 1:17].reshape(batch, 4, 4, height, width)
        meteorology = meteorology.permute(0, 2, 1, 3, 4)
        encoded = self.temporal(meteorology)
        weights = torch.softmax(self.time_logits, dim=0)
        encoded = torch.einsum("bcthw,t->bchw", encoded, weights)
        static = torch.cat([x[:, :1], x[:, 17:20]], dim=1)
        return self.spatial(torch.cat([encoded, static], dim=1))


class JEPAPredictor(nn.Module):
    """Predict full latent map from context latent map (25x25 at 400x400)."""

    def __init__(self, latent_ch, hidden=128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(latent_ch, hidden, 3, padding=1),
            nn.BatchNorm2d(hidden),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, hidden, 3, padding=1),
            nn.BatchNorm2d(hidden),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, latent_ch, 3, padding=1),
        )

    def forward(self, ctx):
        return self.net(ctx)


class JEPA(nn.Module):
    """Masked latent-space prediction with an EMA target encoder (I-JEPA style).

    context encoder sees the block-masked input; the predictor must reconstruct
    the latent features of the masked blocks, supervised by an EMA target
    encoder that sees the full input.  Collapse is prevented by a VISReg-
    (default) or SIGReg-style regularizer applied to the ONLINE context
    latent -- which carries gradient (see audit: the previous VICReg terms on
    the detached target contributed zero gradient).
    """

    def __init__(self, encoder, latent_ch, mask_grid=None, ema_decay=0.996,
                 reg_mode="visreg", reg_slices=256,
                 mask_frac_min=0.3, mask_frac_max=0.6):
        super().__init__()
        self.online = encoder
        self.target = copy.deepcopy(encoder)
        for p in self.target.parameters():
            p.requires_grad_(False)
        self.predictor = JEPAPredictor(latent_ch)
        self.mask_grid = mask_grid
        self.ema_decay = ema_decay
        self.latent_ch = latent_ch
        assert reg_mode in ("visreg", "sigreg")
        self.reg_mode = reg_mode
        self.reg_slices = reg_slices
        if not (0.0 < mask_frac_min <= mask_frac_max < 1.0):
            raise ValueError("mask fractions must satisfy 0 < min <= max < 1")
        self.mask_frac_min = mask_frac_min
        self.mask_frac_max = mask_frac_max

    @torch.no_grad()
    def _ema_update(self):
        with torch.no_grad():
            for po, pt in zip(self.online.parameters(), self.target.parameters()):
                pt.data.mul_(self.ema_decay).add_(po.data, alpha=1 - self.ema_decay)
            for bo, bt in zip(self.online.buffers(), self.target.buffers()):
                bt.data.copy_(bo.data)

    def make_mask(self, x):
        """Random block mask over the latent grid; also zero the input blocks.

        Returns (masked_x, mask01) where mask01 has 1 at masked latent cells.
        """
        B, _, H, W = x.shape
        if H % 16 or W % 16:
            raise ValueError(f"input spatial shape {(H, W)} must be divisible by 16")
        if self.mask_grid is not None:
            gh = gw = self.mask_grid
        else:
            gh, gw = H // 16, W // 16
        if min(gh, gw) < 2:
            raise ValueError("JEPA requires at least a 2x2 latent grid")
        mask = torch.zeros(B, 1, gh, gw, dtype=x.dtype, device=x.device)
        for i in range(B):
            area_frac = torch.empty((), device=x.device).uniform_(
                self.mask_frac_min, self.mask_frac_max).item()
            side = int(round((area_frac ** 0.5) * min(gh, gw)))
            side = min(max(side, 1), min(gh, gw) - 1)
            r0 = int(torch.randint(0, gh - side + 1, (), device=x.device))
            c0 = int(torch.randint(0, gw - side + 1, (), device=x.device))
            mask[i, :, r0:r0 + side, c0:c0 + side] = 1.0

        masked_x = x.clone()
        m = F.interpolate(mask, size=(H, W), mode="nearest")
        masked_x = masked_x * (1.0 - m)     # zero masked input regions
        return masked_x, mask

    def forward(self, x):
        masked_x, mask = self.make_mask(x)
        ctx = self.online(masked_x)[0]               # (B, C, g, g)  [has grad]
        pred = self.predictor(ctx)                   # (B, C, g, g)
        # The EMA target is a deterministic teacher: BatchNorm running stats
        # must not drift during target inference (same protocol as
        # LagrangianJEPA.forward).
        target_training = self.target.training
        self.target.eval()
        with torch.no_grad():
            tgt = self.target(x)[0].detach()
        self.target.train(target_training)
        if pred.shape[-2:] != mask.shape[-2:]:
            raise RuntimeError(
                f"latent shape {pred.shape[-2:]} != mask shape {mask.shape[-2:]}")
        return pred, tgt, mask, ctx

    def loss(self, pred, tgt, mask, ctx, reg_w=0.5):
        """smooth L1 on normalized features of masked cells + anti-collapse reg.

        The regularizer (VISReg by default, SIGReg optional) is applied to the
        ONLINE context latent cells, which carry gradient -- fixing the prior
        dead VICReg terms that were computed on the detached EMA target.
        """
        # normalize each latent cell to unit L2 over channels (I-JEPA)
        pn = F.normalize(pred, dim=1)
        tn = F.normalize(tgt, dim=1)
        m = mask                                    # (B,1,g,g)
        cell_loss = F.smooth_l1_loss(pn, tn, reduction="none").mean(dim=1)
        l1 = (cell_loss * m[:, 0]).sum() / (m.sum() + 1e-6)

        # flatten the ONLINE context latent to (N, C) embeddings for the reg
        c = ctx.permute(0, 2, 3, 1)                 # (B, g, g, C)
        z = c.reshape(-1, c.shape[-1])              # (B*g*g, C), has gradient

        if self.reg_mode == "visreg":
            scale, shape, center = visreg_reg(z, n_slices=self.reg_slices)
            reg = scale + shape + center
        else:
            reg = sigreg_reg(z, n_slices=self.reg_slices)

        return l1 + reg_w * reg
