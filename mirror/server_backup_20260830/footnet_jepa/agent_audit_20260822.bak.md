# footnet_jepa authoritative status (2026-08-22 audit)

## 1. Honest project definition

This directory is a controlled proxy benchmark:

> real HRRR meteorology + receptor query -> normalized horizontal backward
> trajectory residence shape.

It is not STILT/X-STILT, not a physical source-receptor matrix in ppm per flux,
and not a real CO2 inversion. The current label generator uses U10M/V10M only;
PBLH and PRSS do not affect the target. External claims must retain this boundary.

## 2. Bugs corrected in data schema 3

1. U/V channels were multiplied by `10` although the comment and intended scale
   were `0.1`; generated values reached tens to hundreds. Inputs now use explicit
   offsets/scales and realistic order-one values.
2. The former handcrafted Gaussian plume and plume mask supplied an answer-shaped
   shortcut. Inputs now contain a receptor query and metric coordinates instead.
3. A degree grid changed physical pixel width with latitude. The grid is now
   receptor-centred in kilometres with a unique receptor pixel.
4. Particles leaving the output window previously saw zero wind and stalled.
   Labels now sample the full HRRR domain throughout integration and record the
   fraction of residence captured by the output window.
5. Bilinear interpolation silently clipped out-of-domain indices while retaining
   invalid interpolation fractions. It now raises for model inputs and returns
   explicit invalid values for particles outside HRRR.
6. Automatic train/test splits could share the same back-hour meteorological
   files. A temporal-overlap guard now requires an embargo.
7. Loading all available HRRR files would exhaust memory after data expansion.
   Only snapshots required by the selected events are loaded.
8. Old arrays had no enforceable data contract. Schema, configuration, source,
   and contract fingerprints are now recorded; stale data are rejected.

## 3. Bugs corrected in training and JEPA

1. The old mass penalty summed log-transformed outputs over the whole batch.
   Samples could cancel each other and log-space mass has no physical meaning.
   The shape-only target now uses spatial softmax, cross-entropy, and per-event
   total-variation mismatch. Output is non-negative and unit mass by construction.
2. Metrics were flattened over all events; the claimed per-event mass fix had not
   actually been implemented. All metrics are now computed per event, then averaged.
3. Peak error was in grid cells and therefore incomparable across resolutions.
   Peak and centre errors are now kilometres.
4. `SEEDS` existed but was ignored. Non-smoke training now runs all configured
   seeds and reports mean plus variation across seeds.
5. Scratch and JEPA did not share a controlled initialization. They now start from
   identical encoder/decoder weights and use the same supervised batch ordering;
   JEPA pretraining is the intended difference.
6. JEPA masks were created on CPU, causing CUDA device failure. Masks are now on
   the input device, generated independently per sample, and checked against the
   actual encoder resolution.
7. Configured mask fractions were ignored; a hard-coded linear block size was
   used and described as area. The configured values now control masked area.
8. JEPA latent loss divided by masked cells but not channels. It now averages the
   latent vector loss per masked cell.
9. VISReg used unbiased standard deviation and a summed centre term. This could
   produce NaN for small samples and scale the centre penalty with embedding width.
   It now uses population standard deviation and mean reduction.
10. Checkpoints and JSON files were overwritten in place. Runs are immutable,
    provenance-aware directories and standalone evaluation verifies data identity.

## 4. Verified state

- 12 regression tests pass.
- Data build, baseline, scratch, JEPA pretraining/fine-tuning, checkpoint reload,
  and standalone evaluation complete end to end on CPU.
- The 64x64 smoke domain is 256 km wide and captures roughly 93%-98% of proxy
  particle-time residence for the current April/July examples.
- Current formal inference is disabled because test data contain only one July
  receptor snapshot. Six receptors do not equal six independent weather events.

The corrected smoke result is not evidence for JEPA. The zero-parameter mean
training footprint beats all three networks on several shape/location metrics.
Peak distance is especially weak because this residence proxy starts every
particle at the receptor, so the target peak is usually the centre cell.

## 5. Research choices requiring user agreement

### A. What should the supervised target be?

Recommended: STILT/HYSPLIT/FLEXPART surface footprint with physical units. The
current horizontal residence probability is useful only for code and method
sanity. If retained, call the task trajectory-shape emulation, not FootNet H.

### B. Which operator should be learned first?

Recommended: receptor-conditioned backward surface footprint. Alternatives are
source-conditioned forward plume or full Eulerian concentration transport. They
have different labels, losses, domains, and conservation laws and must not share
one ambiguous target.

