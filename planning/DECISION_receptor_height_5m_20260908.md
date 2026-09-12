# 受体高度决策备忘（2026-09-08 确认）

状态：已确认 · 关联：PRE_REGISTRATION_v1.json（zagl=5m 冻结）· PLAN_GLOBAL.md 评审点2

## 决策

一期维持 **zagl=5m 地表通量敏感性足迹**为训练标签（算子 benchmark），
不改高度、不重跑已产出批次。XCO2 柱观测匹配属二期，走多高度 F(z)
柱灵敏度（{5,100,300,800,1500,3000,6000} m，PLAN_GLOBAL 已设计），
不污染一期数据集。

## 依据（2026-09-08 现场核实）

- STILT 高度是 receptor CSV 第 4 列 zagl（make_receptors.py 写 zagl=5），
  非代码写死；改高度=改标签物理定义，会令既有标签全部作废或分叉。
- 已产出全部为 5m（CONTROL 第 3 行 = 5 抽查一致）：
  - HRRR formal：10 日期 × 120，meta.json 每样本 zagl=5.0，
    已合并 formal_hrrr_train_p250_all（1200 样本）
  - GDAS0.5：早期 4560 sim（by-id gdas0p5-v2-*）
  - ERA5：po 7/11 天完成 + 2 天进行中 + ncp 2/11 天完成（其余等下载）
- 单一"合适高度"（如 100m）既不等于柱灵敏度，也破坏一期冻结合同；
  二期正确路径是多高度 F(z) 加权，而非单一高度替换。

## 动作

1. era5 po 剩余日期按 5m 跑完（20160714 补缺、20170421、20170327 收尾中）。
2. 一期结论只写"5m 地表通量敏感性算子"；禁止用 5m 足迹卷积排放逼近
   OCO-2 柱 XCO2 并宣称物理正确（PRE_REGISTRATION explicit_non_claim）。
3. 二期启动时另开 F(z) 多高度批与独立合同，与一期标签物理分离。
