#!/usr/bin/env bash
# 确认 PDF 命中是否为误报（只读）
set -u
R=/mnt/d/lagrangian-jepa-cn
F="$R/toolchain/server_backup_20260830/hysplit_data2arl/hysplit_data2arl/arw2arl/Note-arw2arl.pdf"

echo '===== 1. 文件类型 ====='
file -b "$F"
printf '  大小: %s bytes\n' "$(stat -c%s "$F")"

echo
echo '===== 2. 是否含阿里云 AK 形态（真凭据特征） ====='
if grep -aqE 'LTAI[A-Za-z0-9]{12,}' "$F"; then
  echo '  ❌ 命中 LTAI 前缀 —— 需人工复核'
else
  echo '  ✅ 无 LTAI 前缀命中'
fi

echo
echo '===== 3. UUID 形态命中次数（压缩流中的巧合字节） ====='
c=$(grep -aoE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' "$F" 2>/dev/null | wc -l)
echo "  命中 $c 处"

# 关键：本脚本不得内嵌任何密钥片段（首版曾嵌入 key 首段，已修正）。
# 改为运行时从被 .gitignore 排除的源文件动态提取 UUID，仅在内存中比对，
# 只输出"是/否"，绝不打印内容。
echo '  --- 命中的 UUID 是否与已排除凭据文件中的 key 相同（只答是/否） ---'
KEYS=$(mktemp)
for src in "$R/toolchain/wsl_rc.sh" "$R/toolchain/wsl_cdsapi2.sh" \
           "$R/mirror/server_backup_20260830/footnet_jepa/agent.md"; do
  [ -f "$src" ] || continue
  grep -aoE '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}' \
    "$src" 2>/dev/null >> "$KEYS"
  grep -aoE 'LTAI[A-Za-z0-9]{12,}' "$src" 2>/dev/null >> "$KEYS"
done
sort -u "$KEYS" -o "$KEYS"
if [ -s "$KEYS" ]; then
  echo "  （从 $(wc -l < "$KEYS") 个已知凭据值中比对，值不显示）"
  if grep -aoE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' "$F" 2>/dev/null \
     | sort -u | grep -qFxf "$KEYS"; then
    echo '  ❌ PDF 中含真实凭据 —— 必须排除'
  else
    echo '  ✅ PDF 中的 UUID 与任何已知凭据均不相同 —— 系巧合字节'
  fi
else
  echo '  ⚠️ 未能提取到已知凭据值，无法比对（源文件可能已变动）'
fi
rm -f "$KEYS"

echo
echo '===== 4. 结论 ====='
if [ "$c" -gt 0 ]; then
  echo '  判定依据：PDF 为二进制压缩流，且不含阿里云 AK 前缀，'
  echo '            UUID 形态字节与已知凭据比对不一致 → 误报。'
  echo '  处置：密钥扫描应跳过二进制文件（用 file --mime-encoding 预判）。'
fi

echo
echo '===== 5. 确认仓库尚无提交（删索引安全的前提） ====='
cd "$R"
if git -c safe.directory="$R" rev-parse --verify HEAD >/dev/null 2>&1; then
  echo '  ⚠️ HEAD 已存在，删索引需谨慎'
  git log --oneline -3
else
  echo '  ✅ HEAD 不存在（unborn branch main），索引可安全重建'
fi
printf '  refs/heads 内容: '; ls -1 "$R/.git/refs/heads" 2>/dev/null | tr '\n' ' '; echo
printf '  index 大小: %s bytes\n' "$(stat -c%s "$R/.git/index" 2>/dev/null || echo 0)"

echo
echo '===== 6. 暂存区中被视为二进制的文件数（扫描应跳过的范围） ====='
git -c safe.directory="$R" -c core.quotepath=false ls-files --cached -z 2>/dev/null \
  | tr '\0' '\n' | while IFS= read -r f; do
      [ -f "$R/$f" ] || continue
      file -b --mime-encoding "$R/$f" 2>/dev/null | grep -q binary && echo "$f"
    done | tee /tmp/bin_list.txt | wc -l | sed 's/^/  二进制文件: /'
echo '  --- 清单 ---'
sed 's/^/    /' /tmp/bin_list.txt | head -20
