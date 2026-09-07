#!/usr/bin/env bash
set -x
E=/root/work/hysplit_data2arl/hysplit_data2arl/era52arl
CFG=$E/era52arl.cfg
SP=/root/work/footnet/stilt_pipeline
REC=/mnt/d/lagrangian-jepa-cn/data/receptors_v2
PY=/root/venvs/cds/bin/python
LK=/root/auto_run/locks
mkdir -p $LK
  find $LK -mindepth 1 -maxdepth 1 -type d -mmin +150 -exec rmdir {} \\; 2>/dev/null || true
# Expected ARL sizes per region (full 24h conversion); anything smaller is truncated
ARL_FULL_SIZE_po_valley_italy=23403000
ARL_FULL_SIZE_north_china_plain=24339120
arl_ok() {
  local region=$1 day=$2 out=$3
  local exp_var="ARL_FULL_SIZE_${region}"
  local exp=${!exp_var}
  [ -f "$out" ] && [ "$(stat -c%s "$out")" = "$exp" ]
}
for region in po_valley_italy north_china_plain; do
  for date in 20150211 20150721 20150813 20160115 20160221 20160714 20160909 20170101 20170327 20170421 20171023 20150301 20150520 20150605 20151103 20160106 20160209 20160310 20160506 20161123 20161216 20170626; do
    [ -f "$REC/$region/receptors_${date}_n120_maximin.csv" ] || continue
    d0=$(date -d "$date -1 day" +%Y%m%d)
    mkdir -p /root/met_era5/$region /root/auto_run/elogs_$region
    ok=1
    for day in $d0 $date; do
      out=/root/met_era5/$region/$day
      if arl_ok $region $day "$out"; then continue; fi
      if [ -f "$out" ]; then
        echo "ARL TRUNCATED $region $day $(stat -c%s "$out") - removing for reconvert"; rm -f "$out";
      fi
      p=/mnt/d/lagrangian-jepa-cn/met_cache/era5d/$region/${day}_PL.GRIB
      s=/mnt/d/lagrangian-jepa-cn/met_cache/era5d/$region/${day}_SFC.GRIB
      if [ -s "$p" ] && [ -s "$s" ]; then
        (cd $E && ./era52arl -d$CFG -i$p -a$s -o$out) > /root/auto_run/conv_${region}_${day}.log 2>&1
        if arl_ok $region $day "$out"; then echo "CONV OK $region $day $(stat -c%s $out)";
        else echo "CONV FAIL/TRUNC $region $day $(stat -c%s "$out" 2>/dev/null || echo 0)"; rm -f "$out"; ok=0; fi
      else
        echo "grib missing $region $day"; ok=0
      fi
    done
    [ "$ok" = 1 ] || continue
    man=/root/auto_run/emanifest_${region}_${date}_p250.csv
    lock=$LK/${region}_${date}.lock
    [ -s "$man" ] && { echo "batch skip $region $date"; continue; }
    mkdir $lock 2>/dev/null || { echo "batch locked $region $date"; continue; }
    echo "BATCH $region $date $(date -u)"
    $PY $SP/run_batch.py --receptors $REC/$region/receptors_${date}_n120_maximin.csv --stilt-wd /root/work/stilt --met /root/met_era5/$region --jobs 16 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag era5-v1-$region-$date-p250 --timeout 3600 --log-dir /root/auto_run/elogs_$region --manifest $man > /root/auto_run/era5_${region}_${date}.out 2>&1
    rc=$?; rmdir $lock 2>/dev/null
    echo "rc=$rc $(tail -1 /root/auto_run/era5_${region}_${date}.out)"
    [ -s "$man" ] && echo "FOOTCOUNT $(($(wc -l < $man)-1))"
  done
done
echo "ERA5 POST ITER DONE $(date -u)"