# Lagrangian-JEPA / JEPA-FootNet 本地研究全蓝图（BLUEPRINT v3，2026-09-05）

## 0. 一句话
在本地（Windows11+WSL2+RTX5070 8GB，数据盘 D 约 60GB 余量）建立可复现研究环境：**真实逐日 OCO-2 受体 × 同源气象(HRRR/ERA5) × 真实 STILT 足迹 → schema-v5 数据集 → JEPA 预训练+有监督微调 → 双留出/LORO 泛化评估（以 STILT 粒子自噪声为标尺）**。

## 1. 总览与设计约束（来自评审 1-5，全部已落 plan 文档）
- 标签只用真实 STILT/X-STILT（禁代理/克隆）；铁律：特征与标签同气象源同时次、混源必须换 tag+新 manifest、正式测试一次性。
- 粒子噪声不是硬天花板：参考自噪声用 p500 两个独立半样本 split-half + Spearman-Brown 估计；模型 vs p250噪声、vs p1000参考噪声分开报告（v2.3）。
NaN
- 5m 足迹 = “地表通量敏感性算子”仅限算子学习；XCO2 观测对照二期必须走柱灵敏度（多高度 F(z) 加权）（评审2）。

## 2. 数据说明
### 2.1 资产（已本地化，均在 D:\lagrangian-jepa-cn）
| 资产 | 规模 | 位置/说明 |
|---|---|---|
| footnet_jepa 代码+结果 | ~80MB | mirror\server_backup_20260830\footnet_jepa\ |
| 正式 data（prod v3/v4/v5、strict、单日） | 20.2GB | data\...\footnet_jepa\data\ |
| GenGHG v1.0 | 36GB/48,282 | data\genghg\（train38442/val5210/test4630） |
| 2016-17 STILT reuse 标签+特征 | 30.3GB | reuse_stilt\（hrrr-analysis-* foot.nc/traj.rds + production_v1 model_features npz） |
| STILT 引擎 + data2arl 源码 + era5 样例 | 0.4GB | toolchain\ |
| 受体表 6 区×试点日期 | 35 张 | data\receptors_v2\<region>\ + 正式 19 张 footexp_data\stilt_receptors_v1 |
| OCO-2 Lite 2015-2017 | 918 文件 | D:\co2_data\nasa\oco2_l2_lite_fp_11.2r |
| 整桶清单 | manifest.csv | planning/oss_work 备份 |

### 2.2 数据臂（三个，独立 tag/manifest）
- **hrrr-v1（对照/正式 arm）**：SoCal + CONUS 试点日期用 HRRR(3km)；已本地正式 2016-17：train 10 日(1200) + val 2 日(240) + formal_test 5 日(600 未消费) + so_20171111(120)。
- **era5-v1（主线/全球多地形）**：六区（so/cv/tx/cf/po/ncp）× 试点日期，ERA5 0.25° 驱动 STILT；CDS 限流中逐步到货（ncp 两天已转 ARL、po 待补）。
- **GenGHG（独立实验）**：GFS 城市热点 48k，城市级留出，192²/6° 域；独立章节与 test manifest。

### 2.3 样本定义（schema v5，物理足迹）
- 输入 x(20,128,128)@4km 受体中心窗：ch0 受体脉冲；ch1-16 = 4×[U10M,V10M,PBLH,PRSS]（run_time 回推 0/6/12/18h，双线性插值+归一化 MET_OFFSETS/SCALES）；ch17-19 = (x/half, y/half, radius/half)。
- 标签 y(128,128) = STILT 24h 表面足迹（stilt_surface_sensitivity，物理单位不归一；保守重采样到受体中心 4km 网格；min coverage 0.8）。
- 受体：真实 OCO-2 逐日（QC: flag==0, 350<xco2<450；maximin, seed 20260822；区域 bbox）。
- 粒子数：train p250；val/test/holdout p1000；self-baseline 用双 p500。
- 建集器：data\build\assemble.py + feature_sources.py(npz_hrrr / grib/era5) → x/y/meta（contract fingerprint v5），validate_dataset.py + 真实 load_dataset 双校验。

### 2.4 规划矩阵（试点，era5-v1 主线）
- so_cal_LA_basin(6日)/cent_valley_CA(6)/permian_westTX(6)/po_valley_italy(1首日+扩展)/north_china_plain(1首日+扩展)/co_front_range(5 诊断+HRRR 双源) + 既有正式 arm；后续按 LORO 与扩量需求加日期。

## 3. 训练说明
### 3.1 任务与两阶段
- 阶段A 自监督预训练（JEPA/Met-MAE）：无标签气象快照（可来自不同受体/日期，不需 STILT）学表征；预训练池规模消融 0/1×/3×/10×。
- 阶段B 有监督微调：冻结/微调 encoder + 头，预测物理足迹；或 scratch 从头有监督对照。
### 3.2 臂（7-arm 起，可扩展）
scratch | e_jepa | l_jepa(lagrangian 轨迹掩码) | met_mae | unetpp | fno | temporal_unet（同一 backbone 族 + 每种 5 seeds；统一参数量/epoch/batch/优化器）。
### 3.3 超参与 8GB 显存适配
- grid128 输入；默认 BATCH=8→若 OOM 用 4-8+AMP(bfloat16)+梯度累积；25-100 epochs(按臂)；LR 1e-3(sup)/3e-4(JEPA)；EMA 0.996；mask 0.3-0.6；VISReg λ0.5。
- 预训练 JEPA 目标：掩码 patch 隐特征回归(余弦)；防坍缩 EMA+正则。
- 执行入口：train_stilt_strict.py（正式协议，哈希/契约/一次性 test）；训练在 WSL GPU venv（/root/venvs/ml，torch cu130 sm_120）。
### 3.4 划分（data 协议）
- 训练/验证按日期隔离；正式 test 5 日一次性消费（.used.json 机制），新 era5 线定义自己的 test manifest；LORO 轮换留出（每区独立）；co_front/permian 双留出对照；日期聚合统计。

