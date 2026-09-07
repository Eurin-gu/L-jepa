# SESSION STATE — round 63 (2026-09-06 00:33 UTC)

## ERA5 high-fidelity arm (po/ncp) — IN PROGRESS
- Orchestration: era5_fetch.sh (PID 472, po 11 dates serial) + wsl_era5_watch.sh (PID 5768, loop every 10min: convert new grib -> run_batch era5-v1-*) + my parallel ncp downloaders (pwsh-92: ncp A 6 dates, pwsh-93: ncp B 5 dates).
- GRIB landing: D:\lagrangian-jepa-cn\met_cache\era5d\<region>\<day>_{PL,SFC}.GRIB
- ARL convert target: /root/met_era5/<region>/<day>
- Batch tag: era5-v1-<region>-<date>-p250, manifest /root/auto_run/emanifest_<region>_<date>_p250.csv
- VERIFIED GOOD: era5-v1-po_valley_italy-20171023-p250 = 120/120 real foot.nc
- po GRIB done: 20150210 PL/SFC, 20150211 PL (SFC pending), 20171022/23 (old)
- ncp GRIB done: 20150228 PL (A), 20160309 PL (B)
- CDS queue ~15-35min/req; 3 parallel downloaders active.

## GDAS0.5 wave3 (CONUS exploratory arm) — PAUSED (bandwidth to ERA5)
- R fix applied: find_met_files.r now always extends met_end to next 3h boundary for backward sims => 21:0xZ releases work.
- VERIFIED GOOD (real foot.nc 120/120): gdas0p5-v2-so_cal_LA_basin-{20150102,20150807,20160318}-p250
- gdas05 files on disk: 29 days (~2015-2017 dates)
- wave3.py (CONUS-only, jobs=6) ready at /root/wave3.py; rerun when ERA5 no longer needs bandwidth.

## Key learnings
- "120 dirs in by-id" != success: must count dirs containing nonempty *_foot.nc.
- WSL has 24GB now (.wslconfig memory=24GB, processors=16); jobs=6-8 safe, jobs=16 OOM-killed hycs_std.
- nohup/& dies with wsl.exe client exit; use persistent pwsh background jobs (wsl.exe stays attached).