#!/usr/bin/env bash
set -x
# 1) CV HRRR convert+merge+batch (existing script)
echo "[CV HRRR]"
bash /mnt/d/lagrangian-jepa-cn/toolchain/wsl_cv_hrrr2.sh 2>&1 | tail -20
# 2) ERA5-po convert to ARL + batch
echo "[ERA5 po]"
E=/root/work/hysplit_data2arl/hysplit_data2arl/era52arl
CFG=$E/era52arl.cfg
for day in 20171022 20171023; do
  out=/root/met_era5/po_valley_italy/$day
  mkdir -p /root/met_era5/po_valley_italy
  [ -s "$out" ] && continue
  p=/mnt/d/lagrangian-jepa-cn/met_cache/era5d/po_valley_italy/${day}_PL.GRIB
  s=/mnt/d/lagrangian-jepa-cn/met_cache/era5d/po_valley_italy/${day}_SFC.GRIB
  [ -s "$p" ] && [ -s "$s" ] || { echo "missing $day"; continue; }
  (cd $E && ./era52arl -d$CFG -i$p -a$s -o$out) 2>&1 | tail -2
  ls -la $out
done
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/po_valley_italy/receptors_20171023_n120_maximin.csv --stilt-wd /root/work/stilt --met /root/met_era5/po_valley_italy --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag era5-v1-po_valley_italy-20171023-p250 --timeout 3600 --log-dir /root/auto_run/elogs_po --manifest /root/auto_run/emanifest_po_20171023_p250.csv > /root/auto_run/era5_po.out 2>&1
echo "ERA5 po rc=$?"; tail -2 /root/auto_run/era5_po.out