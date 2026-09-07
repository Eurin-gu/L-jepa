#!/usr/bin/env bash
echo ===build logs===
ls -la /mnt/d/lagrangian-jepa-cn/data/build/ 2>/dev/null | tail -15
echo ===recent files in build===
find /mnt/d/lagrangian-jepa-cn/data/build -newermt "2026-09-05 11:00" -type f 2>/dev/null | head
echo ===era5===
ls /root/era5_grib/*_c_*.grib 2>/dev/null