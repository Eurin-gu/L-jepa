# GDAS0.5 试点执行计划（tag: gdas0p5-v1，2026-09-05）

## 决策：分阶段，不直接全量 23 日期
GDAS0p5→STILT 链路本机从未端到端验证过。先 Stage A（1 日期打通）→ Stage B（4 区覆盖）→ Stage C（23 日期全量）。A/B 成本 ~2 小时，挡住系统性翻车。

## 关键参数（与 HRRR 配方的差异）
- **--met-file-tres-hours 3**（GDAS ARL = 3 小时分辨率；HRRR 配方是 1，勿照抄）
- 每日期需 **当日 + 前一日** 两个日文件（24h 后向轨迹跨午夜；后向不需要次日文件）
- met 目录只放 ARL 文件（铁律：cfg 勿入 met 目录）
- 日文件名 `YYYYMMDD_gdas0p5` 含 %Y%m%d，STILT find_met_files 直接可 grep，无需改链接脚本
- p250（试点/train 级）；tag 规则 `gdas0p5-v1-<region>-<date>-p250`

## Stage A：SoCal 单日期端到端（验证闸门）
日期 20150807（met: 20150806 + 20150807）
```bash
mkdir -p /root/met_gdas05
cp /mnt/d/lagrangian-jepa-cn/met_cache/gdas05/2015080{6,7}_gdas0p5 /root/met_gdas05/
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py \
  --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/so_cal_LA_basin/receptors_20150807_n120_maximin.csv \
  --stilt-wd /root/work/stilt --met /root/met_gdas05 --jobs 24 \
  --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 3 \
  --tag gdas0p5-v1-so_cal_LA_basin-20150807-p250 --timeout 3600 \
  --log-dir /root/stilt_out/logs_20150807_gdas05 --manifest /root/stilt_out/manifest_20150807_gdas05_p250.csv
```
**通过闸门**（全过才进 Stage B）：
1. 120/120 foot.nc 非空且 lon/lat 锚定受体（|中心-受体|<0.06°）
2. 足迹 CoM 距受体 5–50km 量级、值非负、域内质量占比合理
3. manifest 120 行 + sha 记录（v2.2 receipts）

## Stage B：4 区各 1 日期（多区覆盖验证）
| 区 | 日期 | met 文件 |
|---|---|---|
| cent_valley_CA | 20150722 | 20150721+20150722 |
| permian_westTX | 20151013 | 20151012+20151013 |
| co_front_range | 20150911 | 20150910+20150911 |
（命令同 Stage A 换受体表/tag。co_front_range 重点看山地足迹形态是否物理合理——0.5° 分辨率下不追求保真，但不能出网格伪影/断崖。）
it/cn 两区在 Stage C 再用同法验证（受体表已就位）。

## Stage C：23 日期全量（A/B 全绿后）
- 下载：~23×2 文件 ≈ 28GB（dl_gdas05_s3.py 顺序队列，幂等）
- 批跑：~120×45s/24jobs ≈ 5min/日期 × 23 ≈ 2h（实际含 IO 更久，按半天估）
- 每日期完成即验 manifest + 非空，失败日期进重跑队列不阻塞

## 纪律
- 试点 4 日期（20150807/20150722/20151013/20150911）登记进 PRE_REGISTRATION quarantine 附录：可作 train，永不进 test manifest
- 20171111 继续全用途隔离
- 与 hrrr-v1 臂同日期可并存（独立实验），但禁止混 tag
