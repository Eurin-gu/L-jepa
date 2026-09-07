#!/usr/bin/env bash
# Autodl STILT/X-STILT data generation setup (template)
#
# This script installs the dependencies and clones the STILT and X-STILT
# repositories.  It does NOT download large meteorological data automatically;
# set MET_URL and run the download loop manually for your date range.
#
# Usage on Autodl:
#   bash autodl_stilt_setup.sh
set -euo pipefail

# ---------------------------------------------------------------------------
# 0. Paths (edit for your instance)
# ---------------------------------------------------------------------------
WORKDIR="${WORKDIR:-/root/autodl-tmp/stilt}"
METDIR="${METDIR:-/root/autodl-tmp/stilt/met}"
OCO_PATH="${OCO_PATH:-/root/autodl-tmp/stilt/oco2_lite}"
export WORKDIR METDIR OCO_PATH

mkdir -p "$WORKDIR" "$METDIR" "$OCO_PATH"
cd "$WORKDIR"

# ---------------------------------------------------------------------------
# 1. System dependencies (Ubuntu/Debian)
# ---------------------------------------------------------------------------
apt-get update
apt-get install -y --no-install-recommends \
    r-base r-base-dev git netcdf-bin libnetcdf-dev \
    gdal-bin libgdal-dev libudunits2-dev \
    gfortran libcurl4-openssl-dev libssl-dev libxml2-dev

# ---------------------------------------------------------------------------
# 2. R packages
# ---------------------------------------------------------------------------
Rscript -e "
install.packages(c('dplyr','parallel','raster','devtools'), repos='https://cloud.r-project.org')
devtools::install_github('benfasoli/uataq')
"

# ---------------------------------------------------------------------------
# 3. Clone STILT and X-STILT
# ---------------------------------------------------------------------------
if [ ! -d "$WORKDIR/stilt" ]; then
  git clone --depth=1 https://github.com/uataq/stilt.git
fi
if [ ! -d "$WORKDIR/X-STILT" ]; then
  git clone --recursive --depth=1 https://github.com/uataq/X-STILT.git
fi

# ---------------------------------------------------------------------------
# 4. Download ARL meteorological data (example for HRRR)
# ---------------------------------------------------------------------------
# NOAA ARL HRRR archive:
#   https://www.ready.noaa.gov/archives.php
#   ftp://arlftp.arlhq.noaa.gov/pub/archives/hrrr/
#
# Example for one day (edit YYYYMMDD):
#   YYYYMMDD=20240402
#   for HH in 00 06 12 18; do
#     wget -O "$METDIR/hrrr.${YYYYMMDD}${HH}.arl" \
#       "https://www.ready.noaa.gov/data/archives/hrrr/hrrr.${YYYYMMDD}/hrrr.${YYYYMMDD}${HH}.arl"
#   done
#
# X-STILT expects `met_file_format` matching the ARL filenames you download.
# Read the configuration section in X-STILT/run_xstilt.r before running.

# ---------------------------------------------------------------------------
# 5. Download OCO-2 Lite files (for X-STILT column footprints)
# ---------------------------------------------------------------------------
# OCO-2 Lite files can be obtained from NASA GES DISC:
#   https://disc.gsfc.nasa.gov/datasets?keywords=OCO%20L2%20Lite%20FP
#
# Put the matching granule(s) into $OCO_PATH and update the X-STILT config:
#   oco_path  = OCO_PATH
#   obs_sensor = "oco2"
#   obs_species = "co2"
#
# Then run X-STILT from X-STILT directory:
#   Rscript run_xstilt.r
#
# Outputs:
#   <simulation_id>_foot.nc   physical-unit column footprint
#   <simulation_id>_traj.rds  particle trajectories for Lagrangian-JEPA

echo "STILT setup script finished. Next: edit X-STILT/run_xstilt.r and run it."
