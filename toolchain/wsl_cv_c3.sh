#!/usr/bin/env bash
tail -2 /root/auto_run/cv_c.out 2>/dev/null
echo foot=$(ls /root/work/stilt/out/by-id/hrrr-cent_valley_CA-20170522-p250_*/*_foot.nc 2>/dev/null | wc -l) manifest=$(wc -l < /root/auto_run/hmanifest_cent_valley_CA_20170522_p250c.csv 2>/dev/null || echo 0)