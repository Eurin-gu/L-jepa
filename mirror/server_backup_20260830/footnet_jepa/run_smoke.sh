#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 data_builder.py --smoke
python3 train.py --smoke
