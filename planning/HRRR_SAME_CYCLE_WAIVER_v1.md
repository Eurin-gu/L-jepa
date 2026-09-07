# HRRR 正式臂 same-cycle 豁免论证（WAVER / exemption memo）

> 状态: 草稿 v1 — 2026-09-06 03:30 UTC
> 关联: ARM_BUILD_REPORT.md 第 3 条; meta.json alignment="valid_time_only_not_same_cycle"

## 1. 问题
正式臂数据集 meta.json 声明 alignment=valid_time_only_not_same_cycle、stilt_driver_source=external_manifest_unspecified。
因为数据链路未记录「标签 ARL ← 转换用 grib 文件清单」的 receipts，strict same-cycle 无法从数据形式化证明。

## 2. 实测证据（2026-09-06, so_hrrr_20171111 抽查）
| 项 | 证据 |
|---|---|
| 特征 grib 为 f00 | hrrr_20171111/2017111120.grib2 → dataDate=20171111 dataTime=2000 step=0；下载脚本 dl_hrrr_window.py URL 为 hrrr.t%sz.wrfprsf00.grib2 |
| 标签 ARL 为 HRRR | /root/met/20171111 ARL 头标 "171111 HRRR 3.0 1799 1059"；sim CONTROL 用 /root/met/ (20171110+20171111) |
| 同日期 | 特征 dataDate=20171111 = ARL 头 171111 |

## 3. 论证: HRRR f00 架构下 valid_time == cycle 有效时次
HRRR 每小时滚动出 f00 分析（无 forecast lag）。文件 t=YYYYMMDDHH 的 f00 分析场,其循环时次即 HH:00、有效时次即 HH:00（step=0）。
故「某整点有效时刻的气象场」在 HRRR f00 下无跨-cycle 歧义: 唯一候选就是该小时的 f00。
特征取 backhours {0,6,12,18} 的 f00; 标签 24h 后向轨迹的 met 序列也由同一批逐小时 f00 ARL 提供。
两者均锚定同一组有效时次 ⇒ 实际 same-cycle（f00 单值性）。

## 4. 仍属 open 的部分
1. 未逐 sim 记录「ARL 转换用了哪些 grib 文件 + sha256」→ 无法程序化重放验证。
2. 部分历史转换日志（hrrrv12arl → merge_arl）已不完整，无法回溯全部日期。

## 5. 处置建议
- 本豁免覆盖已建 HRRR 正式臂（train/val/test/so/cv），作为 not_same_cycle 声明的支持材料存档。
- 新臂（ERA5-v1 / GDAS0.5-v2）拼装从源头生成 met receipts（cycle_mode=hourly/f00 + per-file sha256），写入 meteorology_manifest，升级 alignment 声明。
- 若需最高形式严谨：对 HRRR 正式臂重跑 ARL 转换并记录 receipts（成本高，列为可选）。