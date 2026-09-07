# 全球多地形 · 真实STILT · 留出区泛化 试点方案（用户2026-09-04确认稿）

## 已锁定决策
- 地理：全球为主；时间窗 **2015-01 ~ 2017-11**（本地 OCO-2 lite 918 天全档，era5 全球全覆盖）
- 气象源：**ERA5 0.25° 全球** 为主（新 tag: era5-v1）；SoCal 保留原 2016-17 HRRR 正式线（tag: hrrr-v1）作对照臂；铁律：混源必须换 tag + 新 manifest
- 标签：**只允许真实 STILT/X-STILT 足迹**（禁粒子代理/克隆假数据）；保留全部审计溯源（sha256/manifest/一次性 formal test）
- 受体：真实逐日 OCO-2 lite（本地档）QC + maximin（make_receptors.py 配方，bbox 按区），train p250 / val·test p1000
- 区域（OCO-2 2015-17 密度日期数）：
  | 区域 | bbox(lat,lon) | 地形/类型 | 角色 | 密度≥120 |
  |---|---|---|---|---|
  | so_cal_LA_basin | 32-35, -119..-116 | 海岸盆地/城市 | train | 94 |
  | cent_valley_CA | 35-39.5, -122..-118.8 | 农业谷地 | train | 95 |
  | permian_westTX | 30.5-33, -103.8..-101 | 半干旱平原/油气 | train | 70 |
  | po_valley_italy | 44.4-45.9, 8..12.2 | 欧陆盆地/农城 | train | 70 |
  | north_china_plain | 38.2-41, 114.2..117.6 | 东亚城市平原 | train | 39 |
  | co_front_range | 38.5-40.6, -106..-104 | **山脉/高原（留出）** | test-holdout | 29 |
- 评估：留出区 = 科罗拉多山脉（跨地形最难泛化）；FootNet 式：预测足迹 vs 留出区全量 STILT(p1000) 参考足迹（Pearson r/RMSE/JS/Overlap/Mass/中心距/峰值距等，逐样本不 pooled）；后阶段加真实 XCO2 正向模拟对照（Hestia/ODIAC/EDGAR/CAMS，SoCal 先行）
- GenGHG v1.0（48,282 真实 STILT 城市足迹, GFS, 36GB）：已开始整体下载作为全球城市基准臂（train/val/test 已按城市内置；x=GFS 112×24×24, y=192×192）
- 节奏：先区试点（3-6 日期/区 ≈ 2-4k 样本）→ 留出评估 → 决定扩量（1万-4万）


## v2 协议修订（2026-09-04，详见 DESIGN_REVIEW_RESPONSE.md）
- 主留出区改为 **两个**：permian_westTX（非山脉对照留出）+ co_front_range（最难地形诊断区，非唯一泛化证据）；并执行 leave-one-region-out 全轮换。
- 角色调整后训练区核心 = so_cal_LA_basin / cent_valley_CA / po_valley_italy / north_china_plain（4），另两区（permian、co_front）作独立留出与 LORO 轮换成员。
- 强制步骤0：pre-registration JSON（指标 offset/平滑核/split/seed/test-manifest 冻结）。
- 强制步骤1：self-baseline（同受体 p250 vs p1000）→ noise floor，全指标归一化报告。
- 基线：train-mean 降级为最低检查；新增风场驱动零参数基线。
- GenGHG 与自建数据为两个独立实验；HRRR×ERA5 同日期配对；新线独立 test manifest；按日期聚类统计；科学时间戳统一真实 UTC。


## v2.1 数据来源：复用 OSS 既有真实 STILT 输出（用户确认可用）
- 桶内 stilt/out/by-id 现存真实 STILT 批：hrrr-analysis-2016*(2,160 文件/18.4GB)、2017*(1,920/13.4GB)、2024 严格(722/10.2GB, 0402/0403/0705)、global-24*/gdashi(2024 GDAS 噪声对照,不用于正式)
- 复用范围(下载中→D:\lagrangian-jepa-cn\reuse_stilt)：2016-17 hrrr-analysis 标签(foot.nc/traj.rds, 31.7GB) + production_v1 正式日期 model_features/受体/清单(0.8GB)
- 2024 严格集标签暂缓（其 npy 已在本地）；需要时再下 10.2GB
- 分工：2016-17 SoCal 正式日期 = 复用现有标签(免重跑)；**新日期/新区域(6区试点) = 本地 WSL STILT 自跑**；自跑标签与复用标签统一 schema v5 + 同协议


