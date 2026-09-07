#!/usr/bin/env bash
# 建库前最后勘察（只读）：mirror 细分体积 / 嵌套 git / 密钥严重度
set -u
R=/mnt/d/lagrangian-jepa-cn

echo '===== 1. mirror 二级目录体积 ====='
for d in "$R"/mirror/server_backup_20260830/*/; do
  [ -d "$d" ] || continue
  printf '  %-28s %8.1f MB  %5d files\n' "$(basename "$d")" \
    "$(du -sm "$d" 2>/dev/null | cut -f1)" \
    "$(find "$d" -type f 2>/dev/null | wc -l)"
done

echo
echo '===== 2. mirror 根下散文件 ====='
find "$R/mirror" -maxdepth 1 -type f -printf '  %10s  %f\n' 2>/dev/null | sort -rn | head

echo
echo '===== 3. mirror 内 >1MB 的文件（决定是否排除） ====='
find "$R/mirror" -type f -size +1M -printf '  %10s  %p\n' 2>/dev/null \
  | sort -rn | head -20 | sed "s|$R/||"

echo
echo '===== 4. 嵌套 .git 目录（会造成 submodule 假象） ====='
found=$(find "$R" -maxdepth 4 -type d -name '.git' 2>/dev/null)
[ -n "$found" ] && echo "$found" | sed "s|$R/||" | sed 's/^/  /' || echo '  (无嵌套 .git)'

echo
echo '===== 5. agent.md 密钥严重度（只报类型与行号，不输出值） ====='
f="$R/mirror/server_backup_20260830/footnet_jepa/agent.md"
if [ -e "$f" ]; then
  grep -nE 'AccessKey|Secret|secret|LTAI|key:' "$f" 2>/dev/null \
    | sed -E -e 's/LTAI[A-Za-z0-9]+/<AK-ID>/' \
             -e 's/[A-Za-z0-9]{28,}/<LONG-STRING-POSSIBLY-SECRET>/' | head -10
  echo "  -> AccessKey Secret 行是否存在: $(grep -cE 'AccessKey Secret|AccessKeySecret' "$f" 2>/dev/null)"
else
  echo '  文件不存在'
fi

echo
echo '===== 6. data/ 下值得入库的非数据文件 ====='
find "$R/data" -maxdepth 2 -type f \( -name '*.md' -o -name '*.py' \) \
  -printf '  %8s  %p\n' 2>/dev/null | sed "s|$R/||" | head -20

echo
echo '===== 7. toolchain 内 >1MB 文件 ====='
find "$R/toolchain" -type f -size +1M -printf '  %10s  %p\n' 2>/dev/null \
  | sort -rn | head -10 | sed "s|$R/||"

echo
echo '===== 8. 换行符现状（Windows/Linux 混用会影响 diff） ====='
crlf=$(find "$R/planning" "$R/toolchain" -maxdepth 1 -type f \( -name '*.md' -o -name '*.sh' \) \
  -exec file {} \; 2>/dev/null | grep -c CRLF)
lf=$(find "$R/planning" "$R/toolchain" -maxdepth 1 -type f \( -name '*.md' -o -name '*.sh' \) \
  -exec file {} \; 2>/dev/null | grep -vc CRLF)
echo "  CRLF 文件: $crlf   非 CRLF: $lf"
