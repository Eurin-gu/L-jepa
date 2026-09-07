#!/usr/bin/env bash
set -x
ln -sf /usr/lib/x86_64-linux-gnu/libeccodes_f90.so /usr/lib/libeccodes_f90.so
ln -sf /usr/lib/x86_64-linux-gnu/libeccodes.so /usr/lib/libeccodes.so
ls -la /usr/lib/libeccodes*
H=/root/work/hysplit_data2arl/hysplit_data2arl
cd $H/era52arl && make clean >/dev/null 2>&1; make 2>&1 | tail -6
echo "[result]"
ls -la era52arl && ./era52arl 2>&1 | head -10