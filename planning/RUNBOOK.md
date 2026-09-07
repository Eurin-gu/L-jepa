# Lagrangian-JEPA 严格正式线本地扩展 Runbook（2026-09-04 版）

## 0. 决策（用户确认）
- 路线：**严格 STILT 正式线扩展**（≤约3000 新增样本）
- 气象源：**只用 2016-2017 HRRR**（缺档日期跳过，不换 ERA5/GDAS）
- 受体：真实逐日 OCO-2 maximin（LA 框 32-35N, -119..-116W, seed 20260822, n 可选 120/250/1000）
- 存储：本地数据盘 D:\lagrangian-jepa-cn（已清理 SolidWorks，空闲 ~143GB）
- 执行：本机 Windows 11；训练用 GPU(RTX 5070 Laptop, Blackwell sm_120, 需 torch cu128)；STILT 引擎按调研结果走 WSL2 或等价 Linux 工具链（待确认）
- 铁律（文档审计）：气象源与输入物理对应；切换气象源必须换 tag+新 manifest；受体不得日期平移/复用；formal_test 一次性消费。

## 1. 项目事实（已核实）
- OSS 桶 lagrangian-jepa-cn @ oss-cn-beijing；428GB/25.1万对象；清单 D:\lagrangian-jepa-cn\mirror\manifest.csv
- 代码仓库：server_backup_20260830/footnet_jepa/（已镜像到 mirror 下，144 文件 76MB；含 code_sync.tar.gz 40MB）
- 正式线 2016-17：production_v1.json 定义 train 11 日期 + val 2 + formal_test 5（受体 n120 maxmin，train p250 / val,test p1000）
- 正式数据产品：prod_all_v3(1680)/v4(1800)/v5(1920) 样本（schema v5, label_source=stilt_xstilt, grid128/4km, 20通道）
- 桶内 per-date 产物（hrrr_stilt_production_v1/<role>/<date>/）：hourly_arl/a{ts}_f00/data.arl(381MB×26-27h) + merged/ + model_features/ + receptors.csv + stilt_logs/<n> + meteorology_manifest.json 等；train 日期保留全量(~24GB/日), formal_test 仅 outputs-only(~0.04GB)
- 真实受体表（19 日期）已在 D:\footexp_data\stilt_receptors_v1\：receptors_YYYYMMDD_n120_maximin.csv(+provenance)
- OCO-2 Lite 本地档：D:\co2_data\nasa\oco2_l2_lite_fp_11.2r（918 文件，2014-12-31~2017-11-20 逐日，命名 oco2_LtCO2_YYMMDD_B11210Ar_*.nc4）
- make_receptors.py 配方：bbox lat[32,35] lon[-119,-116]; qc_flag==0; 350<xco2<450; maximin seed=20260822 time_weight=1; zagl=5; 输出 run_time/lati/long/zagl + provenance

## 2. 关键系统事实
- 系统时钟比真实 UTC 慢 8h（28800s）；所有 OSS 签名脚本必须做偏移补偿（http_date 补丁），见 oss_work 脚本模式
- 本地 GPU：NVIDIA GeForce RTX 5070 Laptop, 8GB, driver 592.07 → CUDA 12.8+; torch 需 cu128 wheel (sm_120)
- CPU 24 核；内存约 16GB 可用/32GB 总（待精确）；D 盘 143GB 空闲
- Python：系统 3.9.13；D:\lagrangian-jepa-cn\py311 = 目标 venv(torch cu128)；工作 venv C:\Users\Yuki\Desktop\.venv-oss(oss2/netCDF4)
- 无 WSL（需启用）；F:\stilt = uataq/stilt 源码；D:\msys64 存在（可备 gfortran?）

## 3. 阶段计划（状态）
- [x] P0 侦察：桶结构/代码/文档/生产配方/受体/CO2档/磁盘清理
- [x] P0 下载代码+文档（76MB → mirror）
- [x] P0 清理 D 盘（+46.9GB）
- [ ] P1 本机环境：py311 venv + torch cu128 + netCDF4/xarray 等（后台 pwsh-2 进行中）→ GPU smoke
- [ ] P1 跑通 footnet_jepa smoke（socal_pilot HRRR_lite 2024 + data_builder/train --smoke）
- [ ] P2 OCO-2 日期筛选（2016-17 逐日有 LA 框候选者）→ 与 HRRR 档交叉 → 选 ≤25 新日期
- [ ] P2 生成新日期受体表（make_receptors.py, n120/n250）
- [ ] P3 OSS 选择性下载（正式 data/ 产品用于对照/复现；具体清单待定）
- [ ] P4 工具链：HRRR 2016-17 grib 获取(存档研究待回)、hrrrv12arl_v2 编译(Windows/WSL)、merge_arl_met、validate
- [ ] P5 STILT 标签生成（run_batch.py, p250 train / p1000 val·test）→ foot.nc/traj.rds
- [ ] P5 data_builder/merge → schema v5 npy(+meta+fingerprint)
- [ ] P6 train_stilt_strict 正式协议训练（7-arm×5-seed 视显存 8GB 调整 batch/fp16）→ 评估
- [ ] P7 结果整理（results/<run-id>/，正式 test 一次性消费）

## 4. 关键命令备忘
- OSS 下载：python oss_download.py <sel.json> <root> <workers>（跳过已存在，8线程）
- 受体：python stilt_pipeline/make_receptors.py --lite oco2_LtCO2_<YYMMDD>_*.nc4 --n 120 --seed 20260822 --out D:\lagrangian-jepa-cn\data\receptors\receptors_<date>_n120_maximin.csv（默认 bbox/zagl 已对齐正式配方）
- 后续 STILT 命令以 stilt_pipeline/README.md 为准（GRIB→ARL→merge→validate→run_batch）

## 5. 开放问题
- HRRR 2016-17 存档端点/覆盖（子代理调研中）
- Windows 跑 STILT+hrrrv12arl_v2 的路径（子代理调研中）
- formal_test 新数据集的一次性评估策略与既有 formal_test manifest 关系（沿用既有 test 日期 or 新日期重新定义——倾向沿用既有 5 正式测试日期避免污染）
- 显存 8GB 下 7-arm×5-seed 训练的可行性（batch/混合精度/序列化）
