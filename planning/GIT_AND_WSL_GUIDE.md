# Git 与 WSL 使用手册

> 本仓库：`D:\lagrangian-jepa-cn`　分支：`main`　首个提交：`5a9fa7d`（2026-09-07）
> 环境：Windows 11 + git 2.54 / WSL2 Ubuntu-24.04（默认用户 `yuki`，root 免密）
> 写给本项目使用者。所有命令都在本机实测过。

---

## 第一部分：这个仓库的 git 现状

### 1.1 规模对照

| 项 | 数值 |
|---|---|
| 磁盘总占用 | 约 114 GB |
| **被 git 跟踪** | **799 文件 / 10.79 MB** |
| `.git` 目录 | 9 MB |
| 被忽略 | 约 114 GB（数据集、气象缓存、STILT 标签、Python 环境、二进制） |

跟踪内容构成：

```
449 toolchain    STILT/era52arl 的 Fortran·R 源码 + 192 个 .sh 编排脚本
217 data         data/build 建集器代码 + data/receptors_v2 受体表
 92 mirror       上游 footnet_jepa 代码快照 + results 实验 json
 39 planning     决策与轮次文档（项目的大脑）
  2 .gitignore / .gitattributes
```

按扩展名：192 `.sh`、135 `.f`、99 `.json`、70 `.py`、66 `.csv`、55 `.md`、55 `.log`、31 `.r`。

### 1.2 三个约定，违反会出事

**约定一：含明文凭据的文件永不入库**

| 文件 | 内容 |
|---|---|
| `mirror/server_backup_20260830/footnet_jepa/agent.md` | 阿里云 AccessKey ID + Secret |
| `toolchain/wsl_rc.sh` | CDS API key（写入 `~/.cdsapirc`） |
| `toolchain/wsl_cdsapi2.sh` | 同一个 CDS key |

它们**在磁盘上保持原样可用**，只是不进版本库。已在 `.gitignore` 第 1 节。

⚠️ git 排除**不等于安全**。这两把密钥已明文落盘多处，轮换仍是待办，见
`planning/PRE_REGISTRATION_v1.json` 的 `open_items_blocking_formal_runs`。
一旦密钥进过任何一个提交，它就在历史里永久存在——即使后来删掉文件，
`git log --all` 仍能翻出来。清理需要重写历史（`filter-repo`）并强制推送，代价极高。
所以**提交前扫描是硬纪律**，见 1.4 节。

**约定二：行尾一律 LF**

Windows 全局配置是 `core.autocrlf = true`，会在 checkout 时把 LF 转 CRLF。
本仓库有 192 个 `.sh` 要在 WSL 里执行，带 CRLF 的脚本会报：

```
bash\r: No such file or directory
```

`.gitattributes` 已锁定 `* text=auto eol=lf`。**不要删除这个文件。**

例外：`data/build/manifests/**`、`data/receptors_v2/**`、`arm_*.csv` 标了 `-text`。
这些 CSV 参与 sha256 审计链且本身是混合换行符，必须按原始字节保存，禁止 git 重写。

**约定三：数据产物永不入库**

`.npy / .pt / .nc / .rds / .GRIB / .npz / .whl` 全部排除。
判断标准很简单：**能从代码重新生成的，不入库**；
`data/receptors_v2/` 的受体表是例外——它是科学定义（seed 20260822 的 maximin 选点），
重建代价高且只有 1.8 MB，所以入库。

### 1.3 日常操作

```bash
# 看现在改了什么
git status
git status --short          # 紧凑版

# 看具体改动的内容
git diff                    # 工作区 vs 暂存区
git diff --staged           # 暂存区 vs 上次提交

# 提交
git add <文件>              # 推荐：指名添加
git add -A                  # 全部（依赖 .gitignore 兜底，慎用）
git commit -m "说明"

# 看历史
git log --oneline -20
git log --stat -1           # 最近一次提交改了哪些文件
git show <commit>           # 看某次提交的完整改动

# 撤销（按危险程度递增）
git restore <文件>          # 丢弃工作区改动 ⚠️ 不可恢复
git restore --staged <文件> # 取消暂存，改动保留
git commit --amend          # 修改最后一次提交（未推送时才安全）
```

