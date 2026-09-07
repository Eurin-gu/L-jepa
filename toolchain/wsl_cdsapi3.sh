#!/usr/bin/env bash
set -x
apt-get install -y python3.12-venv 2>&1 | tail -2
rm -rf /root/venvs/cds
python3 -m venv /root/venvs/cds
/root/venvs/cds/bin/pip install -q cdsapi 2>&1 | tail -2
/root/venvs/cds/bin/python -c "import cdsapi; print('cdsapi ok', cdsapi.__version__)"