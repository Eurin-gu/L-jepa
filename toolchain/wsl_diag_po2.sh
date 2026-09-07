#!/usr/bin/env bash
D=/root/work/stilt/out/by-id/gdas0p5-po_valley_italy-20171023-p250_20171023T120449Z_3571cc857fc8
echo ===stilt.log full===
cat $D/stilt.log 2>/dev/null
echo ===MESSAGE full===
cat $D/MESSAGE 2>/dev/null
echo ===WARNING===
cat $D/WARNING 2>/dev/null
echo ===ls met symlinks===
ls -la /root/met_g05/po_valley_italy/