#!/usr/bin/env bash
ls -la /root/era5_grib/*_c_*.grib 2>/dev/null
echo ===builder recent===
find /mnt/d/lagrangian-jepa-cn/data/build -newermt "2026-09-05 11:30" -type f 2>/dev/null | head -8
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 2 -name meta.json 2>/dev/null