# 评审意见逐条响应与协议修订 v2（2026-09-04）

## 0. 结论：以下修订全部纳入正式协议，写入本文件 + PLAN_GLOBAL.md + RUNBOOK，执行时以此为准。

## 1. STILT 噪声天花板 → 强制 self-baseline（noise floor）
- 修订：任何模型比较前，先对“同一批受体”跑 STILT p250 与 p1000（每区选 ≤30 受体 × 全试点日期），算逐样本 r/RMSE/JS/Overlap 的 **self-baseline 分布**。
- 报告：所有臂（含基线）指标以 self-baseline 为标尺归一化（如 相对噪声可达率 = (模型误差/自噪声) 或按 (r_model - r_noise) 报告 Δ），并附 bootstrap CI。
- 若 self-baseline 过低（r<0.7 等阈值），上调训练粒子数或改评评分位数/网格聚合指标。

## 2. 留出区与地形混淆 + train-mean 基线缺陷
- 修订区域角色：留出区增加 **permian_westTX（非山脉，半干旱平原）作为第二留出对照**；co_front_range 保留为“最难地形诊断区”（非唯一泛化证据）。
- 执行 **leave-one-region-out (LORO)** 系列：5 训练区轮换留出，主结果报告 LORO 平均 + 每区独立指标。
- 零参数基线：**train-mean 仅作最低检查，不作为主要基线**；新增**风场驱动零参数基线**（由同一气象输入按常速平流/局地风聚类构造的先验足迹，无训练参数）并在相同 self-baseline 标尺下报告。
- 记录山区“难”来源分解：zagl5m + 山地 OCO-2 + ERA5 0.25 地形代表性 → 作为诊断项（分升/山脊/谷地子集报告），不并入主 claim。

## 3. GenGHG 臂 apples-to-oranges → 独立实验
- GenGHG（GFS / 2019-25 / 192² 6°域）与本自建（ERA5·HRRR / 2015-17 / 128² 4km 半窗）**报告为两个独立实验/两个独立章节**，禁止叙述为同一 benchmark 的两条臂；各自独立 test manifest。

## 4. 气象源对照的季节混淆
- HRRR 对照臂（SoCal）只与 **同一批日期的 ERA5 SoCal 子集**做配对对照（同日期同受体），避免“气象源效应 vs 季节效应”混淆。
- 时间窗统一：ERA5 主线 2015-01~2017-11；HRRR 对照在重叠月份内选日。

## 5. 有效样本量与聚类
- 独立单元 = 日期（同一日期内天气相关）。配对检验使用 **按日期聚类的 cluster-robust SE**；辅以日期级聚合分析；样本量描述写“N_receptor 个观测 / N_date 个独立日期”。
- co_front_range 日期池 29 → 若不足，放宽到 ≥60 受体日期并保证 ≥20 个独立测试日期。

## 6. 指标预注册（正式实验前冻结进 manifest）
- log10(x+offset)：offset 冻结为 1e-4 × 参考足迹中位数；JS/overlap 按 128² 网格 + 5km 空间平滑核定义；逐样本 + 日期聚合两级均报告。
- Pearson r 与 RMSE 均在 (a) 原始值 (b) log 域 (c) 幅值归一 三版同报。
- 以上与 split/seed/formal-test 规则一起写入 pre-registration JSON（sha256 冻结）。

## 7. 系统时钟 8h → 科学时间戳统一真实 UTC
- 所有 provenance/manifest/CDS 请求记录统一使用 offset 校正后的真实 UTC（helper: now_true_utc = naive_local + measured_server_offset）；OCO-2/ERA5/HRRR 文件时间本身为绝对真 UTC，仅本地脚本时间戳需校正。已在接收器/OSS 签名沿用；新增 provenance 时间戳函数。

## 8. formal_test 一次性语义
- 旧 5 个正式测试日期属 SoCal-HRRR 线，**不得**复用于新 ERA5 全球线；ERA5 线定义**自己的 test manifest**（新增独立未触碰日期子集，一次性消费，.used.json 机制沿用）。

## 9. 预训练同源质疑 → pretrain pool 扫描
- 增加预训练池规模消融：1×/3×/10×（及 0=仅监督对照）在固定下游评测下报告，以支撑“自监督不是多看几遍”的叙事；预训练气象快照与监督标签字段来自同批真实场（诚实标注），用跨源/额外无标签快照补充独立信息。


## v2.3 self-baseline 统计学修正（评审点4）
- 承认：MC 噪声 ∝ 1/√N；r(p250,p1000) 是两含噪实现的互相关（衰减），而模型学条件均值，对 p1000 真值的上限 = r(真值,p1000) 可**合法高于**该互相关 → self-baseline 不是硬天花板，禁止“超 noise floor 即异常”解读。
- 修订协议：
  1) 留出区/验证受体（及 self-baseline 子集 ≤30/区）改为跑 **两个独立 p500 半样本** + 保留 p250 对照（p250 仅供“实现噪声下界”参考）；
  2) 参考足迹 = 两 p500 合并（≈p1000 池）；
  3) 参考自噪声：split-half r(p500a,p500b) + Spearman-Brown 外推（r_pp≈2r/(1+r)）估计“对无噪声真值”上限；
  4) 报告分离：模型误差 vs **p250 实现噪声**、模型误差 vs **p500 半样本(p1000)参考噪声** 两栏 + 合并参考指标；结论只在与参考自噪声同量级口径下比较。
- 计算预算：仅评估子集按 ~2×(p250 成本) 增量，可接受。


## v2.4 co_front_range 诊断去混淆（评审点5）
- 承认：ERA5 0.25°(~25km) 在落基山前缘无法解析地形流 → 该区 STILT 标签本身含系统性失真；“跨地形最难”结论与“标签退化”在当前设计不可分。
- 修订：co_front_range 诊断区要求 **双气象源标签子集**：同一批受体/日期，分别用 ERA5(0.25°) 与 HRRR(3km) 驱动 STILT（CONUS 内可行），比较两套标签；
  - 若模型误差集中在 ERA5↔HRRR 标签分歧大的受体/日期 → 归因“标签退化”；
  - 若在标签一致处仍差 → 才支持“真实跨地形泛化缺口”；
  - 结论写论文前必须附该交叉验证。
- 预算：co_front_range 3-5 日期 × 60 受体 × p500(双源) 子集（HRRR met ~9GB/日，走既有管线）。

## 执行顺序修订
0. pre-registration JSON（指标/split/seed/test manifest）冻结
1. self-baseline（p250 vs p1000 共享受体）→ noise floor
2. 6+1 区（5训练+permian第二留出对照+co_front最难诊断）LORO 主实验
3. GenGHG 独立实验；pretrain pool 扫描；HRRR×ERA5 同日期配对对照
4. XCO2 真实观测对照（二期，SoCal Hestia 先行）