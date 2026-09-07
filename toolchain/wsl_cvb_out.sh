#!/usr/bin/env bash
tail -8 /root/auto_run/cv_b.out 2>/dev/null
echo ===counts===
ls -d /root/work/stilt/out/by-id/hrrr-cent_valley_CA-20170522-p250_* 2>/dev/null | wc -l
ls /root/work/stilt/out/by-id/hrrr-cent_valley_CA-20170522-p250_*/*_foot.nc 2>/dev/null | wc -l
wc -l /root/auto_run/hmanifest_cent_valley_CA_20170522_p250b.csv 2>/dev/null