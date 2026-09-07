#!/usr/bin/env bash
set -x
reg=po_valley_italy; date=20171023; d0=20171022
mdir=/root/met_g05/$reg; mkdir -p $mdir
ln -sf /root/gdas05/${d0}_gdas0p5 $mdir/$d0
ln -sf /root/gdas05/${date}_gdas0p5 $mdir/$date
ls -la $mdir
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/$reg/receptors_${date}_n120_maximin.csv --stilt-wd /root/work/stilt --met $mdir --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag gdas0p5-$reg-$date-p250 --timeout 3600 --log-dir /root/auto_run/g05logs_$reg --manifest /root/auto_run/g05manifest_${reg}_${date}_p250.csv > /root/auto_run/gdas05_${reg}_${date}.out 2>&1
echo "rc=$?"; tail -3 /root/auto_run/gdas05_${reg}_${date}.out