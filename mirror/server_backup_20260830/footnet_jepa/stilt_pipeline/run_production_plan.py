#!/usr/bin/env python3
"""Run resumable HRRR/STILT role queues from a frozen production plan."""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading


UTC = dt.timezone.utc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, prefix=f".{path.name}-", suffix=".tmp",
        delete=False, encoding="utf-8",
    ) as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = handle.name
    os.replace(temporary, path)


def load_and_validate_plan(plan_path: Path, receptor_dir: Path) -> dict:
    with open(plan_path, encoding="utf-8") as handle:
        plan = json.load(handle)
    if plan.get("schema_version") != 1:
        raise ValueError("unsupported production plan schema")
    if plan.get("status") != "roles_frozen_before_label_production":
        raise ValueError("production roles are not frozen")
    roles = plan.get("roles")
    if not isinstance(roles, dict) or set(roles) != {
            "train", "validation", "formal_test"}:
        raise ValueError("production plan must define the three strict roles")
    role_dates = {role: set(value.get("dates", []))
                  for role, value in roles.items()}
    if any(role_dates[left] & role_dates[right]
           for left, right in (("train", "validation"),
                               ("train", "formal_test"),
                               ("validation", "formal_test"))):
        raise ValueError("production role dates overlap")
    all_dates = set().union(*role_dates.values())
    if all_dates != set(plan.get("receptors", {})):
        raise ValueError("role dates do not exactly cover receptor records")
    if len(role_dates["formal_test"]) < 5 \
            or not roles["formal_test"].get("untouched"):
        raise ValueError("formal test must contain at least five untouched dates")
    if set(plan.get("fidelity_calibration", {}).get("dates", [])) \
            - role_dates["train"]:
        raise ValueError("fidelity calibration dates must be training dates")

    expected_total = 0
    for role, value in roles.items():
        particles = value.get("particles")
        expected = len(value.get("dates", [])) * 120
        if not isinstance(particles, int) or particles < 1:
            raise ValueError(f"invalid particle count for {role}")
        if value.get("expected_unique_labels") != expected:
            raise ValueError(f"incorrect expected label count for {role}")
        expected_total += expected
    if plan.get("expected_unique_main_labels") != expected_total:
        raise ValueError("incorrect total expected label count")

    for date, record in plan["receptors"].items():
        csv_path = receptor_dir / record["csv"]
        provenance_path = csv_path.with_suffix(".provenance.json")
        if sha256_file(csv_path) != record.get("csv_sha256"):
            raise ValueError(f"receptor CSV hash mismatch for {date}")
        if sha256_file(provenance_path) != record.get("provenance_sha256"):
            raise ValueError(f"receptor provenance hash mismatch for {date}")
    return plan


def scheduler_command(
    role: str,
    plan: dict,
    plan_path: Path,
    receptor_dir: Path,
    scheduler: Path,
    root: Path,
    stilt_wd: Path,
) -> list[str]:
    role_plan = plan["roles"][role]
    settings = plan["scheduler"]
    receptor_paths = [
        str(receptor_dir / plan["receptors"][date]["csv"])
        for date in role_plan["dates"]
    ]
    return [
        sys.executable,
        str(scheduler),
        "--receptors", *receptor_paths,
        "--dates", *role_plan["dates"],
        "--root", str(root / f"{role}_p{role_plan['particles']}"),
        "--stilt-wd", str(stilt_wd),
        "--download-mode", settings["download_mode"],
        "--meteorology-strategy", plan["meteorology"]["strategy"],
        "--hrrr-base-url", settings["hrrr_base_url"],
        "--hour-workers", str(settings["hour_workers"]),
        "--range-jobs", str(settings["range_jobs"]),
        "--download-timeout", str(settings.get("download_timeout", 180)),
        "--download-retries", str(settings.get("download_retries", 8)),
        "--stilt-jobs", str(settings["stilt_jobs"]),
        "--validation-jobs", str(settings["validation_jobs"]),
        "--numpar", str(role_plan["particles"]),
        "--hours", str(plan["meteorology"]["backtrack_hours"]),
        "--retention", plan["meteorology"]["retention"],
        "--min-free-gib", str(settings["min_free_gib"]),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--receptor-dir", required=True)
    parser.add_argument("--scheduler", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--stilt-wd", required=True)
    parser.add_argument(
        "--roles", default="train,validation,formal_test",
        help="comma-separated subset of train,validation,formal_test",
    )
    parser.add_argument("--role-workers", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.role_workers < 1:
        parser.error("--role-workers must be positive")

    plan_path = Path(args.plan).resolve()
    receptor_dir = Path(args.receptor_dir).resolve()
    scheduler = Path(args.scheduler).resolve()
    root = Path(args.root).resolve()
    stilt_wd = Path(args.stilt_wd).resolve()
    plan = load_and_validate_plan(plan_path, receptor_dir)
    roles = [role for role in args.roles.split(",") if role]
    if not roles or len(roles) != len(set(roles)) \
            or set(roles) - set(plan["roles"]):
        parser.error("--roles must contain unique production roles")
    commands = {
        role: scheduler_command(
            role, plan, plan_path, receptor_dir, scheduler, root, stilt_wd)
        for role in roles
    }
    if args.dry_run:
        print(json.dumps(commands, indent=2))
        return

    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".orchestrator.lock"
    with open(lock_path, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SystemExit("production orchestrator is already running") from exc

        state_path = root / "orchestrator_state.json"
        state = {
            "status": "running",
            "started_at": dt.datetime.now(UTC).isoformat(),
            "plan": str(plan_path),
            "plan_sha256": sha256_file(plan_path),
            "roles": {role: {"status": "pending"} for role in roles},
        }
        state_lock = threading.Lock()
        atomic_json(state_path, state)

        def run_role(role: str) -> int:
            log_path = root / f"{role}.log"
            with open(log_path, "a", encoding="utf-8") as log:
                process = subprocess.Popen(
                    commands[role], stdout=log, stderr=subprocess.STDOUT,
                    text=True,
                )
                with state_lock:
                    state["roles"][role] = {
                        "status": "running",
                        "pid": process.pid,
                        "command": commands[role],
                        "log": str(log_path),
                        "started_at": dt.datetime.now(UTC).isoformat(),
                    }
                    atomic_json(state_path, state)
                return_code = process.wait()
            with state_lock:
                state["roles"][role].update({
                    "status": "complete" if return_code == 0 else "failed",
                    "return_code": return_code,
                    "finished_at": dt.datetime.now(UTC).isoformat(),
                })
                atomic_json(state_path, state)
            return return_code

        with concurrent.futures.ThreadPoolExecutor(
                max_workers=args.role_workers) as executor:
            futures = {executor.submit(run_role, role): role for role in roles}
            return_codes = {
                futures[future]: future.result()
                for future in concurrent.futures.as_completed(futures)
            }
        state["status"] = (
            "complete" if all(code == 0 for code in return_codes.values())
            else "failed"
        )
        state["finished_at"] = dt.datetime.now(UTC).isoformat()
        atomic_json(state_path, state)
        if state["status"] != "complete":
            raise SystemExit("one or more production roles failed; see orchestrator state")


if __name__ == "__main__":
    main()
