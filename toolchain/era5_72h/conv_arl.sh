#!/bin/bash
# 批量转换缺失 ARL (bash 版, 绝对路径)
E=/root/work/hysplit_data2arl/hysplit_data2arl/era52arl
CFG=$E/era52arl.cfg
GB=/mnt/d/lagrangian-jepa-cn/met_cache/era5d/po_valley_italy
OD=/root/met_era5/po_valley_italy
EXPECT=23403000
cd $E || exit 1
DAYS="20150208 20150209 20150718 20150719 20150810 20150811 20160112 20160113 20160218 20160219 20160711 20160712 20160906 20160907 20161229 20161230 20170324 20170325 20170418 20170419 20171020 20171021"
ok=0; fail=0
for d in $DAYS; do
  out=$OD/$d
  if [ -f "$out" ] && [ "$(stat -c%s $out)" = "$EXPECT" ]; then
    echo "  $d 已有"; ok=$((ok+1)); continue
  fi
  ./era52arl -d$CFG -i$GB/${d}_PL.GRIB -a$GB/${d}_SFC.GRIB -o$out > /tmp/arl_$d.log 2>&1
  sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  if [ "$sz" = "$EXPECT" ]; then
    echo "  $d OK"; ok=$((ok+1))
  else
    echo "  $d 失败 size=$sz"; tail -2 /tmp/arl_$d.log | sed "s/^/      /"; fail=$((fail+1))
  fi
done
echo
echo "转换完成: ok=$ok fail=$fail"
echo "ARL 总数: $(ls $OD | wc -l)"
