#!/usr/bin/env bash
set -x
export DEBIAN_FRONTEND=noninteractive
echo "[1b apt] $(date)"
apt-get update -y
apt-get install -y build-essential gfortran git wget curl netcdf-bin libnetcdf-dev libgdal-dev gdal-bin libssl-dev libxml2-dev libhdf5-serial-dev r-base r-base-dev unzip
apt-cache search eccodes | head -20
apt-get install -y libeccodes-dev || echo "eccodes-dev unavailable"
apt-get install -y libeccodes-f90-dev || echo "eccodes-f90 unavailable"
echo "[1b R pkgs (TUNA CRAN)] $(date)"
Rscript -e "install.packages(c('ncdf4','dplyr','raster','lubridate','jsonlite','sp'), repos='https://mirrors.tuna.tsinghua.edu.cn/CRAN/', Ncpus=4)" 2>&1 | tail -20
echo "[1b done] $(date)"; which gfortran Rscript; gfortran --version | head -1