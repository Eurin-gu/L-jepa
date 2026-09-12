# Lagrangian-JEPA 项目代码索引

> 生成于 2026-09-12 · 说明代码位置、用途、以及如何用资源管理器访问

---

## 一、如何可视化访问代码

在 **Windows 资源管理器地址栏** 输入：

    \\wsl$\Ubuntu-24.04\home\yuki\ljepa

也可用：

    \\wsl.localhost\Ubuntu-24.04\home\yuki\ljepa

**为什么进不了 `/root`**：`/root` 权限 700（仅 root 可读），而 Windows 侧用户是 `yuki`，被拒绝。
因此所有脚本已**复制**到 `/home/yuki/ljepa/`（yuki 可读写）。

### Windows 侧代码

| 路径 | 内容 |
|---|---|
| `D:\lagrangian-jepa-cn\data\build\` | 核心建集器（.py 保留，55 个日志已归档到 `_logs\`） |
| `D:\lagrangian-jepa-cn\mirror\...\footnet_jepa\` | 训练/模型核心代码 |
| `D:\lagrangian-jepa-cn\planning\` | 全部文档 |
| `C:\Users\Yuki\Desktop\oss_work\` | 11 个核心脚本（88 个历史已归档到 `_archive\`） |
| `C:\Users\Yuki\Desktop\_archive_wsl_sh\` | 归档的 89 个临时 WSL 调用脚本 |

---

## 二、WSL 整理后结构

    /home/yuki/ljepa/
    ├── README.md          本文档
    ├── _filelist.txt      完整文件清单
    ├── core/    (16)      核心功能脚本（勿删）
    ├── tools/   (24)      检查/进度工具
    ├── temp/    (70)      临时调试脚本（可删）
    └── logs/              日志输出

---

## 三、core/ — 核心脚本（勿删）

### 数据下载

| 脚本 | 用途 |
|---|---|
| `era5_72all.py` | **统一 72h 下载器（运行中）** 按区按月批量补下 |
| `era5_batch.py` | CDS 批量下载（按(区,年月)分组 + 自动拆分多天 GRIB） |
| `era5_72h_fetch.py` | 72h met 专项（旧版） |
| `era5_fullprev.py` | 单区下载（原版） |
| `cds_harvester.py` | **CDS 快速收割器（运行中）** 对象存储直下已完成结果 |
| `era5_guard.py` | CDS 限流恢复守卫 |
| `proxy_watchdog.sh` | 代理看门狗（每 2 分钟查 17891） |

### STILT 生产

| 脚本 | 用途 |
|---|---|
| `era5_column_run.py` | 柱足迹生产（11 天 × 120 受体 × 5 高度） |
| `compose_column.py` | 柱足迹合成（气压厚度加权） |
| `conv_arl.sh` | GRIB → ARL 批量转换（era52arl） |

### 其他

| 脚本 | 用途 |
|---|---|
| `resume_downloads.sh` | 一键恢复所有下载守护 |
| `footnet_inputs.py` | **FootNet 对齐输入构建器（新增）** 24/49 通道 |

---

## 四、tools/ — 常用检查命令

在 PowerShell 里直接跑（都是一条，无转义问题）：

    # 72h 数据覆盖率进度
    wsl.exe -d Ubuntu-24.04 -u root -- bash /root/check_72prog.sh

    # 柱足迹全链路检查
    wsl.exe -d Ubuntu-24.04 -u root -- bash /root/check_column.sh

    # CDS 队列诊断（区分 CDS 卡 vs 我们请求有问题）
    wsl.exe -d Ubuntu-24.04 -u root -- bash /root/cds_diag.sh

    # 一键恢复下载
    wsl.exe -d Ubuntu-24.04 -u root -- bash /root/resume_downloads.sh

    # 柱足迹生产进度
    wsl.exe -d Ubuntu-24.04 -u root -- bash /root/column_status.sh

---

## 五、temp/ — 临时脚本（70 个，可删）

已归档而非直接删除，确认无用后可删：

- `arco_*.py` — ARCO-ERA5 探索（方案已否决）
- `cds_probe2.py` / `cds_mini_test.py` / `cds_limitscope.py` — CDS 探测
- `cmp_24_72.sh` / `cmp_analysis.py` — 24h vs 72h 对照实验（已完成）
- `diag_mask.py` / `col_qc.py` / `col_gap.py` / `col_bydate.py` — 一次性质检
- `domcalc.py` / `count_samples.py` / `check_hours.py` — 一次性计算
- `fetch_*.py`（多个）— 早期下载尝试
- `conv_arl.py` — 有 bug（已被 conv_arl.sh 取代）

---

## 六、当前运行的任务（2026-09-12）

| 进程 | 用途 |
|---|---|
| `era5_72all.py` | 统一 72h 补下（96 天 / 192 文件 / 约 80 小时） |
| `cds_harvester.py` | CDS 结果快速收割（每 3 分钟扫一次） |
| `proxy_watchdog.sh` | 代理看门狗 |

⚠️ 这 3 个脚本的**运行实例在 `/root/`**，`core/` 里是副本。改代码后需重启进程才生效。

---

## 七、数据位置

| 数据 | 路径 |
|---|---|
| ERA5 GRIB | `D:\lagrangian-jepa-cn\met_cache\era5d\<region>\<date>_{PL,SFC}.GRIB` |
| ERA5 ARL | `/root/met_era5/<region>/<date>` |
| STILT 足迹 | `/root/work/stilt/out/by-id/<sim_id>/*_foot.nc` |
| 柱足迹合成 | `/root/colfoot/*.npz` + `column_summary.csv` |
| 数据集 | `D:\lagrangian-jepa-cn\data\datasets\<name>\{x.npy,y.npy,meta.json}` |
| 受体表 | `D:\lagrangian-jepa-cn\data\receptors_v2\<region>\` |

---

## 八、关键文档（planning/）

| 文档 | 内容 |
|---|---|
| `PROJECT_STATUS_20260912.md` | **项目状态总览**（数据集/实验/风险） |
| `COLUMN_FOOTPRINT_METHOD_20260910.md` | 柱足迹方法论 |
| `ERA5_DOWNLOAD_SPEC_20260911.md` | ERA5 下载规格 |
| `CAUSALITY_AUDIT_ERRATUM_20260908.md` | 因果审计 No-Go 更正 |
| `PRE_REGISTRATION_v1.json` | 预注册（冻结） |
| `SAMPLE_INDEPENDENCE_ARGUMENT_20260909.md` | 样本独立性论证 |

---

## 九、快速上手

1. 看项目全貌 → `planning/PROJECT_STATUS_20260912.md`
2. 看下载进度 → `bash /root/check_72prog.sh`
3. 看代码 → 资源管理器进 `\\wsl$\Ubuntu-24.04\home\yuki\ljepa\`
4. 恢复下载 → `bash /root/resume_downloads.sh`
5. 诊断问题 → `bash /root/cds_diag.sh`