### C. What is Lagrangian-JEPA?

Only generic spatial masked JEPA exists today. Before implementation, choose one
pretext target. Recommended first test: predict latent meteorological states along
integrated backward trajectories and compare against Met-MAE and Eulerian-JEPA.

### D. Domain and horizon

The current full grid is 512 km wide for a 24 h proxy. This works for the present
examples but is not guaranteed for all regions/weather. Every dataset must report
capture fraction; low-capture events should trigger domain expansion or a shorter
horizon, not silent renormalization.

### E. What counts as cross-domain evidence?

Recommended first paper scope: held-out region plus held-out season. Cross-model
and cross-resolution evaluation should follow only after this works. A valid test
needs independent dates/regions, not more particles or receptors from one field.

## 6. Go/no-go gate before a large run

Implement and compare, with identical supervised data and decoder:

```text
train-mean shape (zero parameter)
supervised scratch
Met-MAE + fine-tune
Eulerian-JEPA + fine-tune
Lagrangian-JEPA + fine-tune
```

Add a physics simulator reference and evaluate held-out weather clusters. Continue
toward CVPR only if Lagrangian pretraining improves practical transport metrics
across seeds and domains, not merely pretraining loss or same-snapshot RMSE.

## 7. Latest Lagrangian prototype audit

- `lagrangian_jepa.py` and `train_lagrangian_jepa.py` pass smoke execution.
- The trajectory cache now uses a stable SHA256-derived seed rather than Python's
  process-randomized `hash()`, and the target encoder is put in eval mode during
  teacher inference so BatchNorm buffers do not drift independently.
- The prototype now uses only the date-level training subset, refuses to overwrite
  non-empty run directories, and stores data/source fingerprints in its checkpoint.
- It is no longer pretraining-only. `train.py --with-lagrangian` now runs the
  full closed loop: Lagrangian-JEPA pretraining -> supervised fine-tune ->
  validation/test evaluation -> per-seed checkpoint, with the same
  initialization and batch-order controls as Scratch/JEPA.
- `autodl_stilt_setup.sh` is an unpinned installation template. It does not itself
  download verified ARL fields, configure X-STILT, validate `foot.nc`/`traj.rds`,
  or connect those outputs to `data_builder.py`. Do not treat a successful shell
  completion as a valid STILT dataset.

## 8. Blockers before any large-scale run

Do **not** start a large Autodl run or interpret results as real transport
evidence until all four blockers are resolved:

| # | Blocker | Required fix |
|---|---|---|
| 1 | Lagrangian-JEPA closed-loop code | ✅ Resolved in code: `train.py --with-lagrangian` runs pretrain + fine-tune + test + multi-seed; still needs real STILT labels before scientific conclusions |
| 2 | Labels are `simple_lagrangian` proxy, not STILT/X-STILT | Replace/augment with STILT/X-STILT `foot.nc` physical-unit labels and `traj.rds` trajectories |
| 3 | Only 1 train date and 1 test date | Add at least 5 independent held-out meteorological dates/regions before any cross-weather claim |
| 4 | `autodl_stilt_setup.sh` is an install template, not a data pipeline | Build a complete, pinned, validated pipeline: ARL download -> X-STILT config -> run -> `foot.nc`/`traj.rds` validation -> `data_builder.py` ingestion |

Until these are done, the project can only be described as:

> a proxy-method prototype, not a real STILT-based transport emulator.


---

## 9. Lagrangian-JEPA prototype status (2026-08-22)

- `lagrangian_jepa.py` now contains a first prototype:
  - `compute_trajectory_xy()`: real-HRRR mean backward trajectory coordinates.
  - `TrajectoryPredictor`: trajectory-relative attention.
  - `LagrangianJEPA`: masked latent prediction along trajectory segments.
- `train_lagrangian_jepa.py --smoke --epochs 2` runs end-to-end on the current
  proxy data and saves an encoder checkpoint.
- This is **not** the final method. It is a code prototype to be upgraded with
  STILT/X-STILT `traj.rds` trajectories and physical footprints.

### Next step for STILT data

- Use `autodl_stilt_setup.sh` on an Autodl instance to install R, STILT,
  X-STILT, and download ARL met + OCO-2 Lite data.
- Run X-STILT to produce `foot.nc` and `traj.rds`.
- Then update `data_builder.py` to read STILT outputs and switch the
  Lagrangian-JEPA trajectory source from `compute_trajectory_xy` to real STILT
  trajectories.
