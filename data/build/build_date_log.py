#!/usr/bin/env python3
"""Idempotent per-date build + log + validation.

Usage: build_date_log.py --role <role> --date <YYYYMMDD>
Re-runs assemble.py for the date (overwrites x/y/meta deterministically),
then validate_dataset.py (cds venv) and train_stilt_strict.load_dataset
(ml venv, real project code) and writes D:\\...\\data\\build\\build_<date>.log.
Exit 0 only when everything passes.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import date_manifest as DM

BUILD = "/mnt/d/lagrangian-jepa-cn/data/build"
REUSE = "/mnt/d/lagrangian-jepa-cn/reuse_stilt/server_backup_20260830"
RECEPTORS = "/mnt/d/footexp_data/stilt_receptors_v1"
BY_ID = REUSE + "/stilt/out/by-id"
DATASETS = "/mnt/d/lagrangian-jepa-cn/data/datasets"
FOOTNET = ("/mnt/d/lagrangian-jepa-cn/mirror/server_backup_20260830/"
           "footnet_jepa")
CDS_PY = "/root/venvs/cds/bin/python"
ML_PY = "/root/venvs/ml/bin/python"
RUNNER = ("/mnt/d/lagrangian-jepa-cn/data/build/"
          "run_real_load_dataset.py")


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=list(DM.ROLE_DATES), required=True)
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    role, date = args.role, args.date
    log_path = os.path.join(BUILD, "build_{}.log".format(date))
    lines = []
    def log(msg):
        lines.append(msg)
        print(msg)

    log("# build_date_log {} role={}".format(date, role))
    # 1. manifest
    manifest_csv = os.path.join(BUILD, "manifests", "{}_{}.csv".format(role, date))
    try:
        rep = DM.build_date_manifest(role, date, REUSE, RECEPTORS, BY_ID,
                                     manifest_csv)
    except Exception as exc:
        log("[manifest] SKIPPED {}: {}".format(date, exc))
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return 2
    log("[manifest] rows={} matched={} mismatch={} missing_local={}".format(
        rep["out_rows"], rep["matched"], len(rep.get("mismatch") or []),
        len(rep.get("missing_local_files") or [])))
    if rep.get("mismatch"):
        log("[manifest] MISMATCHES: " + json.dumps(rep["mismatch"], indent=1)[:2000])
    # 2. feature descriptor
    desc_path = os.path.join(BUILD, "features_{}_{}.json".format(role, date))
    with open(desc_path, "w", encoding="utf-8") as fh:
        json.dump({"date": date, "source_type": "npz_hrrr",
                   "directory": os.path.join(REUSE, "hrrr_stilt_production_v1",
                                             role, date, "model_features"),
                   "params": {"file_prefix": "a", "file_suffix": "_f00.npz"},
                   "fields": ["U10M", "V10M", "PBLH", "PRSS"]}, fh, indent=2)
    # 3. assemble
    out_dir = os.path.join(DATASETS, "formal_hrrr_" + role, date)
    rc, so, se = run([CDS_PY, os.path.join(BUILD, "assemble.py"),
                      "--manifest", manifest_csv, "--features", desc_path,
                      "--out", out_dir, "--footnet-root", FOOTNET])
    log("[assemble] rc={}".format(rc))
    for line in (so + "\n" + se).splitlines():
        log("  " + line)
    if rc != 0:
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return 1
    # 4. replica validator
    rc, so, se = run([CDS_PY, os.path.join(BUILD, "validate_dataset.py"),
                      "--data", out_dir])
    log("[validate_dataset.py] rc={}".format(rc))
    for line in (so + "\n" + se).splitlines():
        log("  " + line)
    if rc != 0:
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return 1
    # 5. real project load_dataset (torch venv)
    run_script = os.path.join(BUILD, "run_real_load_dataset.py")
    rc, so, se = run([ML_PY, run_script, "--data", out_dir])
    log("[train_stilt_strict.load_dataset] rc={}".format(rc))
    for line in (so + "\n" + se).splitlines():
        log("  " + line)
    if rc != 0:
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return 1
    log("ALL CHECKS PASSED")
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("log written:", log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
