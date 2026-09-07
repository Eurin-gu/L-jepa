#!/usr/bin/env bash
echo ===master_all.log===
tail -30 /root/master_all.log 2>/dev/null
echo ===manifests so far===
ls /root/auto_run/manifest_*_p250.csv 2>/dev/null
echo ===met dirs===
ls /root/met_era5/ 2>/dev/null
echo ===procs===
ps -eo pid,etime,cmd | grep -E "master_all|run_batch|era5_po_fix" | grep -v grep | head