**本项目的提交习惯**：`planning/` 下的轮次文档每次实验后都会更新，
建议和代码改动分开提交，说明写清「这一轮做了什么、结论是什么」。

### 1.4 提交前的凭据扫描（强烈建议养成习惯）

```bash
# 看某个文件为什么被忽略
git check-ignore -v toolchain/wsl_rc.sh

# 扫暂存区里有没有密钥形态（不打印明文）
git diff --cached --name-only | while read f; do
  [ -f "$f" ] || continue
  file -b --mime-encoding "$f" | grep -q binary && continue
  grep -qE 'LTAI[A-Za-z0-9]{12,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' "$f" \
    && echo "疑似密钥: $f"
done
```

两条纪律：

1. **扫描脚本自身不得内嵌密钥明文**。本项目踩过：为了扫 CDS key，
   把它的明文写进了 grep 模式，结果脚本自己成了泄漏源，被闸门拦下。
   正确做法是只做**形态匹配**（UUID 结构、`LTAI` 前缀），或运行时从
   被排除的源文件动态提取待查值。
2. **跳过二进制文件**。`Note-arw2arl.pdf` 是 zip deflate 编码，
   压缩流里巧合出现 2 处 UUID 形态字节，经与已知凭据逐一比对确认不一致，是误报。

本项目已有一个完整的提交前闸门脚本 `toolchain/git_init_commit.sh`，
含体积上限、凭据检查、数据混入检查、大文件检查，任一不过即中止提交。
以后大改 `.gitignore` 后可以拿它重跑验证。

### 1.5 尚未配置远程

本仓库目前**只有本地历史**，没有 `origin`。要推送到 GitHub/Gitee/内网 GitLab：

```bash
git remote add origin <仓库地址>
git push -u origin main
```

⚠️ **推送前务必确认 1.2 节约定一**。推送到任何远程都等于把内容交给第三方，
即使仓库设为 private，凭据也不该进历史。当前状态是干净的，保持住。

---

## 第二部分：WSL 怎么用

### 2.1 为什么这个项目必须用 WSL

STILT（拉格朗日粒子模型）**只支持 Linux**。本项目的标签生成、ARL 格式转换、
批量跑批全部在 WSL2 里执行，Windows 侧只做文件存放和轻量数据处理。

### 2.2 进入 WSL

```powershell
wsl -l -v                        # 列出发行版与状态
wsl -d Ubuntu-24.04              # 以默认用户 yuki 进入
wsl -d Ubuntu-24.04 -u root      # 以 root 进入
```

一次性执行命令（不进交互 shell）：

```powershell
wsl -d Ubuntu-24.04 -- bash -lc 'nvidia-smi'
```

### 2.3 路径映射

| Windows | WSL |
|---|---|
| `D:\lagrangian-jepa-cn` | `/mnt/d/lagrangian-jepa-cn` |
| `C:\Users\Yuki\Desktop\oss_work` | `/mnt/c/Users/Yuki/Desktop/oss_work` |

规则：盘符 `X:\` → `/mnt/x/`，反斜杠改正斜杠。

⚠️ **跨文件系统访问很慢**。WSL 读写 `/mnt/d` 要经过 9P 协议转换，
比原生 ext4 慢一个量级。所以本项目把中间产物（ARL 气象文件、跑批输出）
放在 `/root/met_era5`、`/root/auto_run`（WSL 原生盘），
只把最终数据集写回 `/mnt/d`。你以后加流程时沿用这个分工。

### 2.4 🔴 本项目的三个大坑（都实际踩过）

**坑一：PowerShell 引号嵌套**

这是本项目最频繁的失败原因。PowerShell 会先解析一遍命令字符串，
`wsl -- bash -lc "...嵌套引号..."` 里的 `$()`、`"`、`;` 会被 PowerShell 抢先处理，
结果送到 bash 时已经面目全非，典型报错：

