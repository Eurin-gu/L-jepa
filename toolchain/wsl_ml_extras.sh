#!/usr/bin/env bash
set -x
/root/venvs/ml/bin/pip install -q numpy scipy netCDF4 xarray pandas h5py --index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tail -3
/root/venvs/ml/bin/python -c "import torch, numpy, netCDF4; print('ml env OK torch', torch.__version__, 'numpy', numpy.__version__)"