# 阶段进展汇报（goal round 1）

## ✅ 本轮完成
- 35 张试点受体表（6 区 × 120，QC+maximin+provenance）→ D:\lagrangian-jepa-cn\data\receptors_v2\
- STILT 引擎 + data2arl 源码镜像（367MB）→ D:\lagrangian-jepa-cn\toolchain\（桶里就有预编译 hycs_std linux 二进制 + era52arl/hrrrv12arl_v2.f，WSL 里免自编 HYSPLIT）
- 正式基线数据 4.9GB（prod_all_v5/strict_2024_all/merged 子集）→ D:\lagrangian-jepa-cn\data\
- 调研存档（HRRR 存档 + Windows/STILT 方案）与引擎资产清单 → planning\*.md
- 连通性实测：AWS/GCS HRRR idx=200；ERA5 CDS=202 可达

## 🔄 后台进行
- GenGHG 36GB 下载（~1.4GB/6min → 预计还需 ~2h）
- 本机 py311+PyTorch cu128 环境（torch 大包下载中）

## ⛔ 需要你配合的两件事（关键路径）
1. **安装 WSL2 Ubuntu**（STILT 官方仅支持 Linux；这是跑真实 STILT 的唯一路径）：管理员 PowerShell 里运行
   ```powershell
   wsl --install -d Ubuntu-24.04
   ```
   首次可能需要重启电脑，装完回来告诉我。我会自动完成：环境初始化→编译转换器→单案例 STILT 验证。
2. **ERA5 CDS API key**（主气象源 ERA5 0.25° 2015-17 下载必需）：到 https://cds.climate.copernicus.eu 注册后把 key（形如 `uid:xxxx-xxxx`）发我，我配置 cdsapi。

## ⏭️ 下一步（环境就绪后自动继续）
- GPU smoke 验证（socal_pilot 2024 HRRR-lite 现成数据）
- GenGHG 校验与清单
- WSL/ERA5 就绪后：逐(区域,日期) STILT 产标签 → schema v5 数据集 → 训练