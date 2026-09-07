#!/usr/bin/env bash
D=/root/work/stilt/out/by-id/gdas0p5-v1-so-20150807-p250_20150807T210516Z_9f84b0927568
echo ===stilt.log===
cat $D/stilt.log 2>/dev/null | tail -25
echo ===CONTROL met section===
grep -A3 -B1 met $D/CONTROL 2>/dev/null | head -40
echo ===CONTROL head===
head -20 $D/CONTROL 2>/dev/null