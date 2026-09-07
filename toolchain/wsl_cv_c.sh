#!/usr/bin/env bash
set -x
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/cent_valley_CA/receptors_20170522_n120_maximin.csv --stilt-wd /root/work/stilt --met /root/met_hrrr/cent_valley_CA --jobs 12 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag hrrr-cent_valley_CA-20170522-p250 --timeout 3600 --log-dir /root/auto_run/hlogs_20170522c --manifest /root/auto_run/hmanifest_cent_valley_CA_20170522_p250c.csv --resume > /root/auto_run/cv_c.out 2>&1
echo "rc=$?"; tail -4 /root/auto_run/cv_c.out