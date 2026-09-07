#!/usr/bin/env bash
echo ===met file===
ls -la /root/met_hrrr/cent_valley_CA/20170522 2>&1
echo ===batch out tail===
tail -6 /root/auto_run/hrrr_cent_valley_CA_20170522.out 2>/dev/null
echo ===hmanifest===
wc -l /root/auto_run/hmanifest_cent_valley_CA_20170522_p250.csv 2>/dev/null
echo ===hrrr_work arl count===
ls /root/hrrr_work/20170522/*.arl 2>/dev/null | wc -l