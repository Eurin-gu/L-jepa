#!/usr/bin/env bash
# Produce one UTC date of STILT labels from continuous hourly HRRR ARL data.
#
# Usage: produce_day_labels.sh YYYYMMDD [receptors.csv] [scheduler options...]
set -euo pipefail

DATE="${1:?usage: produce_day_labels.sh YYYYMMDD [receptors.csv] [options...]}"
if [[ ! "$DATE" =~ ^[0-9]{8}$ ]]; then
    echo "date must be YYYYMMDD" >&2
    exit 2
fi

stem=$(LC_ALL=C date -u -d "${DATE:0:4}-${DATE:4:2}-${DATE:6:2}" +%b%d | tr '[:upper:]' '[:lower:]')
REC="${2:-/root/autodl-tmp/receptors/${stem}.csv}"
shift
if (($#)); then
    shift
fi

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec python3 "$SCRIPT_DIR/schedule_hrrr_stilt.py" \
    --receptors "$REC" --dates "$DATE" "$@"
