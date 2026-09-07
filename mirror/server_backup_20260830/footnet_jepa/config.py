"""Configuration for the JEPA-FootNet footprint emulator (real-HRRR OSSE).

This is currently a *trajectory-shape emulator*: given real HRRR meteorological
fields and a receptor location, predict a normalized 24 h horizontal residence
distribution (a proxy precursor, not a STILT source-receptor matrix). JEPA pretrains the
meteorological encoder on unlabelled HRRR fields, then the same encoder is
fine-tuned with a supervised footprint head.

Data notes
----------
* HRRR-lite files are real 2024 analysis fields (U10M, V10M, PBLH, PRSS).
* Receptors are sampled from real OCO-2 sounding manifests (SoCal overpasses)
  by default, or uniformly over CONUS with --receptors random.
* Footprint labels are produced by `simple_lagrangian.py` using the real HRRR
  winds. They are NOT STILT/X-STILT; they are a physically motivated proxy.
  Until real STILT labels are added, all claims must say "OSSE/proxy", not
  "real atmospheric transport matrix".
"""
import os

DATA_SCHEMA_VERSION = 5

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
SOCAL_PILOT = os.path.join(ROOT, "socal_pilot")
HRRR_DIR = os.path.join(SOCAL_PILOT, "data", "HRRR_lite", "2024")
MANIFEST_DIR = os.path.join(SOCAL_PILOT, "data")
OUTDIR = os.path.join(ROOT, "data")
RESULTS = os.path.join(ROOT, "results")

# Allow Autodl to place the (potentially large) dataset outside the code dir.
if os.environ.get("FOOTNET_DATA_DIR"):
    OUTDIR = os.environ["FOOTNET_DATA_DIR"]

# ---------------------------------------------------------------------------
# Receptor-centred grid
# ---------------------------------------------------------------------------
GRID = 128                 # output grid size per side (full run; smoke uses 64)
SPACING_KM = 4.0           # receptor-centred metric spacing
DOMAIN_KM = GRID * SPACING_KM

# Input feature layout (20 channels)
#   ch 0           : receptor impulse (query location)
#   ch 1..16       : 4 back snapshots x (U10M, V10M, PBLH, PRSS), normalized
#   ch 17..19      : local x, local y, radial distance (all / half-domain)
BACKHOURS = [0, 6, 12, 18]       # hours before the receptor analysis time
N_MET = 4
N_CHANNELS = 1 + N_MET * len(BACKHOURS) + 3   # 20
MET_OFFSETS = [0.0, 0.0, 1000.0, 90000.0]
MET_SCALES = [0.1, 0.1, 1e-3, 1e-4]

# ---------------------------------------------------------------------------
# Real-data splits
# ---------------------------------------------------------------------------
# If AUTO_SPLIT is False, build_data uses exactly these snapshot lists.
# If AUTO_SPLIT is True, build_data scans HRRR_DIR and selects all snapshots
# whose YYYYMM is in TRAIN_MONTHS / TEST_MONTHS (or an automatic 80/20 split
# by time when both month lists are empty).  This is the recommended mode on
# Autodl after downloading many HRRR files.
AUTO_SPLIT = False
TRAIN_SNAPSHOTS = ["20240402.18z"]   # April 2024, date-matched OCO-2 overpass
TEST_SNAPSHOTS = ["20240705.18z"]    # July 2024, never-seen month
TRAIN_MONTHS = []                    # e.g. ["202401","202402","202403","202404"]
TEST_MONTHS = []                     # e.g. ["202407","202408"]
# If more than one snapshot is listed, build_data will use all of them.
# Receptor times are the snapshot times; backhours must exist in HRRR_DIR.

# ---------------------------------------------------------------------------
# Receptors / dataset size
# ---------------------------------------------------------------------------
RECEPTOR_MODE = "oco2"       # "oco2" or "random"
N_RECEPTORS_PER_TIME_TRAIN = 120   # full run; smoke overrides lower
N_RECEPTORS_PER_TIME_TEST = 60     # full run
RECEPTOR_SEED = 20260822
# Extra HRRR-only snapshots for the inputs-only self-supervised pool. These
# dates need NO proxy labels and NO OCO-2 manifest; they expand the JEPA
# pretraining pool independently of supervised label availability.
PRETRAIN_EXTRA_SNAPSHOTS = []
N_PRETRAIN_PER_TIME = 120
# Random-receptor bounds (CONUS, with margin for the output grid)
LAT_MIN, LAT_MAX = 26.0, 48.0
LON_MIN, LON_MAX = -125.0, -67.0   # store in -180..180; projection handles 0..360
RANDOM_MARGIN_DEG = 4.0

# ---------------------------------------------------------------------------
# simple_lagrangian proxy target
# ---------------------------------------------------------------------------
NPART = 600                # particles per footprint (full run; smoke lower)
DT = 600.0                 # substep seconds
HPERBLOCK = 6              # hours per wind block
DIFFUSIVITY = 5000.0       # horizontal eddy diffusivity (m^2/s)
TARGET_MODE_SHAPE = "trajectory_shape_probability"
TARGET_MODE_PHYSICAL = "stilt_surface_footprint_physical"
# Switch to TARGET_MODE_PHYSICAL together with LABEL_SOURCE="stilt_xstilt"
# once real foot.nc labels are ingested. The two must always be switched
# together; provenance.data_contract records both and fingerprints them.
TARGET_MODE = TARGET_MODE_SHAPE
LABEL_SOURCE = "simple_lagrangian_proxy"   # or "stilt_xstilt"
MIN_CAPTURE_FRACTION = 0.80
TRAJ_RECORD_STEP_H = 1.0   # Lagrangian-JEPA trajectory recording interval

# ---------------------------------------------------------------------------
# Training / model
# ---------------------------------------------------------------------------
DEVICE = "cuda" if __import__("torch").cuda.is_available() else "cpu"
BATCH_SIZE = 8
EPOCHS_SUPERVISED = 40
LR = 1e-3
SHAPE_MULTISCALE_WEIGHT = 1.0

# JEPA pretraining
EPOCHS_JEPA = 25
LR_JEPA = 3e-4
EMA_DECAY = 0.996
MASK_FRAC_MIN, MASK_FRAC_MAX = 0.3, 0.6
JEPA_REG_MODE = "visreg"
JEPA_REG_WEIGHT = 0.5
JEPA_REG_SLICES = 256

# Smoke settings (CPU-friendly)
SMOKE_GRID = 64
SMOKE_N_TRAIN = 12
SMOKE_N_TEST = 6
SMOKE_NPART = 100
SMOKE_EPOCHS_SUP = 10
SMOKE_EPOCHS_JEPA = 3
SMOKE_BATCH = 4

# ---------------------------------------------------------------------------
# Random seeds
# ---------------------------------------------------------------------------
SEEDS = [20260822, 20260823, 20260824]
MIN_FORMAL_TEST_DATES = 5
MAX_BUILD_RAM_GB = 8.0
