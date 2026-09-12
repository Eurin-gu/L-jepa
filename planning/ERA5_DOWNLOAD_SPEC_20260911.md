# ERA5 数据下载与 STILT 链路规格说明

日期：2026-09-11 · 状态：72h met 下载进行中 · 关联：COLUMN_FOOTPRINT_METHOD_20260910.md

---

## 1. 数据源与请求参数

### 1.1 CDS 数据集（两个）

| 数据集 | 用途 | 内容 |
|---|---|---|
| `reanalysis-era5-pressure-levels` | STILT 三维气象 | 6 变量 × 37 层 |
| `reanalysis-era5-single-levels` | 地表场 + 特征输入 | 9 变量 |

### 1.2 气压层变量（PL，6 个 × 37 层 = 222 场/时次）

```
geopotential              (z)    位势
temperature               (t)    温度
u_component_of_wind       (u)    纬向风
v_component_of_wind       (v)    经向风
vertical_velocity         (w)    垂直速度
relative_humidity         (r)    相对湿度
```

**层（37 层，单位 hPa）**：
```
1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 700, 650, 600,
550, 500, 450, 400, 350, 300, 250, 225, 200, 175, 150, 125, 100, 70,
50, 30, 20, 10, 7, 5, 3, 2, 1
```

### 1.3 地表变量（SFC，9 个）

```
2m_temperature                           (t2m)   2m 温度
10m_u_component_of_wind                  (u10)   10m 纬向风
10m_v_component_of_wind                  (v10)   10m 经向风
total_cloud_cover                        (tcc)   总云量
surface_pressure                         (sp)    地表气压
2m_dewpoint_temperature                  (d2m)   2m 露点
boundary_layer_height                    (blh)   边界层高度
convective_available_potential_energy    (cape)  对流有效位能
geopotential                             (z)     地表位势（地形）
```

> 注：`era52arl.cfg` 声明 14 个 SFC 变量（多 tp/sshf/ssrd/slhf/zust），
> 但下载脚本只请求 9 个。缺的 5 个（降水/感热/短波/潜热/摩擦速度）
> 对 STILT 轨迹非必需，转换正常（ARL 尺寸校验通过）。

### 1.4 时空与格式规格

| 参数 | 值 |
|---|---|
| 时间分辨率 | **逐小时**（00:00–23:00，24 时次/天） |
| 空间分辨率 | **0.25° × 0.25°** |
| 区域 | 按区域 bbox + **6° 余量**（见 §2） |
| 数据格式 | **GRIB**（`data_format=grib`） |
| 打包 | **unarchived**（`download_format=unarchived`） |

---

## 2. 六个区域的 bbox 与余量

| 区域 | 核心 bbox (S, N, W, E) | + 6° 余量后的请求范围 |
|---|---|---|
| po_valley_italy | 44.4, 45.9, 8.0, 12.2 | 38.4–51.9 N, 2.0–18.2 E |
| north_china_plain | 38.2, 41.0, 114.2, 117.6 | 32.2–47.0 N, 108.2–123.6 E |
| so_cal_LA_basin | 32.0, 35.0, -119.0, -116.0 | 26.0–41.0 N, 125.0–110.0 W |
| cent_valley_CA | 35.0, 39.5, -122.0, -118.8 | 29.0–45.5 N, 128.0–112.8 W |
| permian_westTX | 30.5, 33.0, -103.8, -101.0 | 24.5–39.0 N, 109.8–95.0 W |
| co_front_range | 38.5, 40.6, -106.0, -104.0 | 32.5–46.6 N, 112.0–98.0 W |

**为什么要 6° 余量**：STILT 的 24 h 后向轨迹会飘出受体所在 bbox，
余量保证轨迹不撞到气象边界（避免"粒子飞出域"导致的足迹截断）。

**实测网格**（so_cal 例）：61 × 61 点，覆盖 26–41°N / 125–110°W。

---

## 3. 文件规格

| 项 | 值 |
|---|---|
| 命名 | `<YYYYMMDD>_PL.GRIB` / `<YYYYMMDD>_SFC.GRIB` |
| 存放 | `D:\lagrangian-jepa-cn\met_cache\era5d\<region>\` |
| PL 单天大小 | **≈ 38.7 MB**（po）/ 40.2 MB（美国区） |
| SFC 单天大小 | **≈ 1.65 MB**（po）/ 1.72 MB（美国区） |
| 一天合计 | **≈ 40 MB** |

**每个目标日期需要 4 天文件**（72 h 后向）或 **2 天**（24 h 后向）：
```
72h: T-3, T-2, T-1, T     → 8 个文件/日期
24h: T-1, T               → 4 个文件/日期
```

---

## 4. 请求策略（关键设计）

### 4.1 批量请求（对抗 CDS 队列）

**问题**：CDS 免费账号的**排队请求数有上限**，实测同时提交 8 个请求被拒：
```
The job has been rejected
Number queued requests for this dataset is temporarily limited.
```

**方案**：按 **(区域, 年月)** 分组，一个请求携带该月所有需要的天。
请求数从 **136 → 70（↓49%）**。

### 4.2 自动拆分

CDS 返回的是多天合并的 GRIB，脚本用 `eccodes` 按 `dataDate` 拆成单天文件
（与既有命名约定一致，下游管线零改动）。已验证无损。

### 4.3 限流保护

| 机制 | 实现 |
|---|---|
| 单请求超时 | 3 小时（`FETCH_TIMEOUT_S=10800`） |
| 被拒退避 | 最多重试 1 次（退避 30 分钟）后**退出**，不刷请求 |
| 恢复探测 | `era5_guard.py` 每 45 分钟探测 1 次最小请求 |
| 任务优先级 | 72h met（小、关键）→ 美国区 |
| 代理看门狗 | 每 2 分钟检查 17891，挂了自动重启 0dcloud |

---

## 5. 数据流（GRIB → 标签）

```
CDS API
  ↓  批量请求 + 自动拆分
