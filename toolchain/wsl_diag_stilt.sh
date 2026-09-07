#!/usr/bin/env bash
D=/root/work/stilt/out/by-id/hrrr-so-20171111-smoke_20171111T204641Z_4e47e91dcaf0
ls -la $D
echo ===CONTROL===
cat $D/CONTROL 2>/dev/null
echo ===SETUP===
head -50 $D/SETUP.CFG 2>/dev/null
echo ===stilt.log===
cat $D/stilt.log 2>/dev/null | head -60
echo ===MESSAGE===
tail -30 $D/MESSAGE 2>/dev/null
echo ===VMSDIST===
head -20 $D/VMSDIST 2>/dev/null