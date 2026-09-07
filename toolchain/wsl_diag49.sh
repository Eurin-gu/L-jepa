#!/usr/bin/env bash
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 3 -name meta.json 2>/dev/null
echo ===recent build files===
find /mnt/d/lagrangian-jepa-cn/data/build -newermt "2026-09-05 11:20" -type f 2>/dev/null | head