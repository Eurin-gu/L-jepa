#!/usr/bin/env bash
tail -3 /root/auto_run/cv_c.out 2>/dev/null
f=$(ls /root/work/stilt/out/by-id/hrrr-cent_valley_CA-20170522-p250_*/*_foot.nc 2>/dev/null | wc -l)
echo "foot=$f"