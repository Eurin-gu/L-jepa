#!/usr/bin/env bash
D=/root/work/stilt/out/by-id/gdas0p5-v1-so-20150807-p250_20150807T210516Z_27e9ac507406
echo ===stilt.log===; cat $D/stilt.log 2>/dev/null | tail -30
echo ===MESSAGE===; cat $D/MESSAGE 2>/dev/null | tail -20
echo ===WARNING===; cat $D/WARNING 2>/dev/null
echo ===CONTROL met part===; grep -A1 -B0 /root $D/CONTROL 2>/dev/null | head -20