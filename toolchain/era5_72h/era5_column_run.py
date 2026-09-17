# -*- coding: utf-8 -*-
"""Generate PBL column footprints: 11 po dates x 120 receptors x 5 heights.

Height set {5,100,300,800,1500} m covers the PBL (measured PBL top 250-1885 m
on 20171023); >1500 m gives foot=0 under a 24 h back-run because those
particles never touch the surface (verified experimentally).

Each (receptor, height) is a separate STILT run: this engine's HYSPLIT mass
allocation fails for multi-receptor CONTROL files (foot column comes back all
zeros), so heights cannot be combined in one simulation.
"""
import csv, os, subprocess, time, datetime

REC_DIR = "/mnt/d/lagrangian-jepa-cn/data/receptors_v2/po_valley_italy"
DATES = ["20150211","20150721","20150813","20160115","20160221","20160714",
         "20160909","20170101","20170327","20170421","20171023"]
HEIGHTS = [5, 100, 300, 800, 1500]
PY = "/root/venvs/cds/bin/python"
RUNNER = "/root/work/footnet/stilt_pipeline/run_batch.py"
AR = "/root/auto_run"
STILT_WD = "/root/work/stilt"
MET = "/root/met_era5/po_valley_italy"

def build_table(date):
    src = os.path.join(REC_DIR, "receptors_%s_n120_maximin.csv" % date)
    rows = list(csv.DictReader(open(src)))
    out = "/root/colrec_%s.csv" % date
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["run_time", "lati", "long", "zagl"])
        for r in rows:
            for z in HEIGHTS:
                w.writerow([r["run_time"], r["lati"], r["long"], z])
    return out, len(rows) * len(HEIGHTS)

def main():
    print("COLUMN RUN START", datetime.datetime.now().isoformat(), flush=True)
    for date in DATES:
        man = os.path.join(AR, "colmanifest_po_%s_p250.csv" % date)
        if os.path.exists(man) and sum(1 for _ in open(man)) > 600:
            print("[%s] already done (%d rows), skip" % (date, sum(1 for _ in open(man)) - 1), flush=True)
            continue
        table, nrows = build_table(date)
        log = os.path.join(AR, "colrun_po_%s.out" % date)
        cmd = [PY, RUNNER, "--receptors", table, "--stilt-wd", STILT_WD,
               "--met", MET, "--jobs", "4", "--numpar", "250", "--hours", "24",
               "--half-km", "256", "--res", "0.04", "--met-file-tres-hours", "1",
               "--tag", "colera5-po-%s-p250" % date, "--timeout", "3600",
               "--log-dir", os.path.join(AR, "elogs_col_po"), "--manifest", man]
        t0 = time.time()
        with open(log, "w") as fh:
            r = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT)
        n = 0
        if os.path.exists(man):
            n = max(0, sum(1 for _ in open(man)) - 1)
        print("[%s] receptors=%d sims rc=%d manifest_rows=%d elapsed=%.0fs"
              % (date, nrows, r.returncode, n, time.time() - t0), flush=True)
    print("COLUMN RUN DONE", datetime.datetime.now().isoformat(), flush=True)

if __name__ == "__main__":
    main()
