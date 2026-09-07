#!/usr/bin/env bash
set -x
cat > /root/fetch_only.py << "PYEOF"
import cdsapi, os, datetime
PLEVS = [1000,975,950,925,900,875,850,825,800,775,750,700,650,600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,10,7,5,3,2,1]
GRIB = "/root/era5_grib"
REGIONS = [
 ("so", [35.0,-119.0,31.5,-115.5], ["20150102","20150807","20160217","20160318","20160807","20171111"]),
 ("cv", [40.5,-123.0,34.0,-117.5], ["20150111","20150722","20160222","20160908","20170522","20171118"]),
 ("tx", [34.0,-105.0,29.5,-99.5], ["20150128","20151013","20160319","20160904","20170308","20171016"]),
 ("cf", [41.5,-107.0,37.5,-103.0], ["20150128","20150911","20160422","20161123","20170612"]),
]
def fetch(tag, area, days, suffix, dsname, var, lev):
    out = os.path.join(GRIB, tag + "_c" + suffix + ".grib")
    if os.path.exists(out) and os.path.getsize(out) > 500000:
        print("skip", out, flush=True); return
    c = cdsapi.Client()
    req = {"product_type":"reanalysis","year":sorted({str(d.year) for d in days}),"month":sorted({("%02d"%d.month) for d in days}),"day":sorted({("%02d"%d.day) for d in days}),"time":["%02d:00"%h for h in range(24)],"area":area,"data_format":"grib","grid":[0.25,0.25],"variable":var}
    if lev: req["pressure_level"] = lev
    c.retrieve(dsname, req, out)
    print("fetched", out, flush=True)
for tag, area, dates in REGIONS:
    for ds in dates:
        d = datetime.datetime.strptime(ds,"%Y%m%d"); d0 = d - datetime.timedelta(days=1); days=[d0,d]
        print("REQ", tag, ds, flush=True)
        fetch(tag, area, days, "_p", "reanalysis-era5-pressure-levels", ["geopotential","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity","relative_humidity"], PLEVS)
        fetch(tag, area, days, "_s", "reanalysis-era5-single-levels", ["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"], None)
        print("OK", tag, ds, flush=True)
print("FETCH ONLY DONE", flush=True)
PYEOF
echo ready