#!/usr/bin/env bash
set -x
command -v python3 || apt-get install -y python3
python3 -m pip --version || (apt-get install -y python3-pip)
python3 -m pip install -q cdsapi 2>&1 | tail -2
python3 -c "import cdsapi; print('cdsapi', cdsapi.__version__)"