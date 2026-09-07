#!/usr/bin/env bash
# 补测两个待定目录的体积（只读）
set -u
R=/mnt/d/lagrangian-jepa-cn

for d in data/receptors_v2 data/receptors mirror/server_backup_20260830/footnet_jepa/results \
         mirror/server_backup_20260830/footnet_jepa/stilt_pipeline; do
  p="$R/$d"
  if [ -d "$p" ]; then
    n=$(find "$p" -type f 2>/dev/null | wc -l)
    s=$(find "$p" -type f -printf '%s\n' 2>/dev/null | awk '{a+=$1} END{print a+0}')
    printf '  %-58s %5d files  %8.2f MB\n' "$d" "$n" "$(awk -v x="$s" 'BEGIN{print x/1048576}')"
    find "$p" -type f -size +1M -printf '      大文件 %10s  %f\n' 2>/dev/null | head -5
  else
    printf '  %-58s (不存在)\n' "$d"
  fi
done

echo
echo '  --- receptors_v2 内部结构 ---'
find "$R/data/receptors_v2" -maxdepth 1 -type d 2>/dev/null | sed "s|$R/||" | sed 's/^/    /'
echo "    CSV 总数: $(find "$R/data/receptors_v2" -name '*.csv' 2>/dev/null | wc -l)"
echo "    最大 CSV: $(find "$R/data/receptors_v2" -name '*.csv' -printf '%s\n' 2>/dev/null | sort -rn | head -1) bytes"

echo
echo '  --- results/ 内部构成 ---'
find "$R/mirror/server_backup_20260830/footnet_jepa/results" -type f -printf '    %10s  %f\n' 2>/dev/null | sort -rn | head -10
