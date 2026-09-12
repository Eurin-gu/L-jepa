#!/usr/bin/env python3
"""核实 met_tubular 与 met_mae 的掩码面积是否对等（只读，不改仓库代码）。

复刻 models.py:373-411 的 coarse 掩码逻辑，统计实际被遮格子数。
"""
import numpy as np

H = W = 128          # 本项目正式数据集输入尺寸
gh, gw = H // 4, W // 4
tube_radius = 1
mask_fraction = 0.5
n_mask = max(1, min(gh * gw - 1, round(mask_fraction * gh * gw)))

print("coarse grid      : %dx%d = %d cells" % (gh, gw, gh * gw))
print("n_mask (budget)  : %d  (= %.1f%% of coarse cells)"
      % (n_mask, 100.0 * n_mask / (gh * gw)))
print()

rng = np.random.default_rng(0)
counts = []
for b in range(16):
    t = rng.uniform(0.0, 2.0 * np.pi)
    cy, cx = gh / 2.0, gw / 2.0
    r = np.hypot(gh, gw) / 2.0 + tube_radius
    dx, dy = np.cos(t), np.sin(t)
    yy, xx = np.mgrid[0:gh, 0:gw]
    dist = np.abs((xx - cx) * dy - (yy - cy) * dx)
    on_tube = dist <= tube_radius + 0.5
    along = (xx - cx) * dx + (yy - cy) * dy
    half = np.sqrt(n_mask / max(1.0, on_tube.sum() / max(1, gh * gw)))
    # ---- 仓库原样：window 被 * 0.0 置为恒真 ----
    window_repo = np.abs(along) <= (gh * half) / 2.0 * 0.0 + 1e9
    sel_repo = on_tube & window_repo
    coarse_repo = np.zeros((gh, gw))
    coarse_repo[sel_repo] = 1.0
    # 预算裁剪（仓库第 404-408 行）
    flat = coarse_repo.reshape(-1)
    idx = np.where(flat > 0)[0]
    if len(idx) > n_mask:
        flat[idx[n_mask:]] = 0.0
        clipped = True
    else:
        clipped = False
    counts.append((int(coarse_repo.reshape(-1).sum()), clipped,
                   int(on_tube.sum()), float(half)))

area = np.array([c[0] for c in counts], dtype=float)
clipped = any(c[1] for c in counts)
on_tube_n = np.mean([c[2] for c in counts])
half_v = np.mean([c[3] for c in counts])

print("window 是否恒真   : %s   (因 `* 0.0 + 1e9`)" % (not clipped))
print("half 计算值       : %.1f   (域内 along 最大仅 %.1f)"
      % (half_v, np.hypot(gh, gw) / 2.0))
print("on_tube 格子数    : %.1f" % on_tube_n)
print("预算裁剪是否触发  : %s" % clipped)
print()
print("met_tubular 实遮  : %.1f ± %.1f 格  = %.1f%% 面积"
      % (area.mean(), area.std(), 100.0 * area.mean() / (gh * gw)))
print("met_mae 应遮      : %d 格  = %.1f%% 面积"
      % (n_mask, 100.0 * n_mask / (gh * gw)))
print("比例 tubular/mae  : %.3f" % (area.mean() / n_mask))
print()
print("结论: %s" % (
    "掩码预算对等" if abs(area.mean() - n_mask) / n_mask < 0.05
    else "掩码预算【不对等】，met_tubular 遮的面积显著偏离 met_mae"))
