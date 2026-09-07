#!/usr/bin/env bash
echo ===so out tail===
tail -5 /root/auto_run/ab_so_cal_LA_basin_20150807.out 2>/dev/null
echo ===cv out tail===
tail -5 /root/auto_run/ab_cent_valley_CA_20150722.out 2>/dev/null
echo ===count OK lines in logs dirs===
grep -l "OK (" /root/auto_run/ablogs_so_cal_LA_basin/*.log 2>/dev/null | wc -l
grep -l "OK (" /root/auto_run/ablogs_cent_valley_CA/*.log 2>/dev/null | wc -l