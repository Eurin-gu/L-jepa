#!/usr/bin/env bash
set -x
mkdir -p /root/gdas05 /root/met_gdas05
export HTTPS_PROXY=http://127.0.0.1:17891 HTTP_PROXY=http://127.0.0.1:17891
cd /root/gdas05
for f in 20150806_gdas0p5 20150807_gdas0p5; do
  for a in $(seq 1 12); do
    sz=$(stat -c%s $f 2>/dev/null || echo 0)
    if [ "$sz" -gt 500000000 ]; then echo "$f ok $sz"; break; fi
    curl -fL -C - --retry 20 --retry-all-errors --retry-delay 5 -o $f https://www.ready.noaa.gov/data/archives/gdas0p5/2015/08/$f || echo "curl fail attempt $a"
    sleep 3
  done
  sz=$(stat -c%s $f 2>/dev/null || echo 0)
  [ "$sz" -gt 500000000 ] && cp $f /root/met_gdas05/ || echo "STILL BAD $f"
done
ls -la /root/met_gdas05/