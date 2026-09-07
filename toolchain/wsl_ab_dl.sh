#!/usr/bin/env bash
set -x
cp /mnt/c/Users/Yuki/Desktop/oss_work/wsl_dlAB.py /root/gdas05/dlAB.py
cd /root/gdas05 && /root/venvs/cds/bin/python dlAB.py 2>&1 | tail -14