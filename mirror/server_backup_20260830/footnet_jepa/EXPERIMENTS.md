# 📍 footnet_jepa 实验地图（2026-09-01 更新）

> **进入本目录先看这个文件**。把所有内容按「正式 / 探索 / 废弃 / 生产中」归类。
> 服务器路径：/root/autodl-tmp/footnet_jepa/ ；本地副本：go_nogo/footnet_jepa/

---

## 一、快速分类（一句话版）

| 类别 | 内容 | 能否进论文 |
|---|---|---|
| ✅ **正式结果** | formal_untouched_7arm_5seed（prod_all_v3）、formal_v4_7arm_5seed（v4）、formal_v5_mass1（v5） | **能**（核心 claim） |
| ✅ **正式数据** | prod_all_v3 / v4 / v5（2016-17 HRRR 线，1680/1800/1920 样本） | **能** |
| 🔬 探索性 | labelfrac_0.1~1.0（数据效率曲线）、prod_full_7arm_5seed、smoke_prod3、strict_2024_apr_vs_jul | 参考，非正式 |
| 🔬 真实但元数据缺 | strict_2024_all（360，jul05+apr02+apr03 HRRR，run_time 字段缺失待回填）、*_samecycle_strict | 可修复后使用 |
| 🔴 **假数据（勿用）** | 2024_ext_merged、gdas_jul_jul01-06、test_2024_ext、ext_jul*、receptors_1k/apr02-07、gdas_production/jul0* | **永远不进** |
| 🆕 生产中 | GDAS 全球多区域（6583 受体，**噪声对照**）、ERA5 全球（**主数据**） | 构建中 |

---

## 二、数据集总览（data/）

### ✅ 正式（2016-17 HRRR 主线，论文用）
| 目录 | 样本 | 日期范围 | 说明 |
|---|---|---|---|
| prod_all | 1440 | 2016-03-18 ~ 2017-05-17 | v1（labelfrac/prod_full 用） |
| prod_all_v2 | 1560 | 同上 | v2 |
| prod_all_v3 | 1680 | ~2017-09-22 | **formal_untouched 用** |
| prod_all_v4 | 1800 | ~2017-10-06 | **formal_v4 用**（7 arm） |
| prod_all_v5 | 1920 | ~2017-11-18 | **formal_v5_mass1 用**（最新） |
| prod_test2/test5/test_merged、prod_train_merged、prod_trainval(2)、prod_val_merged | 240-960 | 同上 | 切分子集（构建中间产物） |

### 🔬 真实 2024（严格线，探索/可修复）
| 目录 | 样本 | 说明 |
|---|---|---|
| strict_2024_all | 360 | jul05(120)+apr02(120)+apr03(120) HRRR；**meta 240 个 run_time 缺失**（sim_id 可回填） |
| strict_jul05_apr02 | 240 | 子集 |
| apr02/apr03_samecycle_strict、jul05_samecycle_strict（单文件） | 各 ~120 | 同周期严格线（真实） |

### 🔴 假数据（隔离，勿用！）
| 文件/目录 | 问题 |
|---|---|
| 2024_ext_merged（1425） | = test_2024_ext(705) + gdas_jul(720) 拼接，250 个 00:00Z 占位 |
| gdas_jul_jul01-06（720） | 120 点×6 天克隆，时刻逐秒相同，只改日期戳 |
| test_2024_ext（705） | 141 点×5 天克隆 + 00:00Z 占位 |
| ext_jul06、ext_jul1_06 | 克隆扩展 |

---

## 三、结果总览（results/）

| 文件 | 数据 | formal | 说明 |
|---|---|---|---|
| formal_untouched_7arm_5seed.json | prod_all_v3 | ✅ | 7-arm × 5-seed（scratch/e_jepa/l_jepa/met_mae/fno…） |
| formal_v4_7arm_5seed.json | prod_all_v4 | ✅ | 7 arm（含 unetpp/temporal_unet） |
| formal_v5_mass1.json | prod_all_v5 | ✅ | mass-weight 版 |
| labelfrac_0.1~1.0.json | prod_all | ❌ | 数据效率曲线（l_jepa 表现） |
| prod_full_7arm_5seed.json | prod_all | ❌ | 全量（非正式协议） |
| smoke_prod3.json | prod_all | ❌ | 冒烟 |
| strict_2024_apr_vs_jul.json | strict_2024_all | ❌ | 探索性 |
| formal_test_manifest*.json | — | — | 正式协议测试清单（含 .used.json 一次性消费标记） |
| genghg-* 目录 | genghg 合成 | ❌ | **合成代理**实验（非 STILT 真实标签） |

---

## 四、脚本说明

| 脚本 | 作用 |
|---|---|
| train_stilt_strict.py | **正式协议训练**（哈希回执/契约指纹/原子写入/同周期气象对齐） |
| train.py、lagrangian_jepa.py、models.py | 模型 + 训练 |
| data_builder.py | 数据集构建（HRRR 兰伯特输入 + STILT 标签） |
| era5_features.py、era5_met_cache.py | **ERA5 特征管线**（新增，P3） |
| stilt_io.py | STILT footprint 读取（**已升级保守重采样**） |
| merge_final*.py、merge_strict_datasets.py | 数据集合并 |
| simple_lagrangian.py | OSSE 代理标签（早期） |
| genghg_loader.py | 合成数据生成器（代理） |

---

## 五、生产状态（/root/autodl-tmp/，2026-09-01）

| 目录 | 内容 | 状态 |
|---|---|---|
| global_prod/ | GDAS 批 manifests + 日志（240331-240706） | 11 日期，**噪声对照** |
| receptors_global/ | 11 日期受体 CSV（已去重，真实） | ✅ |
| met/ | GDAS ARL（1°） | ✅ |
| met_era5/ | **ERA5 ARL（0.25°）** | 转换中（0401 done） |
| era5/ | ERA5 GRIB 原始 | 下载中（14 天） |
| era5_cache/ | ERA5 特征缓存（U10M/V10M/PBLH/PRSS） | 0401 done |
| stilt/、stilt_pipeline/ | STILT 引擎 + run_batch | ✅ |
| hysplit_data2arl/ | era52arl（ERA5→ARL） | ✅ 已修复 |

**ERA5 主数据线**：下载(14天) → era52arl 转换 → ERA5 STILT 标签批（--tag global-era5-p250）→ era5_features 输入 + 标签 → 合成数据集。

**铁律**：GDAS 系列（P1/P4）永远不进论文表格；切换气象源必须换 tag + 新 manifest（P2）。
