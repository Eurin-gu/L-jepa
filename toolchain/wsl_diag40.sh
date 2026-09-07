#!/usr/bin/env bash
echo ===recent build files===
find /mnt/d/lagrangian-jepa-cn/data/build -newermt "2026-09-05 11:00" -type f 2>/dev/null | head -12
echo ===datasets===
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 2 -name meta.json 2>/dev/null
echo ===era5===
ls /root/era5_grib/*_c_*.grib 2>/dev/null