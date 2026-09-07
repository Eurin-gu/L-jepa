# Lagrangian-JEPA: CVPR 可行性分析、论文方向与实验架构

> 状态：研究规划文档
> 日期：2026-08-22
> 关联代码：`footnet_jepa/`

---

## 1. 一句话回答

**Lagrangian-JEPA 目前是一个有 CVPR 可能性的研究方向，但当前原型还不足以直接投 CVPR 主会。**

它能成为 CVPR 论文的前提是：

> 必须被包装成一种**通用的、面向物理时空场的轨迹感知自监督表征方法**，
> 而不是“又一个 CO2 footprint emulator”。

如果只是做“STILT footprint 预测更准”，那更适合 GMD/AMT/JAMES。

---

## 2. CVPR 可行性拆解

| 维度 | 当前状态 | CVPR 需要达到的状态 |
|---|---|---|
| 方法新颖性 | 已有 generic spatial JEPA | 提出 **Lagrangian-JEPA**：沿轨迹做 latent prediction，而不是随机空间 mask |
| 通用性 | 目前只用于 CO2 footprint | 在至少两个任务/两个示踪物/两个输送模型上验证 |
| 数据 | 只有 GenGHG + 代理 HRRR | 建立并公开一个 benchmark，方便审稿人复现 |
| 跨域泛化 | 未验证 | 必须有跨区域、跨季节、跨分辨率/跨模拟器证据 |
| 与现有工作差异 | FootNet / MAE / I-JEPA 已存在 | 明确对比 Met-MAE、Eulerian-JEPA、FNO、U-Net、FootNet |
| 理论/解释 | 弱 | 可以不强理论，但需要可解释的消融和可视化 |

---

## 3. 核心问题定义

### 3.1 任务

学习一个 **条件足迹算子**：

```text
输入：
    气象场 M(x, y, z, t)
    + 受体/源 query q
    + 回溯时长、高度、边界层信息

输出：
    K(x, y, tau | M, q)
```

其中 `K` 是 source-receptor sensitivity / Lagrangian footprint / 条件 Green's function。

### 3.2 为什么不做完整 CO2 场预测

完整 CO2 预测会把排放、背景、输送耦合在一起，难以分离评价。  
足迹算子只关注“输送”，标签可由 STILT 等模型生成，评价更干净。

---

## 4. 总体架构

