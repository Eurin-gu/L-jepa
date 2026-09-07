#!/usr/bin/env bash
set -x
export DEBIAN_FRONTEND=noninteractive
log=/mnt/d/lagrangian-jepa-cn/toolchain/wsl_prov.log
echo "[stage1 start] $(date)"
apt-get update -y
apt-get install -y build-essential gfortran git wget curl ca-certificates netcdf-bin libnetcdf-dev libnetcdf-fortran-dev libgdal-dev gdal-bin libssl-dev libxml2-dev libhdf5-serial-dev r-base r-base-dev unzip
mkdir -p /root/work/stilt /root/work/footnet /root/work/hysplit_data2arl /root/met /root/era5_grib /root/arl_work /root/stilt_out
cp -a /mnt/d/lagrangian-jepa-cn/toolchain/server_backup_20260830/stilt/. /root/work/stilt/ || true
cp -a /mnt/d/lagrangian-jepa-cn/mirror/server_backup_20260830/footnet_jepa/. /root/work/footnet/ || true
cp -a /mnt/d/lagrangian-jepa-cn/toolchain/server_backup_20260830/hysplit_data2arl/. /root/work/hysplit_data2arl/ || true
chmod +x /root/work/stilt/bin/linux_x64/* /root/work/stilt/exe/* 2>/dev/null || true
echo "[stage1 R packages] $(date)"
Rscript -e "install.packages(c('ncdf4','dplyr','raster','lubridate','jsonlite'), repos='https://cloud.r-project.org', Ncpus=4)" || echo "R pkgs failed"
echo "[stage1 done] $(date)"
which gfortran Rscript; gfortran --version | head -1