# ROUND 69 NOTES (2026-09-06 08:00 UTC)

## Assemble.py equirect (ERA5) support implemented and verified
- Added --grid-type equirect: probe_era5_grid reads Nx/Ny/dlon/dlat/lat_first from ERA5 grib (regular_ll 0.25 deg, lat row0=north).
- latlon_to_grid_xy dispatches to equirect formula when EQ["lon0"] set (no LCC projection).
- Verified probe: dlon=dlat=0.25, lon0=2.0, lat_first=51.9, north_first=True.
- feature_sources already had Era5SfcDaySource (era5_sfc_day) reading per-hour messages from daily merged grib.
- Manifest rebuild tool (from by-id dirs + receptor csv) works: 120 rows for era5-v1-po-20171023.

## Data integrity after WSL OOM/E_UNEXPECTED crash
- by-id (5961 dirs) fully intact; all 6 ERA5 batches + 27 GDAS v2 batches verified 120/120.
- met_era5 intermediate ARL cleaned (po only 20171023, ncp 20150301/20150520) - regenerable.
- era5d po grib: 20150211/20150721/20150813/20171023 (+ncp 3 dates) - key dates present.
- Missing for ERA5 assembly: prev-day SFC gribs (e.g. 20171022_SFC for 20171023 features) - re-download when proxy returns.

## Proxy still DOWN (checked 07:51 UTC): NOAA + CDS unreachable via 127.0.0.1:17891.