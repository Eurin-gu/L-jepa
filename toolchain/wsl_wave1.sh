#!/usr/bin/env bash
set -x
cp /mnt/c/Users/Yuki/Desktop/oss_work/dlw.py /root/gdas05/dlw.py
cd /root/gdas05 && /root/venvs/cds/bin/python dlw.py 2>&1 | tail -8
ls /root/gdas05/ | grep gdas0p5
run1() {
  reg=$1; date=$2
  d0=$(date -d "$date -1 day" +%Y%m%d)
  mdir=/root/met_g05/$reg; mkdir -p $mdir
  ln -sf /root/gdas05/${d0}_gdas0p5 $mdir/$d0
  ln -sf /root/gdas05/${date}_gdas0p5 $mdir/$date
  cd /root/work/footnet/stilt_pipeline
  /root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/$reg/receptors_${date}_n120_maximin.csv --stilt-wd /root/work/stilt --met $mdir --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 3 --tag gdas0p5-v1-$reg-$date-p250 --timeout 3600 --log-dir /root/auto_run/w1logs_$reg --manifest /root/auto_run/w1manifest_${reg}_${date}_p250.csv > /root/auto_run/w1_${reg}_${date}.out 2>&1
  echo "W1 $reg $date rc=$?"
  tail -1 /root/auto_run/w1_${reg}_${date}.out
}
run1 so_cal_LA_basin 20160217
run1 cent_valley_CA 20150111
run1 permian_westTX 20150128
run1 co_front_range 20150128
echo WAVE1_DONE