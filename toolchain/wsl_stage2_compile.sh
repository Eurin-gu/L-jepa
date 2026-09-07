#!/usr/bin/env bash
set -x
H=/root/work/hysplit_data2arl/hysplit_data2arl
cd $H
cp Makefile.inc.gfortran Makefile.inc
sed -i "s|-L/usr/lib64|-L/usr/lib/x86_64-linux-gnu|g" Makefile.inc
sed -i "s|\$(LDFLAGS_FPROG)|\$(LDFLAGS_FPROG) -fallow-argument-mismatch|g" Makefile.inc
sed -i 's|#ECCODES_TOPDIR= /opt/eccodes|ECCODES_TOPDIR= /usr|; s|#ECCODESINC= -I/opt/eccodes/include|ECCODESINC= -I/usr/include|; s|#ECCODESLIBS= -L/opt/eccodes/lib -leccodes_f90 -leccodes|ECCODESLIBS= -L/usr/lib/x86_64-linux-gnu -leccodes_f90 -leccodes|' Makefile.inc
echo "[build metprog library]"
cd metprog/library && make 2>&1 | tail -25; ls -la *.a 2>/dev/null | tail -5; cd $H
echo "[eccodes mod]"; find /usr -iname "eccodes*.mod" 2>/dev/null | head
echo "[build era52arl]"
cd era52arl && make clean 2>/dev/null; make 2>&1 | tail -25; ls -la era52arl 2>/dev/null; cd $H
echo "[patch + build hrrrv12arl_v2 modern]"
cd hrrr2arl
cp hrrrv12arl_v2.f hrrrv12arl_v2.f.orig
patch -N < /root/work/footnet/stilt_pipeline/patches/hrrrv12arl_v2_modern_eccodes.patch 2>&1 | tail -8 || echo "patch not clean"
MODDIR=$(dirname $(find /usr -name "eccodes.mod" 2>/dev/null | head -1))
echo "MODDIR=$MODDIR"
gfortran -O2 -g -ffree-form -fconvert=big-endian -frecord-marker=4 -fallow-argument-mismatch -finit-local-zero -I"$MODDIR" -o hrrrv12arl_v2_modern hrrrv12arl_v2.f ../metprog/library/libhysplit.a -L/usr/lib/x86_64-linux-gnu -leccodes_f90 -leccodes 2>&1 | tail -30
ls -la hrrrv12arl_v2_modern 2>/dev/null
echo "[compile done]"
ls -la $H/era52arl/era52arl $H/hrrr2arl/hrrrv12arl_v2_modern 2>/dev/null