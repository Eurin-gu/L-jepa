#!/bin/bash
while true; do
  /root/venvs/cds/bin/python /root/cds_harvester_v2.py >> /root/cds_harvester_v2.log 2>&1
  rc=$?
  echo "[SUPERVISOR] cds_harvester_v2 退出 rc=$rc $(date +%F_%T) -> 60s 后重启" >> /root/cds_harvester_v2.log
  sleep 60
done
