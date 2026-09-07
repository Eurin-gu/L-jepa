#!/usr/bin/env python3
"""Build data_builder manifest from existing STILT output dirs for a date prefix.
Usage: python3 make_manifest_from_outputs.py <prefix> <out_csv>
"""
import csv, os, sys, glob

prefix = sys.argv[1]  # e.g. 'jul01'
out_csv = sys.argv[2]
base = '/root/autodl-tmp/stilt/out/by-id'

rows = []
for d in sorted(os.listdir(base)):
    if not d.startswith(prefix + '_'):
        continue
    dirp = os.path.join(base, d)
    foot = [f for f in os.listdir(dirp) if f.endswith('_foot.nc')] if os.path.isdir(dirp) else []
    traj = [f for f in os.listdir(dirp) if f.endswith('_traj.rds')] if os.path.isdir(dirp) else []
    if not foot or not traj:
        continue
    foot_p = os.path.join(dirp, foot[0])
    traj_p = os.path.join(dirp, traj[0])
    if os.path.getsize(foot_p) < 1000 or os.path.getsize(traj_p) < 1000:
        continue
    # parse run_time, lat, lon from CONTROL file
    ctrl = os.path.join(dirp, 'CONTROL')
    run_time = ''
    lat = lon = zagl = ''
    if os.path.isfile(ctrl):
        with open(ctrl) as f:
            lines = f.read().splitlines()
        if len(lines) >= 3:
            try:
                ts = lines[0].split()
                yy, mm, dd, hh, mi = int(ts[0]), int(ts[1]), int(ts[2]), int(ts[3]), int(ts[4])
                run_time = f'{yy:04d}-{mm:02d}-{dd:02d}T{hh:02d}:{mi:02d}:00Z'
                coords = lines[2].split()
                lat, lon, zagl = coords[0], coords[1], coords[2]
            except Exception:
                pass
    rows.append([d, run_time, lat, lon, zagl, foot_p, traj_p])

with open(out_csv, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['sim_id', 'run_time', 'lati', 'long', 'zagl', 'foot_nc', 'traj_rds'])
    for r in rows:
        w.writerow(r)
print(f'{prefix}: {len(rows)} rows -> {out_csv}')
