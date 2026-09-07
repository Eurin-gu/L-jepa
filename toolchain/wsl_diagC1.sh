#!/usr/bin/env bash
echo ===era5 combined===
ls -la /root/era5_grib/*_c_*.grib 2>/dev/null
echo ===fetch_safe tail===
tail -4 /root/fetch_safe.log 2>/dev/null
echo ===fetch_sfc tail===
tail -4 /root/fetch_sfc.log 2>/dev/null