```text
┌─────────────────────────────────────────────────────────────────────┐
│                      Lagrangian-JEPA 总体架构                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  气象场 M(x,y,z,t)  +  受体 query q                                   │
│        │                                                             │
│        ▼                                                             │
│  ┌────────────────────┐        ┌──────────────────────┐             │
│  │  Online Encoder     │        │  Target Encoder (EMA) │             │
│  │  (U-Net / ViT)      │        │  共享结构，不更新梯度   │             │
│  └─────────┬──────────┘        └───────────┬──────────┘             │
│            │                               │                         │
│            ▼                               ▼                         │
│  ┌────────────────────┐        ┌──────────────────────┐             │
│  │  Latent Field      │        │  Latent Field        │             │
│  │  z_online          │        │  z_target            │             │
│  └─────────┬──────────┘        └───────────┬──────────┘             │
│            │                               │                         │
│            ▼                               ▼                         │
│  沿后向轨迹采样 latent 特征          沿同一条轨迹采样 target 特征       │
│            │                               │                         │
│            ▼                               ▼                         │
│  ┌────────────────────┐        ┌──────────────────────┐             │
│  │ 可见轨迹点特征      │        │ 被 mask 轨迹点特征    │             │
│  │ (visible)          │        │ (target supervision) │             │
│  └─────────┬──────────┘        └───────────┬──────────┘             │
│            │                               │                         │
│            └──────────────┬────────────────┘                         │
│                           ▼                                          │
│            ┌────────────────────────────┐                            │
│            │ TrajectoryPredictor         │                            │
│            │ 轨迹相对注意力               │                            │
│            │ 用可见轨迹点预测被 mask 段   │                            │
│            └────────────────────────────┘                            │
│                           │                                          │
│                           ▼                                          │
│                Lagrangian-JEPA Pretraining Loss                      │
│                                                                     │
│  ───────────── 下游监督微调 ─────────────                             │
│                                                                     │
│  气象场 + query ──► Encoder ──► Decoder ──► Footprint K              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. 方法细节

### 5.1 轨迹来源

- 优先：GenGHG benchmark 中已有的 STILT 轨迹/footprint；
- 备选：自跑 STILT/X-STILT 生成 `traj.rds`；
- 当前原型：`lagrangian_jepa.compute_trajectory_xy()` 用 HRRR 风场生成代理轨迹。

### 5.2 预训练目标

给定一条后向轨迹上的点：

```text
t0, t-6h, t-12h, t-18h, ...
```

随机 mask 一段连续轨迹点，任务：

```text
用可见轨迹点的 latent 特征预测被 mask 轨迹点的 latent 特征
```

这比普通空间 JEPA 更符合输送的因果结构。

### 5.3 预测器

`TrajectoryPredictor`：

```text
query (masked point) 与所有 visible points 做距离注意力
→ weighted sum visible features
→ 拼接 query 坐标 embedding
→ MLP 输出预测 latent
```

### 5.4 防坍缩

- EMA target encoder；
- VISReg / SIGReg 施加在 online latent 上；
- 避免 JEPA 退化成常数表征。

---

## 6. 数据方案

### 6.1 主数据集：GenGHG v1.0 Benchmark

```text
40,000+ STILT footprint samples
2019–2025
60 个全球城市热点
GFS 气象输入
24h 后向输送
6° × 6° 局地排放域
```

这比“自己下 8 个月 GDAS + 跑 STILT”更合适。

### 6.2 补充验证数据

- 本地 OCO-2 Lite 文件；
- HRRR 真实风场；
- 自跑少量 STILT/X-STILT 作为独立验证；
- 如果可能，加 CH4 / NO2 足迹任务。

---

## 7. 实验设计

### 7.1 主消融

```text
Scratch
Met-MAE
Eulerian-JEPA
Lagrangian-JEPA
```

统一设置：

- 相同 encoder/decoder 结构；
- 相同参数量；
- 相同监督数据；
- 相同训练 epoch / batch / 优化器；
- 多种子（至少 5）。

### 7.2 跨域泛化

| 泛化类型 | 训练 | 测试 |
|---|---|---|
| 跨区域 | 部分城市 | 完全留出城市 |
| 跨季节 | 部分月份 | 独立季节 |
| 跨分辨率 | 粗网格 | 细网格 |
| 跨模拟器/气象驱动 | 一种 GFS/HRRR | 另一种气象/模型 |

第一版至少做：

- 跨区域
- 跨季节

### 7.3 指标

```text
Pearson r
RMSE
JS divergence
Overlap
Mass conservation / mass error
Center distance (km)
Peak distance (km)
推理速度 (s/sample)
```

所有指标逐事件计算，不允许 pooled 抵消。

### 7.4 对比基线

- U-Net
- FNO / GNO
- FootNet（若可复现）
- Met-MAE
- Eulerian-JEPA
- Lagrangian-JEPA
- train-mean shape（零参数基线）

### 7.5 额外验证

- 零样本跨城市；
- few-shot 微调新城市；
- 跨物种/示踪物迁移（CO2 → CH4/NO2）；
- 可视化轨迹注意力；
- 预训练表征的线性探针或迁移分类。

---

## 8. CVPR 论文故事建议

### 8.1 标题建议

```text
Lagrangian Latent Pretraining for Cross-Domain Atmospheric Transport Operators
```

或：

```text
Learning Transport-Aware Representations by Predicting Along Lagrangian Trajectories
```

### 8.2 核心卖点

1. 提出 **Lagrangian-JEPA**：沿物理轨迹组织自监督预测；
2. 不是简单 `x - uT`，而是时变、非均匀风场下的轨迹 latent prediction；
3. 在公开 STILT benchmark 上展示跨区域、跨季节、跨分辨率泛化；
4. 方法可迁移到其他物理场 / 示踪物。

### 8.3 CVPR 审稿人会问

- 和 I-JEPA / MAE 的本质区别？
- 轨迹从哪里来？如果依赖 STILT，是否只是 domain-specific？
- 能否用于图像/视频/点云等通用视觉任务？
- 是否只是把风场坐标作为 attention bias？

回答策略：

- 轨迹可来自任意 Lagrangian 模拟器，也可来自光流/粒子跟踪；
- 方法本质是 **沿流线做 latent prediction**，可以泛化到视频、气象、流体、点云跟踪；
- CO2/STILT 只是第一个强物理约束 benchmark。

---

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 被认为是 FootNet 变体 | 强调 Lagrangian-JEPA 预训练，而不是 footprint 解码器 |
| 被认为是 `x-uT` 的复杂化 | 使用时变三维轨迹 + 多回溯时长 + 轨迹注意力，不只线性平移 |
| 跨域提升不显著 | 先做跨区域/跨季节小规模 Go/No-Go，不显著就转 GMD/AMT |
| 数据太大 | 使用 GenGHG benchmark，不自己生成全部 STILT |
| 审稿人要求通用视觉验证 | 增加一个非大气任务：如视频帧沿光流预测、点云轨迹预测 |

---

## 10. 当前代码与下一步

### 已完成

- `lagrangian_jepa.py`：轨迹采样 + 轨迹注意力预测器 + Lagrangian-JEPA 模型；
- `train_lagrangian_jepa.py`：原型预训练；
- `train.py --with-lagrangian`：预训练 + 下游微调 + 测试 + 多 seed 闭环；
- `autodl_stilt_setup.sh`：STILT 环境模板；
- GenGHG 数据下载/上传中。

### 待完成

1. GenGHG 数据解压与格式解析；
2. `genghg_loader.py` 数据接口；
3. 实现 Met-MAE 和 Eulerian-JEPA；
4. 统一训练脚本，支持四种 pretraining 对比；
5. 跨区域/跨季节 split；
6. 正式实验与可视化。

---

## 11. 结论

- **能投 CVPR，但不是现在。**
- 先把 Lagrangian-JEPA 做成一个**通用轨迹感知自监督方法**；
- 在 GenGHG 上证明跨区域、跨季节、跨分辨率泛化；
- 再补一个非大气任务作为 generalizability 证据；
- 如果跨域结果不强，就退而求其次投 GMD / AMT / JAMES。

> 当前最优路径：**用 GenGHG 做真实 STILT 实验，优先验证 Lagrangian-JEPA 是否比 Met-MAE / Eulerian-JEPA 有跨域优势。**

---

## 12. 论文思路检查与补充实验

### 12.1 论文思路可能的问题

1. **定位不清**：如果只展示 CO2 footprint RMSE，审稿人会认为这是 GMD/AMT
   应用论文。CVPR 版必须证明 Lagrangian-JEPA 是一种通用的轨迹感知表征方法。
2. **新颖性陷阱**：如果 Lagrangian-JEPA 最终被描述成“沿着风场坐标做 mask”，
   审稿人可能认为它只是 `x-uT` 的复杂化。必须强调：
   - 时变非均匀轨迹；
   - latent 空间预测；
   - trajectory-relative attention；
   - 与 Eulerian-JEPA 的严格对比。
3. **数据泄漏**：跨域实验必须按城市/日期分组，不能随机打散后让同一城市、同一
   天气过程同时出现在训练和测试。
4. **公平性**：所有预训练臂必须共享相同 encoder/decoder、参数量、优化器、
   训练预算和监督 batch 顺序。否则差异不能归因于预训练目标。
5. **零参数基线**：必须报告 train-mean footprint 和简单物理 baseline。
   如果学习模型打不过零参数基线，论文不成立。
6. **多 seed 和 CI**：正式实验至少 5 seeds，并报告跨 seed 标准差和配对 CI。
7. **物理单位**：使用真实 STILT footprint 后，模型必须输出非负、带物理单位
   的幅度，不能继续使用 sum=1 的概率损失。

### 12.2 还需要补充的实验

#### A. 数据效率曲线

```text
1%, 5%, 10%, 25%, 100% labeled data
```

自监督预训练的核心价值应在低标签比例下更明显。

#### B. 跨域泛化

- 跨城市/区域：训练 80% 城市，测试 20% 留出城市；
- 跨季节：训练部分月份，测试独立季节；
- 跨分辨率：粗网格训练，细网格测试；
- 跨气象驱动/模拟器：一种 GFS/HRRR 训练，另一种测试。

#### C. 跨示踪物/跨任务迁移

- CO2 footprint → CH4 footprint；
- CO2 footprint → NOx/污染输送 footprint；
- 有条件的话，footprint → 视频光流预测 / 点云轨迹预测，证明通用性。

#### D. 表征质量探针

- 冻结预训练 encoder，线性探针预测：
  - 风场方向；
  - PBLH；
  - 上风向/下风向方向；
  - 输送距离；
- 如果 Lagrangian-JEPA 的探针精度更高，说明它学到了输送相关表征。

#### E. 消融实验

- 轨迹来源：STILT 轨迹 vs 简化轨迹 vs 无轨迹；
- 轨迹长度：6h / 12h / 18h / 24h；
- 掩码段长度：短段 / 长段；
- predictor 设计：距离注意力 / 普通 MLP / transformer；
- 正则化：VISReg / SIGReg / 无正则。

#### F. 鲁棒性与不确定性

- 对风场/PBLH/背景场做扰动，看预测 footprint 的稳定性；
- 多种子 ensemble spread；
- 对低置信样本的拒识能力。

#### G. 效率与工程指标

- 单样本推理速度；
- 与 STILT / FootNet 的速度和精度权衡；
- 参数量、显存占用。

#### H. 下游反演实验

- 将学习到的 footprint 代入简单贝叶斯反演；
- 比较 posterior 与 STILT posterior；
- 报告留出站点/时间段的浓度预测误差。

### 12.3 最低可接受标准

在 GenGHG/真实 STILT 数据上：

1. `train-mean` 零参数基线必须被学习模型显著超过；
2. `Lagrangian-JEPA` 必须在至少一个跨域场景（跨城市或跨季节）上
   显著超过 `Eulerian-JEPA` 和 `Met-MAE`；
3. 多 seed 配对 CI 不含 0；
4. 结果在 1% 或 5% 低标签比例下更明显，否则 story 不成立。
