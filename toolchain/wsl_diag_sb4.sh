#!/usr/bin/env bash
cd /root/work/stilt/out/by-id
FAILDIR=$(for d in *p500a*; do [ -f "$d"/*_foot.nc ] || echo "$d"; done | head -1)
echo FAILDIR=$FAILDIR
echo ===run_batch log===
L=/root/auto_run/logs_sb_a/${FAILDIR#hrrr-so-20171111-p500a_}.log
ls /root/auto_run/logs_sb_a/ | head -3
LOG=$(ls -t /root/auto_run/logs_sb_a/*.log | head -1); echo LOG=$LOG; tail -40 "$LOG"