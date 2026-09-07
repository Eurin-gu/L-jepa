#!/usr/bin/env bash
set -x
echo "=== module test gfortran-13 ==="
printf "program t\n use eccodes\n print *,\"ok13\"\n end\n" > /tmp/t.f90
gfortran -I/usr/lib/x86_64-linux-gnu/fortran/gfortran-mod-15 /tmp/t.f90 -leccodes_f90 -leccodes -o /tmp/t13 2>&1 | tail -8
/tmp/t13 2>&1 | head -2
echo "=== module test gfortran-14 (if installed) ==="
command -v gfortran-14 && gfortran-14 -I/usr/lib/x86_64-linux-gnu/fortran/gfortran-mod-15 /tmp/t.f90 -leccodes_f90 -leccodes -o /tmp/t14 2>&1 | tail -6
echo "=== rej file ==="
cat /root/work/hysplit_data2arl/hysplit_data2arl/hrrr2arl/hrrrv12arl_v2.f.rej 2>/dev/null
echo "=== line 1125-1150 ==="
sed -n "1125,1152p" /root/work/hysplit_data2arl/hysplit_data2arl/hrrr2arl/hrrrv12arl_v2.f