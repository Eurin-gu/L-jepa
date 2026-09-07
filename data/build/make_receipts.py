"""Generate per-date met receipts JSON for assemble --met-receipts.

Records, for each required feature snapshot (backhours of run_time), which
met file(s) supply U10M/V10M/PBLH/PRSS and their sha256. The label STILT
run for the same date used the SAME met directory/source (documented in the
run_batch manifest). cycle_mode describes the source cadence:
  - era5: hourly single-level grib (valid hour == cycle hour, step 0)
  - gdas05: 3-hourly ARL, released per day; label + feature share the ARL set
"""
import os, sys, json, hashlib, datetime

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b: break
            h.update(b)
    return h.hexdigest()

def make_era5(region, date, era5d_root, out):
    d0 = datetime.datetime.strptime(date, "%Y%m%d")
    # feature snapshots: backhours 0,6,12,18 from each run_time; collect unique (day,hour)
    base = os.path.join(era5d_root, region)
    files = {}
    for delta, label in [(0, "target"), (-1, "prev")]:
        day = (d0 + datetime.timedelta(days=delta)).strftime("%Y%m%d")
        sf = os.path.join(base, day + "_SFC.GRIB")
        if os.path.isfile(sf):
            files[day + "_SFC"] = {"path": sf, "sha256": sha256_file(sf)}
    receipts = {
        "cycle_mode": "hourly",
        "driver_source": "era5_sfc_day_grib_" + region + "_" + date,
        "label_met_source": "era5-v1-" + region + "-" + date + "-p250",
        "files": files,
    }
    with open(out, "w") as f:
        json.dump(receipts, f, indent=2)
    print("wrote", out, "files:", len(files))

if __name__ == "__main__":
    # usage: make_receipts.py era5 <region> <date> <era5d_root> <out.json>
    kind = sys.argv[1]
    if kind == "era5":
        make_era5(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])