## 4. 算法说明
### 4.1 基础：JEPA（联合嵌入预测）
- Online encoder E_θ + Target encoder E_ψ(EMA 不更新梯度)；输入块掩码→从可见块预测被掩块隐表示；损失余弦/MSE on ℓ2-normalized features；防坍缩：EMA target + 正则（VISReg/SIGReg 分布熵）。
### 4.2 Lagrangian-JEPA（本工作核心）
- 沿后向轨迹做掩码预测：由风场/受体生成轨迹点(compute_trajectory_xy 或输入风场轨迹)，在 latent 场上采样可见/被掩轨迹点；TrajectoryPredictor 用距离注意力聚合可见点预测掩点；EMA 目标；整体 loss = 轨迹预测 + 正则。
### 4.3 各臂差异
- met_mae：Eulerian 随机掩码 MAE 式回归气象场；e_jepa：patch 掩码 JEPA；unetpp/temporal_unet：直接有监督的编解码/时空 U-Net；fno：谱域算子。
### 4.4 有监督头与输出
- 输出足迹（softplus 幅值头，schema v5 物理）；损失：像素(加权)+幅值+形态(Jensen-Shannon/形状 KL)多尺度；训练中冻结存档 train-mean 与风场零参数基线。

## 5. 指标与统计说明
### 5.1 逐样本指标（预注册，定义冻结进 manifest）
- Pearson r（原始、log10(x+1e-4·med)、幅值归一 三版）、RMSE（同三版）、JS 散度/Overlap（128²+5km 平滑核）、质量守恒误差、中心距离(km)、峰值距离(km)、覆盖率。逐事件不 pooled。
### 5.2 噪声标尺（self-baseline，已实现）
- 同受体 p500a vs p500b split-half r（实测 SoCal 0.987）→ Spearman-Brown 估计对无噪声真值上限；p250 与 pooled(p1000) 单独列；模型指标与参考自噪声同量级口径比较，禁止“超 noise floor=异常”解读。
### 5.3 统计
- 独立单元=日期；配对检验 cluster-robust SE(按日期) + 日期级聚合；显著性与 CI 用 bootstrap。
### 5.4 GenGHG 独立指标**（域192²/6°，城市级 split；用其官方评测口径 + 相同通用指标双报）。

## 6. 执行路线（阶段）
- 0 资产/环境/协议 ✅（完成度见终态快照）
- 1 数据：era5 主线到货→ARL→逐(区,日)120批（后台进行）；CV-HRRR 下载→批；formal 全arm ✅
- 2 建集：多日期合并数据集（train all/val all/test untouched + LORO 子集）
- 3 预训练池与 JEPA/MAE 预训练（含规模扫描）
- 4 正式训练：7-arm×5-seed（scratch/…/l_jepa）→ results/<run-id> 固化
- 5 评估：双留出/LORO + self-baseline 标尺 + pre-registered 指标 → 报告表
- 6 补充：HRRR×ERA5 同日期配对、GenGHG 独立实验、pretrain 消融、XCO2 柱灵敏度(二期)

## 7. 风险与缓解
- CDS/GCS 对本机限速 → 保守单拉取/重试、错峰；OSS 已全量本地不依赖。
- ERA5 0.25 vs HRRR 3km（co_front 地形标签质量）→ HRRR 双源子集交叉验证（v2.4）。
NaN
- 盘余量 ~60GB → 批后清理 grib/小时 ARL；必要时扩展/清理。
- formal test 一次性 → 新线独立 manifest；.used.json 机制。
- 复现性 → 时钟偏移修正、真 UTC 时间戳、manifest/sha 双向锁定、pre-registration 冻结。

## 8. 产物与日志位置
- 数据集 data\datasets\；构建 data\build\（日志 build_<date>.log、ARM_BUILD_REPORT.md、arm_final_summary.csv）
- 训练 results 遵循 train_stilt_strict run-id 结构；计划/协议 planning\*.md；WSL 日志 /root/**/*.log

## 9. 当前后台任务（独立运行）
- era5 safe/sfc fetcher（CDS 限流重试）→ 到货自动转 ARL；CV-HRRR（GCS 限速爬行）；(建集器已交付 formal arm 全量)。

## 10. 下一步（自动）
era5 放行后：ncp/po/so/cv/tx/cf 转 ARL+批 → 各 arm 数据集合并 → 预训练/训练 → 双留出评估。需要“继续”时本蓝图即执行手册。

## 11. 数据/代码位置速查
D:\lagrangian-jepa-cn\ : mirror(代码) · data\datasets(数据集) · data\build(建集) · reuse_stilt(复用标签) · toolchain(引擎/转换器/WSL脚本) · planning(协议/蓝图/快照) · met_cache(HRRR grib 缓存)