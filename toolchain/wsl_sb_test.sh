#!/usr/bin/env bash
set -x
head -2 /root/auto_run/so_sb30.csv > /root/auto_run/sb_one.csv
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /root/auto_run/sb_one.csv --stilt-wd /root/work/stilt --met /root/met --jobs 1 --numpar 500 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag sb-test1 --timeout 600 --log-dir /root/auto_run/logs_sb_test --manifest /root/auto_run/manifest_sb_test.csv > /root/auto_run/sb_test_stdout.log 2>&1
echo rc=$?
tail -30 /root/auto_run/sb_test_stdout.log