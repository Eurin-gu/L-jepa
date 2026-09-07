# RESEARCH: 2016-17 HRRR 存档 & Windows STILT 工具链（子代理 2026-09-04 实测）

## HRRR 2016-2017 逐小时 wrfprs f00 GRIB2（实测存在）
- AWS NODD: https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.YYYYMMDD/conus/hrrr.tHHZ.wrfprsf00.grib2(+.idx)；s3://noaa-hrrr-bdp-pds 匿名可读
- Google 镜像同字节: https://storage.googleapis.com/high-resolution-rapid-refresh/hrrr.YYYYMMDD/conus/hrrr.tHHZ.wrfprsf00.grib2(.idx)
- 抽查 13 日期 + 2016-01-01 全天 24 时次均存在；缺日需按日盘点（24 个 idx/日）
- 体积: 单文件 342-370MB；一天 24 时次 ≈ 8-9GB → 按日期拉 26-27 个小时次即转即删
- NOMADS 仅滚动(2016 实测 403 过期)；Azure 2016 前缀 0 对象
- 2016 上半年 = HRRR v1 期产物（hrrrv12arl_v2.f 需核对变量/层次，标待验证）
详见子代理完整报告（含命令样例与链接）。

## Windows 11 跑 STILT：推荐 WSL2 Ubuntu 24.04
- uataq/stilt v5.1.0 官方仅 Unix；预编译 hycs_std/xtrct_grid/xtrct_time/arw2arl 在 bin/linux_x64（**本机已从 OSS 镜像**）
- 依赖：R≥3.5 + ncdf4/dplyr/raster/parallel/rslurm + 系统 netcdf/gdal；permute.so 由 R CMD SHLIB 编译
- 坑：/mnt/d (drvfs) 小文件 IO 慢 → grib2/ARL 放 WSL ext4；gfortran≥10 需 -fallow-argument-mismatch
- 备选：Docker 官方镜像；MSYS2 仅用于转换器 exe 试验；Rtools 原生 R 不推荐
URL: uataq.github.io/stilt/#/install ; github.com/uataq/stilt (Dockerfile, docs/install.md)

## ERA5 (CDS) 备注
- 官方下载需 CDS API key：https://cds.climate.copernicus.eu（待用户提供）
- 本机已有 era52arl/era52arl.cfg/ERA52ARL.MESSAGE 样例（OSS 镜像, era5/20240401）
