#!/usr/bin/env python3
"""Offline rebuild driver for the 2016-17 formal HRRR arm.

For every (role, date):
  1. asset preflight  (model_features npz present? date manifest present?
                       stilt by-id runs present?)
  2. date_manifest.build_date_manifest -> run_batch csv (maximin order)
  3. write npz feature descriptor json
  4. run assemble.py  -> D:\\lagrangian-jepa-cn\\data\\datasets\\
                         formal_hrrr_<role>\\<date>\\{x,y}.npy + meta.json
  5. run validate_dataset.py on the result and record a summary row
Finally merges the built train_p250 dates into
formal_hrrr_train_p250_all and validates the merge.

Formal-test roles are built/validated only (array construction); nothing
evaluates or consumes them.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
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
PY = "/root/venvs/cds/bin/python"


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def write_feature_descriptor(role, date):
    mf_dir = os.path.join(REUSE, "hrrr_stilt_production_v1", role, date,
                          "model_features")
    descriptor = {
        "date": date,
        "source_type": "npz_hrrr",
        "directory": mf_dir,
        "params": {"file_prefix": "a", "file_suffix": "_f00.npz"},
        "fields": ["U10M", "V10M", "PBLH", "PRSS"],
        "note": ("HRRR full-grid model features aYYYYMMDDHH_f00.npz "
                 "(1059x1799 float32, f00 analysis valid at the named hour)."),
    }
    path = os.path.join(BUILD, "features_{}_{}.json".format(role, date))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(descriptor, fh, indent=2)
    return path


def asset_state(role, date):
    """Return (ok, reason)."""
    mf_dir = os.path.join(REUSE, "hrrr_stilt_production_v1", role, date,
                          "model_features")
    npzs = []
    if os.path.isdir(mf_dir):
        npzs = sorted(n for n in os.listdir(mf_dir) if n.endswith(".npz"))
    if not npzs:
        return False, "model_features npz missing for " + date
    manifest = os.path.join(REUSE, "hrrr_stilt_production_v1", role, date,
                            "manifest.csv")
    if not os.path.isfile(manifest):
        return False, "date manifest.csv missing for " + date
    runs = os.listdir(BY_ID)
    prefix = "hrrr-analysis-" + date + "-"
    n_runs = sum(1 for n in runs if n.startswith(prefix))
    if n_runs == 0:
        return False, "no stilt by-id runs for " + date
    return True, "npz={} by-id-runs={}".format(len(npzs), n_runs)


def build_one(role, date, row):
    ok, reason = asset_state(role, date)
    row["asset_ok"] = ok
    row["asset_reason"] = reason
    if not ok:
        return False
    out_dir = os.path.join(DATASETS, "formal_hrrr_" + role, date)
    manifest_csv = os.path.join(BUILD, "manifests",
                                "{}_{}.csv".format(role, date))
    try:
        rep = DM.build_date_manifest(role, date, REUSE, RECEPTORS, BY_ID,
                                     manifest_csv)
    except Exception as exc:
        row["manifest_error"] = str(exc)
        return False
    row["manifest_report"] = rep
    if rep["matched"] != 120 or rep["out_rows"] != 120:
        row["manifest_error"] = ("matched={} out_rows={}".format(
            rep["matched"], rep["out_rows"]))
        return False
    if rep.get("mismatch"):
        row["manifest_error"] = "mismatches=" + json.dumps(rep["mismatch"])[:400]
        return False
    descriptor = write_feature_descriptor(role, date)
    cmd = [PY, os.path.join(BUILD, "assemble.py"),
           "--manifest", manifest_csv,
           "--features", descriptor,
           "--out", out_dir,
           "--footnet-root", FOOTNET]
    rc, so, se = run(cmd)
    if rc != 0:
        row["assemble_error"] = (se or so)[-1500:]
        return False
    rc, so, se = run([PY, os.path.join(BUILD, "validate_dataset.py"),
                      "--data", out_dir])
    row["validate_rc"] = rc
    row["validate_out"] = (so or se).strip().splitlines()
    if rc != 0:
        return False
    # parse shape/n lines from validate output
    row["built"] = True
    return True


def merge_train(dates_built):
    """Concatenate built train_p250 date dirs into formal_hrrr_train_p250_all."""
    import numpy as np

    out_dir = os.path.join(DATASETS, "formal_hrrr_train_p250_all")
    xs, ys, metas = [], [], []
    for date in dates_built:
        d = os.path.join(DATASETS, "formal_hrrr_train_p250", date)
        x = np.load(os.path.join(d, "x.npy"))
        y = np.load(os.path.join(d, "y.npy"))
        meta = json.load(open(os.path.join(d, "meta.json")))
        xs.append(x)
        ys.append(y)
        metas.append(meta)
    contract = metas[0]["contract"]
    for m in metas[1:]:
        assert m["contract"] == contract, "contracts differ across dates"
    X = np.concatenate(xs).astype(np.float32)
    Y = np.concatenate(ys).astype(np.float32)
    samples = []
    sources = []
    snapshots = set()
    n_skipped = 0
    for date, meta in zip(dates_built, metas):
        sources.append({"prefix": "formal_hrrr_train_p250/" + date,
                        "n": len(meta["samples"])})
        samples.extend(meta["samples"])
        snapshots.update(meta.get("snapshots") or [])
        n_skipped += meta.get("n_skipped") or 0

    def sha256_file(path):
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            while block := fh.read(16 * 1024 * 1024):
                digest.update(block)
        return digest.hexdigest()

    def fingerprint(value):
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    os.makedirs(out_dir, exist_ok=True)
    arrays = {}
    for suffix, arr in (("inputs", X), ("targets", Y)):
        path = os.path.join(out_dir,
                            "x.npy" if suffix == "inputs" else "y.npy")
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            np.save(fh, arr)
        os.replace(tmp, path)
        arrays[suffix] = {
            "path": os.path.abspath(path),
            "bytes": os.path.getsize(path),
            "sha256": sha256_file(path),
            "shape": list(arr.shape),
            "dtype": str(arr.dtype),
        }
    payload = {
        "n_samples": len(samples),
        "samples": samples,
        "snapshots": sorted(snapshots),
        "label_source": "stilt_xstilt",
        "arrays": arrays,
        "sources": sources,
        "n_skipped": n_skipped,
        "contract": contract,
        "contract_fingerprint": metas[0]["contract_fingerprint"],
        "merge_sha256": fingerprint(samples),
        "source_fingerprint": metas[0].get("source_fingerprint"),
    }
    meta_path = os.path.join(out_dir, "meta.json")
    tmp = meta_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True, allow_nan=False)
    os.replace(tmp, meta_path)
    return out_dir, payload["n_samples"], arrays


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=list(DM.ROLE_DATES) + ["all"],
                    default="all")
    ap.add_argument("--skip-merge", action="store_true")
    args = ap.parse_args()
    roles = list(DM.ROLE_DATES) if args.role == "all" else [args.role]
    rows = []
    for role in roles:
        for date in DM.ROLE_DATES[role]:
            row = {"role": role, "date": date, "built": False}
            build_one(role, date, row)
            rows.append(row)
            status = "OK" if row.get("built") else "FAIL"
            print("[{}] {} {} -> {}".format(role, date, status,
                                            row.get("asset_reason", "")))
    summary_path = os.path.join(BUILD, "arm_build_summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)
    # csv summary
    csv_path = os.path.join(BUILD, "arm_build_summary.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["role", "date", "built", "n",
                         "validate_rc", "asset_ok",
                         "asset_reason", "notes"])
        for row in rows:
            n = ""
            if row.get("built") and row.get("validate_out"):
                for line in row["validate_out"]:
                    if line.startswith("  x:"):
                        n = line.split("|")[0].split(":")[1].strip()
            notes = ""
            if row.get("manifest_error"):
                notes = "manifest_error: " + row["manifest_error"]
            elif row.get("assemble_error"):
                notes = "assemble_error: " + row["assemble_error"][:300]
            writer.writerow([row["role"], row["date"], row.get("built"),
                             n, row.get("validate_rc"),
                             row.get("asset_ok"),
                             row.get("asset_reason"), notes])
    print("summary written:", summary_path, csv_path)

    built_train = [r["date"] for r in rows
                   if r["role"] == "train_p250" and r.get("built")]
    if built_train and not args.skip_merge:
        out_dir, n, arrays = merge_train(built_train)
        print("merged train_p250 ->", out_dir, "n=", n)
        print(json.dumps(arrays, indent=2))
        rc, so, se = run([PY, os.path.join(BUILD, "validate_dataset.py"),
                          "--data", out_dir])
        print("merged validate rc", rc)
        print(so or se)
    elif not built_train:
        print("no train_p250 dates built; merge skipped")


if __name__ == "__main__":
    main()
