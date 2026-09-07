#!/usr/bin/env bash
# ERA5 深挖：活跃下载器日志 + ARL 产物完整性（只读）
set -u
FETCH_LOG=/mnt/c/Users/Yuki/Desktop/oss_work/era5_fetch.out.log

echo '===== A. oss_work 近期文件 ====='
ls -la --time-style=long-iso /mnt/c/Users/Yuki/Desktop/oss_work/ | head -40

echo
echo '===== B. 活跃下载器 PID 1487 打开的文件 ====='
ls -l /proc/1487/fd 2>/dev/null | grep -vE 'socket|pipe|null|pts|/dev/' | head -20
echo '--- 工作目录 ---'
ls -l /proc/1487/cwd 2>/dev/null

echo
echo '===== C. /root 下近期日志 ====='
find /root -maxdepth 2 -name '*.log' -newermt '-12 hours' -printf '%TY-%Tm-%Td %TH:%TM %9s %p\n' 2>/dev/null | sort -r | head -20

echo
echo '===== D. met_era5 ARL 尺寸一致性 ====='
find /root/met_era5 -maxdepth 2 -type f -printf '%10s  %p\n' 2>/dev/null | sort -k2

echo
echo '===== E. 转换日志清单 ====='
ls -la --time-style=long-iso /root/auto_run/conv_*.log 2>/dev/null | head -20

echo
echo '===== F. 可疑转换 20150520 日志尾 ====='
for f in /root/auto_run/conv_north_china_plain_20150520.log /root/auto_run/conv_north_china_plain_20150519.log; do
  echo "--- $f ---"
  [ -e "$f" ] && tail -n 10 "$f" || echo '(缺失)'
done

echo
echo '===== G. 下载速率估算（近 12 小时 GRIB 增量） ====='
E5=/mnt/d/lagrangian-jepa-cn/met_cache/era5d
find $E5 -name '*.GRIB' -newermt '-12 hours' -printf '%TH:%TM %10s %p\n' 2>/dev/null | sort | awk '
{
  n++; bytes+=$2;
  split($1,t,":"); hm=t[1]*60+t[2];
  if(first=="") first=hm; last=hm;
  printf "  %s  %8.1f MB  %s\n", $1, $2/1048576, $3;
}
END{
  printf "\n  近12h 到货 %d 个文件, 合计 %.1f MB\n", n, bytes/1048576;
  span=(last-first); if(span<0) span+=1440;
  if(span>0 && n>0) printf "  时间跨度 %d 分钟 -> 平均 %.2f 文件/小时, %.1f MB/小时\n", span, n*60/span, bytes/1048576/(span/60);
}'
