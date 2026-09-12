# 样本独立性论证（受体聚集性 + 日期多样性实测）

日期：2026-09-09 · 状态：数据实测支撑 pre-registration 的日期块切分决策
关联：PRE_REGISTRATION_v1.json（独立单元=日期；blocked split；≥20 独立测试日）

## 1. 问题

120 受体/区/日来自 OCO-2 沿轨 maximin 采样。若受体在空间上高度聚集、
同日足迹近乎相同，则：
- 按受体随机切分 train/val → 泄露（孪生样本跨 split）；
- 有效样本量 = 日期数而非受体数；
- 少日期训练 → 记忆"该区该季节典型足迹"而非"气象→足迹"映射。

## 2. 实测一：同日受体最近邻距离（OCO-2 沿轨聚集）

| 区域 | 日期 | 最近邻距离 min / med / max |
|---|---|---|
| po_valley_italy | 20171023 | 1.0 / 1.6 / 3.0 km |
| north_china_plain | 20170626 | 0.2 / 0.8 / 14.8 km |
| so_cal_LA_basin | 20171111 | 1.4 / 2.5 / 7.5 km |

足迹网格为 128×128 @ 4 km → 相邻受体常落在同一/相邻像素内，
**受体不是空间独立样本**（最近邻 << 足迹空间尺度）。

## 3. 实测二：足迹相似性（po_valley_italy, p250 已产 footprint）

| 比较 | Pearson r 中位 |
|---|---|
| 同日 20171023 内两两 | 0.932 |
| 同日 20150813 内两两 | 0.990 |
| **跨日** 20171023 vs 20150813 | 0.729 |

- 同日足迹 r≈0.93–0.99：同一气象场 + 受体 <3km → 近复制样本。
- 跨日 r≈0.73：气象差异带来的足迹变化真实存在，但小于日内噪声区分度。

## 4. 结论：切分单元必须是日期，不是受体

PRE_REGISTRATION_v1.json 已冻结并获实测支持：
- within_region_split = 按时间块 blocked，禁止随机日期拆分；
- statistics：独立单元=日期；cluster-robust SE（按日期聚类）；
  ≥20 独立测试日期才下正式推断；val 有效日 <5 禁止显著性结论。
- 隔离：20171111（noise-floor/冒烟）永久不得进正式 test。

## 5. 日期多样性现状（季节 × 年度）

| 区域 | n日期 | DJF冬 | MAM春 | JJA夏 | SON秋 | 年度 2015/2016/2017 |
|---|---|---|---|---|---|---|
| po_valley_italy | 11 | 4 | 2 | 3 | 2 | 3/4/4 |
| north_china_plain | 11 | 3 | 4 | 2 | 2 | 4/6/1 |
| so_cal_LA_basin | 6 | 2 | 1 | 2 | 1 | 2/3/1 |
| cent_valley_CA | 6 | 2 | 1 | 1 | 2 | 2/2/2 |
| permian_westTX | 6 | 1 | 2 | 0 | 3 | 2/2/2 |
| co_front_range | 5 | 1 | 1 | 1 | 2 | 2/2/1 |

观察：
- po/ncp（ERA5 主线两区）11 日 × 四季 × 3 年度——季节与年际覆盖良好。
- 美国 4 区仅 5–6 日/区，其中 permian **缺 JJA 夏**；单区季节覆盖偏薄。
- 每区有效独立单元 = 日期数（5–11），距 pre-reg 的"≥20 独立测试日"
  做正式推断尚有缺口 → 主数据生产（美国区 ERA5 下载 23 目标日）
  将把美区抬到 ~6+23/4≈11–12 日/区级别，仍建议后续按密度继续扩日。

## 6. 泛化性风险与缓解

风险：少日期 → 模型可能过拟合区域季节足迹分布。
缓解（已有/规划）：
1. 日期块切分 + 日期级统计（pre-reg 冻结）；
2. 6 区 LORO + 双留出（permian/co_front_range 跨地形）；
3. ERA5 主数据线跨 2015–2017 三年度四季扩日（进行中）；
4. 同日期 HRRR×ERA5 配对臂（exp2）检验跨气象源稳健性；
5. 报告逐样本 + 按日期聚合两档指标，禁止 pooled 抵消。

## 7. 引用材料

- 受体 CSV：data/receptors_v2/<region>/receptors_<date>_n120_maximin.csv
- provenance：同目录 *.provenance.json（bbox/counts/maximin/seed）
- footprint：/root/work/stilt/out/by-id/era5-v1-po_valley_italy-<date>-p250_*/*_foot.nc
- 相似性测量脚本：/root/foot_sim.py（日内/跨日 r）
- 间距测量：/root/rec_spacing.py（最近邻 km）
