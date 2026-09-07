#!/usr/bin/env bash
date -u +%H:%M:%S
echo ===proc===
ps -eo pid,etime,cmd | grep -E "Rscript|hycs_std|run_batch" | grep -v grep | head -15
echo ===recent logs===
ls -la --time-style=+%H:%M /root/stilt_out/logs_20171111/ | tail -3
echo ===sample log tail===
L=$(ls -t /root/stilt_out/logs_20171111/*.log | head -1)
echo $L; tail -25 $L