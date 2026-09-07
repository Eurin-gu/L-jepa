#!/usr/bin/env bash
set -x
cat > /root/era5_po_fix.py << "PYEOF"
import cdsapi, os, datetime, subprocess, io
PLEVS = [1000,975,950,925,900,875,850,825,800,775,750,700,650,600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,10,7,5,3,2,1]
GRIB = "/root/era5_grib"
CFG = "/root/work/hysplit_data2arl/hysplit_data2arl/era52arl/era52arl.cfg"
E52 = "/root/work/hysplit_data2arl/hysplit_data2arl/era52arl/era52arl"
area = [46.5, 7.5, 43.5, 13.0]
days = [datetime.datetime(2017,10,22), datetime.datetime(2017,10,23)]
def fetch(suffix, var_p, lev=None):
    out = os.path.join(GRIB, "po_c" + suffix + ".grib")
    if os.path.exists(out) and os.path.getsize(out) > 500000: return out
    c = cdsapi.Client()
    req = {"product_type":"reanalysis","year":sorted({str(d.year) for d in days}),"month":sorted({("%02d"%d.month) for d in days}),"day":sorted({("%02d"%d.day) for d in days}),"time":["%02d:00"%h for h in range(24)],"area":area,"data_format":"grib","grid":[0.25,0.25]}
    req["variable"] = var_p
    if lev: req["pressure_level"] = lev
    dsname = "reanalysis-era5-pressure-levels" if lev else "reanalysis-era5-single-levels"
    c.retrieve(dsname, req, out)
    print("fetched", out, flush=True)
    return out
import eccodes
def split(combined, suffix):
    bufs = {}
    for d in days:
        k = d.strftime("%Y%m%d")
        p = os.path.join(GRIB, "po_" + k + suffix + ".grib")
        bufs[k] = (p, io.BytesIO())
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
cp = fetch("_p", ["geopotential","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity","relative_humidity"], PLEVS)
cs = fetch("_s", ["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"])
split(cp, "_p"); split(cs, "_s")
for d in days:
    k = d.strftime("%Y%m%d")
    out = "/root/met_era5/" + k
    p = os.path.join(GRIB, "po_" + k + "_p.grib"); s = os.path.join(GRIB, "po_" + k + "_s.grib")
    if os.path.exists(p) and os.path.exists(s) and not (os.path.exists(out) and os.path.getsize(out) > 100000):
        subprocess.run([E52,"-d"+CFG,"-i"+p,"-a"+s,"-o"+out], check=True)
        print("convert", k, os.path.getsize(out), flush=True)
print("PO FIX DONE", flush=True)
PYEOF
/root/venvs/cds/bin/python /root/era5_po_fix.py 2>&1 | tee /root/era5_po_fix.log