era5d/<region>/<date>_{PL,SFC}.GRIB          (≈40 MB/天)
  ↓  era52arl 转换（工具链）
met_era5/<region>/<date>                     (ARL, 23.4 MB/天)
  ↓  run_batch.py → stilt_cli.r → hycs_std
out/by-id/<sim_id>/*_foot.nc                 (足迹标签, 88 KB/个)
  ↓  compose_column.py（柱足迹合成）
colfoot/*.npz                                (柱足迹, 5 高度加权)
```

**ARL 转换规格**（`era52arl.cfg`）：
- 输入：PL + SFC GRIB
- 输出：单文件 ARL，po 区域固定 **23,403,000 bytes**（尺寸校验用）
- 层数：37；变量：6 PL + 14 SFC 声明

---

## 6. STILT 运行规格

| 参数 | 值 | 说明 |
|---|---|---|
| 域半宽 | **±256 km** | 对应 128×128 @ 4 km 下游网格 |
| 网格分辨率 | **0.04°**（≈4 km） | |
| 粒子数 | **250**（train）/ 1000（val/test） | |
| 后向时间 | **-24 h**（当前）/ 计划 72 h | |
| 气象时间步 | 1 小时 | `--met-file-tres-hours 1` |
| 并发 | **4 jobs** | 静音模式（控发热） |
| 标签单位 | `stilt_surface_sensitivity`（物理单位） | |

**柱足迹专用规格**（2026-09-10 批次）：
- 高度集合：**{5, 100, 300, 800, 1500} m**
- 每高度**独立一次运行**（该引擎多受体质量分配失败，无法一次跑多高度）
- tag：`colera5-po-<date>-p250`

---

## 7. 实测性能

| 指标 | 实测值 |
|---|---|
| 下载速度 | **1.3–2.2 MB/s** |
| 单请求（2 天 PL，77.3 MB） | **≈ 44 分钟**（含 CDS 生成排队） |
| 单天 PL 生成 | ≈ 22 分钟 |
| STILT 单次模拟 | **≈ 5 秒**（p250, 24h 后向, 4 并发） |
| 柱足迹 11 天（6600 次） | **≈ 7.8 小时**（实测 2329+2684+…） |

**瓶颈**：CDS 服务端生成时间，不是本地带宽。

---

## 8. 当前进度（2026-09-11 09:20）

| 区域 | GRIB 文件 | 体积 | 说明 |
|---|---|---|---|
| po_valley_italy | **70** | 1383 MB | 72h met 下载中（22 天新增，已完成 ~13 天） |
| north_china_plain | 38 | 797 MB | 24h 需求已满足 |
| so_cal_LA_basin | 17 | 359 MB | 待续（CDS 限流期间中断） |
| cent_valley_CA | 4 | 88 MB | 待续 |
| permian_westTX | 4 | 77 MB | 待续 |
| co_front_range | 4 | 71 MB | 待续 |

**po 区域 72h 目标**：44 天 × 2 = **88 个文件**（当前 70）

---

## 9. 复现命令

| 用途 | 命令 |
|---|---|
| 查看下载进度 | `bash /root/era5_quick_status.sh` |
| 查看柱足迹检查 | `bash /root/check_column.sh` |
| 单区下载（原版） | `python era5_fullprev.py <region> <dates...>` |
| 批量下载（优化版） | `python /root/era5_batch.py [regions...]` |
| 72h met 下载 | `python /root/era5_72h_fetch.py` |
| ARL 转换 | `cd <era52arl> && ./era52arl -d<cfg> -i<PL> -a<SFC> -o<out>` |

**下载脚本位置**：
- `/mnt/c/Users/Yuki/Desktop/oss_work/era5_batch.py`（批量+拆分）
- `/mnt/c/Users/Yuki/Desktop/oss_work/era5_72h_fetch.py`（72h 需求）
- `/mnt/c/Users/Yuki/Desktop/oss_work/era5_fullprev.py`（原版单区）

---

## 10. 已知风险

| # | 风险 | 状态 |
|---|---|---|
| R1 | CDS 限流（队列配额） | 已有批量+退避+guard 应对 |
| R2 | 代理（0dcloud）不稳，今日崩 2 次 | 已加看门狗自动重启 |
| R3 | 磁盘：vhdx 在 C 盘，C 仅剩 ~2.7G | 已删 GDAS 64G 腾出空洞；未压缩 |
| R4 | 请求无断点续跑 | 按文件存在性跳过，可重入 |
| R5 | 美国区 4 区进度停滞 | 排在 72h 之后，链式自动启动 |
