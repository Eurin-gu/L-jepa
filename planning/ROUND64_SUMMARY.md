# ROUND 64 PRODUCTION SUMMARY (2026-09-06 03:20 UTC)

## Verified real foot.nc >=110 batches (all 120/120)
### GDAS0.5-v2 CONUS (8 dates = 960 footprints)
- so_cal_LA_basin: 20150102, 20150807, 20160318
- cent_valley_CA: 20150722, 20160908
- permian_westTX: 20160319, 20160904
- co_front_range: 20160422
### ERA5-v1 global (3 dates = 360 footprints)
- po_valley_italy: 20150211, 20171023
- north_china_plain: 20150301

## Active background tasks
- GDAS NOAA downloaders pwsh-98/99: running, 43 files done, 13 missing pending
- ERA5 CDS downloaders: fetch(po) + ncpA + ncpB (3-way; poB/poC killed to reduce queue)
- era5 watch (PID 5768): auto convert+batch loop

## Next actions
- When GDAS dl completes: run remaining CONUS dates (so 20160807/20171111, cv 20150111/20160222/20170522/20171118, tx 20170308/20171016, cf 20161123/20170612)
- ERA5 watch continues: po 20150721+ and ncp remaining as grib arrives
- Then assemble schema-v5 datasets per met arm