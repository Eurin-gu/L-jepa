#!/usr/bin/env bash
date -u +%H:%M:%S
echo ===builder recent===
find /mnt/d/lagrangian-jepa-cn/data/build -newermt "2026-09-05 11:10" -type f 2>/dev/null | head -10
ls -lat /mnt/d/lagrangian-jepa-cn/data/build/ | head -5
echo ===era5===
ls -la /root/era5_grib/*_c_*.grib 2>/dev/null