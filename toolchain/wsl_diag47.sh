#!/usr/bin/env bash
echo ===recent build===
find /mnt/d/lagrangian-jepa-cn/data/build -newermt "2026-09-05 11:10" -type f 2>/dev/null | head -15
echo ===datasets===
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 2 -name meta.json 2>/dev/null