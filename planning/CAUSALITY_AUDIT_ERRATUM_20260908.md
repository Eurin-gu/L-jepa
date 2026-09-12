# 伪轨迹因果审计（L-JEPA No-Go 判定）更正声明

日期：2026-09-08 · 状态：正式更正 · 上游文档：无（此前判定仅存于对话，未落文档）

## 1. 背景

2026-09-08 运行 `run_ljepa_causality.py`（footnet_jepa 下，7 臂 × 3 seeds，
val_date=20160428，n_val=120）检验"掩码须沿真实入流方向"（L-JEPA 核心主张）。
驱动器：`mirror/server_backup_20260830/footnet_jepa/run_ljepa_causality.py`
结果：`/root/causality_run1/causality_20160428.json`（21 行）
日志：`/root/causality_run1.log`（258 行）
代码：`lagrangian_jepa.py` L183-211 `apply_trajectory_transform`（none/reverse/perp/random_heading）
  + models.py MeteorologyTubularMAE（L~351）

## 2. 原始结果（date-macro Pearson r，3 seeds）

| 臂 | r（均值±std） | relRMSE* | 含义 |
|---|---|---|---|
| scratch | +0.1194 ± 0.1289 | 0.019 | 随机初始化监督基线 |
| met_mae | +0.1905 ± 0.2238 | 0.018 | 随机块掩码预训练 |
| met_tubular | +0.0510 ± 0.0407 | 0.019 | 随机朝向管掩码 |
| lj_true | +0.0952 ± 0.0577 | 0.019 | 真入流轨迹掩码 |
| lj_reverse | +0.1574 ± 0.1422 | 0.019 | F1: −u,−v |
| lj_perp | +0.0712 ± 0.0237 | 0.019 | F2: −v,u |
| lj_rand | +0.1460 ± 0.1667 | 0.020 | F3: 随机固定朝向 |

*注：该列实际是 `raw_rmse`（全像素绝对 RMSE，见 E5），不是相对误差。

配对 t 检验（vs scratch）全部 p>0.55。

## 3. 错误清单（已逐条核实，含代码/日志证据）

- **E1 统计功效不足，不能下 No-Go。** 独立单元是"日期"（120 受体共享当日风场），
  而实验只有 **1 个 val 日期、3 seeds**。臂间差 Δr≈0.05–0.13，seed 波动 σ 达 0.02–0.22
  （met_mae 最高 r 0.366 与最低 −0.061 同臂内出现），paired t p>0.55 只能说明
  "此设定下未检出"，不能断言"无效应"。原话"判定：No-Go"**表述错误**，应改为
  "pilot 层无支持证据（insufficient evidence）"。
- **E2 监督臂未在良性收敛区评测。** 日志显示各臂 val（criterion）自 ep≈8–16 起
  单调上升：scratch ep8 val 6.39 → ep40 val 8.19；met_mae ep16 最低 4.95 → ep40 8.06。
  `train_supervised` 虽按 val_loss 回滚 best_state，但该最低点本身已处于过拟合
  边界附近，且训练预算固定 40 ep 无平台期验证、无独立早停。
- **E3 预训练欠饱和。** 25 ep 下 met_mae loss 0.038→0.036、lj 系 0.022→0.021
  （ep20→ep25 仍下降），未到平台即转入下游；下游 40 ep 亦不足以补偿。
- **E4 主指标 Pearson 被 93.6% 零像素稀释。** `train.py metrics()` 对 128² 全展开
  （含近零背景）算 pearson。背景零区所有臂都预测≈0（一致高分），真正携带信息的
  亮核只占 ~6% 像素 → r 主要由背景决定、对亮核形态/方向几乎不敏感。memo v1.3
  已警示 per-pixel r 不适用，本审计未落实为 shape 指标（JS divergence /
  peak / centroid distance）。
- **E5 relRMSE 是误命名。** `run_ljepa_causality.py` L133 把 date_macro 的
  `raw_rmse` 直接存为 `relRMSE_date_macro`；而 `raw_rmse`（train.py L295/L302）是
  全像素（含零）绝对 RMSE，**无去零、无任何分母**。所以 0.019 对所有臂几乎相同
  = 指标不敏感，不是"误差很低"。memo 4.1 要求的"分母三把尺"（train-mean /
  噪声底 / 目标范数）未落实。
- **E6 单日期无法外推。** val 只有 20160428 一个气象日（driver 取 dates[0]），
  pre-registration 的日期级推断要求 ≥多独立日。本结果对"跨日泛化"无信息量。
- **E7 训练预算与行业惯例不符（40 ep 质疑）。** 用户正确质疑：从随机初始化训
  UNet 类模型通常 100–300 ep + LR schedule + 早停；固定 40 ep（监督）+ 25 ep
  （预训练）既不足以让预训练饱和，也把监督停在过拟合爬升段，任何一臂都未获得
  公平的"充分训练"机会。注意：单纯加长 ep 不解决 E1/E4/E5——此处问题链是
  功效+指标+评测点，epoch 只是其中一环。

## 4. 更正后的判定

> 在 1 个日期 × 3 seeds、监督臂过拟合后评测、指标被零稀释、relRMSE 误标号的
> pilot 设定下，7 臂之间**未检出显著差异**。此结果**不支持**也不**否定**
> "掩码沿真实入流方向有效"——证据效力不足，不能作为 L-JEPA 的 No-Go，
> 只能作为"欠动力 pilot 未检出信号"。

## 5. v2 审计设计（建议）

1. ≥5 个独立 val 日期（LORO 或日期分组留出）+ ≥10 seeds，配对检验按日期宏。
2. 主指标换 shape 类：mass 归一后 JS divergence / peak distance / centroid
   distance；Pearson 仅作参考并报告 zero-masked 版本。
3. relRMSE 落实 memo 4.1 分母三把尺；删除 `relRMSE_date_macro` 误命名。
4. 预训练训到损失平台（≥100 ep 或早停）+ 每臂独立 best-val 早停；scratch
   获得同等充分预算，允许 100–300 ep。
5. 训练集扩日期（与数据生产主线同步：ERA5/GDAS 多日期到货后复用）。
6. 判定标准改为 v2 生效后按 pre-registration 门槛 C 走（相对 scratch/空间掩码
   的日期级增量 + 相对噪声底归一化成绩）。

## 6. 引用材料

- 结果 json：`/root/causality_run1/causality_20160428.json`
- 驱动器：`run_ljepa_causality.py`（含 E5 证据 L133；训练预算 L39-40）
- 指标定义：`train.py` L275-338（pearson L314、raw_rmse L302）
- 训练日志：`/root/causality_run1.log`（E2/E3 过拟合曲线证据）
- memo 对口章节：JEPA_与地表足迹算子_匹配度难点与价值评估 v1.3 §3.1/§4.1/§6
