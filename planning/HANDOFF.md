# 交接文档：Lagrangian-JEPA 全球多地形数据集 + STILT + 本地GPU训练
> 写给接手 agent。以下全部为已核实事实；接手后先按第6节核对现状，再按第7节续跑。

## 1. 项目是什么
用户（研究者）在做大气 CO2 足迹深度学习项目 Lagrangian-JEPA / JEPA-FootNet：给定 气象场+受体(位置/时间)，预测 24h 后向轨迹足迹分布。目标：构建可进论文的全球多地形、真实STILT、带留出区泛化的大数据集，并在本机 RTX5070 上训练。代码仓库在阿里云 OSS 桶 lagrangian-jepa-cn（北京地域）的 server_backup_20260830/footnet_jepa/。

## 2. 用户已锁定的方案（勿偏离，铁律）
- 时间窗 2015-01 ~ 2017-11（本地 OCO-2 lite 逐日全档）
- 区域：训练5区 = so_cal_LA_basin / cent_valley_CA / permian_westTX / po_valley_italy / north_china_plain；留出测试1区 = co_front_range（跨地形泛化）
- 标签：只允许真实 STILT/X-STILT 足迹（禁粒子代理/克隆假数据；文档黑名单 2024_ext_merged 等永不使用）
- 气象源：ERA5 0.25° 全球为主(tag era5-v1)；SoCal 保留原 2016-17 HRRR 正式线(tag hrrr-v1)做对照；混源必须换 tag+新 manifest；受体必须真实逐日 OCO-2
- 受体配方=正式线同款：make_receptors.py --n 120 --seed 20260822（QC flag==0, 350<xco2<450, maximin, zagl=5），输出含 provenance
- 评估：留出区预测足迹 vs 全量 STILT(p1000) 参考（FootNet 式逐样本指标）；二期加真实 XCO2 x 排放正向模拟(SoCal Hestia 先行)
- GenGHG v1.0（48,282 真实 STILT 城市足迹, GFS, 36GB）= 全球城市基准臂，train/val/test 按城市内置
- 节奏：先区试点(每区3-6日约2-4k样本)跑通全链路与留出评估，再扩量

## 3. 机器与环境现状
- Windows 11；GPU RTX 5070 Laptop 8GB（Blackwell sm_120，需 torch cu128）；驱动 592.07（WSL 内 CUDA 直通可用）
- CPU 24 核；内存约32GB；D 盘=数据盘，当前空闲约111GB（GenGHG 还在下，完成后约余 75GB）
- 重要：系统时钟比真实 UTC 慢 8 小时；所有阿里云 OSS 签名脚本必须打 http_date 偏移补丁（模式见 C:/Users/Yuki/Desktop/oss_work 内脚本，偏移实测约28800s）
- 网络：python requests/urllib 正常；curl.exe 与 Invoke-WebRequest 不可靠(别用)；download.pytorch.org 被重置；阿里 pytorch-wheels 限速；清华 TUNA 快
- OSS 访问 venv：C:/Users/Yuki/Desktop/.venv-oss（py3.9+oss2+netCDF4+requests，含时间补丁下载器 oss_download.py）
- WSL2：Ubuntu-24.04（root 免密），apt 系统包+gfortran+eccodes-dev 已装；R 包(ncdf4/dplyr/raster 等)安装状态待核实（可能未完成）

## 4. 已完成资产（均在 D:\lagrangian-jepa-cn 下）
- planning/: 决策与手册(RUNBOOK/PLAN_GLOBAL/WSL_EXECUTION/ENGINE_ASSETS/RESEARCH/ENV_DECISIONS/HANDOFF)
- mirror/: OSS 根镜像（代码 144 文件 + 全桶清单 manifest.csv 251,227 行 key,size,last_modified）
- mirror/.../footnet_jepa/: 代码仓库全量小文件（含 stilt_pipeline 脚本、models/train*/data_builder、results json）
- toolchain/: uataq/stilt 引擎（bin/linux_x64/hycs_std 等预编译 + r/src/permute.so）+ hysplit_data2arl 全套（era52arl、hrrr2arl/hrrrv12arl_v2.f、arw2arl、Makefile.inc.gfortran）+ era5/20240401 转换样例 cfg
- data/receptors_v2/: 35 张受体表（6区x120，标准列 + provenance）
- data/genghg/: GenGHG 已下约25GB/36GB（test 4630 完整；train 部分；val 未下完）——需续下
- data/: 正式基线 prod_all_v5 / strict_2024_all / prod_*_merged / prod_test 单日(5日期)，约5.5GB
- py311/: Windows venv numpy/netCDF4/xarray/pandas + torch2.14 CPU（GPU 版放 WSL 装）

