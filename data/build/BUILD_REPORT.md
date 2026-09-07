# Local dataset assembler build report (so_hrrr_20171111)

Date: 2017-11-11 STILT receptor batch (HRRR-driven, hrrr-so-20171111-p250),
assembled locally from real HRRR grib2 features + real STILT foot.nc labels.

## Code delivered (D:\lagrangian-jepa-cn\data\build\)
- assemble.py            : main assembler (manifest csv + per-date feature
                           descriptor json -> x.npy / y.npy / meta.json)
- feature_sources.py     : per-date readers. Declarative dispatch by
                           "source_type"; JSON descriptor selects reader and
                           directory (每日期一个 json + 每快照读取配置; actual
                           read functions live here)
- features_hrrr_20171111.json : descriptor for this date (HRRR wrfprs f00)
- validate_dataset.py    : standalone replica of train_stilt_strict.load_dataset
                           checks (no torch needed)
- logs: build_full.log, smoke.log, sanity*.log, crosscheck*.log,
        real_load.log (project load_dataset), inspect_*.log

## Where it runs
WSL Ubuntu-24.04, python /root/venvs/cds/bin/python (numpy + netCDF4 +
eccodes 2.48). Windows-side copy of same files under D:\...\data\build\
is executed through /mnt/d. No modification of footnet_jepa code.

## Semantics (mirrors server pipeline exactly)
- Input grid 128x128 @ 4 km receptor-centred; 20 channels
  ch0 impulse | ch1-16 = 4 backhours [0,6,12,18] x (U10M,V10M,PBLH,PRSS)
  normalised by MET_OFFSETS [0,0,1000,90000] & MET_SCALES [0.1,0.1,1e-3,1e-4]
  | ch17-19 local x/y/radius over half domain.
- Meteorology sampling = data_builder._assemble_input: receptor_grid ->
  regular lat/lon -> HRRR Lambert conformal latlon_to_grid_xy (copy of
  data_builder constants 1799x1059 @3 km, lat0/lat1/lat2=38.5, lon0=262.5,
  a=6371229) -> bilinear (bounds check on).
- Labels = stilt_io.read_stilt_footprint-equivalent: read <sim>_foot.nc,
  integrate time, sort lat/lon ascending, resample footprint (physical
  units, NOT normalised) onto the same 128x128@4km grid with np.interp
  bilinear, NaN-outside-domain -> 0, min_coverage = 0.80 gate.
- meta.json: prod_test_merged-style samples + build_stilt arrays records
  + provenance.data_contract/fingerprint equivalents
  (schema_version 5, grid 128, spacing_km 4.0, target_mode
  "stilt_surface_footprint_physical", label_source "stilt_xstilt",
  meteorology.alignment "valid_time_only_not_same_cycle",
  random_receptor_bounds null) + contract_fingerprint + source_fingerprint
  over footnet_jepa *.py.

## Feature extraction from HRRR grib (finds)
Files: D:\lagrangian-jepa-cn\met_cache\hrrr_20171111\YYYYMMDDHH.grib2
(wrfprs, 1799x1059 Lambert 3km, f00 instant, dataTime == filename hour).
Messages actually used (present in every required file, verified stats):
- U10M  : shortName "10u", paramId 165, typeOfLevel heightAboveGround 10,
          unit m/s            (present: YES)
- V10M  : shortName "10v", paramId 166, typeOfLevel heightAboveGround 10,
          unit m/s            (present: YES)
- PBLH  : shortName "blh", paramId 159, typeOfLevel surface, unit m
          (present: YES, inside the wrfprs file)
- PRSS  : shortName "sp",  paramId 134, typeOfLevel surface, unit Pa
          (present: YES, inside the wrfprs file)
