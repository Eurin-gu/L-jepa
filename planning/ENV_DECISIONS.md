# 环境决策记录（2026-09-04 晚更新）

- Windows 直装 torch cu128: 不可行/极慢（download.pytorch.org 连接重置；阿里/SJTU/华为镜像 cu128 win wheel 限速 <0.3MB/s；PyPI win wheel = CPU-only 111MB）
- 决策：**GPU 训练环境放 WSL2 Ubuntu（Linux torch cu128, CUDA 直通）**，与 STILT 共用 Linux 工具链
- Windows py311 venv (D:\lagrangian-jepa-cn\py311) = 数据处理/OSS/受体/清单工具（已装 numpy/scipy/netCDF4/xarray/pandas/requests/h5py）
- WSL2 就绪后在 Linux 内 pip 装 torch cu128 (manylinux)：优先 TUNA/阿里/官方 index，届时再实测最快源
- 待用户：安装 WSL2、提供 ERA5 CDS key