#!/usr/bin/env bash
ls -lat /mnt/d/lagrangian-jepa-cn/data/build/ | head -6
find /mnt/d/lagrangian-jepa-cn/data/datasets -maxdepth 2 -name meta.json 2>/dev/null