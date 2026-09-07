#!/usr/bin/env bash
for tag in gdas0p5-v1-so-20150807-p250 gdas0p5-v1-cv-20150722-p250 gdas0p5-v1-tx-20151013-p250 gdas0p5-v1-cf-20150911-p250; do
  n=$(ls /root/work/stilt/out/by-id/${tag}_*/*_foot.nc 2>/dev/null | wc -l)
  nt=$(ls /root/work/stilt/out/by-id/${tag}_*/*_traj.rds 2>/dev/null | wc -l)
  nd=$(ls -d /root/work/stilt/out/by-id/${tag}_* 2>/dev/null | wc -l)
  echo "$tag dirs=$nd foot=$n traj=$nt"
done