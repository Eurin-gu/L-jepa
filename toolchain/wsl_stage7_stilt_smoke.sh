#!/usr/bin/env bash
set -x
RC=D:/lagrangian-jepa-cn/data/receptors_v2/so_cal_LA_basin/receptors_20171111_n120_maximin.csv
RP=/mnt/d/lagrangian-jepa-cn/data/receptors_v2/so_cal_LA_basin/receptors_20171111_n120_maximin.csv
mkdir -p /root/stilt_out/logs
head -2 "$RP" > /root/stilt_out/smoke.csv
cat /root/stilt_out/smoke.csv
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /root/stilt_out/smoke.csv --stilt-wd /root/work/stilt --met /root/met --jobs 1 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag hrrr-so-20171111-smoke --timeout 2400 --log-dir /root/stilt_out/logs --manifest /root/stilt_out/manifest_smoke.csv 2>&1 | tail -30
echo "=== outputs ==="
find /root/work/stilt/out -type f 2>/dev/null | head -10
cat /root/stilt_out/manifest_smoke.csv 2>/dev/null