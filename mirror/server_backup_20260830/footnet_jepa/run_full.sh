#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# On Autodl, put large data in a writable path and point FOOTNET_DATA_DIR there.
# Example:
#   export FOOTNET_DATA_DIR=/root/autodl-tmp/footnet_data
python3 data_builder.py --receptors "${FOOTNET_RECEPTORS:-random}"
python3 train.py
python3 evaluate.py
