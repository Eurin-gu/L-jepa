#!/usr/bin/env bash
export HTTPS_PROXY=http://127.0.0.1:17891
export HTTP_PROXY=http://127.0.0.1:17891
export https_proxy=http://127.0.0.1:17891
export http_proxy=http://127.0.0.1:17891
MARK=/mnt/c/Users/Yuki/Desktop/oss_work/era5_fixall.done
cp /mnt/c/Users/Yuki/Desktop/oss_work/era5_fixall.py /root/era5_fixall.py
echo "FIXALL RUN $(date -u)"
/root/venvs/cds/bin/python /root/era5_fixall.py 2>&1 | tee /root/era5_fixall.log
if grep -q "ERA5 FIXALL DONE" /root/era5_fixall.log 2>/dev/null; then touch "$MARK"; echo "MARKER SET"; fi
echo "FIXALL_ITER_END $(date -u)"