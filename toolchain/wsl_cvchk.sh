#!/usr/bin/env bash
wc -l /root/auto_run/hmanifest_cent_valley_CA_20170522_p250.csv 2>/dev/null
n=$(ls -d /root/work/stilt/out/by-id/hrrr-cent_valley_CA-20170522-p250_* 2>/dev/null | wc -l)
f=$(ls /root/work/stilt/out/by-id/hrrr-cent_valley_CA-20170522-p250_*/*_foot.nc 2>/dev/null | wc -l)
echo "dirs=$n foot=$f"
free -m | head -2
ps -eo pid,etime,cmd | grep -E "run_batch|hycs_std|Rscript" | grep -v grep | head