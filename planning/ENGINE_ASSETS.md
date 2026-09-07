# ENGINE ASSETS（桶内现成工具链 → 本地镜像）

本地镜像根: D:\lagrangian-jepa-cn\toolchain\
- server_backup_20260830/stilt/ → uataq/stilt 安装（含 bin/linux_x64/hycs_std 2.5MB、exe/、r/src/permute.{f90,so}、docs、Dockerfile）【已镜像, 已排除 out/ 60k 输出对象】
- server_backup_20260830/hysplit_data2arl/ → NOAA data2arl 源码全家（era52arl/era52arl.f+Makefile+cfg、hrrr2arl/hrrrv12arl_v2.f(+patch)、arw2arl/、api2arl/、Makefile.inc.gfortran、COMPILE.txt）【已镜像 5.1MB】
- server_backup_20260830/hysplit_data2arl.zip (923KB)【已镜像】
- server_backup_20260830/era5/20240401/{era52arl.cfg, ERA52ARL.MESSAGE, arldata.cfg} → ERA5 转换样例配置【已镜像】

用途：WSL2 Ubuntu 内直接使用 hycs_std linux 二进制 + 编译 era52arl/hrrrv12arl 转换器；无需 NOAA ARL 注册自编 HYSPLIT。
注意：hrrrv12arl_v2.f 解码库依赖（g2lib/jasper 或 netcdf）待按源文件确认后编译；patch 文件位于 stilt_pipeline/patches/。
