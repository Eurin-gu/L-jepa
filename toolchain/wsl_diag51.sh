#!/usr/bin/env bash
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 3 -name meta.json 2>/dev/null | sort
echo ===count===
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 3 -name meta.json 2>/dev/null | wc -l