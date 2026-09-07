#!/usr/bin/env bash
set -x
python3 -m venv /root/venvs/ml || true
/root/venvs/ml/bin/pip install -q -U pip 2>&1 | tail -1
echo "[try pytorch official index]"
/root/venvs/ml/bin/pip install torch --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tail -6
if /root/venvs/ml/bin/python -c "import torch" 2>/dev/null; then
  echo "torch ok from official"
else
  echo "[fallback aliyun mirror]"
  /root/venvs/ml/bin/pip install torch==2.9.1+cu128 -f https://mirrors.aliyun.com/pytorch-wheels/cu128/ --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tail -6
fi
/root/venvs/ml/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_capability() if torch.cuda.is_available() else None)" 2>&1