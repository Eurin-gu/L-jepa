#!/usr/bin/env bash
echo ===_c_ files===
ls -la /root/era5_grib/*_c_*.grib 2>/dev/null
echo ===daily suffix files===
ls /root/era5_grib/*_p.grib /root/era5_grib/*_s.grib 2>/dev/null | head -20