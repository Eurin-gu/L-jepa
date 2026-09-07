#!/usr/bin/env bash
L=$(ls -t /root/auto_run/logs_ncp/*.log 2>/dev/null | head -1)
echo LOG=$L
tail -40 "$L" 2>/dev/null
D=$(grep -o "out/by-id/[^ ]*" "$L" 2>/dev/null | head -1)
echo ===run dir tail===
tail -25 "/root/work/stilt/$D/stilt.log" 2>/dev/null
echo ===MESSAGE===
tail -15 "/root/work/stilt/$D/MESSAGE" 2>/dev/null