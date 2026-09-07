#!/usr/bin/env bash
set -x
cd /mnt/d/lagrangian-jepa-cn/data/build
OUT=/mnt/d/lagrangian-jepa-cn/data/datasets/cv_hrrr_20170522
mkdir -p $OUT
/root/venvs/cds/bin/python assemble.py --manifest /root/auto_run/hmanifest_cent_valley_CA_20170522_p250c.csv --features /mnt/d/lagrangian-jepa-cn/data/build/features_hrrr_20170522.json --out $OUT --footnet-root /mnt/d/lagrangian-jepa-cn/mirror/server_backup_20260830/footnet_jepa > /root/auto_run/cv_assemble.log 2>&1
echo "assemble rc=$?"; tail -6 /root/auto_run/cv_assemble.log
/root/venvs/cds/bin/python validate_dataset.py --data $OUT 2>&1 | tail -12