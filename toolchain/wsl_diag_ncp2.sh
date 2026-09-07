#!/usr/bin/env bash
ID=era5-ncp-20170626-p250_20170626T052050Z_13a7e9215bdb
D=/root/work/stilt/out/by-id/$ID
ls -la $D 2>/dev/null
echo ===stilt.log===
cat $D/stilt.log 2>/dev/null | tail -40
echo ===MESSAGE===
tail -20 $D/MESSAGE 2>/dev/null
echo ===WARNING===
cat $D/WARNING 2>/dev/null | head -20