#!/usr/bin/env bash
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 3 -name meta.json 2>/dev/null
echo ===era5===
ls -la /root/era5_grib/*_c_*.grib 2>/dev/null