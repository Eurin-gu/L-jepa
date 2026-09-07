#!/usr/bin/env bash
# 核查 ncp 20150520 转换截断是否已污染跑批（只读）
set -u
R=north_china_plain; D=20150520; D0=20150519

echo '===== 1. 同区域 ARL 尺寸对照（应完全一致） ====='
ls -l --block-size=1 /root/met_era5/$R/ 2>/dev/null | awk '{printf "  %10s  %s\n", $5, $NF}'

echo
echo '===== 2. GRIB 源文件是否完整（两个日期各 PL+SFC） ====='
for f in /mnt/d/lagrangian-jepa-cn/met_cache/era5d/$R/${D0}_PL.GRIB \
         /mnt/d/lagrangian-jepa-cn/met_cache/era5d/$R/${D0}_SFC.GRIB \
         /mnt/d/lagrangian-jepa-cn/met_cache/era5d/$R/${D}_PL.GRIB \
         /mnt/d/lagrangian-jepa-cn/met_cache/era5d/$R/${D}_SFC.GRIB; do
  [ -e "$f" ] && printf '  %10s  %s\n' "$(stat -c%s "$f")" "$(basename "$f")" || printf '  MISSING  %s\n' "$(basename "$f")"
done

echo
echo '===== 3. conv 日志是否收尾（有 Finished TIME ... 24 才算完成） ====='
for day in $D0 $D; do
  f=/root/auto_run/conv_${R}_${day}.log
  echo "--- $day ---"
  if [ -e "$f" ]; then
    echo "  size=$(stat -c%s "$f") mtime=$(stat -c '%y' "$f")"
    echo "  最后一个 Finished 行: $(grep 'Finished TIME' "$f" | tail -n 1)"
    echo "  Finished 计数: $(grep -c 'Finished TIME' "$f")"
    echo "  最后 3 行:"; tail -n 3 "$f" | sed 's/^/    /'
  else
    echo '  (日志缺失)'
  fi
done

echo
echo '===== 4. 该日期跑批是否已执行、产出多少足迹 ====='
man=/root/auto_run/emanifest_${R}_${D}_p250.csv
if [ -e "$man" ]; then
  echo "  manifest 存在: lines=$(wc -l < "$man")  mtime=$(stat -c '%y' "$man")"
  echo '  前 3 行:'; head -n 3 "$man" | sed 's/^/    /'
else
  echo '  manifest 不存在 -> 跑批尚未执行'
fi
out=/root/auto_run/era5_${R}_${D}.out
if [ -e "$out" ]; then
  echo "  批处理输出 mtime=$(stat -c '%y' "$out")"
  tail -n 12 "$out" | sed 's/^/    /'
else
  echo '  (批处理输出缺失)'
fi

echo
echo '===== 5. 对照：正常日期的 conv 日志 Finished 计数 ====='
for day in 20150301 20160310; do
  f=/root/auto_run/conv_${R}_${day}.log
  [ -e "$f" ] && echo "  $day: Finished=$(grep -c 'Finished TIME' "$f")  ARL=$(stat -c%s /root/met_era5/$R/$day 2>/dev/null)"
done

echo
echo '===== 6. post 脚本的跳过条件（决定能否自动重转） ====='
grep -n 'out=/root/met_era5\|\[ -s "\$out" \]' /mnt/d/lagrangian-jepa-cn/toolchain/wsl_era5_post.sh
