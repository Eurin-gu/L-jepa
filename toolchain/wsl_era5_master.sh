#!/usr/bin/env bash
set -x
cat > /root/era5_master.py << "PYEOF"
import cdsapi, os, datetime, subprocess, time, io
PLEVS=[1000,975,950,925,900,875,850,825,800,775,750,700,650,600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,10,7,5,3,2,1]
GRIB=/root/era5_grib
CFG="/root/work/hysplit_data2arl/hysplit_data2arl/era52arl/era52arl.cfg"
E52="/root/work/hysplit_data2arl/hysplit_data2arl/era52arl/era52arl"
def day_hrs(d): return ["%02d:00"%h for h in range(24)]
def fetch_combined(tag, area, days, suffix):
    out = "%s/%s_c%s.grib" % (GRIB, tag, suffix)
    if os.path.exists(out) and os.path.getsize(out) > 500000: return out
    kind = "p" if suffix=="_p" else "s"
    c = cdsapi.Client()
    req = {"product_type":"reanalysis","year":sorted({str(d.year) for d in days}),"month":sorted({("%02d"%d.month) for d in days}),"day":sorted({("%02d"%d.day) for d in days}),"time":day_hrs(days[0]),"area":area,"data_format":"grib","grid":[0.25,0.25]}
    if kind=="p":
        req["variable"]=["geopotential","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity","relative_humidity"]; req["pressure_level"]=PLEVS
        c.retrieve("reanalysis-era5-pressure-levels", req, out)
    else:
        req["variable"]=["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"]
        c.retrieve("reanalysis-era5-single-levels", req, out)
    print("fetched", out, flush=True)
    return out
def split_by_day(combined, tag, days):
    import eccodes
    outd = {}
    for d in days:
        k = d.strftime("%Y%m%d")
        outd[k] = "%s/%s_%s.grib" % (GRIB, tag, k)
    want = {k for k,p in outd.items() if not (os.path.exists(p) and os.path.getsize(p)>300000)}
    if not want: return outd
    bufs = {k: io.BytesIO() for k in want}
    with open(combined,"rb") as fh:
        while True:
            gid = eccodes.codes_grib_new_from_file(fh)
            if gid is None: break
            try:
                ds = eccodes.codes_get(gid,"dataDate")
                k = "%04d%02d%02d" % (ds//10000, (ds//100)%100, ds%100)
                if k in bufs: bufs[k].write(eccodes.codes_get_message(gid))
            finally:
                eccodes.codes_release(gid)
    for k,b in bufs.items():
        data = b.getvalue()
        if len(data) > 300000:
            open(outd[k],"wb").write(data)
            print("split", outd[k], len(data), flush=True)
        else: print("EMPTY split day", k, len(data), flush=True)
    return outd
def convert_day(day):
    out = "/root/met_era5/" + day
    if os.path.exists(out) and os.path.getsize(out) > 100000: return True
    p = "%s/%s_%s.grib" % (GRIB, tag, day)
    s = "%s/%s_%s.grib" % (GRIB, tag, day)
    if not (os.path.exists(p) and os.path.exists(s)): return False
    r = subprocess.run([E52,"-d"+CFG,"-i"+p,"-a"+s,"-o"+out], capture_output=True, text=True)
    ok = os.path.exists(out) and os.path.getsize(out) > 100000
    print("convert", day, "ok" if ok else ("FAIL "+r.stdout[-300:]+r.stderr[-300:]), flush=True)
    return ok
CONFIG = [
  ("po", "/root/era5_grib/po_valley_italy_20171023", [46.5,7.5,43.5,13.0], ["20171023"]),
  ("ncp", "/root/era5_grib/north_china_plain_20170626", [41.5,113.5,37.5,118.5], ["20170626"]),
]
for tag, legacy, area, dates in CONFIG:
    for ds in dates:
        d = datetime.datetime.strptime(ds, "%Y%m%d")
        d0 = d - datetime.timedelta(days=1)
        days = [d0, d]
        comb_p = None
        # prefer legacy combined from earlier fetch3
        if os.path.isdir(legacy):
            lp = os.path.join(legacy, "DATA.GRIB")
            ls = os.path.join(legacy, "SFC.GRIB")
            if os.path.exists(lp) and os.path.getsize(lp)>500000:
                dailyp = split_by_day(lp, tag, days)
                dailys = split_by_day(ls, tag, days)
            else:
                comb_p = fetch_combined(tag, area, days, "_p"); fetch_combined(tag, area, days, "_s")
                split_by_day(comb_p, tag, days)
        else:
            comb_p = fetch_combined(tag, area, days, "_p"); fetch_combined(tag, area, days, "_s")
            split_by_day(comb_p, tag, days)
        for dd in (d0, d):
            k = dd.strftime("%Y%m%d")
            convert_day(k)
        print("DONE date", tag, ds, flush=True)
print("MASTER PASS DONE", flush=True)
PYEOF
echo "installing eccodes python"
apt-get install -y python3-eccodes 2>&1 | tail -1
/root/venvs/cds/bin/pip install -q eccodes 2>&1 | tail -1 || true
/root/venvs/cds/bin/python /root/era5_master.py 2>&1 | tee /root/era5_master.log