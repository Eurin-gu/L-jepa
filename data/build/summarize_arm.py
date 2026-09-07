#!/usr/bin/env python3
"""Summarize built formal_hrrr_* datasets (replica validator over each dir)."""
import csv, json, os, re, subprocess
BUILD = "/mnt/d/lagrangian-jepa-cn/data/build"
DATASETS = "/mnt/d/lagrangian-jepa-cn/data/datasets"
CDS = "/root/venvs/cds/bin/python"
roles = ["train_p250", "validation_p1000", "formal_test_p1000"]
dirs = []
for role in roles:
    base = os.path.join(DATASETS, "formal_hrrr_" + role)
    if not os.path.isdir(base):
        continue
    for d in sorted(os.listdir(base)):
        dd = os.path.join(base, d)
        if os.path.isfile(os.path.join(dd, "meta.json")):
            dirs.append((role, d, dd))
dirs.append(("train_p250_merged", "all",
             os.path.join(DATASETS, "formal_hrrr_train_p250_all")))
rows = []
for role, date, dd in dirs:
    proc = subprocess.run([CDS, os.path.join(BUILD, "validate_dataset.py"),
                           "--data", dd], capture_output=True, text=True)
    so = proc.stdout + proc.stderr
    row = {"role": role, "date": date, "rc": proc.returncode,
           "pass": proc.returncode == 0 and "load_dataset replica: PASS" in so}
    m = re.search(r"x:\s*\(([^)]*)\)\s*float32", so)
    if m:
        row["xshape"] = "(" + m.group(1) + ")"
    m = re.search(r"samples:\s*(\d+)", so)
    if m:
        row["n_samples"] = m.group(1)
    m = re.search(r"unique sim_ids:\s*(\d+)\s*\|\s*unique receptors:\s*(\d+)\s*\|\s*unique input/target pairs:\s*(\d+)", so)
    if not m:
        m = re.search(r"unique_sim_ids:\s*(\d+)[^0-9]+unique_receptors:\s*(\d+)[^0-9]+unique_input_target_pairs:\s*(\d+)", so)
    if m:
        row["unique"] = list(m.groups())
    m = re.search(r"inputs_sha256:\s*([0-9a-f]+)", so)
    if m:
        row["inputs_sha256"] = m.group(1)
    m = re.search(r"targets_sha256:\s*([0-9a-f]+)", so)
    if m:
        row["targets_sha256"] = m.group(1)
    m = re.search(r"coverage min/mean/max:\s*([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)", so)
    if m:
        row["coverage_mean"] = m.group(2)
    rows.append(row)
with open(os.path.join(BUILD, "arm_final_summary.json"), "w") as fh:
    json.dump(rows, fh, indent=2)
with open(os.path.join(BUILD, "arm_final_summary.csv"), "w", newline="") as fh:
    cols = ["role","date","pass","n_samples","xshape","unique",
            "inputs_sha256","targets_sha256","coverage_mean"]
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
print("written arm_final_summary.csv / .json")
