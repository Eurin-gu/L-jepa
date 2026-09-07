#!/usr/bin/env bash
set -x
cd /root/met_gdas05
ln -sf /root/met_gdas05/20150806_gdas0p5 20150806
ln -sf /root/met_gdas05/20150807_gdas0p5 20150807
ls -la /root/met_gdas05/
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/so_cal_LA_basin/receptors_20150807_n120_maximin.csv --stilt-wd /root/work/stilt --met /root/met_gdas05 --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 3 --tag gdas0p5-v1-so_cal_LA_basin-20150807-p250 --timeout 3600 --log-dir /root/auto_run/logs_soA --manifest /root/auto_run/manifest_soA_gdas05_p250.csv > /root/auto_run/soA_gdas05.out 2>&1
echo "rc=$?"; tail -3 /root/auto_run/soA_gdas05.out