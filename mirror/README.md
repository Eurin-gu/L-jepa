# lagrangian-jepa-cn 数据桶说明（2026-09-02 更新）

> 本 bucket 存放 Lagrangian-JEPA 项目的全部数据与服务器备份镜像。
> 数据真实性审计与分类见下；**假数据已删除（2026-09-02）**，审计痕迹保留在本文件。

---

## 一、目录结构

| 前缀 | 内容 | 状态 |
|---|---|---|
| server_backup_20260830/ | 服务器数据盘持续镜像（主体，~465GB） | 随服务器同步 |
| hrrr/ | 真实 HRRR-lite 气象 netCDF（2024-01 起，逐 6h） | ✅ 真实 |
| gdas/ | GDAS 1° ARL 周文件 | ✅ 真实 |
| hrrr_arl/ | HRRR ARL（29 文件） | ✅ 真实 |
| hrrr_stilt_apr02_strict/ | HRRR STILT 2024-04-02 严格生产 | ✅ 真实 |
| manifest.json | OSS 同步清单 | 管理文件 |

---

## 二、数据集分类（server_backup_20260830/footnet_jepa/data/）

### ✅ 正式（论文主体，2016-17 HRRR production 线，真实逐日 OCO-2 几何）
- prod_all_v3 / v4 / v5（1680 / 1800 / 1920 样本）—— formal_untouched / formal_v4 / formal_v5_mass1 用
- prod_train_2016xxxx~2017xxxx、prod_test_2016xxxx、prod_val_*—— 逐日期切分（真实）
- prod_test_20160318/0802/1111/170116/170922 —— 正式测试集

### ✅ 真实 2024（探索/可修复）
- strict_2024_all（360：jul05+apr02+apr03 HRRR，真实；meta 240 个 run_time 待回填）
- jul05_samecycle_strict、apr02/apr03_samecycle_strict（真实单日）

### 🔴 已删除（2026-09-02，假数据/复制品）—— 勿再生成
- ~~gdas_jul_jul01-06~~（120 点 × 6 天克隆，只改日期戳）
- ~~test_2024_ext~~（141 点 × 5 天 + 00:00Z 占位）
- ~~ext_jul06 / ext_jul1_06~~（克隆扩展）
- ~~2024_ext_merged~~（上述假数据拼接，1425）
- ~~train_stilt_apr~~（250 样本 00:00Z 占位）

---

## 三、受体与生产（server_backup_20260830/）

### 🔴 已删除（假受体）
- ~~receptors_1k/~~（LA 盆地单日几何跨日期复制）
- ~~gdas_production/apr*_1k/hi500、jul*_p250/hi500~~（同 LA 几何复制/120 点克隆）
- ~~stilt/out/by-id/gdashi1k-*~~（26,716 对象，1k 假批产物）
- ~~stilt/out/by-id/gdas-jul*~~（8,400 对象，jul 克隆批产物）

### ✅ 保留（真实）
- receptors_global/（11 日期多区域受体，已去重，跨日期零重叠——真实 OCO-2 采样）
- stilt/out/by-id/global-240*（新 GDAS 全球多区域足迹，受体真实；**标签为 1° 气象噪声对照，不进论文正式结果**）
- stilt/out/by-id/hrrr-2024*（HRRR 2024 真实）

---

## 四、正式结果（server_backup_20260830/footnet_jepa/results/）

| 文件 | 数据 | formal | 说明 |
|---|---|---|---|
| formal_untouched_7arm_5seed.json | prod_all_v3 | ✅ | 7-arm×5-seed |
| formal_v4_7arm_5seed.json | prod_all_v4 | ✅ | 含 unetpp/temporal_unet |
| formal_v5_mass1.json | prod_all_v5 | ✅ | mass-weight |
| labelfrac_0.1~1.0.json | prod_all | ❌ 探索 | 数据效率曲线 |
| strict_2024_apr_vs_jul.json | strict_2024_all | ❌ 探索 | |

---

## 五、审计铁律
1. **气象源与输入必须物理对应**（输入 HRRR 风场不得配 GDAS 标签——P4）
2. **切换气象源必须换 tag + 新 manifest**（不得 --resume 混源——P2）
3. **受体必须来自真实逐日 OCO-2 过境**（禁止日期平移/几何复用）
4. **GDAS 1° 标签为噪声对照**（4km 尺度无气象结构——P1），不进论文
5. 正式实验只用 production 线（2016-17 真实几何）与将来验证通过的 ERA5 线