## 评审点（2）：zagl=5m 地表足迹 vs OCO-2 柱观测 —— 物理错配
- 判定：当前 5m 地表足迹 = “地表通量敏感性足迹算子（surface-flux sensitivity footprint）”，仅用于算子学习 benchmark 与 CVPR 运输表征故事，**自洽，可保留**。
- 禁止：把 5m 足迹直接卷积地表排放去逼近 OCO-2 柱 XCO2 并宣称物理正确。
- 补救（二期观测对照必须走柱灵敏度）：
  1) 对 XCO2 验证 (区域,日期) 子集，用同一 STILT 引擎跑**多起始高度** {5m,100,300,800,1500,3000,6000m}，逐高度存档 F(z)（分级足迹），
  2) 用 OCO-2 压力权重/先验+AK 近似构造**柱灵敏度** F_col = Σ_z w_z F(z)（模型与参考同式），
  3) XCO2 增强 = F_col ⊗ 排放(ODIAC/EDGAR/Hestia) + 背景，再与观测比；
  4) 报告里明确区分：“地表足迹算子”（benchmark 指标）与“柱模式前向模型”（观测对照）为两个产品，禁止混用结论。
- 执行标记：二期新增“柱灵敏度批”子任务；一期所有声称仅限“5m 地表足迹算子”。


## v2.2 标签/特征同源纪律（评审点3）
- **铁律**：任何样本的输入特征与其 STILT 标签必须来自同一气象源、同一循环时次（HRRR 配 HRRR，ERA5 配 ERA5）；特征 npz 的 source sha 与标签 met manifest 双向锁定。
- **复用 HRRR 标签只允许进 hrrr-v1 对照臂**（SoCal，HRRR 特征+HRRR 标签，同源自洽）；禁止把 HRRR 驱动标签混入 era5-v1 训练池。
- era5-v1（主线，六区试点）：每 (区域,日期) = ERA5 特征(同源 grib) + ERA5 驱动 STILT 自跑标签；CONUS 区亦按此执行（不改用 HRRR），HRRR 仅作 SoCal 对照臂。
- 本机已跑 SoCal 2017-11-11 (HRRR) 等自跑标签 → 归 hrrr-v1 对照臂（含与同日 ERA5 的配对源对照实验）。
- 如需把某正式日期放进 era5 池：必须用 ERA5 重跑该日期 STILT（新 manifest），文档明示例外+论证后才可。


## 建集器里程碑（子代理交付 2026-09-05）
- 代码：D:\lagrangian-jepa-cn\data\build\{assemble.py, feature_sources.py, validate_dataset.py, features_hrrr_20171111.json, BUILD_REPORT.md}
- 产物：D:\lagrangian-jepa-cn\data\datasets\so_hrrr_20171111\{x.npy(120,20,128,128), y.npy(120,128,128), meta.json}，schema v5/physical/stilt_xstilt
- 校验：复刻器 PASS + 真实 train_stilt_strict.load_dataset PASS（120 唯一）
- 实测：HRRR wrfprs 内含 U10M/V10M(10u/10v@10m)、PBLH(blh)、PRSS(sp)；ERA5 SFC(typeOfLevel=surface) 选择器已适配
- 注意：LCC 原点与归档 grib 差 ~500m(1%) 未逐字节对齐服务器；无 meteorology_features receipts(非 same-cycle 声明)；单日期不满足 ≥5 正式测试日期 → 需多日期后再定 formal test manifest

## 待办状态
- [ ] pwsh-5：GenGHG 36GB 下载（后台进行中）
- [ ] pwsh-2：py311+torch cu128 环境（后台进行中）
- [ ] 子代理：HRRR/ERA5 存档与 Windows STILT 工具链调研（进行中）
- [ ] 生成 6 区 × 试点日期的受体表（make_receptors.py, bbox 按区）
- [ ] ERA5 2015-17 全球逐日期下载（CDS/era52arl→ARL 管线；按日期 ~3-5GB）
- [ ] STILT 工具链落地（WSL2 或等价）→ 逐日期 run_batch p250/p1000
- [ ] schema v5 data_builder/merge（footnet 契约 20ch/128²）+ 指纹
- [ ] train_stilt_strict / train_lagrangian_jepa 本地 GPU 正式协议
- [ ] 留出区评估 + （二期）XCO2 观测对照
