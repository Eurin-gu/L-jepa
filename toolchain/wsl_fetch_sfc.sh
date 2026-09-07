#!/usr/bin/env bash
set -x
cat > /root/fetch_sfc_only.py << "PYEOF"
import cdsapi, os, datetime, time
GRIB = "/root/era5_grib"
VAR=["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"]
J = [
 ("so", [35.0,-119.0,31.5,-115.5], ["20150102","20150807","20160217","20160318","20160807","20171111"]),
 ("cv", [40.5,-123.0,34.0,-117.5], ["20150111","20150722","20160222","20160908","20170522","20171118"]),
 ("tx", [34.0,-105.0,29.5,-99.5], ["20150128","20151013","20160319","20160904","20170308","20171016"]),
 ("cf", [41.5,-107.0,37.5,-103.0], ["20150128","20150911","20160422","20161123","20170612"]),
 ("ncp", [41.5,113.5,37.5,118.5], ["20170626"]),
 ("po", [46.5,7.5,43.5,13.0], ["20171023"]),
]
for tag, area, dates in J:
    for ds in dates:
        d = datetime.datetime.strptime(ds,"%Y%m%d"); d0=d-datetime.timedelta(days=1); days=[d0,d]
        out = os.path.join(GRIB, tag+"_c_s.grib")
        if os.path.exists(out) and os.path.getsize(out) > 500000: print("skip", out, flush=True); continue
        while True:
            try:
                req={"product_type":"reanalysis","year":sorted({str(dd.year) for dd in days}),"month":sorted({("%02d"%dd.month) for dd in days}),"day":sorted({("%02d"%dd.day) for dd in days}),"time":["%02d:00"%h for h in range(24)],"area":area,"data_format":"grib","grid":[0.25,0.25],"variable":VAR}
                cdsapi.Client().retrieve("reanalysis-era5-single-levels", req, out)
                print("sfc fetched", out, flush=True); break
            except Exception as ex:
                msg=str(ex)
                print("ERR", msg[:120], flush=True)
                time.sleep(600 if ("queued" in msg.lower() or "limited" in msg.lower() or "rejected" in msg.lower()) else 60)
print("SFC ONLY DONE", flush=True)
PYEOF
echo ready