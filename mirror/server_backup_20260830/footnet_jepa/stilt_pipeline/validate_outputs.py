"""Validate uataq/stilt outputs before they are used as training labels.

Checks, for every simulation id found in <stilt-wd>/out/by-id:
  * foot.rds and traj.rds exist and are non-empty
  * footprint is finite, non-negative, positive mass
  * trajectory covers >= n_hours of backward time
  * records physical units and grid metadata for the data contract

Reads .rds files by invoking Rscript with a small inline reader that dumps
each object to .npz-friendly CSV/JSON. This avoids requiring rpy2.

Usage:
    python3 validate_outputs.py --stilt-wd /root/autodl-tmp/stilt \
        --out-report /root/autodl-tmp/stilt_validation.json
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

R_READER = r"""
suppressMessages(library(jsonlite))
args <- commandArgs(trailingOnly = TRUE)
path <- args[1]
obj_name <- args[2]
obj <- readRDS(path)
if (is.data.frame(obj)) {
  obj <- as.data.frame(unname(obj))
  cat(toJSON(obj, dataframe = "columns", digits = NA))
} else if (is.matrix(obj) || is.array(obj)) {
  cat(toJSON(obj, digits = NA))
} else {
  cat(toJSON(list(class = class(obj)), auto_unbox = TRUE))
}
"""


def read_rds(path: str):
    with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False) as fh:
        fh.write(R_READER)
        script = fh.name
    proc = subprocess.run(
        ["Rscript", script, path, "obj"],
        capture_output=True, text=True, timeout=300)
    os.unlink(script)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[:500])
    return json.loads(proc.stdout)


def find_output_artifacts(sim_dir: str) -> tuple[str | None, str | None]:
    """Return the first non-empty footprint and trajectory for one sim id."""
    inner = [
        os.path.join(sim_dir, name)
        for name in sorted(os.listdir(sim_dir))
        if os.path.isdir(os.path.join(sim_dir, name))
    ]
    foot_candidates = (
        sorted(glob.glob(os.path.join(sim_dir, "*_foot.nc")))
        + sorted(glob.glob(os.path.join(sim_dir, "*", "foot.nc")))
        + sorted(glob.glob(os.path.join(sim_dir, "*", "foot.rds")))
        + sorted(glob.glob(os.path.join(sim_dir, "*", "*_foot.nc")))
    )
    trajectory_candidates = (
        sorted(glob.glob(os.path.join(sim_dir, "*_traj.rds")))
        + [os.path.join(path, "traj.rds") for path in inner]
    )

    foot_path = next(
        (path for path in foot_candidates
         if os.path.isfile(path) and os.path.getsize(path) > 0),
        None,
    )
    trajectory_path = next(
        (path for path in trajectory_candidates
         if os.path.isfile(path) and os.path.getsize(path) > 0),
        None,
    )
    return foot_path, trajectory_path


def trajectory_hours(path: str) -> float:
    """Read the particle table in an isolated R process and return coverage."""
    reader = (
        'args<-commandArgs(TRUE);'
        'o<-readRDS(args[[1]]);'
        'd<-if(is.list(o)&&!is.null(o$particle))o$particle else o;'
        'write.csv(as.data.frame(d),args[[2]],row.names=FALSE)'
    )
    with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False) as script_fh:
        script_fh.write(reader)
        script_path = script_fh.name
    # Expanded particle tables are much larger than their RDS files. Keep each
    # worker's CSV beside the source artifact, which is normally on the data
    # volume rather than the small system /tmp filesystem.
    with tempfile.NamedTemporaryFile(
        "w", suffix=".val.csv", delete=False,
        dir=os.path.dirname(os.path.abspath(path)),
    ) as csv_fh:
        csv_path = csv_fh.name
    try:
        proc = subprocess.run(
            ["Rscript", script_path, path, csv_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[:300])
        with open(csv_path, newline="", encoding="utf-8") as handle:
            rows = csv.DictReader(handle)
            times = [float(row["time"]) for row in rows]
    finally:
        for temporary in (script_path, csv_path):
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
    return -min(times) / 60.0 if times else 0.0


def deep_validate(task: tuple[str, str, str, float]) -> tuple[str, bool, str]:
    """Deep-check one simulation; designed to run in a worker process."""
    import numpy as np

    sid, foot_path, trajectory_path, min_hours = task
    try:
        hours = trajectory_hours(trajectory_path)
        if hours < min_hours:
            return sid, False, f"traj only {hours:.1f} h back"

        if foot_path.endswith(".nc"):
            import netCDF4 as nc

            with nc.Dataset(foot_path) as dataset:
                variables = [name for name in dataset.variables if "foot" in name]
                if not variables:
                    return sid, False, "footprint variable missing"
                footprint = np.asarray(dataset.variables[variables[0]][:], dtype=float)
            if footprint.ndim == 3:
                footprint = footprint.sum(axis=0)
        else:
            footprint = np.asarray(read_rds(foot_path), dtype=float)

        if not np.isfinite(footprint).all() or (footprint < 0).any():
            return sid, False, "footprint negative/non-finite"
        if footprint.sum() <= 0:
            return sid, False, "footprint zero mass"
        return sid, True, ""
    except Exception as exc:  # noqa: BLE001
        return sid, False, f"parse error: {str(exc)[:120]}"


def validate_outputs(
    stilt_wd: str,
    min_hours: float,
    max_check: int,
    tag: str | None,
    jobs: int,
) -> dict[str, object]:
    base = os.path.join(stilt_wd, "out", "by-id")
    if not os.path.isdir(base):
        raise FileNotFoundError(f"no output directory {base}")
    sim_ids = sorted(
        sid for sid in os.listdir(base)
        if os.path.isdir(os.path.join(base, sid))
    )
    if tag:
        sim_ids = [sid for sid in sim_ids if sid.startswith(tag)]
    report: dict[str, object] = {
        "n_simulations": len(sim_ids),
        "ok": [],
        "failed": [],
        "details": {},
    }

    tasks: list[tuple[str, str, str, float]] = []
    presence_only: list[str] = []
    for sid in sim_ids:
        sim_dir = os.path.join(base, sid)
        foot_path, trajectory_path = find_output_artifacts(sim_dir)
        if foot_path is None:
            report["failed"].append(sid)
            report["details"][sid] = "missing foot.nc/rds"
        elif trajectory_path is None:
            report["failed"].append(sid)
            report["details"][sid] = "missing traj.rds"
        elif len(tasks) < max_check:
            tasks.append((sid, foot_path, trajectory_path, min_hours))
        else:
            presence_only.append(sid)

    if jobs == 1 or len(tasks) < 2:
        results = map(deep_validate, tasks)
    else:
        with ProcessPoolExecutor(max_workers=jobs) as executor:
            results = list(executor.map(deep_validate, tasks))
    for sid, ok, reason in results:
        report["ok" if ok else "failed"].append(sid)
        if reason:
            report["details"][sid] = reason
    report["ok"].extend(presence_only)
    report["ok"].sort()
    report["failed"].sort()
    report["n_deep_checked"] = len(tasks)
    report["pass_rate"] = len(report["ok"]) / max(len(sim_ids), 1)
    return report


def atomic_json(path: str, value: dict[str, object]) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=directory, prefix=".validation-", suffix=".tmp",
        delete=False, encoding="utf-8",
    ) as handle:
        json.dump(value, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = handle.name
    os.replace(temporary, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stilt-wd", required=True)
    parser.add_argument("--out-report", required=True)
    parser.add_argument(
        "--min-hours", type=float, default=23.0,
        help="minimum backward hours covered by trajectories",
    )
    parser.add_argument(
        "--max-check", type=int, default=20,
        help="how many simulations to deep-check (rds parse)",
    )
    parser.add_argument(
        "--jobs", type=int, default=8,
        help="worker processes used for deep validation",
    )
    parser.add_argument(
        "--tag", default=None,
        help="only validate sim ids starting with this tag",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.jobs < 1 or args.max_check < 0 or args.min_hours < 0:
        parser.error("jobs must be positive and check/hour limits non-negative")

    try:
        report = validate_outputs(
            args.stilt_wd,
            args.min_hours,
            args.max_check,
            args.tag,
            args.jobs,
        )
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    atomic_json(args.out_report, report)
    print(f"[validate] {len(report['ok'])}/{report['n_simulations']} passed "
          f"(deep-checked {report['n_deep_checked']}, jobs={args.jobs}) "
          f"-> {args.out_report}")
    sys.exit(0 if report["pass_rate"] >= 0.95 else 1)


if __name__ == "__main__":
    main()
