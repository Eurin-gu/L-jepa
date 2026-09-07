#!/usr/bin/env bash
set -x
G=/mnt/d/lagrangian-jepa-cn/met_cache/gdas
W=/root/met_gdas
mkdir -p $W
declare -A jobs
jobs[po_valley_italy]=20171023
jobs[north_china_plain]=20170626
for reg in po_valley_italy north_china_plain; do
  date=${jobs[$reg]}
  wk=$( [ "$reg" = "po_valley_italy" ] && echo gdas1.oct17.w4 || echo gdas1.jun17.w4 )
  [ -s "$G/$wk" ] || { echo "MISSING $wk"; continue; }
  mdir=$W/$reg
  mkdir -p $mdir
  d0=$(date -d "$date -1 day" +%Y%m%d)
  for d in $d0 $date; do ln -sf $G/$wk $mdir/$d; done
  ls -la $mdir
  cd /root/work/footnet/stilt_pipeline
  /root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/$reg/receptors_${date}_n120_maximin.csv --stilt-wd /root/work/stilt --met $mdir --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag gdas-exp-$reg-$date-p250 --timeout 3600 --log-dir /root/auto_run/glogs_$reg --manifest /root/auto_run/gmanifest_${reg}_${date}_p250.csv > /root/auto_run/gdas_${reg}_${date}.out 2>&1
  echo "GDAS DONE $reg $date rc=$?"
  tail -2 /root/auto_run/gdas_${reg}_${date}.out
done
echo ALL_GDAS_DONE