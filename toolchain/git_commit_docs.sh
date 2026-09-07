#!/usr/bin/env bash
# 第二次提交：使用手册 + 提交后核验脚本（沿用同一套闸门）
set -u
R=/mnt/d/lagrangian-jepa-cn
cd "$R" || exit 1
G="git -c safe.directory=$R -c core.quotepath=false"
MAX_FILE_MB=2

echo '===== 1. 待提交内容 ====='
$G status --short

echo
echo '===== 2. 暂存指定文件（不用 add -A） ====='
# 手册中「辅助脚本」表列出的工具一并入库，使文档与仓库实际一致。
# 逐个指名添加，不用 add -A。
$G add planning/GIT_AND_WSL_GUIDE.md
for s in git_postverify.sh git_init_commit.sh git_secret_scan.sh git_verify_fp.sh \
         git_presurvey.sh git_presurvey2.sh git_diagnose.sh git_measure_pending.sh \
         git_chown.sh git_init_stage.sh git_commit_docs.sh; do
  [ -f "toolchain/$s" ] && $G add "toolchain/$s"
done
echo "  rc=$?"
$G diff --cached --name-only

echo
echo '===== 3. 闸门：凭据文件不得入库 ====='
sec=0
for f in mirror/server_backup_20260830/footnet_jepa/agent.md toolchain/wsl_rc.sh toolchain/wsl_cdsapi2.sh; do
  $G ls-files --cached | grep -qxF "$f" && { echo "  ❌ STAGED: $f"; sec=1; }
done
[ "$sec" -eq 0 ] && echo '  ✅ 三个凭据文件仍未入库'

echo
echo '===== 4. 闸门：新增两个文件的密钥形态扫描 ====='
khit=0
for f in planning/GIT_AND_WSL_GUIDE.md toolchain/git_postverify.sh; do
  [ -f "$f" ] || continue
  enc=$(file -b --mime-encoding "$f")
  [ "$enc" = "binary" ] && continue
  if grep -qE 'LTAI[A-Za-z0-9]{12,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' "$f"; then
    echo "  ❌ 疑似密钥: $f"; khit=1
  fi
done
[ "$khit" -eq 0 ] && echo '  ✅ 无命中（两文件均不含密钥明文，只做形态匹配）'

echo
echo '===== 5. 闸门：大文件 ====='
big=0
for f in planning/GIT_AND_WSL_GUIDE.md toolchain/git_postverify.sh; do
  s=$(stat -c%s "$f")
  printf '  %8.2f KB  %s\n' "$(awk -v x="$s" 'BEGIN{print x/1024}')" "$f"
  [ "$s" -gt $((MAX_FILE_MB*1048576)) ] && big=1
done
[ "$big" -eq 0 ] && echo '  ✅ 均远低于 2MB 上限'

echo
echo '===== 6. 闸门：数据扩展名不得混入本次暂存 ====='
dbad=$($G diff --cached --name-only | grep -cE '\.(npy|pt|nc|nc4|rds|GRIB|grib2|npz|whl|h5)$')
[ "$dbad" -eq 0 ] && echo '  ✅ 0 个' || echo "  ❌ $dbad 个"

echo
echo '===== 7. 判定 ====='
if [ "$sec" -eq 1 ] || [ "$khit" -eq 1 ] || [ "$big" -eq 1 ] || [ "$dbad" -ne 0 ]; then
  echo '  ❌ 中止提交'; exit 1
fi
echo '  ✅ 通过'

echo
echo '===== 8. 提交 ====='
$G commit -q -F - <<'MSG'
docs: 补充 Git 与 WSL 使用手册，加入提交后核验脚本

planning/GIT_AND_WSL_GUIDE.md
  三部分：仓库 git 现状与三条硬约定 / WSL 使用与本项目三个实测坑 /
  建库过程记录（含闸门拦下的 7 个问题及处置）。
  重点记录：
  - 凭据文件永不入库，但 git 排除不等于安全，密钥轮换仍是待办
  - core.autocrlf=true 会把 192 个 .sh 转成 CRLF 而在 WSL 下无法执行，
    故 .gitattributes 锁定 LF；审计链 CSV 标 -text 保持原始字节
  - PowerShell 引号嵌套是本项目最频繁的失败原因，多行逻辑一律走 .sh 文件
  - root 操作 /mnt/d 触发 dubious ownership，应改用 yuki 身份或单次
    -c safe.directory 授权，不改全局配置
  - core.fileMode 必须为 false，否则挂载盘权限位导致 status 永远脏

toolchain/git_postverify.sh
  提交后独立核验，比查暂存清单更严格：遍历全部 blob 对象比对已知凭据值
  （值从被排除的源文件动态提取，脚本自身不含明文），确认数据扩展名与
  大数据目录跟踪数为 0，抽查忽略规则生效与历史中 .sh 的行尾。
MSG
echo "  commit rc=$?"

echo
echo '===== 9. 结果 ====='
$G log --format='  %h  %an  %ad%n      %s' --date=short
printf '  提交总数: %s\n' "$($G rev-list --count HEAD)"
printf '  跟踪文件: %s\n' "$($G ls-files | wc -l)"
printf '  .git 体积: %s MB\n' "$(du -sm .git | cut -f1)"
echo
echo '  --- 工作区状态 ---'
n=$($G status --short | wc -l)
[ "$n" -eq 0 ] && echo '  ✅ 干净' || $G status --short
