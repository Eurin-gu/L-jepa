#!/usr/bin/env bash
# ERA5 下载进度/速率/卡死体检（只读）
set -u
REC=/mnt/d/lagrangian-jepa-cn/data/receptors_v2
E5=/mnt/d/lagrangian-jepa-cn/met_cache/era5d
MET=/root/met_era5
LK=/root/auto_run/locks
FETCH_LOG=/mnt/c/Users/Yuki/Desktop/oss_work/era5_fetch.out.log
FIX_LOG=/root/era5_fixall.log

date '+LOCAL_NOW %F %T %Z'
date -u '+UTC_NOW  %F %T'

echo
echo '===== 1. 活进程 ====='
ps -eo pid,etime,stat,rss,cmd --sort=start_time \
  | grep -Ei 'era5|fixall|watch|fullprev|cdsapi|run_batch' | grep -v grep || echo '(无匹配进程)'

echo
echo '===== 2. 日志新鲜度 ====='
for f in "$FETCH_LOG" "$FIX_LOG"; do
  if [ -e "$f" ]; then
    m=$(stat -c %Y "$f"); n=$(date +%s); age=$(( (n-m)/60 ))
    printf '%-70s size=%-9s age=%s min\n' "$f" "$(stat -c %s "$f")" "$age"
  else
    printf '%-70s MISSING\n' "$f"
  fi
done

echo
echo '===== 3. fetch 日志尾部 ====='
[ -e "$FETCH_LOG" ] && tail -n 25 "$FETCH_LOG" || echo '(无)'

echo
echo '===== 4. GRIB 到货 ====='
for r in po_valley_italy north_china_plain; do
  d=$E5/$r
  [ -d "$d" ] || { echo "$r: 目录不存在"; continue; }
  tot=$(find "$d" -maxdepth 1 -name '*.GRIB' -type f 2>/dev/null | wc -l)
  pl=$(find "$d" -maxdepth 1 -name '*_PL.GRIB'  2>/dev/null | wc -l)
  sf=$(find "$d" -maxdepth 1 -name '*_SFC.GRIB' 2>/dev/null | wc -l)
  sz=$(du -sm "$d" 2>/dev/null | cut -f1)
  echo "$r: GRIB=$tot (PL=$pl SFC=$sf) size=${sz}MB"
  echo '  最近 6 个到货:'
  find "$d" -maxdepth 1 -name '*.GRIB' -printf '    %TY-%Tm-%Td %TH:%TM  %10s  %f\n' 2>/dev/null \
    | sort -r | head -n 6
done

echo
echo '===== 5. 应到货清单 vs 实到 ====='
PO='20150211 20150721 20150813 20160115 20160221 20160714 20160909 20170101 20170327 20170421 20171023'
NCP='20150301 20150520 20150605 20151103 20160106 20160209 20160310 20160506 20161123 20161216 20170626'
for r in po_valley_italy north_china_plain; do
  [ "$r" = po_valley_italy ] && LST="$PO" || LST="$NCP"
  echo "-- $r --"
  have=0; want=0; miss=''
  for date in $LST; do
    [ -f "$REC/$r/receptors_${date}_n120_maximin.csv" ] || continue
    for day in $(date -d "$date -1 day" +%Y%m%d) $date; do
      want=$((want+2))
      p=$E5/$r/${day}_PL.GRIB; s=$E5/$r/${day}_SFC.GRIB
      if [ -s "$p" ] && [ -s "$s" ]; then have=$((have+2)); else miss="$miss $day"; fi
    done
  done
  echo "   需 $want 个 GRIB, 已到 $have 个, 缺 $((want-have)) 个"
  [ -n "$miss" ] && echo "   缺日期(prev+target 任一半缺):$miss"
done

echo
echo '===== 6. 转换产物 met_era5 ====='
for r in po_valley_italy north_china_plain; do
  d=$MET/$r
  if [ -d "$d" ]; then
    n=$(find "$d" -maxdepth 1 -type f 2>/dev/null | wc -l)
    echo "$r: ARL 文件 $n 个"
    find "$d" -maxdepth 1 -type f -printf '    %TY-%Tm-%Td %TH:%TM %10s %f\n' 2>/dev/null | sort -r | head -n 5
  else
    echo "$r: (目录不存在)"
  fi
done

echo
echo '===== 7. manifest 产出 ====='
for r in po_valley_italy north_china_plain; do
  n=$(ls /root/auto_run/emanifest_${r}_*_p250.csv 2>/dev/null | wc -l)
  echo "$r: manifest $n 个"
  for m in /root/auto_run/emanifest_${r}_*_p250.csv; do
    [ -e "$m" ] || continue
    printf '    %-58s lines=%-5s\n' "$(basename "$m")" "$(wc -l < "$m")"
  done
done

echo
echo '===== 8. 批处理锁 ====='
if [ -d "$LK" ]; then
  n=$(find "$LK" -mindepth 1 -maxdepth 1 2>/dev/null | wc -l)
  echo "锁数量: $n"
  find "$LK" -mindepth 1 -maxdepth 1 -printf '    %TY-%Tm-%Td %TH:%TM  %f\n' 2>/dev/null | sort -r | head
else
  echo '(无锁目录)'
fi

echo
echo '===== 9. 卡死判据 ====='
newest=$(find $E5 -name '*.GRIB' -printf '%T@\n' 2>/dev/null | sort -rn | head -n 1)
if [ -n "${newest:-}" ]; then
  age=$(( ($(date +%s) - ${newest%.*}) / 60 ))
  echo "最新 GRIB 距今 ${age} 分钟"
  if [ "$age" -gt 60 ]; then echo '判据: >60min 无新文件 -> 疑似停滞(可能在 CDS 排队)'; else echo '判据: 1 小时内有新文件 -> 下载在推进'; fi
else
  echo '尚无任何 GRIB 到货'
fi
logage=999
[ -e "$FETCH_LOG" ] && logage=$(( ($(date +%s) - $(stat -c %Y "$FETCH_LOG")) / 60 ))
echo "fetch 日志距今 ${logage} 分钟"
if [ "$logage" -gt 30 ]; then echo '判据: 日志 30min 未更新 -> 下载器可能挂起/退避等待'; fi
