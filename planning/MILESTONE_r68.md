# MILESTONE r68 (2026-09-06 07:45 UTC): 3960 verified footprints, 33 FULL batches

## GDAS0p5-v2: 27 dates x 120 = 3240
- CONUS complete: so x6, cv x6, tx x6, cf x5
- Global: po 20160221/20160909/20171023, ncp 20161123

## ERA5-v1: 6 dates x 120 = 720
- po: 20150211, 20150721, 20171023
- ncp: 20150301, 20150520, 20160310

## Cumulative (all arms) > 6000 footprints
- + GDAS0p5-v1 6 dates (720, earlier validation arm)
- + HRRR so 20171111 120, cv 20170522 120, formal reuse 2016-17 (1200 train + 240 val + 600 test)

## Blocked on proxy (user to re-enable 127.0.0.1:17891)
- ERA5 po/ncp remaining dates (~16)
- GDAS po/ncp remaining met (33 files)
- WSL incident recovered: serial execution jobs=8 only, no parallel batches (lesson: 1 batch at a time)