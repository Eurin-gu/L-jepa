"""Batch-drive uataq/stilt over a receptor CSV, in parallel.

For each row of receptors.csv this launches one stilt_cli.r run with a
receptor-centred footprint window (default half-width 256 km to match the
FootNet 128 x 128 @ 4 km domain), backward duration -24 h, and integrated
surface footprint output.

Outputs land under <stilt_wd>/out/by-id/<simulation_id>/ as
    <YYYYmmDDHH_mm_ss>/foot.rds and traj.rds   (uataq/stilt layout)

Usage:
    python3 run_batch.py --receptors /root/autodl-tmp/receptors/apr02.csv \
        --stilt-wd /root/autodl-tmp/stilt --met /root/autodl-tmp/met \
        --jobs 16 --numpar 1000
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

KM_PER_DEG_LAT = 110.54


def deg_lon_per_km(lat: float) -> float:
    return 1.0 / (111.32 * math.cos(math.radians(lat)))


def simulation_id(row, args) -> str:
    identity = "|".join([
        row["run_time"],
        f"{float(row['lati']):.8f}",
        f"{float(row['long']):.8f}",
        f"{float(row['zagl']):.3f}",
        str(args.hours),
        str(args.numpar),
        f"{args.half_km:g}",
        f"{args.res:g}",
    ])
    digest = hashlib.sha256(identity.encode("ascii")).hexdigest()[:12]
    timestamp = row["run_time"].replace("-", "").replace(":", "")
    return f"{args.tag}_{timestamp}_{digest}"


def find_artifacts(stilt_wd: str, sim_id: str) -> tuple[str, str]:
    sim_dir = os.path.join(stilt_wd, "out", "by-id", sim_id)
    foot_candidates = (
        glob.glob(os.path.join(sim_dir, "*_foot.nc"))
        + glob.glob(os.path.join(sim_dir, "*", "foot.nc"))
        + glob.glob(os.path.join(sim_dir, "*", "*_foot.nc"))
    )
    traj_candidates = (
        glob.glob(os.path.join(sim_dir, "*_traj.rds"))
        + glob.glob(os.path.join(sim_dir, "*", "traj.rds"))
        + glob.glob(os.path.join(sim_dir, "*", "*_traj.rds"))
    )

    def first_nonempty(paths: list[str]) -> str:
        return next(
            (path for path in sorted(paths) if os.path.getsize(path) > 0), ""
        )

    return first_nonempty(foot_candidates), first_nonempty(traj_candidates)


def build_cmd(row, args) -> list[str]:
    run_time, lati, long_, zagl = row["run_time"], float(row["lati"]), \
        float(row["long"]), float(row["zagl"])
    # receptor-centred square window, aligned to the grid resolution so the
    # extent contains an integer number of cells
    dlat = args.half_km / KM_PER_DEG_LAT
    dlon = args.half_km * deg_lon_per_km(lati)
    xmn = round(long_ - dlon, 5)
    xmx = round(long_ + dlon, 5)
    ymn = round(lati - dlat, 5)
    ymx = round(lati + dlat, 5)
    ncell = int(round((xmx - xmn) / args.res))
    xmx = round(xmn + ncell * args.res, 5)
    ymx = round(ymn + int(round((ymx - ymn) / args.res)) * args.res, 5)
    sim_id = simulation_id(row, args)
    # stilt_cli.r parses r_run_time with format='%Y-%m-%dT%H:%M:%S' -- no
    # trailing 'Z' allowed, otherwise as.POSIXct yields NA
    rt = run_time[:-1] if run_time.endswith("Z") else run_time
    cli = os.path.join(args.stilt_wd, "r", "stilt_cli.r")
    return [
        "Rscript", cli,
        f"r_run_time={rt}",
        f"r_lati={lati}",
        f"r_long={long_}",
        f"r_zagl={zagl:g}",
        f"met_path={args.met}",
        "met_file_format=%Y%m%d",
        f"met_file_tres={args.met_file_tres_hours:g} hours",
        "n_met_min=1",
        f"n_hours=-{args.hours:d}",
        f"numpar={args.numpar:d}",
        f"xmn={xmn}", f"xmx={xmx}",
        f"ymn={ymn}", f"ymx={ymx}",
        f"xres={args.res:g}", f"yres={args.res:g}",
        "time_integrate=T",
        f"timeout={args.timeout:d}",
        f"simulation_id={sim_id}",
    ], sim_id


def run_one(cmd, sim_id, log_dir, stilt_wd, resume=False):
    log = os.path.join(log_dir, f"{sim_id}.log")
    t0 = time.time()
    if resume:
        foot, traj = find_artifacts(stilt_wd, sim_id)
        if foot and traj:
            return sim_id, True, 0.0, foot, traj
    with open(log, "w") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                              cwd=os.path.dirname(cmd[1]))
    ok = proc.returncode == 0
    foot, traj = find_artifacts(stilt_wd, sim_id) if ok else ("", "")
    ok = ok and bool(foot) and bool(traj)
    return sim_id, ok, time.time() - t0, foot, traj


MANIFEST_FIELDS = [
    "sim_id", "run_time", "lati", "long", "zagl", "foot_nc", "traj_rds"
]


def read_manifest(path: str) -> dict[str, dict[str, str]]:
    if not os.path.isfile(path):
        return {}
    with open(path, newline="") as handle:
        return {
            row["sim_id"]: row
            for row in csv.DictReader(handle)
            if row.get("sim_id")
        }


def write_manifest(path: str, rows: dict[str, dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows[key] for key in sorted(rows))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--receptors", required=True)
    ap.add_argument("--stilt-wd", required=True)
    ap.add_argument("--met", required=True)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--numpar", type=int, default=1000)
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--half-km", type=float, default=256.0)
    ap.add_argument("--res", type=float, default=0.04,
                    help="footprint grid resolution in degrees")
    ap.add_argument("--met-file-tres-hours", type=float, default=3.0,
                    help="meteorology file search interval; use 1 for hourly ARL")
    ap.add_argument("--tag", default="rec")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--log-dir", default=None)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--resume", action="store_true",
                    help="reuse non-empty footprint and trajectory pairs")
    args = ap.parse_args()

    if args.jobs < 1 or args.numpar < 1 or args.hours < 1:
        ap.error("jobs, numpar, and hours must be positive")
    if args.met_file_tres_hours <= 0:
        ap.error("met-file-tres-hours must be positive")

    with open(args.receptors) as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit("empty receptors csv")

    log_dir = args.log_dir or os.path.join(
        os.path.dirname(os.path.abspath(args.receptors)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    manifest_path = args.manifest or os.path.join(
        os.path.dirname(os.path.abspath(args.receptors)),
        os.path.basename(args.receptors).replace(".csv", "_manifest.csv"))
    manifest_rows = read_manifest(manifest_path)

    print(f"[batch] {len(rows)} receptors, jobs={args.jobs}, "
          f"numpar={args.numpar}")
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {}
        scheduled_ids = set()
        for row in rows:
            cmd, sim_id = build_cmd(row, args)
            if sim_id in scheduled_ids:
                raise SystemExit(f"duplicate receptor simulation: {sim_id}")
            scheduled_ids.add(sim_id)
            futures[pool.submit(run_one, cmd, sim_id, log_dir,
                                args.stilt_wd, args.resume)] = (sim_id, row)
        done = 0
        for fut in as_completed(futures):
            sim_id, ok, dt, foot_nc, traj_rds = fut.result()
            row = futures[fut][1]
            manifest_rows[sim_id] = {
                "sim_id": sim_id,
                "run_time": row["run_time"],
                "lati": row["lati"], "long": row["long"],
                "zagl": row["zagl"],
                "foot_nc": foot_nc, "traj_rds": traj_rds,
            }
            write_manifest(manifest_path, manifest_rows)
            results.append((sim_id, ok))
            done += 1
            print(f"[{done}/{len(rows)}] {sim_id}: "
                  f"{'OK' if ok else 'FAILED'} ({dt:.0f}s)", flush=True)
    n_ok = sum(ok for _, ok in results)
    print(f"[batch] finished: {n_ok}/{len(results)} succeeded")
    sys.exit(0 if n_ok == len(results) else 1)


if __name__ == "__main__":
    main()
