#!/usr/bin/env bash
ls -la /root/era5_grib/*_c_*.grib 2>/dev/null
echo ===fetch_safe tail===
tail -5 /root/fetch_safe.log 2>/dev/null