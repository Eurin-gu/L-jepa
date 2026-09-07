#!/usr/bin/env bash
set -x
/root/venvs/cds/bin/pip install -q numpy 2>&1 | tail -1
H=/root/work/hysplit_data2arl/hysplit_data2arl/hrrr2arl
P=/root/venvs/cds/bin/python
M=/root/work/footnet/stilt_pipeline/merge_arl_met.py
ls -la $H/arldata.cfg $H/api2arl.cfg 2>/dev/null
CFG=$H/arldata.cfg
WORK=/root/arl_work/20171111
mkdir -p /root/met
cd /root/work/footnet/stilt_pipeline
IN10=""
for hh in 20 21 22 23; do IN10="$IN10 --input $WORK/20171110${hh}.arl $CFG"; done
echo "[merge day10]"; $P $M $IN10 --out /root/met/20171110 --out-config /root/met/20171110.cfg 2>&1 | tail -6 || echo "merge10 FAILED"
IN11=""
for hh in 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21; do IN11="$IN11 --input $WORK/20171111${hh}.arl $CFG"; done
echo "[merge day11]"; $P $M $IN11 --out /root/met/20171111 --out-config /root/met/20171111.cfg 2>&1 | tail -6 || echo "merge11 FAILED"
echo "[cleanup hourly]"; rm -f $WORK/*.arl
ls -la /root/met/ 2>/dev/null
df -h / | tail -1