#!/usr/bin/env bash
# 核实手册中引用的数字是否与仓库当前状态一致（只读）
set -u
R=/mnt/d/lagrangian-jepa-cn
cd "$R" || exit 1
G="git -c safe.directory=$R -c core.quotepath=false"

echo '===== 1. 提交历史 ====='
$G log --oneline

echo
echo '===== 2. 当前跟踪文件总数与总体积 ====='
N=$($G ls-files | wc -l)
echo "文件数 = $N"
$G ls-files -z | du -ch --files0-from=- 2>/dev/null | tail -n 1
echo ".git 体积 = $(du -sh .git | cut -f1)"

echo
echo '===== 3. 按扩展名计数（前 12） ====='
$G ls-files | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -n 12

echo
echo '===== 4. 按顶层目录计数 ====='
$G ls-files | cut -d/ -f1 | sort | uniq -c | sort -rn

echo
echo '===== 5. .sh 数量（手册称 192） ====='
$G ls-files '*.sh' | wc -l

echo
echo '===== 6. 仓库级配置（手册 2.4 坑三引用） ====='
for k in user.name user.email core.fileMode core.quotepath core.autocrlf; do
  printf '%-18s = %s\n' "$k" "$($G config --local --get $k 2>/dev/null || echo '(未设置)')"
done

echo
echo '===== 7. 三个凭据文件确认未入库 ====='
for f in mirror/server_backup_20260830/footnet_jepa/agent.md toolchain/wsl_rc.sh toolchain/wsl_cdsapi2.sh; do
  T=$($G ls-files -- "$f" | wc -l)
  H=$($G log --all --oneline -- "$f" | wc -l)
  D=$([ -f "$f" ] && echo 存在 || echo 缺失)
  printf '  跟踪=%s 历史=%s 磁盘=%s  %s\n' "$T" "$H" "$D" "$f"
done

echo
echo '===== 8. 工作区状态 ====='
$G status --short | head -n 10
echo "(以上为空则工作区干净)"
