#!/usr/bin/env bash
set -x
mkdir -p /root/met_cfg
mv -f /root/met/*.cfg /root/met_cfg/ 2>/dev/null
ls -la /root/met/
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /root/stilt_out/smoke.csv --stilt-wd /root/work/stilt --met /root/met --jobs 1 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag hrrr-so-20171111-smoke2 --timeout 2400 --log-dir /root/stilt_out/logs2 --manifest /root/stilt_out/manifest_smoke2.csv 2>&1 | tail -25
echo "=== outputs ==="
find /root/work/stilt/out/by-id/hrrr-so-20171111-smoke2* -type f 2>/dev/null | head -20
cat /root/stilt_out/manifest_smoke2.csv 2>/dev/null