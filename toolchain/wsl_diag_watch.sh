#!/usr/bin/env bash
echo ===auto.log===
tail -25 /root/auto_run/auto.log 2>/dev/null
echo ===procs===
ps -eo pid,etime,cmd | grep -E "watch.sh|run_one|run_batch|hycs_std" | grep -v grep | head -8
echo ===met===
ls /root/met_era5/