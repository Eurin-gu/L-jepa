#!/usr/bin/env bash
ps -eo pid,etime,cmd | grep assemble.py | grep -v grep | head -2
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 3 -name meta.json 2>/dev/null | wc -l
ls /mnt/d/lagrangian-jepa-cn/data/datasets/formal_hrrr_*/ -d 2>/dev/null