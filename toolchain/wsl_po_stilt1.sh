#!/usr/bin/env bash
set -x
R=/mnt/d/lagrangian-jepa-cn/data/receptors_v2/po_valley_italy/receptors_20171023_n120_maximin.csv
mkdir -p /root/stilt_out/po_smoke
head -2 "$R" > /root/stilt_out/po_smoke.csv
cat /root/stilt_out/po_smoke.csv
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /root/stilt_out/po_smoke.csv --stilt-wd /root/work/stilt --met /root/met_era5 --jobs 1 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag era5-po-20171023-smoke --timeout 1800 --log-dir /root/stilt_out/po_smoke --manifest /root/stilt_out/po_smoke_manifest.csv 2>&1 | tail -20
cat /root/stilt_out/po_smoke_manifest.csv 2>/dev/null