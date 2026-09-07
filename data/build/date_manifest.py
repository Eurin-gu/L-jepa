#!/usr/bin/env python3
"""Build run_batch-format CSVs for the 2016-17 formal HRRR arm from local assets.

Source of truth per date:
  * receptor list / order : D:\\footexp_data\\stilt_receptors_v1\\
                            receptors_<date>_n120_maximin.csv
                            (columns run_time,lati,long,zagl; order = maximin)
  * per-receptor sim rows : <reuse>/hrrr_stilt_production_v1/<role>/<date>/
                            manifest.csv (run_batch format, sim_id + original
                            /root/autodl-tmp/... foot/traj paths)
  * label files            : <reuse>/stilt/out/by-id/<sim_id>/<sim_id>_foot.nc
                            (+ _traj.rds)

Rows are emitted in the receptors-v1 (maximin) order.  Every receptor is
matched to its sim_id via 5-decimal lat/lon; run_time, zagl and the local
foot.nc/traj.rds existence are verified (foot.nc geographic anchoring is
checked against the CSV coordinate as an extra guard).  Mismatches are
reported, never silently fixed.
"""
from __future__ import annotations

import argparse
import csv
import json
import os

import netCDF4 as nc

ROLE_DATES = {
    "train_p250": ["20160428", "20160523", "20160615", "20160901",
                   "20161021", "20170314", "20170429", "20170611",
                   "20170720", "20171006", "20171118"],
    "validation_p1000": ["20160715", "20170517"],
    "formal_test_p1000": ["20160318", "20160802", "20161111", "20170116",
                          "20170922"],
}


def norm_path(path):
    if path.startswith("/"):
        return path
    drive = path[0].upper()
    rest = path[2:].replace("\\", "/")
    return "/mnt/" + drive.lower() + rest


def read_csv_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def fmt5(value):
    return "{:.5f}".format(float(value))


def build_date_manifest(role, date, reuse_root, receptors_root, by_id_root,
                        out_csv):
    manifest_csv = os.path.join(reuse_root, "hrrr_stilt_production_v1",
                                role, date, "manifest.csv")
    receptor_csv = os.path.join(receptors_root,
                                "receptors_{}_n120_maximin.csv".format(date))
    if not os.path.isfile(manifest_csv):
        raise FileNotFoundError("date manifest.csv missing: " + manifest_csv)
    if not os.path.isfile(receptor_csv):
        raise FileNotFoundError("receptor csv missing: " + receptor_csv)

    manifest_rows = read_csv_rows(manifest_csv)
    receptor_rows = read_csv_rows(receptor_csv)
    report = {
        "role": role, "date": date,
        "manifest_rows": len(manifest_rows),
        "receptor_rows": len(receptor_rows),
        "matched": 0, "mismatch": [], "missing_local_files": [],
    }

    by_latlon = {}
    dup = []
    for row in manifest_rows:
        key = (fmt5(row["lati"]), fmt5(row["long"]))
        if key in by_latlon:
            dup.append(key)
        by_latlon[key] = row
    if dup:
        report["duplicate_manifest_latlon"] = dup

    out_rows = []
    for index, rec in enumerate(receptor_rows):
        key = (fmt5(rec["lati"]), fmt5(rec["long"]))
        row = by_latlon.get(key)
        if row is None:
            report["mismatch"].append(
                {"index": index, "issue": "receptor not in date manifest",
                 "receptor": rec})
            continue
        if row["run_time"] != rec["run_time"]:
            report["mismatch"].append(
                {"index": index, "sim_id": row["sim_id"], "issue": "run_time differs",
                 "manifest_run_time": row["run_time"],
                 "receptor_run_time": rec["run_time"]})
        if row["zagl"] != rec["zagl"]:
            report["mismatch"].append(
                {"index": index, "sim_id": row["sim_id"], "issue": "zagl differs",
                 "manifest_zagl": row["zagl"], "receptor_zagl": rec["zagl"]})

        sim_id = row["sim_id"]
        sim_dir = os.path.join(by_id_root, sim_id)
        foot_nc = os.path.join(sim_dir, sim_id + "_foot.nc")
        traj_rds = os.path.join(sim_dir, sim_id + "_traj.rds")
        if not (os.path.isfile(foot_nc) and os.path.isfile(traj_rds)):
            report["missing_local_files"].append(
                {"index": index, "sim_id": sim_id,
                 "foot": os.path.isfile(foot_nc),
                 "traj": os.path.isfile(traj_rds)})
            report["mismatch"].append(
                {"index": index, "sim_id": sim_id,
                 "issue": "local by-id files missing"})
            continue

        # Extra guard: foot.nc grid must be anchored on the CSV receptor.
        try:
            with nc.Dataset(foot_nc) as ds:
                lat = [float(v) for v in ds.variables["lat"][:]]
                lon = [float(v) for v in ds.variables["lon"][:]]
            lat_c = (lat[0] + lat[-1]) / 2.0
            lon_c = (lon[0] + lon[-1]) / 2.0
            if (abs(lat_c - float(rec["lati"])) > 0.06
                    or abs(lon_c - float(rec["long"])) > 0.08):
                report["mismatch"].append(
                    {"index": index, "sim_id": sim_id,
                     "issue": "foot.nc not anchored on receptor",
                     "foot_centre": [lat_c, lon_c],
                     "receptor": [rec["lati"], rec["long"]]})
        except Exception as exc:
            report["mismatch"].append(
                {"index": index, "sim_id": sim_id,
                 "issue": "foot.nc read failed: " + str(exc)})

        out_rows.append({
            "sim_id": sim_id, "run_time": row["run_time"],
            "lati": row["lati"], "long": row["long"], "zagl": row["zagl"],
            "foot_nc": foot_nc, "traj_rds": traj_rds,
        })
        report["matched"] += 1

    report["out_rows"] = len(out_rows)
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["sim_id", "run_time", "lati", "long", "zagl",
                            "foot_nc", "traj_rds"])
        writer.writeheader()
        writer.writerows(out_rows)
    report["out_csv"] = out_csv
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=sorted(ROLE_DATES), required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--reuse-root", default="/mnt/d/lagrangian-jepa-cn/reuse_stilt/server_backup_20260830")
    ap.add_argument("--receptors-root", default="/mnt/d/footexp_data/stilt_receptors_v1")
    ap.add_argument("--by-id-root", default="/mnt/d/lagrangian-jepa-cn/reuse_stilt/server_backup_20260830/stilt/out/by-id")
    ap.add_argument("--out-csv", required=True)
    args = ap.parse_args()
    report = build_date_manifest(
        args.role, args.date,
        norm_path(args.reuse_root), norm_path(args.receptors_root),
        norm_path(args.by_id_root), norm_path(args.out_csv))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
