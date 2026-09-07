#!/usr/bin/env bash
set -x
H=/root/work/hysplit_data2arl/hysplit_data2arl/hrrr2arl
SRC=/mnt/d/lagrangian-jepa-cn/met_cache/hrrr_20171111
WORK=/root/arl_work/20171111
CFG=$H/arldata.cfg
[ -f $CFG ] || CFG=$H/api2arl.cfg
mkdir -p $WORK /root/met
cd $H
for f in $SRC/*.grib2; do
  base=$(basename $f .grib2)
  out=$WORK/${base}.arl
  [ -s "$out" ] && [ $(stat -c%s "$out") -gt 100000000 ] && continue
  echo "convert $base"
  ./hrrrv12arl_v2_modern -dapi2arl.cfg -earldata.cfg -i$f -o$out -gHRRR > $WORK/conv_$base.log 2>&1 || echo "CONV FAIL $base"
done
ls -la $WORK/*.arl | wc -l
ls -la $WORK/*.arl | head -5