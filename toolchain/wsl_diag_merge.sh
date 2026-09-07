#!/usr/bin/env bash
df -h / | tail -1
ls -ld /root/met_hrrr /root/met_hrrr/cent_valley_CA 2>&1
touch /root/met_hrrr/cent_valley_CA/_t && echo write_ok && rm -f /root/met_hrrr/cent_valley_CA/_t
ls /root/hrrr_work/20170522/*.arl | wc -l