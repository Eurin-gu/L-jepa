#!/usr/bin/env bash
set -x
cp /mnt/c/Users/Yuki/Desktop/oss_work/wsl_dlA_robust.py /root/gdas05/dlA_robust.py
cd /root/gdas05 && /root/venvs/cds/bin/python dlA_robust.py 2>&1 | tail -8