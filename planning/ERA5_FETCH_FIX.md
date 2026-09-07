# ERA5 下载修复（2026-09-05 诊断 + 新管线）

## 诊断结论（实测，Windows 侧 .venv-oss + cdsapi 0.7.7）
- 认证 ✓：~/.cdsapirc 为新格式（36 字符 UUID key + https://cds.climate.copernicus.eu/api），请求被正常接受。
- 许可 ✓：single-levels 与 pressure-levels 两个数据集均已同意，试探请求均 accepted，无 licence 报错。
- **瓶颈 = 新 CDS 队列 + 请求体量**：最小测试请求（1 变量/1 层/1 时次/小区域）在队列中 >4 分钟仍 accepted；原 fetcher 的全球逐日请求（6 气压量 × 37 层 + 14 地表量，全经纬 0.25°）单日 3–5GB，属于 CDS 最重的一档，排队以小时计，且易触发 cost limit 失败后被 fetcher 无限重试。

## 修复：区域子集管线（已交付 C:\Users\Yuki\Desktop\oss_work\era5_regional_fetch.py）
- 按 6 区 bbox + 10° 余量取子集（24h 后向轨迹足够），单区单日 ≈ **100MB（PL ~90MB + SFC ~6MB），比全球请求小 30–50 倍**，队列与 cost limit 压力同步下降。
- 变量/层严格按 toolchain era52arl.cfg：PL = z,t,u,v,w,r × 37 层；SFC = 14 量；**GRIB 格式**（era52arl 直接可吃，无需 netcdf→grib 转换）。
- 幂等：已存在且 >1MB 的文件自动跳过；服务端 failed 自动重试 3 次；顺序提交避免自我挤占队列。
- 用法（Windows 侧即可跑，无需 WSL）：
  ```
  C:/Users/Yuki/Desktop/.venv-oss/Scripts/python.exe C:/Users/Yuki/Desktop/oss_work/era5_regional_fetch.py <REGION> <YYYYMMDD> [更多日期]
  # 例：era5_regional_fetch.py so_cal_LA_basin 20160807 20160808
  ```
  产物：D:\lagrangian-jepa-cn\met_cache\era5\<region>\<date>_PL.GRIB / <date>_SFC.GRIB，WSL 经 /mnt/d 读取后直接 era52arl。
- 注意：SFC 变量名用 CDS 标准长名（与 toolchain cfg 的 GRIB shortName 对应关系已核对：10u/10v/blh/sp 等）；BUILD_REPORT 已实测 ERA5 SFC 文件 typeOfLevel=surface 选择器适配。

## 原 WSL fetcher 处置建议
- 停掉全球逐日版本（它在与新管线抢同一账号的队列配额，互相拖慢）。
- 若日后确需全球档（如背景场）：改用**按月打包**请求（year+month 整月、day 全列、time 全列），单请求一个月，队列效率远高于逐日。

## 备选（Plan B，仅当 CDS 持续不可用）
- ARCO-ERA5（GCS，gs://gcp-public-data-arco-era5，zarr，全档 0.25°）→ 需 zarr→GRIB 转换器再接 era52arl，工作量约 1 天，暂不必启用。

## 验证状态
- [进行中] so_cal_LA_basin 20171111 单日端到端（PL+SFC GRIB）下载测试，完成后以文件字节数与 eccodes 变量清点为准。
