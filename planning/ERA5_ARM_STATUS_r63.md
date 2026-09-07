# ERA5 ARM STATUS (round 63, 2026-09-06 01:20 UTC)

## Active parallel downloaders (5)
| route | region | dates | proc |
|---|---|---|---|
| fetch(orig) | po_valley_italy | 20150721 + later | 472 |
| poB (mine) | po_valley_italy | 20150813 20160115 20160221 20160714 | 12918 |
| poC (mine) | po_valley_italy | 20160909 20170101 20170327 20170421 | 12924 |
| ncpA (mine) | north_china_plain | 20150301 20150520 20150605 20151103 20160106 20160209 | 6392 |
| ncpB (mine) | north_china_plain | 20160310 20160506 20161123 20161216 20170626 | 6396 |

## Completed ERA5 batches (real foot.nc 120/120 verified)
- era5-v1-po_valley_italy-20171023-p250  (from earlier)
- era5-v1-po_valley_italy-20150211-p250  (00:44 UTC)

## Automation
- wsl_era5_watch.sh (PID 5768) loops every 10 min: convert new grib -> run era5-v1-* batch until all 22 date-manifests exist.
- GRIB -> /root/met_era5/<region>/<day> via era52arl.
- ncp 20150228 & 20160309 prev ARLs converted; watch running batches as each date completes.

## Notes
- CDS request queue 15-43 min each; 5-way parallel is the max useful parallelism.
- GDAS0.5 wave3 CONUS remains paused for bandwidth; resume after ERA5 download wave completes.
- Verified fix: real foot.nc count (not by-id dir count) is the success criterion.