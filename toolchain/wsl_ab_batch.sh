#!/usr/bin/env bash
set -x
G=/root/gdas05
cd /root/work/footnet/stilt_pipeline
run3() {
  reg=$1; date=$2; tag=$3;
  d1=$(date -d "$date +1 day" +%Y%m%d); d0=$(date -d "$date -1 day" +%Y%m%d)
  for f in $d0 $date $d1; do [ -s "$G/${f}_gdas0p5" ] || { echo "MISS $f"; return; }; done
  mdir=/root/met_ab_$reg; mkdir -p $mdir
  ln -sf $G/${d0}_gdas0p5 $mdir/$d0; ln -sf $G/${date}_gdas0p5 $mdir/$date; ln -sf $G/${d1}_gdas0p5 $mdir/$d1
  /root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/$reg/receptors_${date}_n120_maximin.csv --stilt-wd /root/work/stilt --met $mdir --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 3 --tag $tag --timeout 3600 --log-dir /root/auto_run/ablogs_$reg --manifest /root/auto_run/abmanifest_${reg}_${date}.csv > /root/auto_run/ab_${reg}_${date}.out 2>&1
  echo "AB DONE $reg $date rc=$?"; tail -2 /root/auto_run/ab_${reg}_${date}.out
}
run3 so_cal_LA_basin 20150807 gdas0p5-v1-so-20150807-p250
run3 cent_valley_CA 20150722 gdas0p5-v1-cv-20150722-p250
run3 permian_westTX 20151013 gdas0p5-v1-tx-20151013-p250
run3 co_front_range 20150911 gdas0p5-v1-cf-20150911-p250
echo AB_ALL_DONE