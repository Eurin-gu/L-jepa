#!/usr/bin/env bash
set -x
cp /mnt/c/Users/Yuki/Desktop/oss_work/era5_pipeline_all.py /root/era5_pipeline_all.py
cd /root && /root/venvs/cds/bin/python era5_pipeline_all.py 2>&1 | tee /root/era5_pipeline_all.log