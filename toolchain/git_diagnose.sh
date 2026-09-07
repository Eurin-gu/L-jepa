#!/usr/bin/env bash
# 排查闸门拦下的两个问题（只读）
set -u
R=/mnt/d/lagrangian-jepa-cn
cd "$R" || exit 1

echo '===== A. data/server_backup_20260830/ 结构（20.7GB，含误入的 meta.json） ====='
du -sm "$R"/data/server_backup_20260830/*/ 2>/dev/null | sort -rn | head -10 | sed 's/^/  /'
echo '  --- 二级 ---'
du -sm "$R"/data/server_backup_20260830/*/*/ 2>/dev/null | sort -rn | head -12 | sed "s|$R/||" | sed 's/^/  /'
echo '  --- 该子树内的非数据文本文件（>1MB） ---'
find "$R/data/server_backup_20260830" -type f -size +1M -printf '    %8.2f MB  %p\n' 2>/dev/null \
  | awk '{printf "    %8.2f MB  %s\n", $1/1, $3}' | head -5
find "$R/data/server_backup_20260830" -type f \( -name '*.py' -o -name '*.md' -o -name '*.sh' \) \
  -printf '    %8s  %p\n' 2>/dev/null | sed "s|$R/||" | head -15

echo
echo '===== B. 那个带引号的暂存条目（文件名含特殊字符） ====='
git ls-files --cached | grep -n '"' | head -5
echo '  --- 用 -z 安全列出非 ASCII/特殊字符文件名 ---'
git ls-files --cached -z | tr '\0' '\n' | grep -vE '^[\x20-\x7E]+$' | head -10 | cat -A | head -10

echo
echo '===== C. 我的勘察脚本中的 key 字面量（需去除） ====='
for f in toolchain/git_presurvey.sh toolchain/git_secret_scan.sh toolchain/git_init_stage.sh \
         toolchain/git_init_commit.sh toolchain/git_measure_pending.sh toolchain/git_chown.sh; do
  [ -e "$f" ] || continue
  c=$(grep -c '58bf9f99' "$f" 2>/dev/null || echo 0)
  printf '  %-40s key 字面量 %s 处\n' "$f" "$c"
done

echo
echo '===== D. CSV 实际换行符（.gitattributes 规范化前的现状） ====='
for f in data/build/arm_final_summary.csv data/receptors_v2/so_cal_LA_basin/receptors_20160807_n120_maximin.csv \
         planning/oco2_candidates_2016_2017.csv; do
  [ -e "$f" ] && printf '  %-72s %s\n' "$f" "$(file -b "$f")"
done

echo
echo '===== E. 全仓 CRLF 文件计数（按扩展名） ====='
find "$R/planning" "$R/data/build" "$R/data/receptors_v2" "$R/toolchain" "$R/mirror" \
  -type f \( -name '*.csv' -o -name '*.json' -o -name '*.md' -o -name '*.py' -o -name '*.sh' \
     -o -name '*.txt' -o -name '*.f' -o -name '*.r' -o -name '*.inc' -o -name '*.cfg' -o -name '*.log' \) \
  -size -20M 2>/dev/null | while read -r p; do
    file -b "$p" 2>/dev/null | grep -q CRLF && echo "$p"
  done | sed -n 's/.*\.\([A-Za-z0-9_]\{1,10\}\)$/\1/p' | tr 'A-Z' 'a-z' \
  | sort | uniq -c | sort -rn | head -10 | sed 's/^/  /'

echo
echo '===== F. 若排除 data/server_backup_20260830，暂存体积预估 ====='
git ls-files --cached -z | tr '\0' '\n' \
  | grep -v '^data/server_backup_20260830/' > /tmp/would_stage.txt
echo "  文件数: $(wc -l < /tmp/would_stage.txt)  (当前 $(git ls-files --cached | wc -l))"
tr '\n' '\0' < /tmp/would_stage.txt | xargs -0 du -cb 2>/dev/null | tail -1 \
  | awk '{printf "  体积:   %.2f MB\n", $1/1048576}'
echo '  --- 排除后 >2MB 的文件 ---'
tr '\n' '\0' < /tmp/would_stage.txt | xargs -0 du -b 2>/dev/null \
  | awk '$1>2097152 {printf "    %8.2f MB  %s\n", $1/1048576, $2}' | sort -rn | head
