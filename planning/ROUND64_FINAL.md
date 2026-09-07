# ROUND 64 FINAL (2026-09-06 04:10 UTC)

## Data production status
### Verified complete (120/120 real foot.nc):
- GDAS0p5-v2: 10 dates now (so x5: 20150102/20150807/20160217/20160318/20160807; cv x2: 20150722/20160908; tx x2: 20160319/20160904; cf x1: 20160422)
- ERA5-v1: 4 dates (po: 20150211/20171023; ncp: 20150301/20160310)

## Active automation
- autorun4 (pwsh-107): SERIAL executor, 13 pending GDAS dates, ~8min each, no met-dir race, no overload
- era5 watch (PID 5768): auto convert+batch for po/ncp as grib arrives
- era5 CDS downloaders: fetch(po) + ncpA + ncpB

## Infrastructure fixes this round
- WSL memory 16GB -> 24GB (.wslconfig); jobs capped 6-8
- autorun v1-v3 races fixed: per-date met dirs + serial execution (v4)
- real foot.nc counting = success criterion

## Remaining
- autorun4: finish remaining GDAS dates (so 20171111, cv x4, tx x3, cf x3)
- ERA5: po remaining ~9 dates + ncp ~9 dates download+batch (CDS queue slow, hours)
- Assemble schema-v5 datasets