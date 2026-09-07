#!/usr/bin/env bash
echo ===proc===
ps -eo pid,etime,cmd | grep -E "sb-test1|hycs_std|stilt_cli" | grep -v grep | head
echo ===dirs===
ls -d /root/work/stilt/out/by-id/sb-test1* 2>/dev/null
D=$(ls -d /root/work/stilt/out/by-id/sb-test1* 2>/dev/null | head -1)
if [ -n "$D" ]; then ls "$D"; echo ===log===; tail -15 "$D/stilt.log" 2>/dev/null; echo ===MESSAGE===; tail -25 "$D/MESSAGE" 2>/dev/null; fi