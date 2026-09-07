#!/usr/bin/env bash
echo ===gdas05 files===
ls -la /root/gdas05/*gdas0p5 2>/dev/null | awk "{print \$5, \$9}"
echo ===w1 manifests===
wc -l /root/auto_run/w1manifest_*_p250.csv 2>/dev/null
echo ===w1 outs tail===
for f in /root/auto_run/w1_*.out; do echo "-- $f"; tail -1 "$f" 2>/dev/null; done