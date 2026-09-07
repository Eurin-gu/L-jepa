#!/usr/bin/env bash
set -x
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/so_cal_LA_basin/receptors_20171111_n120_maximin.csv --stilt-wd /root/work/stilt --met /root/met --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag hrrr-so-20171111-p250 --timeout 3600 --log-dir /root/stilt_out/logs_20171111 --manifest /root/stilt_out/manifest_20171111_p250.csv 2>&1 | tail -15
echo DONE