#!/usr/bin/env bash
D=/root/work/stilt/out/by-id
DIR=$(ls -d $D/gdas0p5-po_valley_italy-* 2>/dev/null | head -1)
echo DIR=$DIR
if [ -n "$DIR" ]; then tail -20 $DIR/stilt.log 2>/dev/null; echo ===MESSAGE===; tail -12 $DIR/MESSAGE 2>/dev/null; fi
echo ===receptor log===
L=$(ls -t /root/auto_run/g05logs_po_valley_italy/*.log 2>/dev/null | head -1); tail -30 "$L" 2>/dev/null