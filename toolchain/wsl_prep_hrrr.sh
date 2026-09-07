#!/usr/bin/env bash
set -x
cat > /root/hrrr_date.sh << "RUNNER"
#!/usr/bin/env bash
set -x
REGION=$1; DATE=$2
D0=$(date -d "$DATE -1 day" +%Y%m%d)
REC=/mnt/d/lagrangian-jepa-cn/data/receptors_v2/$REGION/receptors_${DATE}_n120_maximin.csv
H=/root/work/hysplit_data2arl/hysplit_data2arl/hrrr2arl
W=/root/hrrr_win/$DATE
mkdir -p $W /root/met_hrrr/$REGION
BASE=https://storage.googleapis.com/high-resolution-rapid-refresh
echo "[dl window] $(date)"
for hh in 19 20 21 22; do f=${D0}${hh}; [ -s $W/$f.grib2 ] || curl -fL -sS -o $W/$f.grib2 $BASE/hrrr.$D0/conus/hrrr.t${hh}z.wrfprsf00.grib2 || echo FAILDL $f; done
for hh in $(seq -w 0 22); do f=${DATE}${hh}; [ -s $W/$f.grib2 ] || curl -fL -sS -o $W/$f.grib2 $BASE/hrrr.$DATE/conus/hrrr.t${hh}z.wrfprsf00.grib2 || echo FAILDL $f; done
echo "[convert] $(date)"
cd $H
for f in $W/*.grib2; do
  base=$(basename $f .grib2)
  out=$W/${base}.arl
  [ -s "$out" ] && continue
  ./hrrrv12arl_v2_modern -dapi2arl.cfg -earldata.cfg -i$f -o$out -gHRRR > $W/conv_$base.log 2>&1 || echo CONVFAIL $base
done
echo "[merge] $(date)"
M=/root/work/footnet/stilt_pipeline/merge_arl_met.py
CFG=$H/arldata.cfg
cd /root/work/footnet/stilt_pipeline
for day in $D0 $DATE; do
  out=/root/met_hrrr/$REGION/$day
  [ -s "$out" ] && continue
  INS=""
  for f in $W/${day}*.arl; do [ -s "$f" ] && INS="$INS --input $f $CFG"; done
  [ -n "$INS" ] && /root/venvs/cds/bin/python $M $INS --out $out --out-config /root/met_cfg/$day.cfg 2>&1 | tail -2 || echo MERGEFAIL $day
done
echo "[cleanup grib] $(date)"
rm -f $W/*.grib2 $W/*.arl
echo "[batch] $(date)"
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors $REC --stilt-wd /root/work/stilt --met /root/met_hrrr/$REGION --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag hrrr-$REGION-$DATE-p250 --timeout 3600 --log-dir /root/auto_run/hlogs_$DATE --manifest /root/auto_run/hmanifest_${REGION}_${DATE}_p250.csv > /root/auto_run/hrrr_${REGION}_${DATE}.out 2>&1
echo "HRRR $REGION $DATE rc=$? $(date)"
tail -2 /root/auto_run/hrrr_${REGION}_${DATE}.out
RUNNER
chmod +x /root/hrrr_date.sh
echo ready