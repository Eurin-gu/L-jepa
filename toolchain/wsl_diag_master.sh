#!/usr/bin/env bash
echo ===master.log===
tail -30 /root/era5_master.log 2>/dev/null
echo ===procs===
ps -eo pid,etime,cmd | grep -E "eccodes|era5_master|cdsapi" | grep -v grep | head -8
echo ===grib files===
ls /root/era5_grib/ | head -30