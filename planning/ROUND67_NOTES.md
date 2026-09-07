# ROUND 67 NOTES (2026-09-06 06:20 UTC)

## Assembly architecture findings for ERA5 arm
- assemble.py assumes HRRR Lambert conformal grid via latlon_to_grid_xy/_lcc_fwd (38.5N center).
- ERA5 is equirectangular 0.25°: assembling ERA5 labels requires an equirectangular projection path in assemble_input (grid_x = (lon-lon0)/dlon, grid_y = (lat0-lat)/dlat).
- feature_sources.py supports era5_sfc_grib (per-hour file per snapshot) but current era5d store is daily-merged SFC grib (24h x 9 vars, 216 msgs).
- Need: (a) equirectangular assemble variant; (b) either split daily merged -> hourly or add merged-grib reader selecting by dataTime.
- This is post-production assembly work; documented for the assembly phase.

## Production status (round 67)
- GDAS0.5 CONUS exploratory arm COMPLETE: 23 dates x 120 = 2760 footprints.
- ERA5 mainline (po/ncp): 5 dates complete batches; po grib 14 files, ncp 12; CDS queue congestion slow (requests 40-90 min).
- Downloaders active: fetch(po serial), ncpA. ncpB stopped to reduce queue depth (no clear gain; congestion is server-side).