```
/bin/bash: -c: line 1: syntax error near unexpected token `('
```

**解决办法：只要逻辑超过一行，就写成 `.sh` 文件再执行。**

```powershell
# ❌ 别这样
wsl -d Ubuntu-24.04 -- bash -lc 'for f in a b; do echo "$(stat -c %s $f)"; done'

# ✅ 这样
wsl -d Ubuntu-24.04 -- bash /mnt/d/lagrangian-jepa-cn/toolchain/你的脚本.sh
```

本项目 `toolchain/` 下的 `era5_progress.sh`、`era5_deepcheck.sh` 就是这么来的。

另一个变体：`wsl ... > /tmp/x.txt` 里的 `/tmp/x.txt` 会被 PowerShell 当成
Windows 路径解析成 `D:\tmp\x.txt`，然后报目录不存在。重定向要放在脚本内部做。

**坑二：dubious ownership**

用 root 身份操作 `/mnt/d` 下的仓库，git 会拒绝：

```
fatal: detected dubious ownership in repository at '/mnt/d/lagrangian-jepa-cn'
```

原因是 `/mnt/d` 是 Windows 挂载盘，所有文件属主由挂载选项统一映射为 `yuki`(1000:1000)，
root 去看就觉得「这仓库不是我的，可能被篡改」。

**推荐解法：直接用 yuki 身份跑 git，从根上避开。**

```powershell
wsl -d Ubuntu-24.04 -- bash 脚本.sh          # 默认就是 yuki，没问题
wsl -d Ubuntu-24.04 -u root -- bash 脚本.sh  # root 会撞上这个问题
```

如果确实需要 root（比如读 `/root/auto_run` 下的日志），
用单次授权，**不要改全局配置**：

```bash
git -c safe.directory=/mnt/d/lagrangian-jepa-cn status
```

本项目脚本里统一封装成了 `G="git -c safe.directory=$R"`。

**坑三：Windows 和 WSL 各有独立的 git 配置**

两侧的全局配置互不相通。本项目把身份配在**仓库级**（`.git/config`），
两侧共用，所以不受影响：

```bash
git config user.name    # Yuying Gu
git config user.email   # 2534171146@qq.com
git config core.fileMode   # false（跨文件系统必须关，否则权限位一直显示为已修改）
git config core.quotepath  # false（让中文名正常显示，不转义成 \351\241\271）
```

`core.fileMode false` 特别重要：Windows 挂载盘不支持 Unix 权限位，
不关的话 `git status` 会永远显示所有文件已修改。

### 2.5 本项目在 WSL 里的关键路径

| 路径 | 内容 |
|---|---|
| `/root/venvs/cds` | cdsapi 虚拟环境（ERA5 下载） |
| `/root/venvs/ml` | torch 虚拟环境（GPU 训练） |
| `/root/met_era5/<region>/<day>` | ERA5 转出的 ARL 气象文件 |
| `/root/auto_run/` | 跑批清单 `emanifest_*`、转换日志 `conv_*`、锁目录 `locks/` |
| `/root/work/stilt` | STILT 引擎与输出 `out/by-id/` |
| `/root/work/hysplit_data2arl` | 格式转换器源码 |
| `~/.cdsapirc` | CDS 认证配置（由 `wsl_rc.sh` 写入） |

代理（ERA5/GDAS 下载依赖）：

```bash
export HTTPS_PROXY=http://127.0.0.1:17891
export HTTP_PROXY=http://127.0.0.1:17891
```

### 2.6 常用 WSL 体检命令

```bash
# GPU 是否可用
nvidia-smi

# 磁盘（注意看 /mnt/d 的剩余空间）
df -h /mnt/d /root

# 看本项目相关的活进程
ps -eo pid,etime,stat,cmd | grep -Ei 'era5|fixall|stilt|run_batch' | grep -v grep

# 看某个日志尾部
tail -f /root/auto_run/era5_po_valley_italy_20150211.out

# ERA5 下载进度总览（本项目自带）
bash /mnt/d/lagrangian-jepa-cn/toolchain/era5_progress.sh
```

⚠️ **系统时钟比真实 UTC 慢 8 小时**（见 `planning/HANDOFF.md` 第 20 行）。
所有阿里云 OSS 签名脚本必须做偏移补偿。读文档里的时间戳时留意这点。

### 2.7 单实例纪律

ERA5 下载链路要求单实例运行，详见 `planning/ROUND73_STATUS.md`：

```
## User-side automation active (do not duplicate)
- era5_fixall manages era5d po/ncp + met_era5 + manifests. AVOID conflicting with it.
```

原因有三，前两条项目里有实测记录：

1. **CDS 队列配额同账号共享**，多开只会互相拖慢。`ROUND67_NOTES.md` 实测：
   ncpA + ncpB 双下载器并行「no clear gain; congestion is server-side」，后来停掉一个。
2. **写入范围重叠**，`era5d` / `met_era5` / `manifests` 三处会被同时写。
3. `wsl_era5_fixall.sh` 用 `tee`（覆盖而非追加）写日志，
   且完成标记 `era5_fixall.done` 依赖 grep 这个日志——
   两实例互相截断会导致标记永不落盘。它没有 flock，单实例纯靠约定维持。

**动手前先 `ps` 看一眼有没有同名进程在跑。**

---

## 第三部分：建库过程记录（含踩过的坑）

首轮提交并非一次成功，闸门拦下两次。记录在此供参考：

| 轮次 | 问题 | 处置 |
|---|---|---|
| 1 | `dubious ownership`（用 root 操作 `/mnt/d`） | 改用 yuki 身份跑 git |
| 1 | `git diff --cached` 在空仓库退化为 `--no-index`，报错刷屏 | 改用 `git ls-files` |
| 2 | 漏排 `data/server_backup_20260830/`（20.7 GB），9 个大 `meta.json` 混入 | 补入 `.gitignore`，体积 89 MB → 11 MB |
| 2 | `git rm -r --cached .` 失败（三方内容互不相同） | 空仓库 HEAD 不存在，直接删 `.git/index` 重建 |
| 2 | 我自己的核验脚本内嵌了密钥明文，被自己的闸门拦下 | 改为形态匹配，不含明文 |
| 3 | `Note-arw2arl.pdf` 压缩流中 UUID 形态字节造成误报 | 扫描跳过二进制，并逐一比对确认非真凭据 |
| 3 | 编译产物 `era52arl`（无扩展名）混入 | 补入 `.gitignore`，源码 `.f` 已入库可重编 |

体积闸门的设计价值在此体现：如果直接 `git add -A && git commit`，
那 9 个大 meta.json（合计约 70 MB）会永久留在历史里，事后清理要重写历史。

### 提交后核验结果

`toolchain/git_postverify.sh` 从 git 对象库层面验证（比查暂存清单严格）：

```
✅ 三个凭据文件从未入库（git log --all -- <file> 均为空）
✅ 遍历全部 blob 对象，未发现任何已知凭据值
✅ 10 种数据扩展名跟踪数均为 0
✅ 7 个大数据目录跟踪数均为 0
✅ 5 个抽查的应忽略文件，check-ignore 全部确认生效
✅ 3 个抽查的 .sh 在历史中为 ASCII/UTF-8 text executable（LF，可执行）
```

### 本目录下的辅助脚本

| 脚本 | 用途 |
|---|---|
| `git_init_commit.sh` | 暂存 + 五项闸门核验 + 提交（含体积上限） |
| `git_postverify.sh` | 提交后从对象库层面独立核验 |
| `git_secret_scan.sh` | 凭据扫描（输出脱敏） |
| `git_verify_fp.sh` | 判定扫描命中是否为误报 |
| `git_presurvey.sh` / `git_presurvey2.sh` | 建库前体积与文件类型勘察 |
| `git_diagnose.sh` | 排查闸门拦下的问题 |
| `git_measure_pending.sh` | 测量待定目录体积 |
| `git_chown.sh` | 修正 `.git` 属主 |

全部只读或只动 `.git` 内部，不修改任何数据文件。
