#!/usr/bin/env bash
D=/mnt/d/lagrangian-jepa-cn/reuse_stilt/server_backup_20260830/hrrr_stilt_production_v1/formal_test_p1000/20160318/model_features
ls -la $D 2>/dev/null | head -15
echo ===labels for 20160318===
ls /mnt/d/lagrangian-jepa-cn/reuse_stilt/server_backup_20260830/stilt/out/by-id/ 2>/dev/null | grep 20160318 | head -5
find /mnt/d/lagrangian-jepa-cn/reuse_stilt/server_backup_20260830/stilt/out/by-id -maxdepth 1 -type d -name "*20160318*" 2>/dev/null | wc -l