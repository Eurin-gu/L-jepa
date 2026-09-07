#!/usr/bin/env bash
set -x
cat > /root/fetch_safe.py << "PYEOF"
import cdsapi, os, datetime, time
PLEVS = [1000,975,950,925,900,875,850,825,800,775,750,700,650,600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,10,7,5,3,2,1]
GRIB = "/root/era5_grib"
J = [
 ("so", [35.0,-119.0,31.5,-115.5], ["20150102","20150807","20160217","20160318","20160807","20171111"]),
 ("cv", [40.5,-123.0,34.0,-117.5], ["20150111","20150722","20160222","20160908","20170522","20171118"]),
 ("tx", [34.0,-105.0,29.5,-99.5], ["20150128","20151013","20160319","20160904","20170308","20171016"]),
 ("cf", [41.5,-107.0,37.5,-103.0], ["20150128","20150911","20160422","20161123","20170612"]),
 ("ncp", [41.5,113.5,37.5,118.5], ["20170626"]),
 ("po", [46.5,7.5,43.5,13.0], ["20171023"]),
]
def run_req(dsname, req, out):
    while True:
        try:
            cdsapi.Client().retrieve(dsname, req, out)
            print("fetched", out, flush=True); return
        except Exception as ex:
            msg = str(ex)
            print("ERR", out, msg[:160], flush=True)
            if "queued" in msg.lower() or "rejected" in msg.lower() or "limited" in msg.lower():
                time.sleep(600)
            else:
                time.sleep(60)
for tag, area, dates in J:
    for ds in dates:
        d = datetime.datetime.strptime(ds,"%Y%m%d"); d0 = d - datetime.timedelta(days=1); days=[d0,d]
        for suffix, dsname, var, lev in [
          ("_p","reanalysis-era5-pressure-levels",["geopotential","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity","relative_humidity"],PLEVS),
          ("_s","reanalysis-era5-single-levels",["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"],None),
        ]:
            out = os.path.join(GRIB, tag + "_c" + suffix + ".grib")
            if os.path.exists(out) and os.path.getsize(out) > 500000:
                print("skip", out, flush=True); continue
            print("REQ", out, flush=True)
            yrs = sorted({dd.year for dd in days}); mons = sorted({dd.month for dd in days}); dys = sorted({dd.day for dd in days})
            req = {"product_type":"reanalysis","year":[str(y) for y in yrs],"month":["%02d"%m for m in mons],"day":["%02d"%x for x in dys],"time":["%02d:00"%h for h in range(24)],"area":area,"data_format":"grib","grid":[0.25,0.25],"variable":var}
            if lev: req["pressure_level"] = lev
            run_req(dsname, req, out)
print("FETCH SAFE DONE", flush=True)
PYEOF
echo ready