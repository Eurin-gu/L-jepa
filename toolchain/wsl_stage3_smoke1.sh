#!/usr/bin/env bash
set -x
mkdir -p /root/smoke/hr1 && cd /root/smoke/hr1
BASE=https://noaa-hrrr-bdp-pds.s3.amazonaws.com
echo "[download]"
curl -fL -sS -o hrrr.t12z.wrfprsf00.grib2 $BASE/hrrr.20171111/conus/hrrr.t12z.wrfprsf00.grib2 && ls -la hrrr.t12z.wrfprsf00.grib2
curl -fL -sS -o hrrr.t12z.wrfprsf00.grib2.idx $BASE/hrrr.20171111/conus/hrrr.t12z.wrfprsf00.grib2.idx
echo "[convert]"
cd /root/work/hysplit_data2arl/hysplit_data2arl/hrrr2arl && ./hrrrv12arl_v2_modern -i /root/smoke/hr1/hrrr.t12z.wrfprsf00.grib2 -o /root/smoke/hr1/data.arl -g HRRR 2>&1 | tail -15
ls -la /root/smoke/hr1/data.arl
ls /root/smoke/hr1/