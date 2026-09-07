#!/usr/bin/env bash
# 凭据命中核查：输出前对密钥做脱敏，不呈现明文（只读）
set -u
R=/mnt/d/lagrangian-jepa-cn
PAT='(AccessKeyId|access_key_id|AccessKeySecret|LTAI[A-Za-z0-9]{12,}|cdsapirc|api_key|secret|Bearer )'

redact() {
  sed -E \
    -e 's/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/<UUID-REDACTED>/g' \
    -e 's/LTAI[A-Za-z0-9]{12,}/<ALIYUN-AK-REDACTED>/g' \
    -e 's/(key|secret|token|password)([[:space:]]*[:=][[:space:]]*)[^[:space:],"]+/\1\2<REDACTED>/gi'
}

for f in planning/ERA5_FETCH_FIX.md planning/HANDOFF.md \
         mirror/server_backup_20260830/footnet_jepa/agent.md; do
  echo "===== $f ====="
  if [ -e "$R/$f" ]; then
    grep -nE "$PAT" "$R/$f" 2>/dev/null | redact | head -8
    n=$(grep -cE "$PAT" "$R/$f" 2>/dev/null || echo 0)
    echo "  (命中 $n 行)"
  else
    echo '  文件不存在'
  fi
  echo
done

echo '===== 明文 UUID 密钥全仓扫描（脱敏计数，不输出原文） ====='
grep -rIl -E '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' \
  "$R/planning" "$R/toolchain" "$R/mirror" "$R/data/build" 2>/dev/null \
  | grep -vE '/(py311|site-packages)/' | while read -r p; do
      c=$(grep -coE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' "$p" 2>/dev/null || echo 0)
      printf '  %s  (UUID 形态字符串 %s 处)\n' "${p#$R/}" "$c"
    done

echo
echo '===== 阿里云 AK 形态（LTAI 前缀）全仓扫描 ====='
hits=$(grep -rIl -E 'LTAI[A-Za-z0-9]{12,}' "$R/planning" "$R/toolchain" "$R/mirror" "$R/data/build" 2>/dev/null | grep -vE '/(py311|site-packages)/')
if [ -n "$hits" ]; then echo "$hits" | sed "s|$R/||" | sed 's/^/  /'; else echo '  (无命中)'; fi
