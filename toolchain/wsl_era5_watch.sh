#!/usr/bin/env bash
FETCH_LOG=/mnt/c/Users/Yuki/Desktop/oss_work/era5_fetch.out.log
REC=/mnt/d/lagrangian-jepa-cn/data/receptors_v2
PO="20150211 20150721 20150813 20160115 20160221 20160714 20160909 20170101 20170327 20170421 20171023"
NCP="20150301 20150520 20150605 20151103 20160106 20160209 20160310 20160506 20161123 20161216 20170626"
ALL="$PO $NCP"
echo "WATCHER START $(date -u)"
while true; do
  bash /mnt/d/lagrangian-jepa-cn/toolchain/wsl_era5_post.sh 2>&1 | tail -30
  done_flag=1
  for region in po_valley_italy north_china_plain; do
    for date in $ALL; do
      [ -f "$REC/$region/receptors_${date}_n120_maximin.csv" ] || continue
      man=/root/auto_run/emanifest_${region}_${date}_p250.csv
      [ -s "$man" ] || done_flag=0
    done
  done
  if [ "$done_flag" = 1 ]; then echo "ALL MANIFESTS DONE $(date -u)"; break; fi
  if grep -q "ERA5 FETCH ALL DONE" "$FETCH_LOG" 2>/dev/null; then
    # fetch done: one more pass then evaluate again
    echo "FETCH-DONE MARKED, waiting for batches... $(date -u)"
  fi
  sleep 600
done
echo "WATCHER EXIT $(date -u)"