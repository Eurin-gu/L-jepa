#!/usr/bin/env bash
ps -eo pid,etime,cmd | grep -E "assemble.py|validate" | grep -v grep | head -3
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 3 -name meta.json 2>/dev/null | wc -l
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 1 -type d 2>/dev/null