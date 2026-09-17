# ERA5 72h 数据获取管线（WSL + CDS API）

从 Copernicus CDS 批量获取 ERA5，按受体区域裁剪、落地为逐日 GRIB，再转 ARL 供 STILT 使用。

## 为什么需要这套东西

CDS 免费账号是**排队制**：单个请求端到端时延中位数约 **90 分钟**（实测 35–332 min），
并发/排队额度很小（实测 5 个 `accepted` 就满了，之后一律 `rejected`）。
所以真正的瓶颈不是带宽，而是**队列调度**；这套管线的一切设计都是围绕这个约束。

## 架构：投递与收割分离

```
era5_72all.py      投递端（唯一实例，flock 锁）
  ├─ queue_busy()      查 CDS 上 accepted/running 数，非空就等，不盲投
  ├─ era5_batch.py     area() 按区算 bbox；fetch_group() 提交并下载；split_grib() 拆成逐日文件
  └─ bbox_guard.py     写入路径上的内容校验（区域 + 网格）

cds_harvester_v2.py  收割端
  ├─ 轮询 CDS 已完成的 job
  ├─ 从对象存储 href 直下（比 cdsapi 轮询快一个数量级）
  ├─ region_from_grib()  **由 GRIB bbox 反推区域**，绝不硬编码
  └─ split_grib() 落地到正确区域目录
```

两者各自有 `run_*_forever.sh` 守护循环；生产环境用 systemd `Restart=always` 更稳。

## 关键设计（都是踩坑换来的）

### 1. 区域必须由数据自身推断，不能硬编码
早期版本的收割器硬编码 `REGION="po_valley_italy"`，结果**所有区域的数据都被写进了 po 目录**。
当两个区的 72h 窗口重叠时，同名文件会**静默覆盖**掉正确数据。
现在 `region_from_grib()` 读 GRIB 头的 bbox 反推区域，`bbox_guard.py` 在**写入路径**上二次校验。

### 2. 「文件存在且体积达标」≠「数据正确」
原来的 `have()` 只查体积，44 MB 的错区文件照样通过 —— 缺口被掩盖成 0。
现在所有 `have()` / 完整性判定都走 `bbox_guard.verify_bbox()`（内容级）。

### 3. 客户端超时必须大于服务端排队延迟
`FETCH_TIMEOUT_S` 曾设为 3 小时，而 CDS 排队实测可超过 5 小时 →
客户端把**仍在排队的 job 判为失败**并反复重投，把队列彻底塞死。现设为 8 小时。

### 4. 同一时刻只能有一个投递者
曾出现 3 个守护脚本 + 1 个下载器同时抢额度，互相饿死。现在 `era5_72all.py` 有 `flock` 单实例锁。

### 5. 同一区域的网格必须完全一致
HYSPLIT 要求一次模拟所用的 4 天气象文件网格相同。`_check_grid_consistency()` 会拒绝
网格签名 `(Ni, Nj, la1, lo1, la2, lo2)` 与已有文件不一致的新数据。

### 6. CDS 的 `area` 网格对齐
请求里带 `grid=[0.25,0.25]` 时，CDS 会把数据**双线性重采样到以 `area` 角点为原点**的网格。
若角点不在 ERA5 原生 0.25° 网格上（如 51.9 / 38.4），纬度就会整体偏移 0.10° 并被平滑。
`era5_batch.area()` 支持 `ERA5_GRID_MODE=native`，把角点向外对齐到 0.25 的整数倍以取原生值。
**切换模式必须先清空该区旧文件**，否则网格护栏会拒绝新数据。

### 7. 收割失败不能标记为已处理
收割抛异常时若也 `mark(jid)`，一次网络抖动就等于永久丢数据。现在失败不标记，下一轮重试。
CDS 偶发返回 **3470 字节的「假成功」结果**，已加 100 KB 有效性下限自动跳过。

## 依赖的环境变量 / 路径

脚本按 WSL 环境编写，移植时需要改：

| 位置 | 原值 | 说明 |
|---|---|---|
| `BASE` | `/mnt/d/lagrangian-jepa-cn/met_cache/era5d` | 逐日 GRIB 落地目录 |
| `REC` | `/mnt/d/lagrangian-jepa-cn/data/receptors_v2` | 受体坐标（决定目标日） |
| `cdsapi` 凭据 | `~/.cdsapirc` | CDS API key，**不入库** |
| `era52arl` | `toolchain/…/hysplit_data2arl` | GRIB → ARL 转换 |

## 文件清单

| 文件 | 作用 |
|---|---|
| `era5_batch.py` | CDS 批量获取核心（区域定义、月度分组请求、逐日拆分、网格护栏）|
| `era5_72all.py` | 72h 统一补下的投递端（队列闸门 + 单实例锁）|
| `cds_harvester_v2.py` | 收割端（按 bbox 判区）|
| `bbox_guard.py` | 区域/网格内容校验，含隔离机制 |
| `plan72.py` | 按目标日算出 72h 缺口（T-3..T）|
| `audit72.py` | 按内容重算完整性（与 plan 对账）|
| `scan_pollution.py` | 全区间错区污染扫描 |
| `region_inventory.py` / `po_inventory.py` / `inventory.py` | 数据盘点 |
| `rh_field2.py` | 相对湿度 ↔ 比湿 跨源对拍验证 |
| `count_times.py` / `profile_grib.py` | GRIB 内容剖析（时次/层/变量）|
| `cds_queue.py` / `cds_stats.py` / `check_72prog.py` | 队列与进度监控 |
| `compose_column.py` / `era5_column_run.py` / `check_column*.py` | 柱足迹生产与合成 |
| `conv_arl.sh` | GRIB → ARL |
| `grid_test.py` / `test_guard.py` | 护栏单元测试 |
| `run_downloader_forever.sh` / `run_harvester_forever.sh` | 守护循环 |

## 口径速查

- 目标日 T 的 72h 回算需要 **T-3, T-2, T-1, T** 共 4 天气象
- 每天 **2 个文件**：`PL`（pressure-levels，37 层 × 6 变量）+ `SFC`（single-levels，9 变量）
- 每天 **24 个整点时次**
- 故 N 个目标日 → `4N` 天 → `8N` 个文件（如 11 个目标日 = 44 天 = 88 文件）
