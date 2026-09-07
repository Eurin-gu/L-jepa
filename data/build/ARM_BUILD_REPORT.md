# 2016-17 Formal HRRR arm — offline dataset rebuild report

Assembled entirely from local assets in D:\lagrangian-jepa-cn\reuse_stilt\
(server_backup_20260830\hrrr_stilt_production_v1 + stilt\out\by-id) and
D:\footexp_data\stilt_receptors_v1. Nothing was downloaded; reuse_stilt and
footnet_jepa files were never modified.

## Code added/changed (D:\lagrangian-jepa-cn\data\build\)
- feature_sources.py     : + source_type 'npz_hrrr' (NpzHrrrSource) reading
                           a<YYYYMMDDHH>_f00.npz (U10M/V10M/PBLH/PRSS,
                           float32 (1059,1799), full HRRR Lambert grid);
                           sampling unchanged (data_builder LCC formula).
- date_manifest.py       : per-date run_batch CSV from date manifest.csv +
                           receptors_<date>_n120_maximin.csv, rows in
                           maximin (CSV) order, lat/lon 5-decimal match,
                           run_time/zagl equality + foot.nc geographic
                           anchoring checked; local foot/traj paths resolved.
- run_arm_build.py       : per-(role,date) preflight -> manifest -> features
                           json -> assemble.py -> validate; + merge_train().
- build_date_log.py      : idempotent per-date build+log+validation runner;
                           writes build_<date>.log (per-date tracking), also
                           records SKIPPED dates with reason.
- summarize_arm.py       : final per-dataset validation summary
                           (arm_final_summary.csv/.json).
- validate_dataset.py    : unchanged (replica of load_dataset checks).
Logs: build_<date>.log (16 built + 1 skip), console_<date>.log, per-date
arrays sha inside each meta.json.

## Receptors / label conventions (verified during manifest build)
- Label runs: hrrr-analysis-<date>-p<250|1000>-h24-<hash>_<T>_<hash>/ with
  <simid>_foot.nc and <simid>_traj.rds (120 per date). No CONTROL files are
  kept locally; receptor lat/lon/run_time/zagl come from the date-level
  manifest.csv + receptors_v1 CSV (identical values, checked row by row).
- By-id dir <simid> matches manifest sim_id exactly; foot.nc grid anchoring
  was cross-checked (|centre - receptor| < 0.06 deg lat / 0.08 deg lon).
- Manifest rows are ordered by receptors_v1 (maximin) order.

## Build matrix (all x.npy (120,20,128,128) f32, y.npy (120,128,128) f32)
role,date,n_samples,coverage,validator(PASS=replica + real load_dataset)
train_p250 20160428 120 ok | 20160523 120 | 20160615 120 | 20160901 120 |
           20161021 120 | 20170314 120 | 20170429 120 | 20170611 120 |
           20171006 120 | 20171118 120
validation_p1000 20160715 120 | 20170517 120
formal_test_p1000 20160318 120 | 20160802 120 | 20161111 120 |
                 20170116 120 | 20170922 120
Merged train: formal_hrrr_train_p250_all (1200 = 10 dates x 120)
All dates: uniqueness sim_id/receptor/content 120/120/120 (merged 1200);
contract schema v5, grid 128 @4 km, target_mode stilt_surface_footprint_physical,
label_source stilt_xstilt; arrays sha256 match meta records; coverage 0.9844
per sample (foot domains receptor-anchored with same extent).

See arm_final_summary.csv for per-date inputs/targets sha256.

## Skipped
- train_p250/20170720 : no local assets (date dir without manifest.csv,
  no model_features npz, no by-id runs) -> documented skip (build_20170720.log).

## Notes / open items
1. Train merge is valid per load_dataset (fingerprints/arrays recomputed for
   merged files; contract identical across dates, asserted during merge).
2. Runs whose receptors straddle two hours (20170314 train, 20170517 val)
   need both 6-hour feature chains; assemble picked the per-receptor
   required set automatically (8 npz loaded, 2 snapshot groups).
3. meta.json carries no meteorology_features/driver receipts (as before);
   load_dataset passes but strict same-cycle formal claims are not made.
4. Formal-test dirs were only built and file-validated; no evaluation or
   split/consumption was performed.
5. npz orientation assumed identical to the grib/hysplit convention
   (row 0 = south) that the original server pipeline used with the same
   data_builder latlon_to_grid_xy formula; verified internally
   (direct npz bilinear == assembled channel, |diff| < 3e-7).
