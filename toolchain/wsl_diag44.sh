#!/usr/bin/env bash
echo ===arm_smoke.log===
cat /mnt/d/lagrangian-jepa-cn/data/build/arm_smoke.log 2>/dev/null | tail -20
echo ===recent build===
find /mnt/d/lagrangian-jepa-cn/data/build -newermt "2026-09-05 11:10" -type f 2>/dev/null | head -12
echo ===datasets===
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 2 -name meta.json 2>/dev/null