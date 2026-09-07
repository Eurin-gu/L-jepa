#!/usr/bin/env bash
echo ===runner===
tail -25 /root/runner_final.log 2>/dev/null
echo ===met===
find /root/met_era5 -type f 2>/dev/null | head
echo ===manifests===
ls /root/auto_run/manifest_*_p250.csv 2>/dev/null
echo ===era5 gribs===
ls /root/era5_grib/*.grib 2>/dev/null | head -20