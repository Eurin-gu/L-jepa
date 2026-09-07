#!/usr/bin/env bash
set -x
echo "=== watch.out ==="; cat /root/auto_run/watch.out 2>/dev/null | head -5
# ncp batch directly
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/north_china_plain/receptors_20170626_n120_maximin.csv --stilt-wd /root/work/stilt --met /root/met_era5 --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag era5-ncp-20170626-p250 --timeout 3600 --log-dir /root/auto_run/logs_ncp --manifest /root/auto_run/manifest_ncp_20170626_p250.csv 2>&1 | tail -6
echo NCP_BATCH_DONE