## 5. 关键技术结论（踩坑记录）
- STILT 只支持 Linux：在 WSL2 Ubuntu 跑；用镜像的预编译 hycs_std + permute.so 免 NOAA 注册自编 HYSPLIT
- 转换器编译：era52arl/hrrrv12arl 依赖 eccodes(已装2.34.1) + hysplit metprog/library(需先 make) + Makefile.inc（由 Makefile.inc.gfortran 修改 ECCODES 路径）
- HRRR 2016-17 逐小时 wrfprs f00：AWS noaa-hrrr-bdp-pds / hrrr.YYYYMMDD/conus/hrrr.tHHZ.wrfprsf00.grib2(.idx)，342-370MB/时，支持 Range；Google GCS 同字节镜像
- ERA5 官方 CDS：用户已注册但 API key 未提供；需先同意 single-levels 与 pressure-levels 两个数据集的许可；下载子集按 era52arl.cfg（6气压变量x37层 + 14地表量，单日3-5GB）
- run_batch.py 调 Rscript stilt_cli.r，met_file_format=%Y%m%d，默认半窗256km / res 0.04 / 回溯24h；产物 out/by-id/<tag>_*/foot.nc + traj.rds
- schema v5 = 物理足迹，grid128 / 4km / 20通道；data_builder + stilt_io 重采样；训练 train_stilt_strict.py（7-arm x 5-seed，8GB显存需调 batch/fp16）
- GenGHG 校验通过：x(112,24,24) y(1,192,192)；genghg_loader.load_pt / parse_sample_name 可用；内置按城市留出拆分

## 6. 检查现状（接手第1步）
1. 数 genghg 文件数：目标 48,282（D:\lagrangian-jepa-cn\data\genghg 递归 *.pt）
2. WSL 工具核对：wsl -d Ubuntu-24.04 -u root 进入后检查 gfortran / Rscript / ncdf4 是否可用（缺则重跑 toolchain/wsl_provision_stage1c.sh）
3. nvidia-smi（GPU 正常）

## 7. 立即续跑（幂等，按序）
1. 续下 GenGHG（跳过已有文件）：venv-oss python oss_work/oss_download.py oss_work/sel_genghg.json D:/lagrangian-jepa-cn/data/genghg 32（后台）
2. 完成 WSL 初始化：重跑 toolchain/wsl_provision_stage1c.sh（R 包幂等，清华 CRAN）
3. WSL 内编译转换器：/root/work/hysplit_data2arl 下 cp Makefile.inc.gfortran Makefile.inc 并配 ECCODES 路径；make -C metprog/library；make -C era52arl；make -C hrrr2arl（逐步排错）
4. 单案例端到端（SoCal HRRR，无需 CDS）：取 data/receptors_v2/so_cal_LA_basin 一个日期(如 20160807) 前2-5个受体 → AWS 拉该受体窗口26-27个 wrfprs f00 → hrrrv12arl_v2 转 ARL → merge_arl_met → run_batch --jobs 少量 --numpar 250 → 验证 foot.nc/traj.rds 非空
5. 验证通过后按 (区域,日期) 队列批量：CONUS 4 区(LA/谷地/德州/科罗拉多)用 HRRR；IT/CN 两区等 CDS key 用 ERA5
6. 组 schema v5 数据集 → 留出区评估 → 本地 GPU(WSL torch cu128) 训练

## 8. 等待用户的唯一输入
- ERA5 CDS API key（uid:key 格式）：拿到后在 WSL 配 ~/.cdsapirc + pip install cdsapi；用于 po_valley_italy 与 north_china_plain 两区。美国四区不依赖。

## 9. 常用命令/路径
- OSS 下载器：oss_work/oss_download.py <sel.json> <目标根> <workers>（跳过已存在，时间补丁内置）
- OSS 全桶清单：mirror/manifest.csv
- 受体：data/receptors_v2/<区>/receptors_<YYYYMMDD>_n120_maximin.csv（新日期用 make_receptors.py 现成配方）
- Windows 数据处理 python：D:\lagrangian-jepa-cn\py311\Scripts\python.exe
- 工作脚本目录：C:\Users\Yuki\Desktop\oss_work\
- 先读 planning/PLAN_GLOBAL.md 与 planning/WSL_EXECUTION.md