#!/usr/bin/env bash
set -x
sed -i 's/^    print("VAL"/print("VAL"/' /root/train_pool1.py
python3 -c "import ast; ast.parse(open('/root/train_pool1.py').read()); print('syntax ok')"
/root/venvs/ml/bin/python /root/train_pool1.py 2>&1 | tee /root/train_pool1.log