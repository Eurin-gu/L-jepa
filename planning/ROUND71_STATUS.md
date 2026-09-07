# ROUND 71 STATUS (2026-09-06 00:15 UTC)

## GPU environment VERIFIED
- torch.cuda available: NVIDIA GeForce RTX 5070 Laptop GPU, 8151 MiB
- /root/venvs/ml has torch 2.x + cu130 (sm_120)

## Proxy 0dcloudCore: LISTEN but NOT forwarding
- PID 51176 listens on 17891 but all HTTPS (example/NOAA/CDS) return 000/SSL fail.
- User needs to check 0dcloud connection/mode in their GUI.

## Resume checklist (when proxy works)
1. GDAS po/ncp remaining met: 33 files via gdas_dl_only.py (NOAA ~10 min/file)
2. GDAS po/ncp v2 batches: run autorun-style serial for unlocked dates
3. ERA5 remaining po/ncp (~16 dates): era5 fetch (serial po + ncp), CDS queue is slow
4. ERA5 prev-day SFC grib re-download for assembly features (po 20150210,20150720,20150812,20171022; ncp 20150228,20150519,20160309)
5. Era5SfcDaySource + assemble.py --grid-type equirect path VERIFIED; run assembly once prev SFC present
6. GDAS v2 assembly: needs GDAS feature source (later; exploratory arm)

## Data bank (safe in by-id, 5961 dirs)
- GDAS v2: 27 dates x 120 = 3240 verified
- ERA5 v1: 6 dates x 120 = 720 verified
- GDAS v1: 6 dates, HRRR: so/cv + formal reuse => cumulative > 6000