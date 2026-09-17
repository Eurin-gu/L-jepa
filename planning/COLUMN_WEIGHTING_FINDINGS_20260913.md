# 柱足迹垂直加权与释放高度的科学结论

日期: 2026-09-13
状态: 已用实测数据验证 (OCO-2 Lite v11.2r + ERA5 + STILT/HYSPLIT)

---

## 1. 修正: OCO-2 权重随高度的分布 (推翻此前的错误估计)

**此前记录 (错误)**: "cumulative AK·PW reaches 50% by ~4.40 km, **75% by ~1.97 km**,
90% by ~0.95 km, 95% by ~0.47 km" —— 该结论自相矛盾 (50% 在 4.4 km 却 95% 在 0.47 km),
来源于有 bug 的分析脚本. **作废.**

**实测 (6 区域, 地形 4 m ~ 2163 m, 高度一致)**:

累积 AK·PW 占总量比例 (按 m AGL):

| 高度 AGL | po(627m) | cent_valley(4m) | ncp(6m) | so_cal(162m) | co_front(2163m) | permian(1346m) |
|---|---|---|---|---|---|---|
| 100 m  | 0.0%  | 1.2%  | 1.1%  | 1.6%  | 1.3%  | 1.2%  |
| 250 m  | 0.0%  | 3.1%  | 3.0%  | 3.9%  | 3.2%  | 3.0%  |
| 500 m  | 2.9%  | 6.2%  | 6.2%  | 7.4%  | 6.4%  | 5.9%  |
| 1 km   | 9.7%  | 12.3% | 12.5% | 13.7% | 12.6% | 11.6% |
| 2 km   | 22.4% | 23.8% | 24.3% | 25.3% | 24.2% | 22.4% |
| 3 km   | 33.9% | 34.2% | 35.2% | 35.8% | 34.7% | 32.4% |
| 5 km   | 53.3% | 52.2% | 54.0% | 53.7% | 52.4% | 49.7% |
| 8 km   | 74.2% | 72.3% | 74.6% | 73.5% | 71.6% | 69.1% |
| 10 km  | 83.4% | 81.7% | 83.5% | 82.6% | 80.1% | 78.3% |
| 12 km  | 89.7% | 88.3% | 89.6% | 88.9% | 85.6% | 85.0% |
| 15 km  | 94.8% | 93.9% | 94.5% | 94.1% | 90.3% | 91.4% |
| 20 km  | 97.6% | 97.1% | 97.4% | 97.1% | 93.2% | 95.1% |

**结论**: 柱权重在整层大气中近似 **均匀** (每个 OCO-2 层约 5%), 并非集中近地层.
50% 在 ~5 km, 75% 在 ~8 km, 90% 在 ~12.5 km, 95% 在 ~15.5 km.

=> 释放高度 **必须覆盖到 ~16 km**, 而不是只加密低层.

---

## 2. OCO-2 加权网格的精确结构 (实测)

### 2.1 20 个数是 LEVEL 还是 LAYER? —— 按 O'Dell et al. (2012) App.A 判定

