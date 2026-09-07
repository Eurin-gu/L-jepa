# 贡献声明 / 问题定位 / 对比基线 / 意义（v1.0，供 pre-reg v1.1 并入）

## 1. 一句话意义主张（可再改写）
“**高分辨率、多地形、真实受体几何的地表通量敏感性（surface flux sensitivity）足迹算子**：用轨迹感知的 Lagrangian-JEPA 隐空间预训练，在跨区域/跨地形/跨期的样本外输送上获得比空间掩码 JEPA/Met-MAE/U-Net 更稳健的泛化——为城市与地面 GHG 监测提供毫秒级、可验证的 STILT 替代算子，并开源首个该口径的多地形基准。**（本 claim 严格限于地表影响核，不宣称柱 XCO2 物理）**”

## 2. 任务与对象定义（措辞纪律）
- 目标：K(r | M, q)：受体 q 处、气象 M 下 24h 回溯的**地表通量影响核/足迹**（STILT 5m 面足迹，schema-v5，128²@4km）
- 非目标（明确排除）：柱 XCO2 足迹（X-STILT）、GenGHG 合成、全浓度场预测
- 术语：全文使用 surface flux sensitivity / surface influence kernel / back-trajectory surface influence；禁止等同 “XCO2 footprint operator”
- 桥接：保留 X-STILT 柱对照子集（面 vs 柱差异量化，二期），并在 XCO2/卫星语境里仅作 external sanity

## 3. 与既有文献/工作的定位
- 同族-地面档：STILT (Lin 2003)、Gerbig 2003（近地面浓度足迹）、城市 STILT 反演（LA/INFLUX/东京/成都-重庆等）→ 我们 = 这些量的**学习代理 + 基准**
- 同族-卫星档：X-STILT (Wu 2018)、FootNet v1 (GMD 2025，柱足迹 emulator, ~650×) → 互补而非上下位；正式对比仅在同口径（柱）子集进行并注明
- 方法线：I-JEPA/V-JEPA、Met-MAE、FourCastNet/FNO、temporal U-Net → 统一算法规格下比较（同 encoder/参数量/预算）

## 4. 对比基线表（正式实验必跑）
| 类别 | 基线 | 说明/用途 |
|---|---|---|
| 零参数 | train-mean（形状均值）| 最低检查，防“赢平均值”假象 |
| 零参数 | 风驱动先验（常速平流/局地风高斯先验足迹）| 证明学习模型的增益来自数据而非风场形态 |
| 经典 | 岭回归/浅MLP（受体+气象统计量）| 线性/浅容量上界参考 |
| 结构 | U-Net / U-Net++（同 FootNet 主干）| 常见强监督基线 |
| 结构 | FNO / GNO、Temporal U-Net | 谱/时空算子基线 |
| 表示 | Scratch（同结构有监督）| 自监督增量 = 与 scratch 之差 |
| 表示 | Met-MAE（气象掩码自编码）| 气象域自监督对照 |
| 表示 | Eulerian-JEPA（空间掩码）| 检验“沿轨迹 vs 空间掩码”是否重要（核心消融）|
| 表示 | **Lagrangian-JEPA（本工作）** | 轨迹感知掩码预测 |
| 真值标尺 | 同受体 STILT 全量 + p500 split-half | 谁都不许超对无噪声真值上限；噪声归一化报告 |

## 5. 评价协议（并入 PREREG v1.1）
- 指标：Pearson r / RMSE / relRMSE（raw、log10(x+1e-4·med)、amp-norm 三版）、JS/Overlap(128²+5km核)、Mass error、Center/Peak km、Coverage；逐样本不 pooled + 按日期聚类统计
- 噪声标尺：split-half p500a/b + Spearman-Brown；模型 vs p250噪声、vs p1000参考噪声分栏
- 切分：时间块 blocked 的区内外 split；train/val 按日期；≥2 独立留出区（permian 独立、co_front 诊断+HRRR双源）；LORO 主结果；正式 test 一次性 (.used)；era5/hrrr/gdas 各自 tag 与 test manifest；隔离日 20171111 及试点 4 日不进 test
- 数据集规模目标：主实验 ≥10k 真实 OCO-2 样本（p250 训练；eval/留出 p1000 子集）多地形多时期

## 6. 意义分层与证据计划
1. 方法学：L-JEPA vs 空间JEPA/Met-MAE/U-Net 的跨地形/跨期/跨源泛化增益（主实验）
2. 应用：城市/地面 GHG——STILT 替代速度（测 ms/sample vs CPU-min）、清单正向验证路径（Hestia/ODIAC）
3. 数据：开源多地形 4km 地表影响核基准（真实 OCO-2 受体几何 + 真实 STILT 标签 + 噪声标尺）
4. 科学桥接：X-STILT 柱对照子集 + （若可得）真实地面/塔/机载观测外部验证

## 7. 待定（提交 pre-reg 前需你确认）
- [ ] 意义主张措辞是否采用/改写
- [ ] 是否允许把“X-STILT 柱对照子集”写进主实验（推荐）
- [ ] 真实观测外部验证的可用数据源（SoCal 塔？机载？先查本地 co2_data/hestia）
- [ ] 是否发布基准的开放范围（论文后）