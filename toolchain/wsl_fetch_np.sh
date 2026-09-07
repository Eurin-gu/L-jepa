#!/usr/bin/env bash
set -x
cat > /root/fetch_np.py << "PYEOF"
import cdsapi, os, datetime
PLEVS = [1000,975,950,925,900,875,850,825,800,775,750,700,650,600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,10,7,5,3,2,1]
GRIB = "/root/era5_grib"
J = [
 ("ncp", [41.5,113.5,37.5,118.5], ["20170625","20170626"]),
 ("po", [46.5,7.5,43.5,13.0], ["20171022","20171023"]),
]
def fetch(tag, area, days, suffix, dsname, var, lev):
    out = os.path.join(GRIB, tag + "_c" + suffix + ".grib")
    if os.path.exists(out) and os.path.getsize(out) > 500000:
        print("skip", out, flush=True); return
    c = cdsapi.Client()
    yrs = sorted({d[:4] for d in days}); mons = sorted({d[4:6] for d in days}); dys = sorted({d[6:8] for d in days})
    req = {"product_type":"reanalysis","year":yrs,"month":mons,"day":dys,"time":["%02d:00"%h for h in range(24)],"area":area,"data_format":"grib","grid":[0.25,0.25],"variable":var}
    if lev: req["pressure_level"] = lev
    c.retrieve(dsname, req, out)
    print("fetched", out, flush=True)
for tag, area, days in J:
    fetch(tag, area, days, "_p", "reanalysis-era5-pressure-levels", ["geopotential","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity","relative_humidity"], PLEVS)
    fetch(tag, area, days, "_s", "reanalysis-era5-single-levels", ["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"], None)
print("NCP PO FETCH DONE", flush=True)
PYEOF
/root/venvs/cds/bin/python /root/fetch_np.py 2>&1 | tee /root/fetch_np.log