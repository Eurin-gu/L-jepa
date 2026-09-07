# MILESTONE — round 65 (2026-09-06 05:30 UTC)

## 3360 real footprints verified FULL (28 batches x 120)

### GDAS0.5-v2 CONUS (23 dates = 2760) — COMPLETE for all planned dates
- so_cal_LA_basin x6: 20150102 20150807 20160217 20160318 20160807 20171111
- cent_valley_CA x6: 20150111 20150722 20160222 20160908 20170522 20171118
- permian_westTX x6: 20150128 20151013 20160319 20160904 20170308 20171016
- co_front_range x5: 20150128 20150911 20160422 20161123 20170612

### ERA5-v1 global (5 dates = 600) — in progress
- po_valley_italy x3: 20150211 20150721 20171023
- north_china_plain x2: 20150301 20160310
- remaining po ~8 dates, ncp ~9 dates downloading via CDS (slow queue)

## Cumulative (incl earlier arms)
- GDAS0p5-v1: 6 dates x 120 = 720 (earlier validation arm)
- HRRR: so 20171111 120 + cv 20170522 120 + formal arm (2016-17 reuse)
- Running total across all arms > 5000+ footprints

## Active
- era5 CDS downloaders (fetch po + ncpA + ncpB)
- era5 watch auto convert+batch
- Next: finish ERA5 arm, then assemble schema-v5 datasets