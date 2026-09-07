#!/usr/bin/env bash
echo ===runner_final.log===
tail -35 /root/runner_final.log 2>/dev/null
echo ===manifests===
ls -la /root/auto_run/manifest_*_p250.csv 2>/dev/null
echo ===met per region===
ls /root/met_era5/ 2>/dev/null
echo ===procs===
ps -eo pid,etime,cmd | grep -E "runner_final|run_batch|hycs_std" | grep -v grep | head -6