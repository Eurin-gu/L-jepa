#!/bin/bash
date "+LOCAL %F %T"; date -u "+UTC   %F %T"
echo; echo "===== 进程 ====="
ps -eo pid,etime,pcpu,cmd --sort=start_time | grep -E "era5_fixall|era5_night_watch|era5_fullprev|run_batch|stilt_cli|proxy_watch" | grep -v grep || echo "(无)"
echo; echo "===== ERA5 GRIB 到货(全6区) ====="
for r in po_valley_italy north_china_plain so_cal_LA_basin cent_valley_CA permian_westTX co_front_range; do
  d=/mnt/d/lagrangian-jepa-cn/met_cache/era5d/$r
  [ -d "$d" ] || { echo "$r: (目录未建)"; continue; }
  tot=$(find $d -maxdepth 1 -name "*.GRIB" 2>/dev/null | wc -l)
  sz=$(du -sm $d 2>/dev/null | cut -f1)
  new=$(find $d -maxdepth 1 -name "*.GRIB" -printf "%f" 2>/dev/null | tail -c 30)
  echo "$r: GRIB=$tot size=${sz}MB"
done
echo; echo "===== po STILT manifest(应11) ====="
for m in /root/auto_run/emanifest_po_valley_italy_*_p250.csv; do
  [ -e "$m" ] && printf "  %-22s rows=%s
" "$(basename $m | sed -E "s/emanifest_po_valley_italy_([0-9]+)_p250.csv/\1/")" "$(($(wc -l < $m)-1))"
done | sort
echo; echo "===== ncp/fixall 日志尾 ====="
tail -3 /root/era5_fixall.log 2>/dev/null
echo; echo "===== night watch 是否在跑 ====="
pgrep -f "era5_night_watch" >/dev/null && echo "RUNNING (美国区下载中)" || echo "not running / finished"
echo; echo "===== 卡死判据: 最新 GRIB 年龄 ====="
newest=$(find /mnt/d/lagrangian-jepa-cn/met_cache/era5d -name "*.GRIB" -printf "%T@\n" 2>/dev/null | sort -rn | head -1)
if [ -n "$newest" ]; then age=$(( ($(date +%s) - ${newest%.*}) / 60 )); echo "最新GRIB ${age} 分钟前"; [ $age -gt 90 ] && echo "!! 疑似停滞(可能CDS排队)"; else echo "尚无"; fi