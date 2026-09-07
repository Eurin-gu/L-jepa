# NOISE FLOOR (self-baseline) — 首个数据点
日期: SoCal 2017-11-11 (HRRR, 30 共享受体, 24h back, 4km grid)
- split-half r(p500a vs p500b): median 0.9869, mean 0.9854
- split-half relRMSE (相对均值): median 0.340
- pooled(p1000-like) vs p250 r: median 0.9864
含义: 该标签体系粒子噪声 ~1.5% 相关性损失；模型逐样本 r 上限应以此标尺归一化比较（v2.3 协议）。
注: relRMSE ~0.34 相对大(足迹重尾), 后续补 log 域/归一化三版本指标。
manifest: /root/auto_run/manifest_so_sb_a2.csv, _b2.csv; 算法: /root/noise_floor.py