#!/usr/bin/env bash
set -x
export DEBIAN_FRONTEND=noninteractive
echo "[1c switch sources] $(date)"
for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list; do
  [ -f "$f" ] || continue
  sed -i "s|http://archive.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g; s|http://security.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g; s|https://archive.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g; s|https://security.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g" "$f"
done
apt-get update -y 2>&1 | tail -3
echo "[1c apt install] $(date)"
apt-get install -y build-essential gfortran git wget curl netcdf-bin libnetcdf-dev libgdal-dev gdal-bin libssl-dev libxml2-dev libhdf5-serial-dev r-base r-base-dev unzip 2>&1 | tail -8
apt-cache search eccodes | head
apt-get install -y libeccodes-dev 2>&1 | tail -4
echo "[1c R pkgs TUNA] $(date)"
Rscript -e "install.packages(c('ncdf4','dplyr','raster','lubridate','jsonlite','sp'), repos='https://mirrors.tuna.tsinghua.edu.cn/CRAN/', Ncpus=4)" 2>&1 | tail -12
echo "[1c done] $(date)"
which gfortran Rscript; gfortran --version | head -1; Rscript --version; ls /usr/lib/x86_64-linux-gnu/ | grep -i eccodes | head