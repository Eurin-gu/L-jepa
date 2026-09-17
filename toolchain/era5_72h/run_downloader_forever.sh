#!/bin/bash
# 2026-09-13: 代理抖动会打死下载器, 用守护循环自动拉起
while true; do
  /root/venvs/cds/bin/python /root/era5_72all.py >> /root/era5_72all.log 2>&1
  rc=$?
  echo "[SUPERVISOR] era5_72all 退出 rc=$rc $(date +%F_%T) -> 60s 后重启" >> /root/era5_72all.log
  sleep 60
done
