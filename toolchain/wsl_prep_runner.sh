#!/usr/bin/env bash
set -x
rm -f /root/met_era5/* /root/met_era5/*/* 2>/dev/null
rm -f /root/auto_run/manifest_*_p250.csv 2>/dev/null
cat > /root/runner_final.py << "PYEOF"
import cdsapi, os, datetime, subprocess, io
PLEVS = [1000,975,950,925,900,875,850,825,800,775,750,700,650,600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,10,7,5,3,2,1]
GRIB="/root/era5_grib"; CFG="/root/work/hysplit_data2arl/hysplit_data2arl/era52arl/era52arl.cfg"; E52="/root/work/hysplit_data2arl/hysplit_data2arl/era52arl/era52arl"
SP="/root/work/footnet/stilt_pipeline"; REC="/mnt/d/lagrangian-jepa-cn/data/receptors_v2"
REGIONS = {
 "ncp": ("north_china_plain", [41.5,113.5,37.5,118.5], ["20170626"]),
 "po": ("po_valley_italy", [46.5,7.5,43.5,13.0], ["20171023"]),
 "so": ("so_cal_LA_basin", [35.0,-119.0,31.5,-115.5], ["20150102","20150807","20160217","20160318","20160807","20171111"]),
 "cv": ("cent_valley_CA", [40.5,-123.0,34.0,-117.5], ["20150111","20150722","20160222","20160908","20170522","20171118"]),
 "tx": ("permian_westTX", [34.0,-105.0,29.5,-99.5], ["20150128","20151013","20160319","20160904","20170308","20171016"]),
 "cf": ("co_front_range", [41.5,-107.0,37.5,-103.0], ["20150128","20150911","20160422","20161123","20170612"]),
}
def fetch_combined(tag, area, days):
    for suffix, kind, dsname, var, lev in [
        ("_p","p","reanalysis-era5-pressure-levels",["geopotential","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity","relative_humidity"],PLEVS),
        ("_s","s","reanalysis-era5-single-levels",["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"],None),
    ]:
        out = os.path.join(GRIB, tag + "_c" + suffix + ".grib")
        if not (os.path.exists(out) and os.path.getsize(out) > 500000):
            c = cdsapi.Client()
            req = {"product_type":"reanalysis","year":sorted({str(d.year) for d in days}),"month":sorted({("%02d"%d.month) for d in days}),"day":sorted({("%02d"%d.day) for d in days}),"time":["%02d:00"%h for h in range(24)],"area":area,"data_format":"grib","grid":[0.25,0.25],"variable":var}
            if lev: req["pressure_level"] = lev
            c.retrieve(dsname, req, out)
            print("fetched", out, flush=True)
def split_days(tag, days, suffix):
    import eccodes
    combined = os.path.join(GRIB, tag + "_c" + suffix + ".grib")
    if not (os.path.exists(combined) and os.path.getsize(combined) > 500000):
        print("missing combined", combined, flush=True); return False
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
        if len(data) > 300000:
            open(p,"wb").write(data); print("split", p, len(data), flush=True)
        else: print("EMPTY", k, suffix, len(data), flush=True)
    return True
def convert(tag, region, days):
    mdir = "/root/met_era5/" + region
    os.makedirs(mdir, exist_ok=True)
    okall = True
    for d in days:
        k = d.strftime("%Y%m%d")
        out = os.path.join(mdir, k)
        if os.path.exists(out) and os.path.getsize(out) > 100000: continue
        p = os.path.join(GRIB, tag + "_" + k + "_p.grib"); s = os.path.join(GRIB, tag + "_" + k + "_s.grib")
        if not (os.path.exists(p) and os.path.exists(s)): okall = False; continue
        r = subprocess.run([E52,"-d"+CFG,"-i"+p,"-a"+s,"-o"+out], capture_output=True, text=True)
        okc = os.path.exists(out) and os.path.getsize(out) > 100000
        print("convert", region, k, okc, flush=True)
        if not okc: okall = False
    return okall
def batch(region, date, mdir):
    man = "/root/auto_run/manifest_%s_%s_p250.csv" % (region, date)
    if os.path.exists(man): print("skip batch", region, date, flush=True); return
    rec = os.path.join(REC, region, "receptors_%s_n120_maximin.csv" % date)
    if not os.path.exists(rec): print("no receptors", rec, flush=True); return
    cmd = ["/root/venvs/cds/bin/python","run_batch.py","--receptors",rec,"--stilt-wd","/root/work/stilt","--met",mdir,"--jobs","24","--numpar","250","--hours","24","--half-km","256","--res","0.04","--met-file-tres-hours","1","--tag","era5-%s-%s-p250"%(region,date),"--timeout","3600","--log-dir","/root/auto_run/logs_%s_%s"%(region,date),"--manifest",man]
    r = subprocess.run(cmd, cwd=SP, capture_output=True, text=True)
    t = ((r.stdout or "")[-300:] + (r.stderr or "")[-300:]).replace(chr(10)," | ")
    print("batch", region, date, "rc", r.returncode, t[-280:], flush=True)
for tag,(region, area, dates) in REGIONS.items():
    for ds in dates:
        d = datetime.datetime.strptime(ds,"%Y%m%d"); d0 = d - datetime.timedelta(days=1); days = [d0, d]
        mdir = "/root/met_era5/" + region
        man = "/root/auto_run/manifest_%s_%s_p250.csv" % (region, ds)
        both = all(os.path.exists(os.path.join(mdir, dd.strftime("%Y%m%d"))) for dd in days)
        if both and os.path.exists(man): print("skip done", region, ds, flush=True); continue
        print("PROCESS", region, ds, flush=True)
        fetch_combined(tag, area, days)
        split_days(tag, days, "_p"); split_days(tag, days, "_s")
        if convert(tag, region, days): batch(region, ds, mdir)
        print("DONE", region, ds, flush=True)
print("RUNNER FINAL DONE", flush=True)
PYEOF
wsl_touch=1