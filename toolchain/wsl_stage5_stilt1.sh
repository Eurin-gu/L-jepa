#!/usr/bin/env bash
set -x
cd /root/work/stilt
Rscript r/stilt_cli.r r_run_time=2017-11-11T20:46:41Z r_lati=32.00134 r_long=-116.23976 r_zagl=5 met_path=/root/met met_file_format=%Y%m%d met_file_tres=1 xmn=-117.5 xmx=-115.0 ymn=31.0 ymx=33.0 xres=0.04 yres=0.04 numpar=250 horus=24 2>&1 | tail -25
echo "=== outputs ==="
find /root/work/stilt/out -type f 2>/dev/null | tail -10