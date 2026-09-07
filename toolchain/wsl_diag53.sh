#!/usr/bin/env bash
ps -eo pid,etime,cmd | grep -E "assemble.py" | grep -v grep | head -3
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 3 -name meta.json 2>/dev/null | wc -l
ls /root/era5_grib/*_c_*.grib 2>/dev/null