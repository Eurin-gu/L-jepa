# ROUND 74 STATUS (2026-09-06 08:22 local / 00:22 UTC)

## Proxy: still DOWN (noaa=000 all polls)
- proxy-watch (pwsh-132) polling every 120s, will auto-launch GDAS dl when NOAA reachable.
- User era5_fixall.py (PID 10046) looping every 300s, 9 passes, 37 missing (proxy-blocked).
- watch/post (12513/12515) standing by.

## Clock note
- WSL UTC 00:21 = Windows local 08:21 (UTC+8). No drift issue.

## Data state
- gdas05 58 files (full pn set incomplete: 33 missing).
- by-id 5961 dirs intact; 33 batches FULL verified.
- No local-ready GDAS batches remain; all external-dependent.