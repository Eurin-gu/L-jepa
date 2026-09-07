#!/usr/bin/env bash
set -x
cd /mnt/d/lagrangian-jepa-cn/data/build
/root/venvs/cds/bin/python validate_dataset.py --data /mnt/d/lagrangian-jepa-cn/data/datasets/formal_hrrr_formal_test_p1000/20160318 2>&1 | tail -20