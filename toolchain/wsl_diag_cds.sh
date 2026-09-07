#!/usr/bin/env bash
echo ===po_fix.log===
tail -15 /root/era5_po_fix.log 2>/dev/null
echo ===fulldays===
tail -8 /root/era5_fulldays.log 2>/dev/null
echo ===socal===
tail -6 /root/era5_socal.log 2>/dev/null
echo ===grib files with size===
ls -la /root/era5_grib/ | head -40