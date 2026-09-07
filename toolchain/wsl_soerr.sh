#!/usr/bin/env bash
L=$(ls -t /root/auto_run/ablogs_so_cal_LA_basin/*.log 2>/dev/null | head -1); echo LOG=$L
tail -40 "$L" 2>/dev/null