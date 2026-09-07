#!/usr/bin/env bash
set -x
REGION=cent_valley_CA; DATE=20170522; D0=20170521
SRC=/mnt/d/lagrangian-jepa-cn/met_cache/hrrr_20170522
H=/root/work/hysplit_data2arl/hysplit_data2arl/hrrr2arl
W=/root/hrrr_work/$DATE
mkdir -p $W /root/met_hrrr/$REGION /root/met_cfg
echo "[convert] $(date)"
cd $H
for f in $SRC/*.grib2; do
  base=$(basename $f .grib2)
  out=$W/${base}.arl
  [ -s "$out" ] && continue
  ./hrrrv12arl_v2_modern -dapi2arl.cfg -earldata.cfg -i$f -o$out -gHRRR > $W/conv_$base.log 2>&1 || echo CONVFAIL $base
done
ls $W/*.arl | wc -l
echo "[merge] $(date)"
M=/root/work/footnet/stilt_pipeline/merge_arl_met.py
CFG=$H/arldata.cfg
cd /root/work/footnet/stilt_pipeline
for day in $D0 $DATE; do
  out=/root/met_hrrr/$REGION/$day
  [ -s "$out" ] && continue
  INS=""
  for f in $W/${day}*.arl; do [ -s "$f" ] && INS="$INS --input $f $CFG"; done
  echo "merge $day files: $(echo $INS | wc -w)"
  [ -n "$INS" ] && /root/venvs/cds/bin/python $M $INS --out $out --out-config /root/met_cfg/$day.cfg 2>&1 | tail -2 || echo MERGEFAIL $day
done
rm -rf $W
echo "[batch] $(date)"
cd /root/work/footnet/stilt_pipeline
REC=/mnt/d/lagrangian-jepa-cn/data/receptors_v2/$REGION/receptors_${DATE}_n120_maximin.csv
/root/venvs/cds/bin/python run_batch.py --receptors $REC --stilt-wd /root/work/stilt --met /root/met_hrrr/$REGION --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag hrrr-$REGION-$DATE-p250 --timeout 3600 --log-dir /root/auto_run/hlogs_$DATE --manifest /root/auto_run/hmanifest_${REGION}_${DATE}_p250.csv > /root/auto_run/hrrr_${REGION}_${DATE}.out 2>&1
echo "HRRR DONE rc=$? $(date)"
tail -2 /root/auto_run/hrrr_${REGION}_${DATE}.out