#!/usr/bin/env bash
E=/root/work/hysplit_data2arl/hysplit_data2arl/era52arl
mkdir -p /root/met_era5 /root/auto_run
cp -f /mnt/d/lagrangian-jepa-cn/toolchain/server_backup_20260830/era5/20240401/era52arl.cfg $E/era52arl.cfg
cat > /root/auto_run/run_one.sh << "INNER"
#!/usr/bin/env bash
set -x
REGION=$1; DATE=$2
D0=$(date -d "$DATE -1 day" +%Y%m%d)
E=/root/work/hysplit_data2arl/hysplit_data2arl/era52arl
# convert each of two days when p+s grib ready
for day in $D0 $DATE; do
  out=/root/met_era5/$day
  [ -s "$out" ] && continue
  p=/root/era5_grib/${REGION}_${day}_p.grib; s=/root/era5_grib/${REGION}_${day}_s.grib
  [ -s "$p" ] || { echo "wait $p"; exit 0; }
  [ -s "$s" ] || { echo "wait $s"; exit 0; }
  (cd $E && ./era52arl -d$E/era52arl.cfg -i$p -a$s -o$out) || { echo "CONV FAIL $day"; exit 0; }
  ls -la $out || exit 0
done
# both days present? then batch
[ -s /root/met_era5/$D0 ] || { echo "wait day0"; exit 0; }
[ -s /root/met_era5/$DATE ] || { echo "wait day1"; exit 0; }
MAN=/root/auto_run/manifest_${REGION}_${DATE}_p250.csv
[ -s "$MAN" ] && { echo "already done"; exit 0; }
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/${REGION}/receptors_${DATE}_n120_maximin.csv --stilt-wd /root/work/stilt --met /root/met_era5 --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 --tag era5-${REGION}-${DATE}-p250 --timeout 3600 --log-dir /root/auto_run/logs_${DATE} --manifest $MAN 2>&1 | tail -4
INNER
chmod +x /root/auto_run/run_one.sh
cat > /root/auto_run/watch.sh << "WATCH"
#!/usr/bin/env bash
declare -A REGMAP
while true; do
  for entry in "po_valley_italy:20171023" "north_china_plain:20170626" "so_cal_LA_basin:20171111" "so_cal_LA_basin:20160318"; do
    R=${entry%%:*}; D=${entry##*:}
    bash /root/auto_run/run_one.sh "$R" "$D" >> /root/auto_run/auto.log 2>&1
  done
  sleep 120
done
WATCH
chmod +x /root/auto_run/watch.sh
nohup bash /root/auto_run/watch.sh > /root/auto_run/watch.out 2>&1 &
echo "watch started pid $!"