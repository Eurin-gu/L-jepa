#!/usr/bin/env bash
echo ===foot files p500a/b===
find /root/work/stilt/out/by-id -name "*_foot.nc" -path "*p500a*" 2>/dev/null | wc -l
find /root/work/stilt/out/by-id -name "*_foot.nc" -path "*p500b*" 2>/dev/null | wc -l
echo ===manifests===
wc -l /root/auto_run/manifest_so_sb_a.csv /root/auto_run/manifest_so_sb_b.csv 2>/dev/null
echo ===sample fail log (sb)===
L=$(ls -t /root/auto_run/logs_sb_a/*.log 2>/dev/null | head -1); tail -8 "$L" 2>/dev/null