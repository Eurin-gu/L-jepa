#!/usr/bin/env bash
echo ===era5_c files===
ls -la /root/era5_grib/*_c_*.grib 2>/dev/null | head -20
echo ===po_fix/fulldays leftovers running?===
ps -eo pid,etime,cmd | grep -E "era5|fetch|c d s|runner" | grep -v grep | head