#!/usr/bin/env bash
set -x
H=/root/work/hysplit_data2arl/hysplit_data2arl
SRC=/mnt/d/lagrangian-jepa-cn/met_cache/hrrr_20171111
CONV=$H/hrrr2arl/hrrrv12arl_v2_modern
WORK=/root/arl_work/20171111
mkdir -p $WORK
cd $WORK
for f in $SRC/*.grib2; do
  base=$(basename $f .grib2)
  ymd=${base:0:8}
  hh=${base:8:2}
  out=$WORK/${ymd}_${hh}.arl
  [ -s "$out" ] && continue
  echo "convert $base"
  (cd $H/hrrr2arl && $CONV -i $f -o $out -g HRRR > $WORK/conv_$base.log 2>&1) || echo "CONV FAIL $base"
done
ls -la $WORK/*.arl | head -40