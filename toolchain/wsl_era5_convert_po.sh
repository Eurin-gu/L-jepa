#!/usr/bin/env bash
set -x
H=/root/work/hysplit_data2arl/hysplit_data2arl
E=$H/era52arl
mkdir -p /root/met_era5 /root/era5_work
cp /mnt/d/lagrangian-jepa-cn/toolchain/server_backup_20260830/era5/20240401/era52arl.cfg $E/era52arl.cfg
ls -la $E/era52arl.cfg
# convert po days
for day in 20171022 20171023; do
  out=/root/met_era5/$day
  [ -s "$out" ] && continue
  echo "convert $day"
  (cd $E && ./era52arl -d$E/era52arl.cfg -i/root/era5_grib/po_${day}_DATA.GRIB -a/root/era5_grib/po_${day}_SFC.GRIB -o$out) 2>&1 | tail -15 || echo "CONV FAIL $day"
  ls -la $out 2>/dev/null
done
ls -la /root/met_era5/