#!/usr/bin/env bash
set -x
H=/root/work/hysplit_data2arl/hysplit_data2arl
cd $H
sed -i "s|^ECCODESINC=.*|ECCODESINC= -I/usr/include -I/usr/lib/x86_64-linux-gnu/fortran/gfortran-mod-15|" Makefile.inc
grep ^ECCODESINC Makefile.inc
cd era52arl && make clean >/dev/null 2>&1; make 2>&1 | tail -6
echo "[result]"; ls -la era52arl 2>/dev/null && ./era52arl 2>&1 | head -8