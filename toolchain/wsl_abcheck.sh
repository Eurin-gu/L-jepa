#!/usr/bin/env bash
for f in so_cal_LA_basin_20150807 cent_valley_CA_20150722 permian_westTX_20151013 co_front_range_20150911; do
  echo -n "$f manifest lines: "; wc -l < /root/auto_run/abmanifest_$f.csv 2>/dev/null
done