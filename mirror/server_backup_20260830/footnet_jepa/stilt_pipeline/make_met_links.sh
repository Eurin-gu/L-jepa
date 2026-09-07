#!/bin/bash
# Create per-day symlinks for GDAS monthly-week ARL files.
#
# find_met_files() greps filenames by strftime patterns such as '%Y%m%d',
# but NOAA's gdas1.<month>.wN archives encode no date in their names.  One
# week file covers days (7*(N-1)+1) .. min(7*N, end-of-month) of its month,
# all hours, so a symlink named '<YYYYMMDD>.<original>' lets every day map
# back to the same physical file without duplicating data.
#
# Usage: bash make_met_links.sh /root/autodl-tmp/met
set -euo pipefail

MET_DIR="${1:?usage: make_met_links.sh <met_dir>}"
cd "$MET_DIR"

shopt -s nullglob
for f in gdas1.[a-z][a-z][a-z][0-9][0-9].w[1-5]; do
    stem="${f#gdas1.}"
    mon="${stem:0:3}"; yy="20${stem:3:2}"; wk="${stem##*w}"
    mm=$(date -d "${mon} 01 ${yy}" +%m)
    last_day=$(date -d "${mon} 01 ${yy} +1 month -1 day" +%d)
    first=$(( 7 * (wk - 1) + 1 ))
    last=$(( 7 * wk )); (( last > last_day )) && last=$last_day
    for (( d = first; d <= last; d++ )); do
        dd=$(printf '%02d' "$d")
        link="${yy}${mm}${dd}.${f}"
        [[ -e "$link" ]] || ln -sf "$f" "$link"
        echo "linked $link -> $f"
    done
done
echo "done"
