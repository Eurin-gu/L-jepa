#!/usr/bin/env bash
ps -eo pid,etime,cmd | grep -E "assemble|python.*datasets|validate" | grep -v grep | head
echo ===recent files===
find /mnt/d/lagrangian-jepa-cn/data/build /mnt/d/lagrangian-jepa-cn/data/datasets -newermt "2026-09-05 11:25" -type f 2>/dev/null | head