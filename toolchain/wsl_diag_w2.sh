#!/usr/bin/env bash
echo ===log tail===
tail -15 /root/wave2.log 2>/dev/null
echo ===manifests===
wc -l /root/auto_run/w2manifest_*_p250.csv 2>/dev/null