#!/usr/bin/env bash
set -x
cat > /root/fetch_era5_fulldays.py << "PYEOF"
import cdsapi, os, datetime
PLEVS=[1000,975,950,925,900,875,850,825,800,775,750,700,650,600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,10,7,5,3,2,1]
c=cdsapi.Client()
def day(area, day, out, kind):
    if os.path.exists(out) and os.path.getsize(out) > 500000:
        print("skip", out); return
    req={"product_type":"reanalysis","year":str(day.year),"month":"%02d"%day.month,"day":"%02d"%day.day,"time":["%02d:00"%h for h in range(24)],"area":area,"data_format":"grib","grid":[0.25,0.25]}
    if kind=="p":
        req["variable"]=["geopotential","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity","relative_humidity"]; req["pressure_level"]=PLEVS
        c.retrieve("reanalysis-era5-pressure-levels", req, out)
    else:
        req["variable"]=["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"]
        c.retrieve("reanalysis-era5-single-levels", req, out)
    print("done", out, flush=True)
sets=[
 ("po", [46.5,7.5,43.5,13.0], 2017,10,[22,23]),
 ("ncp", [41.5,113.5,37.5,118.5], 2017,6,[25,26]),
 ("so", [35.0,-119.0,31.5,-115.5], 2017,11,[10,11]),
 ("so", [35.0,-119.0,31.5,-115.5], 2016,3,[17,18]),
]
for tag, area, y, m, days in sets:
    for dd in days:
        d = datetime.date(y, m, dd)
        day(area, d, "/root/era5_grib/%s_%04d%02d%02d_p.grib" % (tag, y, m, dd), "p")
        day(area, d, "/root/era5_grib/%s_%04d%02d%02d_s.grib" % (tag, y, m, dd), "s")
print("FULLDAYS DONE", flush=True)
PYEOF
/root/venvs/cds/bin/python /root/fetch_era5_fulldays.py 2>&1 | tee /root/era5_fulldays.log