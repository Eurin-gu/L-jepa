#!/usr/bin/env bash
set -x
H=/root/work/hysplit_data2arl/hysplit_data2arl
MOD=/usr/lib/x86_64-linux-gnu/fortran/gfortran-mod-15
cd $H
sed -i 's|ECCODESINC= -I/usr/include|ECCODESINC= -I/usr/include -I$MOD|' Makefile.inc
grep ECCODESINC Makefile.inc
echo "[era52arl]"
cd era52arl && make clean >/dev/null 2>&1; make 2>&1 | tail -12; cd $H
echo "[hrrrv12arl v2 modern]"
cd hrrr2arl
rm -f hrrrv12arl_v2.f.rej
gfortran -O2 -g -ffree-form -ffree-line-length-none -fconvert=big-endian -frecord-marker=4 -fallow-argument-mismatch -finit-local-zero -I$MOD -o hrrrv12arl_v2_modern hrrrv12arl_v2.f ../metprog/library/libhysplit.a -L/usr/lib/x86_64-linux-gnu -leccodes_f90 -leccodes 2>&1 | tail -20
echo "[binaries]"
ls -la $H/era52arl/era52arl $H/hrrr2arl/hrrrv12arl_v2_modern 2>/dev/null
echo "[sanity run]"
cd $H/era52arl && ./era52arl 2>&1 | head -8
cd $H/hrrr2arl && ./hrrrv12arl_v2_modern 2>&1 | head -8