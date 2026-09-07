#!/usr/bin/env bash
find /mnt/d/lagrangian-jepa-cn/data/datasets/formal_hrrr_train_p250 -maxdepth 2 -name meta.json 2>/dev/null | sort
echo total=$(find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 3 -name meta.json | wc -l)