=> NO missing HRRR fields; no fallback to wrfsfc or ERA5 was required for
the main build. ERA5 SFC files (/root/era5_grib/*_SFC.GRIB, e.g.
po_20171023_SFC.GRIB) hold the same four variables (10u/10v/blh/sp) but
with typeOfLevel "surface" (level 0); feature_sources.ERA5_SFC_SELECTORS
was updated accordingly so an ERA5 fallback build works with the same
assembler.

## Build log summary (full: build_full.log)
- manifest rows: 120 (all foot_nc exist), snapshots ['20171111.20z']
- required feature snapshots: 20171111.02z / .08z / .14z / .20z (all present)
- per-file field means consistent with direct eccodes stats
- samples kept 120, skipped 0 (all coverages 0.984436... >= 0.80)
- wall time ~14 s (4 grib loads ~11 s + 120 footprints)
- outputs:
    D:\lagrangian-jepa-cn\data\datasets\so_hrrr_20171111\x.npy
        (120, 20, 128, 128) float32, 157286528 bytes
    .../y.npy (120, 128, 128) float32, 7864448 bytes
    .../meta.json 52012 bytes
- x/y arrays sha256 (meta.json 'arrays'):
    inputs 46471aedbe30a55db31cf0051f447ed6af54466d8b158ec87a4f70913e5af502
    targets 95d7499e7b58fa9ee7037431700b3ea9e8d3a52511428b5a5f50944912492475

## Validation results
1. validate_dataset.py (replica of load_dataset checks): PASS
   - x 4-D, ch=20, y (N,128,128), finite x/y, y >= 0
   - contract schema_version 5, target_mode physical, label_source stilt_xstilt
   - contract_fingerprint == fingerprint(contract)
   - samples count == len(x); unique sim_ids / receptors / contents = 120
   - arrays inputs/targets sha256 + shape + dtype match
2. Project train_stilt_strict.load_dataset (real code import, WSL ml venv,
   footnet_jepa mirror on sys.path): PASS
   (see real_load.log) - same fingerprints, uniqueness 120/120/120.
   -> passes the strict schema-v5 loader used by training.

## Sanity / cross-checks
- ch0 impulse = 1 exactly at (64,64); ch17-19 in [-1,1]; radius corners 1.414
- U10M pixel value reconstructed from x ch1 (2.65157 m/s) equals direct
  bilinear evaluation of the same grib with the same formula to 1e-7.
- Anchoring the LCC formula to the grib's own first grid point (instead of
  data_builder's origin-at-(899,529) convention) shifts sampling by ~0.17
  cell (~500 m) -> 0.026 m/s on U10M at the receptor (~1%). Conventions
  agree within smooth-field tolerance; we kept data_builder's formula to
  stay identical to server inputs.
- Footprint label mass CoM ~5-10 km from the receptor with content fully
  inside the central 160 km box (receptor-scale STILT run geometry), values
  non-negative, sums 15.0-48.5 per sample, units stilt_surface_sensitivity.

## Known issues / notes
1. Grid-origin convention: data_builder latlon_to_grid_xy places the LCC
   origin (38.5 N, 262.5 E) exactly at cell (899,529); the archived grib
   grid's SW corner is at cell (0,0) with lat/lon (21.138123, 237.280472),
   ~0.1-0.2 cell offset from that idealisation. Difference is <=~500 m;
   fine for U/V/PBLH/PRSS sampling but byte-for-byte equality with server
   hysplit-cache sampling is not claimed.
2. Coverage identical across all samples (0.984436...) because every
   foot.nc domain is receptor-anchored with the same extent; all >= 0.80.
3. meta.json carries no meteorology_features / driver receipts (no scheduler
   met manifest available locally); load_dataset does not require them, but
   make_strict_split reports meteorology_feature_coverage=False and formal
   "same-cycle" claims are not supported -> use as strict_v5 train/val data
   (single date, so formal test split still needs more dates).
4. ERA5 fallback (task 4) was NOT exercised end-to-end because HRRR already
   contains all fields; selectors verified against po_20171023_SFC.GRIB.
5. Assembler is date-generic: any manifest row whose run_time falls within
   the hours covered by the descriptor dir works; extend with additional
   descriptor JSON files for other dates.
