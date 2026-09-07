#!/usr/bin/env bash
set -x
cat > /root/fetch_era5_days.py << "PYEOF"
import cdsapi, os, datetime
PLEVS=[1000,975,950,925,900,875,850,825,800,775,750,700,650,600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,10,7,5,3,2,1]
c=cdsapi.Client()
def fetch_day(region, area, day, hrs, out, kind):
    if os.path.exists(out) and os.path.getsize(out) > 500000:
        print("skip", out); return
    req={"product_type":"reanalysis","year":str(day.year),"month":"%02d"%day.month,"day":"%02d"%day.day,
         "time":["%02d:00"%h for h in hrs],"area":area,"data_format":"grib","grid":[0.25,0.25]}
    if kind=="p":
        req["variable"]=["geopotential","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity","relative_humidity"]
        req["pressure_level"]=PLEVS
        c.retrieve("reanalysis-era5-pressure-levels", req, out)
    else:
        req["variable"]=["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"]
        c.retrieve("reanalysis-era5-single-levels", req, out)
    print("done", out, flush=True)
jobs=[
 ("po_valley_italy",[46.5,7.5,43.5,13.0],datetime.date(2017,10,22),[20,21,22,23],"/root/era5_grib/po_20171022", "p"),
 ("po_valley_italy",[46.5,7.5,43.5,13.0],datetime.date(2017,10,22),[20,21,22,23],"/root/era5_grib/po_20171022", "s"),
 ("po_valley_italy",[46.5,7.5,43.5,13.0],datetime.date(2017,10,23),list(range(0,22)),"/root/era5_grib/po_20171023", "p"),
 ("po_valley_italy",[46.5,7.5,43.5,13.0],datetime.date(2017,10,23),list(range(0,22)),"/root/era5_grib/po_20171023", "s"),
 ("north_china_plain",[41.5,113.5,37.5,118.5],datetime.date(2017,6,25),[20,21,22,23],"/root/era5_grib/ncp_20170625", "p"),
 ("north_china_plain",[41.5,113.5,37.5,118.5],datetime.date(2017,6,25),[20,21,22,23],"/root/era5_grib/ncp_20170625", "s"),
 ("north_china_plain",[41.5,113.5,37.5,118.5],datetime.date(2017,6,26),list(range(0,22)),"/root/era5_grib/ncp_20170626", "p"),
 ("north_china_plain",[41.5,113.5,37.5,118.5],datetime.date(2017,6,26),list(range(0,22)),"/root/era5_grib/ncp_20170626", "s"),
]
for region, area, day, hrs, base, kind in jobs:
    suf = "DATA.GRIB" if kind=="p" else "SFC.GRIB"
    fetch_day(region, area, day, hrs, base+"_"+suf, kind)
print("PER-DAY ERA5 DONE", flush=True)
PYEOF
/root/venvs/cds/bin/python /root/fetch_era5_days.py 2>&1 | tee /root/era5_days.log