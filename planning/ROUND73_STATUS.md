# ROUND 73 STATUS (2026-09-06 00:25 UTC)

## Proxy: INTERMITTENT then DOWN again
- 00:20:16 one successful NOAA fetch (200), then 000 again.
- 0dcloudCore (PID 51176) listening on 17891/9090 but mostly not forwarding.
- User-side agents actively retrying; will auto-complete when proxy stabilizes.

## User-side automation active (do not duplicate)
- era5_fixall.py (PID 10046): PHASE1 fetch full prev+target until complete (37 missing po), backs off 300s, loops.
- wsl_era5_watch.sh (12513) + post (12515): convert+batch loop.
- era5_fixall manages era5d po/ncp + met_era5 + manifests. AVOID conflicting with it.

## My GDAS downloader (NOAA, no CDS conflict)
- Keeps failing instantly while proxy down (head err).
- Will restart when NOAA reachable. pn5 done; resume list saved in gdas_dl_pn5.log args.

## Awaiting stable proxy; all data safe (by-id 5961, 33 batches FULL verified, formal arm intact).