#!/usr/bin/env bash
set -x
mkdir -p /root/met_soA
ln -sf /root/gdas05/20150806_gdas0p5 /root/met_soA/20150806
ln -sf /root/gdas05/20150807_gdas0p5 /root/met_soA/20150807
ls -la /root/met_soA/
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/so_cal_LA_basin/receptors_20150807_n120_maximin.csv --stilt-wd /root/work/stilt --met /root/met_soA --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 3 --tag gdas0p5-v1-so-20150807-p250 --timeout 3600 --log-dir /root/auto_run/logs_soA3 --manifest /root/auto_run/manifest_soA3.csv > /root/auto_run/soA3.out 2>&1
echo "rc=$?"; tail -3 /root/auto_run/soA3.out