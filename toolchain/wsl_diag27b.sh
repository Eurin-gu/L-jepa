#!/usr/bin/env bash
echo ===win files===
ls /root/hrrr_win/20170522/*.grib2 2>/dev/null | wc -l
du -sh /root/hrrr_win/20170522 2>/dev/null
echo ===out log tail===
tail -5 /root/auto_run/hrrr_cent_valley_CA_20170522.out 2>/dev/null
echo ===hrrr proc===
ps -eo pid,etime,cmd | grep -E "hrrr_date|curl|hrrrv12arl" | grep -v grep | head -4