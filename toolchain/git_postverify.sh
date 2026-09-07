#!/usr/bin/env bash
# 提交后独立核验：从历史对象层面确认，而非只看暂存清单（只读）
set -u
R=/mnt/d/lagrangian-jepa-cn
cd "$R" || exit 1
G="git -c safe.directory=$R -c core.quotepath=false"

echo '===== 1. 提交历史 ====='
$G log --format='  %h  %an <%ae>  %ad%n      %s' --date=iso
printf '  提交总数: %s\n' "$($G rev-list --count HEAD)"

echo
echo '===== 2. 🔴 从 git 对象库层面搜凭据（比查暂存清单更严格） ====='
echo '  --- 2a. 历史中是否存在这三个文件 ---'
for f in mirror/server_backup_20260830/footnet_jepa/agent.md toolchain/wsl_rc.sh toolchain/wsl_cdsapi2.sh; do
  c=$($G log --all --oneline -- "$f" | wc -l)
  [ "$c" -eq 0 ] && echo "    ✅ 从未入库: $f" || echo "    ❌ 历史中有 $c 次提交涉及: $f"
done

echo '  --- 2b. 遍历全部 blob 对象搜密钥形态（最严格） ---'
# 不写密钥明文；从被排除源文件动态提取待查值，只报计数
KEYS=$(mktemp)
for src in toolchain/wsl_rc.sh toolchain/wsl_cdsapi2.sh \
           mirror/server_backup_20260830/footnet_jepa/agent.md; do
  [ -f "$src" ] || continue
  grep -aoE '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}' "$src" >> "$KEYS" 2>/dev/null
  grep -aoE 'LTAI[A-Za-z0-9]{12,}' "$src" >> "$KEYS" 2>/dev/null
  grep -aoE '[A-Za-z0-9]{30}' "$src" >> "$KEYS" 2>/dev/null
done
sort -u "$KEYS" -o "$KEYS"
nkeys=$(wc -l < "$KEYS")
echo "    （提取到 $nkeys 个待查凭据值，值不显示）"
bad=0
while IFS= read -r oid; do
  obj=$($G cat-file blob "$oid" 2>/dev/null) || continue
  if printf '%s' "$obj" | grep -qFf "$KEYS" 2>/dev/null; then
    echo "    ❌ blob 含凭据: $oid"
    bad=1
  fi
done < <($G rev-list --objects --all | awk '{print $1}' | sort -u)
[ "$bad" -eq 0 ] && echo '    ✅ 全部 blob 中均未发现任何已知凭据值'
rm -f "$KEYS"

echo
echo '===== 3. 数据扩展名是否被跟踪（必须全 0） ====='
for pat in '\.npy$' '\.pt$' '\.nc$' '\.nc4$' '\.rds$' '\.GRIB$' '\.grib2$' '\.npz$' '\.whl$' '\.h5$'; do
  c=$($G ls-files | grep -cE "$pat")
  printf '  %-12s %s\n' "$pat" "$([ "$c" -eq 0 ] && echo "✅ 0" || echo "❌ $c")"
done

echo
echo '===== 4. 大数据目录是否被跟踪（必须全 0） ====='
for d in data/datasets data/genghg data/server_backup_20260830 met_cache reuse_stilt py311 downloads; do
  c=$($G ls-files -- "$d" | wc -l)
  printf '  %-38s %s\n' "$d" "$([ "$c" -eq 0 ] && echo "✅ 0" || echo "❌ $c")"
done

echo
echo '===== 5. 跟踪内容构成 ====='
printf '  跟踪文件总数: %s\n' "$($G ls-files | wc -l)"
$G ls-files | awk -F/ '{print $1}' | sort | uniq -c | sort -rn | sed 's/^/    /'
echo '  --- 各扩展名 ---'
$G ls-files | sed -n 's/.*\.\([A-Za-z0-9_]\{1,10\}\)$/\1/p' | tr 'A-Z' 'a-z' \
  | sort | uniq -c | sort -rn | head -12 | sed 's/^/    /'

echo
echo '===== 6. 仓库体积 ====='
printf '  .git      = %s MB\n' "$(du -sm .git | cut -f1)"
$G count-objects -vH | sed 's/^/    /'

echo
echo '===== 7. 工作区状态（提交后应干净，忽略项不显示） ====='
$G status --short | head -10
n=$($G status --short | wc -l)
[ "$n" -eq 0 ] && echo '  ✅ 工作区干净' || echo "  有 $n 项变更（见上）"

echo
echo '===== 8. 忽略规则生效确认（抽查应被忽略的文件） ====='
for f in data/datasets/formal_hrrr_train_p250_all/x.npy \
         met_cache/era5d/po_valley_italy/20160221_PL.GRIB \
         toolchain/wsl_rc.sh \
         mirror/server_backup_20260830/footnet_jepa/agent.md \
         py311/Scripts/python.exe; do
  if [ -e "$f" ]; then
    r=$($G check-ignore -v "$f" 2>/dev/null)
    [ -n "$r" ] && echo "  ✅ 已忽略: $f" || echo "  ❌ 未忽略（危险）: $f"
  fi
done

echo
echo '===== 9. .sh 行尾抽查（WSL 可执行性） ====='
for f in toolchain/wsl_era5_post.sh toolchain/era5_progress.sh toolchain/wsl_era5_fixall.sh; do
  [ -e "$f" ] || continue
  blob=$($G show "HEAD:$f" 2>/dev/null | file -b -)
  printf '  %-42s 历史中: %s\n' "$f" "$blob"
done
