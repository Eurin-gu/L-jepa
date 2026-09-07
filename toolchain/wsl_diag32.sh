#!/usr/bin/env bash
echo ===era5 combined===
ls -la /root/era5_grib/*_c_*.grib 2>/dev/null
echo ===fetch tail===
tail -6 /root/fetch_safe.log 2>/dev/null
echo ===cv files===
ls /root/hrrr_win/20170522/*.grib2 2>/dev/null | wc -l
du -sh /root/hrrr_win/20170522 2>/dev/null