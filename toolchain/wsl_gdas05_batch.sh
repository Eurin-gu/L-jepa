#!/usr/bin/env bash
set -x
G=/mnt/d/lagrangian-jepa-cn/met_cache/gdas05
W=/root/met_g05
mkdir -p $W
run() {
  reg=$1; date=$2;
  d0=$(date -d "$date -1 day" +%Y%m%d)
  f0=${d0}_gdas0p5; f1=${date}_gdas0p5
  [ -s "$G/$f0" ] || { echo "MISSING $f0"; return; }
  [ -s "$G/$f1" ] || { echo "MISSING $f1"; return; }
  mdir=$W/$reg; mkdir -p $mdir
  ln -sf $G/$f0 $mdir/$d0; ln -sf $G/$f1 $mdir/$date
  ls -la $mdir
  cd /root/work/footnet/stilt_pipeline
  /root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/$reg/receptors_${date}_n120_maximin.csv --stilt-wd /root/work/stilt --met $mdir --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag gdas0p5-$reg-$date-p250 --timeout 3600 --log-dir /root/auto_run/g05logs_$reg --manifest /root/auto_run/g05manifest_${reg}_${date}_p250.csv > /root/auto_run/gdas05_${reg}_${date}.out 2>&1
  echo "G05 DONE $reg $date rc=$?"
  tail -2 /root/auto_run/gdas05_${reg}_${date}.out
}
run po_valley_italy 20171023
run north_china_plain 20170626
echo ALL_G05_DONE