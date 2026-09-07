#!/usr/bin/env bash
# 初始化仓库 + 暂存 + 提交前核验（不执行 commit）
set -u
R=/mnt/d/lagrangian-jepa-cn
cd "$R" || exit 1

echo '===== 1. 初始化 ====='
if [ -d .git ]; then
  echo '  .git 已存在，跳过 init'
else
  git init -q -b main && echo '  git init 完成，默认分支 main'
fi

echo
echo '===== 2. 暂存（可能较慢，需遍历 114GB 目录树做忽略判定） ====='
time git add -A 2>&1 | tail -5

echo
echo '===== 3. 暂存规模 ====='
n=$(git diff --cached --name-only | wc -l)
echo "  暂存文件数: $n"
git diff --cached --name-only | awk -F/ '{print $1}' | sort | uniq -c | sort -rn | sed 's/^/    /'

echo
echo '===== 4. 暂存内容总体积 ====='
git diff --cached --name-only -z 2>/dev/null | xargs -0 du -cb 2>/dev/null | tail -1 \
  | awk '{printf "  %.2f MB\n", $1/1048576}'

echo
echo '===== 5. 🔴 凭据文件是否被误暂存（必须全部为 NO） ====='
for f in mirror/server_backup_20260830/footnet_jepa/agent.md toolchain/wsl_rc.sh toolchain/wsl_cdsapi2.sh; do
  if git diff --cached --name-only | grep -qxF "$f"; then
    echo "  ❌ STAGED: $f"
  else
    echo "  ✅ 未入库: $f"
  fi
done

echo
echo '===== 6. 暂存内容中扫描密钥形态（必须无命中） ====='
hits=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  if grep -qE 'LTAI[A-Za-z0-9]{12,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' "$f" 2>/dev/null; then
    echo "  ❌ 疑似密钥: $f"
    hits=$((hits+1))
  fi
done < <(git diff --cached --name-only)
[ "$hits" -eq 0 ] && echo '  ✅ 无密钥形态命中'

echo
echo '===== 7. 大文件核查（>2MB 的暂存文件） ====='
git diff --cached --name-only -z 2>/dev/null | xargs -0 du -b 2>/dev/null \
  | awk '$1>2097152 {printf "  %8.1f MB  %s\n", $1/1048576, $2}' | sort -rn | head -10
echo '  (以上为空则表示无大文件)'

echo
echo '===== 8. 数据目录是否被误纳入（必须为 0） ====='
for pat in '^data/datasets/' '^data/genghg/' '^met_cache/' '^reuse_stilt/' '^py311/' '\.npy$' '\.pt$' '\.nc$' '\.rds$' '\.GRIB$' '\.grib2$'; do
  c=$(git diff --cached --name-only | grep -cE "$pat")
  printf '  %-22s %s\n' "$pat" "$([ "$c" -eq 0 ] && echo "✅ 0" || echo "❌ $c 个")"
done

echo
echo '===== 9. 各类文件暂存计数 ====='
git diff --cached --name-only | sed -n 's/.*\.\([A-Za-z0-9_]\{1,10\}\)$/\1/p' \
  | tr 'A-Z' 'a-z' | sort | uniq -c | sort -rn | head -15 | sed 's/^/  /'
noext=$(git diff --cached --name-only | grep -vcE '\.[A-Za-z0-9_]{1,10}$')
echo "  (无扩展名)          $noext"

echo
echo '===== 10. 关键文件确认已入库 ====='
for f in .gitignore planning/HANDOFF.md planning/PLAN_GLOBAL.md planning/PRE_REGISTRATION_v1.json \
         planning/HRRR_SAME_CYCLE_WAIVER_v1.md planning/INCIDENT_arl_truncation_20150520.md \
         data/build/assemble.py data/build/feature_sources.py data/build/ARM_BUILD_REPORT.md \
         data/build/make_receipts.py toolchain/wsl_era5_post.sh toolchain/era5_progress.sh \
         mirror/server_backup_20260830/footnet_jepa/models.py \
         mirror/server_backup_20260830/footnet_jepa/train_stilt_strict.py \
         mirror/server_backup_20260830/footnet_jepa/stilt_pipeline/run_batch.py; do
  if git diff --cached --name-only | grep -qxF "$f"; then echo "  ✅ $f"; else echo "  ❌ 缺: $f"; fi
done

echo
echo '===== 11. 保留的构建日志（审计证据） ====='
git diff --cached --name-only | grep -E '^data/build/.*\.log$' | wc -l | sed 's/^/  data\/build 下 .log 数: /'

echo
echo '===== 12. 当前 git 身份（提交前必须非空） ====='
printf '  user.name  = %s\n' "$(git config user.name || echo '(未设置)')"
printf '  user.email = %s\n' "$(git config user.email || echo '(未设置)')"
echo
echo '核验结束。commit 尚未执行，等待署名。'
