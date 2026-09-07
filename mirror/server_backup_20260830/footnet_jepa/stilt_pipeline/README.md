# STILT label pipeline

Generates physically-based surface footprint labels (and trajectories) with
[uataq/stilt](https://github.com/uataq/stilt), replacing the
`simple_lagrangian` proxy. These are the labels for data schema v5
(`LABEL_SOURCE = "stilt_xstilt"` in `config.py`).

## Prerequisites (one-time, on the Autodl box)

```bash
cd /root/autodl-tmp/stilt && ./setup          # hycs_std + permute.so  ✅ done
Rscript /tmp/install_pkgs.r                   # lubridate/ncdf4/...    ✅ done
```

GDAS ARL week files live in `/root/autodl-tmp/met/`.

## HRRR GRIB2 -> ARL (modern ecCodes)

The NOAA `hrrrv12arl_v2.f` source predates the long ecCodes `typeOfLevel`
names. Applying the unmodified converter to current AWS HRRR files can leave
the grid at `0 x 0`, write a `00/00/00` timestamp, or silently emit a
surface-only ARL file. Apply the maintained compatibility patch before using
current HRRR data:

```bash
cd /root/data2arl/hrrr2arl
cp -a hrrrv12arl_v2.f hrrrv12arl_v2.f.orig
# The patch baseline is the pristine GRIB-API converter shipped as v1.
cp hrrrv12arl_v1.f hrrrv12arl_v2.f
patch < /root/autodl-tmp/footnet_jepa/stilt_pipeline/patches/\
hrrrv12arl_v2_modern_eccodes.patch
bash /root/build_hrrr2arl.sh
```

Do not use `wrfsfc` as a 3D STILT input. It contains only a few incomplete
diagnostic pressure levels. Download the required records from `wrfprs` using
the adjacent NOAA byte-offset index:

```bash
python3 fetch_hrrr_arl_subset.py \
  --date 20240705 --hour 18 \
  --out /root/autodl-tmp/hrrr_subset/20240705.18.grib2
```

This fetches complete GRIB messages for HGT/TMP/RH/DPT/SPFH/VVEL/UGRD/VGRD
on the configured pressure levels, plus the surface fields used by STILT. It
does not download or rewrite partial GRIB messages.

Some proxies throttle the many HTTP ranges used by that command. When a full
object is substantially faster, download it with aria2 and extract the same
messages locally:

```bash
python3 fetch_hrrr_arl_full.py \
  --date 20240704 --hour 18 \
  --forecast-hours 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 \
                   15 16 17 18 19 20 21 22 23 24 25 26 27 28 \
  --out-dir /media/ubuntu22/YUYING/arl_jul05 \
  --proxy http://127.0.0.1:7897
```

This workflow resumes only files carrying an aria2 incomplete marker, verifies
every complete full GRIB against its NOAA index, extracts locally, and verifies
the subset again. For the 2024-07-05 21:08Z receptor, this cycle spans
2024-07-04 18Z (`f00`) through 2024-07-05 22Z (`f28`); `f27` and `f28` bracket
the receptor minute. HYSPLIT requires a constant meteorological time interval,
so every hourly forecast in that span is required; a sparse selection such as
`f00/f03/f09/...` is invalid. Do not stop at `f27` or omit intermediate hours.
Add `--remove-full` only when the validated full objects are no longer needed.

Convert each time in a clean working directory. Reuse the same `arldata.cfg`
only when every input has the same grid, levels, and variable contract:

```bash
mkdir -p /root/autodl-tmp/hrrr_arl/20240705_18
cd /root/autodl-tmp/hrrr_arl/20240705_18
/root/data2arl/hrrr2arl/hrrrv12arl_v2 \
  -dapi2arl.cfg -earldata.cfg \
  -i/root/autodl-tmp/hrrr_subset/20240705.18.grib2 \
  -o20240705.18.hrrra -gHRRR

python3 /root/autodl-tmp/footnet_jepa/stilt_pipeline/validate_arl_met.py \
  --arl 20240705.18.hrrra --config arldata.cfg
```

Validation must report a real timestamp, pressure-coordinate upper levels,
and the required STILT surface/upper-air fields. A successful Fortran build or
a nonzero output size is not sufficient validation.

The `YY/MM/DD/HH` fields in every ARL record label are the GRIB valid time.
The adjacent forecast-hour field is metadata and HYSPLIT does not add it to
the label time. Encoding the cycle time there makes all forecasts from one
cycle appear to HYSPLIT as a single meteorological time.

Each converter invocation writes one time block. STILT must receive one ARL
archive containing every hourly block that covers the complete trajectory;
separate one-time files do not provide temporal interpolation. Merge the files
in chronological order only after each conversion succeeds:

```bash
python3 /root/autodl-tmp/footnet_jepa/stilt_pipeline/merge_arl_met.py \
  --input /root/autodl-tmp/hrrr_arl/20240705_17/20240705.17.hrrra \
          /root/autodl-tmp/hrrr_arl/20240705_17/arldata.cfg \
  --input /root/autodl-tmp/hrrr_arl/20240705_18/20240705.18.hrrra \
          /root/autodl-tmp/hrrr_arl/20240705_18/arldata.cfg \
  --out /root/autodl-tmp/met/hrrr.20240705.17-18.arl \
  --out-config /root/autodl-tmp/hrrr_arl/merged_17_18/arldata.cfg

python3 /root/autodl-tmp/footnet_jepa/stilt_pipeline/validate_arl_met.py \
  --arl /root/autodl-tmp/met/hrrr.20240705.17-18.arl \
  --config /root/autodl-tmp/hrrr_arl/merged_17_18/arldata.cfg --min-times 2
```

The merger rejects a changed projection/grid/level/variable configuration,
duplicate or decreasing valid times, malformed inputs, and existing outputs.
Use `--force` only when intentionally replacing a previously validated pair.
Keep `arldata.cfg` outside the STILT meteorology directory because STILT scans
that directory by date-bearing filename and would otherwise treat it as data.

HRRR `wrfprs` analysis files do not publish U/V momentum-flux records. HYSPLIT
may therefore log `FLUXES not found` and select `KBLS=2`; that fallback is
expected and was exercised by the trajectory smoke test. Do not manufacture
`UMOF`/`VMOF` from unrelated surface fields merely to suppress the warning.

## Steps

### 0. Day symlinks for met files (rerun whenever new .wN files arrive)

```bash
bash make_met_links.sh /root/autodl-tmp/met
```

`find_met_files()` greps filenames by `%Y%m%d`; the week archives carry no
date, so each day gets a symlink to its week file.

### 1. Receptor list from OCO-2 Lite

```bash
python3 make_receptors.py \
    --lite /root/autodl-tmp/oco2_lite/oco2_LtCO2_240402_*.nc4 \
    --n 120 --out /root/autodl-tmp/receptors/apr02.csv
```

### 2. Run STILT over all receptors

```bash
python3 run_batch.py --receptors /root/autodl-tmp/receptors/apr02.csv \
    --stilt-wd /root/autodl-tmp/stilt --met /root/autodl-tmp/met \
    --jobs 16 --numpar 1000
```

Each receptor gets a receptor-centred ±256 km footprint window at 0.04°,
matching the FootNet domain geometry; `time_integrate=T` produces a single
integrated 24 h surface footprint.

Start with a **single-receptor smoke** first:

```bash
head -2 receptors.csv > smoke.csv && python3 run_batch.py --receptors smoke.csv ...
```

### Continuous hourly production scheduler

Do not use the old sparse `f03/f09/...` daily workflow. The scheduler splits
one or more receptor CSV files by UTC date, derives the exact hourly coverage
for every 24 h back trajectory, and selects a 00/06/12/18Z HRRR extended
cycle whose consecutive forecasts cover the whole batch:

```bash
python3 schedule_hrrr_stilt.py \
  --receptors /root/autodl-tmp/receptors/apr_jul_600.csv \
  --dates 20240705 \
  --hour-workers 2 --range-jobs 4 \
  --stilt-jobs 8 --numpar 1000 \
  --retention outputs-only
```

Use `--dry-run` first to inspect the cycle and forecast-hour plan without
downloading. A full UTC day can require `f00..f48`; the default disk preflight
budgets approximately 0.16 GiB of subset GRIB and 0.36 GiB of ARL per hour,
plus space for the merged copy and a 20 GiB reserve.

Each date runs sequentially and has an exclusive lock under
`/root/autodl-tmp/hrrr_stilt_batches/YYYYMMDD/`. Downloads and conversions are
atomic and validated before reuse. `run_batch.py --resume` uses deterministic
simulation ids and an idempotent manifest, so restarting the same command
does not regenerate complete receptor outputs.

Retention applies only after STILT and output validation succeed:

* `outputs-only` (default): retain labels, trajectories, manifest, logs,
  validation report, and the merged ARL size/SHA-256 in `state.json`; remove
  all reproducible GRIB/ARL data.
* `merged`: additionally retain the merged hourly ARL for reruns.
* `all`: retain subsets, single-hour ARLs, and the merged ARL for diagnostics.

For each model-input valid time (`0/-6/-12/-18 h` per receptor), the scheduler
also extracts `U10M/V10M/PBLH/PRSS` from the exact `wrfprs fXX` subset used to
build the STILT ARL. These compact files survive every retention mode. Their
paths, valid times, forecast hours, source hashes, and the STILT archive hash
are recorded in `meteorology_manifest.json` with
`alignment=same_cycle_forecast_realization`.

For a single date, the compatibility entry point is:

```bash
bash produce_day_labels.sh 20240705 \
  /root/autodl-tmp/receptors/jul05.csv --dry-run
```

For an unattended multi-date queue, run the scheduler itself under
`setsid`/`nohup`; its stdout is the queue log while each date retains detailed
stage logs in its work directory.

### 3. Validate

```bash
python3 validate_outputs.py --stilt-wd /root/autodl-tmp/stilt \
    --out-report /root/autodl-tmp/stilt_validation.json
```

Pass rate must be ≥95% before ingestion.

## Schema-v5 ingestion

```bash
python3 ../data_builder.py --label-source stilt \
  --stilt-manifest /path/to/YYYYMMDD/manifest.csv \
  --meteorology-manifest /path/to/YYYYMMDD/meteorology_manifest.json \
  --out-prefix jul05_samecycle
```

The physical footprint remains unnormalized and the contract is fingerprinted
as schema v5. Omitting `--meteorology-manifest` is permitted only for legacy
audits and explicitly records `valid_time_only_not_same_cycle`.

`traj.rds` conversion is implemented in `stilt_io.py`, but a trajectory from
the same STILT solve as the label is privileged simulator information. Use it
only in a named privileged ablation. The primary L-JEPA arm derives its mean
trajectory from the meteorological inputs available at deployment.
