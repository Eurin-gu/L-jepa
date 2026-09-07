#!/usr/bin/env bash
set -x
cat > /root/legacy_ncp_po.py << "PYEOF"
import os, datetime, subprocess, io
GRIB="/root/era5_grib"; CFG="/root/work/hysplit_data2arl/hysplit_data2arl/era52arl/era52arl.cfg"; E52="/root/work/hysplit_data2arl/hysplit_data2arl/era52arl/era52arl"
SP="/root/work/footnet/stilt_pipeline"; REC="/mnt/d/lagrangian-jepa-cn/data/receptors_v2"
JOB = [
 ("ncp","north_china_plain","/root/era5_grib/north_china_plain_20170626","20170626"),
 ("po","po_valley_italy","/root/era5_grib/po_valley_italy_20171023","20171023"),
]
def split_from(combined, tag, days, suffix):
    import eccodes
    bufs = {}
    for d in days:
        k = d.strftime("%Y%m%d")
        bufs[k] = (os.path.join(GRIB, tag + "_" + k + suffix + ".grib"), io.BytesIO())
    with open(combined,"rb") as fh:
        while True:
            try: gid = eccodes.codes_grib_new_from_file(fh)
            except Exception as ex:
                if "End of resource" in str(ex) or "PrematureEnd" in str(ex): break
                raise
            if gid is None: break
            try:
                ds = eccodes.codes_get(gid,"dataDate")
                k = "%04d%02d%02d" % (ds//10000,(ds//100)%100,ds%100)
                if k in bufs: bufs[k][1].write(eccodes.codes_get_message(gid))
            finally: eccodes.codes_release(gid)
    for k,(p,b) in bufs.items():
        data = b.getvalue()
        if len(data) > 300000: open(p,"wb").write(data); print("split", p, len(data), flush=True)
        else: print("EMPTY", k, suffix, len(data), flush=True)
def convert(region, days):
    mdir = "/root/met_era5/" + region
    os.makedirs(mdir, exist_ok=True)
    for d in days:
        k = d.strftime("%Y%m%d")
        out = os.path.join(mdir, k)
        if os.path.exists(out) and os.path.getsize(out) > 100000: continue
        p = os.path.join(GRIB, "ncp" if region.startswith("north") else "po", "_") if False else None
        tag = "ncp" if region.startswith("north") else "po"
        p = os.path.join(GRIB, tag + "_" + k + "_p.grib"); s = os.path.join(GRIB, tag + "_" + k + "_s.grib")
        if not (os.path.exists(p) and os.path.exists(s)): print("missing", p, s, flush=True); continue
        r = subprocess.run([E52,"-d"+CFG,"-i"+p,"-a"+s,"-o"+out], capture_output=True, text=True)
        okc = os.path.exists(out) and os.path.getsize(out) > 100000
        print("convert", region, k, okc, flush=True)
        if not okc: print((r.stdout+r.stderr)[-400:], flush=True)
def batch(region, date, mdir):
    man = "/root/auto_run/manifest_%s_%s_p250.csv" % (region, date)
    if os.path.exists(man): print("skip batch", region, flush=True); return
    rec = os.path.join(REC, region, "receptors_%s_n120_maximin.csv" % date)
    cmd = ["/root/venvs/cds/bin/python","run_batch.py","--receptors",rec,"--stilt-wd","/root/work/stilt","--met",mdir,"--jobs","24","--numpar","250","--hours","24","--half-km","256","--res","0.04","--met-file-tres-hours","1","--tag","era5-%s-%s-p250"%(region,date),"--timeout","3600","--log-dir","/root/auto_run/logs_%s_%s"%(region,date),"--manifest",man]
    r = subprocess.run(cmd, cwd=SP, capture_output=True, text=True)
    print("batch", region, date, "rc", r.returncode, ((r.stdout or "")[-200:]).replace(chr(10)," | "), flush=True)
for tag, region, legacy, ds in JOB:
    d = datetime.datetime.strptime(ds,"%Y%m%d"); d0 = d - datetime.timedelta(days=1); days=[d0,d]
    lp = os.path.join(legacy,"DATA.GRIB"); ls = os.path.join(legacy,"SFC.GRIB")
    if not (os.path.exists(lp) and os.path.exists(ls)): print("legacy missing", legacy, flush=True); continue
    split_from(lp, tag, days, "_p")
    split_from(ls, tag, days, "_s")
    mdir = "/root/met_era5/" + region
    convert(region, days)
    batch(region, ds, mdir)
print("LEGACY NCP PO DONE", flush=True)
PYEOF
echo file ready