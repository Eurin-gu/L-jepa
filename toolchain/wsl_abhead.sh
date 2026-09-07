#!/usr/bin/env bash
head -3 /root/auto_run/abmanifest_so_cal_LA_basin_20150807.csv
echo ---
D=$(ls -d /root/work/stilt/out/by-id/gdas0p5-v1-so-20150807-p250_* | head -1); echo $D; ls $D | head