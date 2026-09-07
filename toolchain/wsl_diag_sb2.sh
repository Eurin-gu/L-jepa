#!/usr/bin/env bash
cd /root/work/stilt/out/by-id
echo ===dir counts===
ls -d *p500a* 2>/dev/null | wc -l
ls -d *p500b* 2>/dev/null | wc -l
echo ===a sample dir listing===
D=$(ls -d *p500a* 2>/dev/null | head -12 | tail -1); echo $D; ls $D 2>/dev/null | head; tail -12 $D/stilt.log 2>/dev/null; tail -6 $D/MESSAGE 2>/dev/null