#!/usr/bin/env python3
"""统计各臂实际参数量，量化 capacity_protocol 偏差（只读，不改仓库代码）。

配置对齐 formal_v5_mass1.json 的 experiment_config: base=8, in_channels=20
"""
import sys, os

# 平台无关：优先用当前工作目录，其次尝试两侧已知仓库路径
_HERE = os.path.dirname(os.path.abspath(__file__))
_CANDIDATES = [
    os.getcwd(),
    os.path.join(_HERE, "..", "mirror", "server_backup_20260830", "footnet_jepa"),
    "/mnt/d/lagrangian-jepa-cn/mirror/server_backup_20260830/footnet_jepa",
]
for _c in _CANDIDATES:
    _c = os.path.abspath(_c)
    if os.path.isfile(os.path.join(_c, "models.py")):
        sys.path.insert(0, _c)
        break
else:
    raise SystemExit("找不到 models.py，请在 footnet_jepa 目录下运行本脚本")

import torch
from models import (HighResEncoder, HighResPlainUNet, FNO2d,
                    NestedUNetSmall, TemporalUNet)

IN_CH = 20
BASE = 8            # formal_v5_mass1 实验配置

def n_params(m):
    return sum(p.numel() for p in m.parameters())

rows = []

# --- 共享主干四臂：scratch / e_jepa / l_jepa / met_mae ---
# 监督阶段都是 HighResPlainUNet(base=8)
shared = HighResPlainUNet(in_channels=IN_CH, base=BASE, out_channels=1)
rows.append(("scratch/e_jepa/l_jepa/met_mae", "HighResPlainUNet(base=8)",
             n_params(shared)))

# 预训练阶段的额外模块（只在预训练时用，不进监督模型）
enc = HighResEncoder(in_channels=IN_CH, base=BASE)
rows.append(("  └ 预训练 encoder(仅自监督阶段)", "HighResEncoder(base=8)",
             n_params(enc)))

# --- 独立架构臂 ---
# train_stilt_strict.py:466-469  width=max(8, base*4)=32, modes=12, depth=4
fno = FNO2d(in_channels=IN_CH, width=max(8, BASE * 4), modes=12, depth=4)
rows.append(("fno", "FNO2d(width=32,modes=12,depth=4)", n_params(fno)))

unetpp = NestedUNetSmall(num_classes=1, input_channels=IN_CH,
                         nb_filter=[BASE * 2 ** i for i in range(5)])
rows.append(("unetpp", "NestedUNetSmall(nb_filter=8..128)", n_params(unetpp)))

tunet = TemporalUNet(in_channels=IN_CH, base=BASE, out_channels=1)
rows.append(("temporal_unet", "TemporalUNet(base=8)", n_params(tunet)))

base_n = n_params(shared)
print("配置: in_channels=%d, base=%d  (对齐 formal_v5_mass1)" % (IN_CH, BASE))
print("=" * 84)
print("%-38s %-38s %12s" % ("臂", "架构", "参数量"))
print("-" * 84)
for name, arch, n in rows:
    ratio = n / base_n
    flag = "" if abs(ratio - 1) < 0.02 else ("  ← %.2fx" % ratio)
    print("%-38s %-38s %12s%s" % (name, arch, format(n, ","), flag))
print("=" * 84)

print()
print("FNO / 共享主干 = %.2fx" % (n_params(fno) / base_n))
print("unetpp / 共享主干 = %.2fx" % (n_params(unetpp) / base_n))
print("temporal_unet / 共享主干 = %.2fx" % (n_params(tunet) / base_n))
print()

# FNO 内部构成拆解
print("--- FNO2d 参数构成拆解 ---")
for name, mod in fno.named_children():
    print("  %-14s %12s" % (name, format(n_params(mod), ",")))
sp = n_params(fno.blocks[0].spectral)
lc = n_params(fno.blocks[0].local)
nm = n_params(fno.blocks[0].norm)
print("  单个 FNOBlock 内部:")
print("    spectral(复数权重)  %12s   ← 复数张量，实参数量为 2x" % format(sp, ","))
print("    local(1x1 conv)     %12s" % format(lc, ","))
print("    norm(GroupNorm)     %12s" % format(nm, ","))
print()
print("  SpectralConv2d 权重形状: %s (cfloat)"
      % (tuple(fno.blocks[0].spectral.weight_positive.shape),))
print("  注意: cfloat 每个元素含实部+虚部，PyTorch numel() 计为 1，")
print("        但实际可训练标量是其 2 倍。")
print("  FNO 实际可训练标量 = %s"
      % format(n_params(fno) + sp * 4, ","))
