# ROUND 68 INCIDENT + RECOVERY (2026-09-06 07:40 UTC)

## What happened
- Two GDAS batches (po 20160221 + po 20171023 v2) run in parallel at jobs=8 each caused WSL OOM (hycs_std 2.2GB anon x 16 > 24GB), killing all processes incl era5 fetch/watch.
- WSL then hit E_UNEXPECTED service error; full `wsl --shutdown` restart required.

## Recovery (complete)
- Serial recovery script ran interrupted batches one-at-a-time jobs=8:
  po_valley_italy 20160221 -> 120/120 (was 72)
  po_valley_italy 20171023 -> 120/120 (was 47)
- WSL restarted clean: 23GB mem, load normal.

## Proxy status: DOWN (user-controlled)
- 127.0.0.1:17891 not listening (only TimeWait residues). NOAA + CDS unreachable.
- era5 fetch2 / watch2 relaunched but cannot download without proxy.
- GDAS po/ncp downloaders (33 remaining files) blocked on NOAA via proxy.

## Local-ready work possible without proxy
- GDAS batches for dates whose met already on disk.
- Remaining GDAS po/ncp met-ready: (after recovery) po 20160221/20160909/20171023 done; others need downloads.

## Needs user action
- Re-enable proxy (127.0.0.1:17891) to resume ERA5 + GDAS downloads.