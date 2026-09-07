#!/usr/bin/env bash
set -x
R=/mnt/d/lagrangian-jepa-cn/data/receptors_v2/so_cal_LA_basin/receptors_20171111_n120_maximin.csv
head -31 "$R" > /root/auto_run/so_sb30.csv
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /root/auto_run/so_sb30.csv --stilt-wd /root/work/stilt --met /root/met --jobs 24 --numpar 500 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag hrrr-so-20171111-p500a2 --timeout 3600 --log-dir /root/auto_run/logs_sb_a2 --manifest /root/auto_run/manifest_so_sb_a2.csv > /root/auto_run/sb_a2.out 2>&1
echo A_DONE rc=$?
tail -3 /root/auto_run/sb_a2.out
/root/venvs/cds/bin/python run_batch.py --receptors /root/auto_run/so_sb30.csv --stilt-wd /root/work/stilt --met /root/met --jobs 24 --numpar 500 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag hrrr-so-20171111-p500b2 --timeout 3600 --log-dir /root/auto_run/logs_sb_b2 --manifest /root/auto_run/manifest_so_sb_b2.csv > /root/auto_run/sb_b2.out 2>&1
echo B_DONE rc=$?
tail -3 /root/auto_run/sb_b2.out
echo ALL_SB_DONE