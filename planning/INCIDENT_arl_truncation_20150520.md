# 数据完整性事故处置 — ncp 20150520 ARL 截断 (2026-09-06 05:00 UTC)

## 问题（由协作 agent 发现并核实）
- met_era5/north_china_plain/20150520 ARL = 14,065,870 字节，vs 正常 24,339,120（少 42%）
- conv 日志 20150520 只 Finished 10 次（应 24），尾部停在半行无收尾
- 但批次跑批照样 120/120 "成功"（STILT 用 11h 截断气象场跑完 24h 后向轨迹 → 足迹几乎肯定错）
- 根因：wsl_era5_post.sh 第 19/24 行用 `-s`（存在且非空）判转换成功，从不校验完整性；fixall.py 同样只判 >100KB

## 澄清（prev 日 5 小时非截断）
- conv 日志 finished=5 的 prev 日（如 20150228/20150519/20160309/20150812/20171022）是旧 era5_day_wsl.py 只下载 prev 19-23Z 的产物，设计如此
- 但 era5_fullprev.py（fixall 用）下载 prev 全天 → prev ARL 也应是全尺寸（po 20150720 = 23403000 证实）
- ncp 20150519 prev grib 已删（需 fixall 重下）

## 处置（已完成）
1. 删除污染：ncp 20150520 的截断 ARL + manifest + by-id 120 foot
2. 修复 wsl_era5_post.sh：arl_ok() 校验完整尺寸（po 23403000/ncp 24339120），截断删除重转
3. 修复 era5_fixall.py：转换校验 == 完整尺寸
4. fixall 后续到 ncp 阶段会自动：重下 20150519 prev → 重转 20150519+20150520 → 重跑批次

## 受影响清单（已核实仅此一例）
- era5-v1-north_china_plain-20150520（已删，待 fixall 重建）
- 其余 ARL（po 20150211/20150720/20150721/20171023, ncp 20150301/20160310）全尺寸正常