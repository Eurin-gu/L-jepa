#!/usr/bin/env bash
# 建库前勘察：文件类型分布 + 凭据扫描（只读，不做任何写入）
set -u
R=/mnt/d/lagrangian-jepa-cn

echo '===== 1. 各顶层目录的文件类型分布（按扩展名计数） ====='
for d in planning data toolchain mirror downloads .workbuddy reuse_stilt met_cache py311; do
  [ -d "$R/$d" ] || continue
  echo "--- $d ---"
  find "$R/$d" -type f 2>/dev/null \
    | sed -n 's/.*\.\([A-Za-z0-9_]\{1,10\}\)$/\1/p' \
    | tr 'A-Z' 'a-z' | sort | uniq -c | sort -rn | head -12
  echo
done

echo '===== 2. 无扩展名文件（可能是脚本或数据） ====='
find "$R" -maxdepth 3 -type f ! -name '*.*' ! -path '*/py311/*' 2>/dev/null | head -20

echo
echo '===== 3. 凭据/密钥扫描（建库前必查） ====='
echo '--- 3a. 文件名含敏感标记 ---'
find "$R" -type f \( -iname '*cdsapirc*' -o -iname '*.pem' -o -iname '*credential*' \
  -o -iname '*secret*' -o -iname '*apikey*' -o -iname '*api_key*' -o -iname '*.env' \
  -o -iname 'id_rsa*' -o -iname '*token*' -o -iname '*accesskey*' \) \
  ! -path '*/py311/*' 2>/dev/null | head -30

echo
echo '--- 3b. 代码/文档中疑似硬编码密钥（仅列文件名与行号） ---'
grep -rIl -E '(AccessKeyId|access_key_id|AccessKeySecret|LTAI[A-Za-z0-9]{12,}|cdsapirc|api_key\s*[:=]\s*["'"'"'][A-Za-z0-9_-]{20,})' \
  "$R/planning" "$R/data/build" "$R/toolchain" "$R/mirror" 2>/dev/null \
  | grep -vE '/(py311|site-packages)/' | head -20

echo
echo '===== 4. 需要跟踪的核心代码/文档体积估算 ====='
tot=0
for d in planning mirror data/build toolchain; do
  s=$(find "$R/$d" -type f \
      \( -name '*.md' -o -name '*.py' -o -name '*.sh' -o -name '*.json' -o -name '*.csv' \
         -o -name '*.f' -o -name '*.r' -o -name '*.R' -o -name '*.cfg' -o -name '*.txt' \) \
      -printf '%s\n' 2>/dev/null | awk '{a+=$1} END{print a+0}')
  n=$(find "$R/$d" -type f \
      \( -name '*.md' -o -name '*.py' -o -name '*.sh' -o -name '*.json' -o -name '*.csv' \
         -o -name '*.f' -o -name '*.r' -o -name '*.R' -o -name '*.cfg' -o -name '*.txt' \) \
      2>/dev/null | wc -l)
  printf '  %-14s %6d files  %8.1f MB\n' "$d" "$n" "$(echo "$s/1048576" | bc -l)"
  tot=$((tot+s))
done
printf '  %-14s %26.1f MB\n' '合计' "$(echo "$tot/1048576" | bc -l)"

echo
echo '===== 5. 潜在的大文本文件（>5MB 且是文本类型，会拖慢仓库） ====='
find "$R/planning" "$R/data/build" "$R/toolchain" "$R/mirror" -type f \
  \( -name '*.json' -o -name '*.csv' -o -name '*.log' -o -name '*.md' -o -name '*.txt' \) \
  -size +5M -printf '%10s  %p\n' 2>/dev/null | sort -rn | head -15

echo
echo '===== 6. git 身份配置 ====='
printf '  user.name  = %s\n' "$(git config --global user.name 2>/dev/null || echo '(未设置)')"
printf '  user.email = %s\n' "$(git config --global user.email 2>/dev/null || echo '(未设置)')"
