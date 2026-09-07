# WSL2 + ERA5/HRRR → STILT 执行手册（准备就绪，等待 WSL2 安装）

## 前置（用户已做/待做）
- [ ] 管理员 PowerShell: wsl --install -d Ubuntu-24.04 （首次可能需重启）
- [ ] wsl --set-default Ubuntu-24.04；设置默认用户密码
- [ ] 提供 ERA5 CDS key（uid:key）用于 2015-17 全球 ERA5

## 已就绪资产（Windows 侧）
- 代码: D:\lagrangian-jepa-cn\mirror\server_backup_20260830\footnet_jepa\（含 stilt_pipeline/*.py）
- STILT 引擎: D:\lagrangian-jepa-cn\toolchain\server_backup_20260830\stilt\（bin/linux_x64/hycs_std、r/、Dockerfile）
- 转换器源码: D:\lagrangian-jepa-cn\toolchain\server_backup_20260830\hysplit_data2arl\（era52arl、hrrr2arl/hrrrv12arl_v2.f、arw2arl、Makefile.inc.gfortran）
- ERA5 转换样例配置: toolchain\...\era5\20240401\{era52arl.cfg, ERA52ARL.MESSAGE, arldata.cfg}
- 受体表: D:\lagrangian-jepa-cn\data\receptors_v2\<region>\receptors_<YYYYMMDD>_n120_maximin.csv (35 张)

## WSL 内初始化（Windows pwsh 驱动：wsl -d Ubuntu-24.04 -- bash -lc "..."）
```bash
sudo apt update && sudo apt install -y build-essential gfortran git wget curl netcdf-bin libnetcdf-dev libnetcdf-fortran-dev libgdal-dev gdal-bin libssl-dev libxml2-dev libhdf5-serial-dev r-base r-base-dev
Rscript -e "install.packages(c('devtools','remotes','ncdf4','dplyr','raster','lubridate'), repos='https://cloud.r-project.org')"
mkdir -p ~/work/stilt ~/work/footnet ~/met ~/era5_grib ~/arl_work ~/stilt_out
cp -a /mnt/d/lagrangian-jepa-cn/toolchain/server_backup_20260830/stilt/. ~/work/stilt/
cp -a /mnt/d/lagrangian-jepa-cn/mirror/server_backup_20260830/footnet_jepa/. ~/work/footnet/
cp -a /mnt/d/lagrangian-jepa-cn/toolchain/server_backup_20260830/hysplit_data2arl/. ~/work/hysplit_data2arl/
cd ~/work/hysplit_data2arl/era52arl && make -f Makefile   # 依赖按 COMPILE.txt/README；gfortran>=10 加 -fallow-argument-mismatch
chmod +x ~/work/stilt/bin/linux_x64/* ~/work/stilt/exe/*
```

## 气象获取
- CONUS 对照臂(SoCal HRRR 2016-17)：AWS/GCS hrrr.YYYYMMDD/conus/hrrr.tHHZ.wrfprsf00.grib2(.idx)，342-370MB/h；按受体窗口取 26-27 个小时次 → hrrrv12arl_v2 → merge → ~/met/hrrr.<date>.arl + make_met_links 日链接
- 全球主数据(ERA5 0.25°)：cdsapi 下载日文件（level/var 子集同 era5/20240401 样例）→ era52arl(era52arl.cfg) → ~/met/<YYYYMMDD>.era5
- 逐(区域,日期)处理完即删中间 grib，仅留 ARL（日 3-5GB 周转）

## STILT 标签
```bash
cd ~/work/footnet/stilt_pipeline
python3 run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/<region>/receptors_<date>_n120_maximin.csv --stilt-wd ~/work/stilt --met ~/met --jobs 24 --numpar 250 --tag era5-v1-<region>-<date> --half-km 256 --res 0.04 --hours -24
# 输出 ~/work/stilt/out/by-id/<tag>_*/foot.nc + traj.rds；留出区用 --numpar 1000
```
（正式协议：train p250 / validation & holdout p1000；同周期气象对齐 + manifest/hash 溯源，参照 train_stilt_strict.py 契约）

## data_builder → schema v5
- 特征：从同一批 GRIB/ERA5 提 U10M/V10M/PBLH/PRSS 快照（era5_features.py 模式，source-aligned sha）→ npz 缓存
- 标签：foot.nc + traj.rds（stilt_io.py 保守重采样 → 4km/128×128 受体中心窗）
- data_builder.py / merge → x.npy/y.npy/meta.json(contract fingerprint v5, physical) + traj.npy

## 训练/评估
- torch cu128 (Blackwell) venv D:\lagrangian-jepa-cn\py311
- train_stilt_strict.py（scratch/e_jepa/l_jepa/met_mae/unetpp/fno × seeds；8GB 显存调 batch/fp16）
- 留出区(co_front_range)评估：预测足迹 vs 全量 STILT p1000 参考（Pearson r/RMSE/JS/Overlap/Mass/center/peak km；逐样本）
- （二期）XCO2 正向模拟：footprint×排放(SoCal Hestia / ODIAC) vs OCO-2 观测

## 待办
- [ ] WSL2 安装（用户）
- [ ] ERA5 CDS key（用户）
- [ ] 本机 torch 环境 smoke（进行中）
- [ ] GenGHG 下载完成校验（进行中）