权威原文 (O'Dell et al. 2012, AMT 5, 99-121, p.117):

> Let the pre-defined pressure levels, **p = p_1..N**, be ordered from space to surface,
> and truncated such that the last level, **p_N, is physically located below the surface**,
> where the surface level is defined by the retrieved surface pressure p_S.
> ... layer i is bounded by the pressure levels p_i and p_{i+1}, except for the last layer
> which is bounded by pressure level **p_{N-1}** and the surface level **p_S**

    h'_i = c_i dp_i / sum_j c_j dp_j        (A4)   c = (1-q)/(g M_dry)   (A2)
    h_i  = A5 分段式,  f_i = 1/2,  f_S = (p_S - p_{N-1})/(p_N - p_{N-1})   (A8)

**A5 中 i=N 分支是 f_S f_{N-1} h'_{N-1} (含 f_{N-1})**; 漏掉 f_{N-1} 会使
sum h_i = 1 + f_S(1-f_{N-1}) h'_{N-1} != 1.

**实测验证 (po 20171023, sounding 2017102312044972)**:

| 检验 | 结果 |
|---|---|
| level 个数 N | **20** |
| 反解 h -> h' | **19 个 LAYER** |
| sum(h') | 1.0000000019 == sum(h) |
| h' 均匀性 | 全部 ~= 1/19 = 0.0526316  (spread 仅 0.876%) |
| 正向重建 h' -> h | **max abs diff = 0.000e+00** |
| f_S | 1.000000 => p_S = p_N = 927.183 hPa |
| h' 单调性 | 自顶向下严格递减 0.052866 -> 0.052407, 比 1.0088 = 水汽订正 |

**结论**: 文件里的 20 个 pressure_weight 是 **20 个 LEVEL 权重**,
**不是** 20 个 layer 的层积分权重; 层只有 **19** 个, L_i = [p_i, p_{i+1}].

**对前一次判断的更正**: 先前据 "PW0/PW1 = 0.5001" 推断 "首末是半厚度层", **这是错的**.
首末权重恰为一半来自 A5 的插值端点 h_1 = (1-f_1)h'_1 = h'_1/2 与
h_N = f_S f h'_{N-1} = h'_{N-1}/2 (f_S=1), **与层厚无关**; 19 个层的厚度其实是均匀的.

据此, 先前 "midpoint control volume + 层中心 167.7 m" 的做法也站不住:
最底层 L_19 = [878.384, 927.183] hPa, 其中心在 **~279.5 m AGL**, 不是 167.7 m.

### 2.2 其余结构 (实测)

- 20 个 level 气压 **均匀分布** (非对数), 间距 48.799 hPa (po 20171023)
- 顶 = 0.055 ~ 0.103 hPa (随 sounding 变), 底 p_N = p_S = retrieval 地表气压
  (与 ERA5 sp 相差 6.41 hPa; OCO-2 用自带 GEOS-5 气象)
  => 加权网格严格用 OCO-2 的 P; ERA5 剖面 **只** 用于 P<->z 换算
- **sum(h) = 1.000000** (918 文件抽样验证)
- **sum(AK*h) = 0.78 ~ 0.94 (均值 0.899)** — 平流层灵敏度缺失是真实物理, 不可归一化为 1
- h 不是 dP/p_surf: 反解后 h' ∝ c_i dp_i 且严格单调, ~1% 漂移 = **水汽/干空气订正**;
  **必须直接使用 OCO-2 下发的 pressure_weight, 不可自行重算**

### 2.3 释放方案与最终裁决

**关键是把两件事解耦:**

    (1) OCO-2 -> 垂直权重        严格按 O'Dell h' -> h     —— 物理定义
    (2) level -> STILT 释放高度   数值实现选择            —— 采样位置

**最终裁决 (改用 layer form):**

    scheme = layer
    zmap   = absolute
    z_i    = z_ERA5( P_{i, layer center} ),   P_{i,layer center} = (p_i + p_{i+1})/2
    权重   = AKbar_i * h'_i,                  AKbar_i = (AK_i + AK_{i+1})/2
    释放层数 = 19   (O'Dell 的 layer, 不是 20 个 state-vector level)

po 20171023 最底层: **902.784 hPa -> 279.5 m AGL**
(927.183 hPa / 56.6 m 只是该 layer 的**底部边界**, 不能作为 release height)

**核心判断: X-STILT 的 release level 代表 O'Dell 的 LAYER, 而不是 state-vector level.**
O'Dell 的结构是 20 pressure levels => **19 layers**; release 是粒子释放位置,
物理上对应的是 layer 的贡献, 因此应把 OCO-2 的 layer contribution 映射到
X-STILT 的 release layers, 而不是人为制造 "20 个 layer center".

**不使用 `sigma`**: 它假设 OCO-2 的归一化压力坐标与 ERA5 高度可逐层对应,
而两者并非同一垂直坐标系; 比 absolute 假设更强.

**不使用 Voronoi / center=914.98 hPa / 167.7 m** (曾一度提出, 已撤回):
Voronoi 控制体以 level 为**中心**, 与 O'Dell "以 level 为 layer 边界" 的结构不同,
属于另一种离散化; 内部层恰好重合, 最底层差 111 m. 已弃用.

**关于 56.6 m 的正确说法**: 它**不是** "OCO-2 最后一个 state-vector level 位于
56.6 m 高度", 而是 "该 layer 的**底部边界**在压力坐标映射后落在约 56.6 m AGL".

四种方案 sum(w) 全部为 0.87581935 (同一求积的不同下标写法):

| scheme | 释放层数 | 释放高度 | 权重 | sum(w) |
|---|---|---|---|---|
| **`layer` (默认, 采用)** | 19 | O'Dell 层中心 | AKbar_i · h'_i | 0.87581935 |
| `level` + raw | 20 | z(p_i) | AK_i · h_i | 0.87581935 |
| `level` + voronoi (已弃用) | 20 | Voronoi 中心 | AK_i · h_i | 0.87581935 |
| `refined` | 任意 (低层加密) | 指定 | h' 与 AKbar 按气压重叠分配 | 0.87581935 |

- `layer` 与 `level` 是 **同一求积的两种下标写法** (逐项可证), 故 sum(w) 严格相同.
- `refined` 用于需要自定义释放网格时: 把每个 layer 的贡献 (h'_i * AKbar_i)
  按气压重叠分配到 release layers. AK 必须取 **该 OCO-2 layer 自身的层平均 AKbar_i**,
  不能取释放点处的 AK —— 否则跨 238 hPa ~ TOA 的顶层释放会用 AK(238 hPa)=1.246
  代表整层 (实际 0.25~0.88), 造成 ~1.6% 高估 (已修正).

**负 AGL 处理**: 部分受体 OCO-2 的 p_S 高于 ERA5 sp, 其最低 layer 中心会落到 ERA5
地形之下 (实测 po 20171023: 120 个受体中 27 个). 已改为 **夹到地面 (5 m AGL)**
并统计上报, 而不是丢弃 (丢弃会损失该 layer 全部权重).

用法:

    python3 column_weighting.py --verify-acos                    # 验证 h<->h' 与守恒
    python3 column_weighting.py --check --scheme layer           # 诊断表 (默认)
    python3 column_weighting.py --emit-table --region R --date D # 产出 STILT 表 + 权重 JSON

---

## 3. 关键发现: 高空释放的零足迹是 **域截断**, 不是"从未接触地面"

测试工况: po 20160714 (夏季), 受体 44.70957N/9.78720E, 72 h 后向, 500 粒子, ±256 km 窗口.

| 释放高度 | 进入 PBL 的粒子步数 | 发生时段 | 距受体距离 | 落在 ±256 km 内 |
|---|---|---|---|---|
| 5 m | 260,603 | 全程 72 h | — | — |
| 500 m | 264,950 | 全程 72 h (t=-4320..-1 min) | 中位 96.6 km, 最大 948 km | **57.8%** |
| 1500 m | 260,365 | 全程 72 h | 中位 110.0 km, 最大 921 km | **54.7%** |
| 3000 m | 10,829 | 仅 -34 h .. -22 h | **524 ~ 733 km** | **0.0%** |
| 5000 m | **0** | 从未下沉 | min z = 3789 m | 0 |
| 8000 m | **0** | 从未下沉 | min z = 6805 m | 0 |

**解读**:
- 3000 m 的 10,829 步地面接触 **全部** 发生在 524-733 km 外 —— 被 ±256 km 窗口截断,
  所以 STILT 报 "No non-zero footprint values found within the footprint domain",
  但粒子 **确实** 到过地面. **不是 bug.**
- 5000 m 及以上在 72 h 内 **完全没有** 下沉进入 PBL (最小高度 3789 m > 局地混合层).
- 高空气团移速快, 很快移出 ERA5 气象域而被终止 (5000 m 仅 286,606 行 vs 500 m 的 954,543 行).

**=> 在 128x128 @4km 受体中心网格内 (约 ±256 km), 高度 >= 3000 m 的释放对柱足迹贡献为 0.**
  ≤2523 m 的 OCO-2 层合计占总权重 **33.3%**; ≤1467 m 的层合计 **21.1%**.

---

## 4. 实现

`data/build/column_weighting.py`:

- `oco2_layer_bounds(P)`     层边界
- `era5_pz_profile(...)`     实际 ERA5 P-z 剖面 (geopotential, 37 层 + sp + 地形)
- `p_to_z` / `z_to_p`
- `oco2_center_release_levels(...)`  严格方案: 释放高程 = OCO-2 层中心高度
- `refine_low_levels(...)`   低层加密 (z<1.5 km, dz<=250 m)
- `map_weights(...)`         按 **气压重叠** 把 W_i=AK_i·PW_i 分配到释放层

守恒性: 释放层完整铺满 [0, p_ground] 且 p_ground >= OCO-2 网格底
=> **sum(w) == sum(W)**, 实测残差 ~1e-16.

严格方案下 w_j **等于** W_i (无需插值), 即 Wu et al. (2018) Eq.4 的最忠实实现.

CLI:
```bash
python3 column_weighting.py --check --scheme strict      # 诊断表
python3 column_weighting.py --emit-table --region po_valley_italy --date 20171023
```

---

## 5. 待决问题 (需用户裁定)

现有 JEPA schema 目标网格为 **128x128 @4km 受体中心 (约 ±256 km)**.
但 72 h 后向上, 地面接触的 **质量重心在域外** (500 m 释放也仅 57.8% 在域内).

两个方向:
- **(A) 保持 ±256 km**: 产物为 "近场柱足迹", 高空层 (>=3 km) 贡献恒为 0.
  诚实但有信息损失.
- **(B) 扩大窗口** (如 ±512 km 或 ±1000 km): 保留更多远场贡献, 但目标网格尺寸改变,
  需重新定义 schema (例如 256x256 @4km).

建议: 先用 **(A)** 产出正式数据集 (与既有 schema 一致), 同时在产物里 **归档完整域** 的
foot.nc, 以便将来按 (B) 重切.

---

## 6. 数据完整性

- OCO-2 Lite v11.2r 共 **918** 文件 (2014-12-31 .. 2017-11-20), 其中 **27 个损坏**
  (NetCDF HDF error), 需重下. **11 个目标日期全部完好.**
- WSL 侧已安装 netCDF4 1.7.4 (此前只能在 Windows py311 用 netCDF4, 而 eccodes 只在 WSL).
- 918 个 .nc4 的 9p 权限为 mode 000, 已 chmod 644 修复 (否则 HDF5 open() 报 EACCES).
