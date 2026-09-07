#!/usr/bin/env bash
echo ===era5===
ls -la /root/era5_grib/*_c_*.grib 2>/dev/null
echo ===fetch log tail===
tail -3 /root/fetch_safe.log 2>/dev/null