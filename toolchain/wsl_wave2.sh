#!/usr/bin/env bash
set -x
cp /mnt/c/Users/Yuki/Desktop/oss_work/wave2.py /root/wave2.py
cd /root && /root/venvs/cds/bin/python wave2.py 2>&1 | tee /root/wave2.log