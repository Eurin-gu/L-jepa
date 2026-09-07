"""Download HRRR grib2 analysis snapshots and convert them to HRRR-lite .nc.

The FootNet data contract consumes `hysplit.<YYYYMMDD>.<HH>z.nc` files with
variables U10M, V10M, PBLH, PRSS on the native HRRR Lambert-conformal grid.
This script reproduces those files for arbitrary dates so the dataset can be
expanded beyond Apr 1-2 / Jul 4-5.

Source : AWS Open Data (noaa-hrrr-bdp-pds), downloaded through a local proxy
         (NOAA READY throttles CN links but S3 does not).
Output : same layout as socal_pilot/data/HRRR_lite/<year>/hysplit.*.nc

Usage:
    python3 fetch_hrrr.py --dates 20240701 20240702 --hours 0 6 12 18 \
        --out-dir /media/ubuntu22/YUYING/HRRR_lite/2024 \
        [--proxy http://127.0.0.1:7897]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np


def download_grib(date: str, hour: int, out_path: str, proxy: str | None):
    url = (f"https://noaa-hrrr-bdp-pds.s3.amazonaws.com/"
           f"hrrr.{date}/conus/hrrr.t{hour:02d}z.wrfsfcf00.grib2")
    cmd = ["aria2c", "-x", "8", "-s", "8", "-k", "1M",
           "--file-allocation=none", "--console-log-level=warn",
           "--summary-interval=0", "--max-tries=10", "--retry-wait=5",
           "--continue=true", "-d", os.path.dirname(out_path),
           "-o", os.path.basename(out_path) + ".grib2"]
    if proxy:
        cmd.append(f"--all-proxy={proxy}")
    cmd.append(url)
    print(f"[hrrr] downloading {url}", flush=True)
    subprocess.run(cmd, check=True)
    return out_path + ".grib2"


def convert_grib(grib_path: str, out_nc: str):
    """Extract U10M/V10M/PBLH/PRSS -> hysplit-style lite NetCDF.

    HRRR conus wrfsfc files group variables by typeOfLevel, which cfgrib
    refuses to open in one dataset; use one handle per group.
    """
    import xarray as xr

    bk = {"indexpath": ""}
    ds10 = xr.open_dataset(grib_path, engine="cfgrib", backend_kwargs={
        **bk, "filter_by_keys": {"typeOfLevel": "heightAboveGround",
                                 "level": 10}})
    dss = xr.open_dataset(grib_path, engine="cfgrib", backend_kwargs={
        **bk, "filter_by_keys": {"typeOfLevel": "surface",
                                 "stepType": "instant"}})

    def to_2d(a):
        arr = np.asarray(a.values, dtype=np.float32)
        if arr.ndim == 3:
            arr = arr[0]
        return arr

    fields = {"U10M": to_2d(ds10["u10"]), "V10M": to_2d(ds10["v10"]),
              "PBLH": to_2d(dss["blh"] if "blh" in dss else dss["hpbl"]), "PRSS": to_2d(dss["sp"])}

    import netCDF4 as nc
    tmp = out_nc + ".tmp"
    with nc.Dataset(tmp, "w") as out:
        ny, nx = fields["U10M"].shape
        out.createDimension("y", ny)
        out.createDimension("x", nx)
        for name, arr in fields.items():
            var = out.createVariable(name, "f4", ("y", "x"),
                                     zlib=True, complevel=1)
            var[:] = arr
    os.replace(tmp, out_nc)
    ds10.close()
    dss.close()
    print(f"[hrrr] wrote {out_nc}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", nargs="+", required=True,
                    help="YYYYMMDD list")
    ap.add_argument("--hours", nargs="+", type=int, default=[0, 6, 12, 18])
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--proxy", default="http://127.0.0.1:7897")
    ap.add_argument("--keep-grib", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    failures = []
    for date in args.dates:
        for hour in args.hours:
            stem = f"hysplit.{date}.{hour:02d}z"
            out_nc = os.path.join(args.out_dir, stem + ".nc")
            if os.path.exists(out_nc) and os.path.getsize(out_nc) > 1e6:
                print(f"[hrrr] skip existing {stem}")
                continue
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    stem_path = os.path.join(tmp, stem)
                    grib = download_grib(date, hour, stem_path, args.proxy)
                    convert_grib(grib, out_nc)
            except Exception as exc:                      # noqa: BLE001
                print(f"[hrrr] FAILED {stem}: {exc}", flush=True)
                failures.append(stem)
    if failures:
        print(f"[hrrr] {len(failures)} failures: {failures}")
        sys.exit(1)
    print("[hrrr] all done")


if __name__ == "__main__":
    main()
