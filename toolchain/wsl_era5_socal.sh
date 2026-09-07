#!/usr/bin/env bash
set -x
cat > /root/fetch_era5_socal.py << "PYEOF"
import cdsapi, os, datetime
PLEVS=[1000,975,950,925,900,875,850,825,800,775,750,700,650,600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,10,7,5,3,2,1]
c=cdsapi.Client()
def fetch_day(area, day, hrs, out, kind):
    if os.path.exists(out) and os.path.getsize(out) > 500000: print("skip", out); return
    req={"product_type":"reanalysis","year":str(day.year),"month":"%02d"%day.month,"day":"%02d"%day.day,"time":["%02d:00"%h for h in hrs],"area":area,"data_format":"grib","grid":[0.25,0.25]}
    if kind=="p":
        req["variable"]=["geopotential","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity","relative_humidity"]; req["pressure_level"]=PLEVS
        c.retrieve("reanalysis-era5-pressure-levels", req, out)
    else:
        req["variable"]=["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"]
        c.retrieve("reanalysis-era5-single-levels", req, out)
    print("done", out, flush=True)
AREA=[35.0,-119.0,31.5,-115.5]  # so_cal box padded
for datestr, day0 in [("20171111", 11), ("20160318", 18)]:
    d = datetime.date(2017 if datestr[0]=="1" else 2016, 11 if datestr[0]=="1" else 3, day0)
    d0 = d - datetime.timedelta(days=1)
    fetch_day(AREA, d0, [20,21,22,23], "/root/era5_grib/so_%s_prev_p.grib" % datestr, "p")
    fetch_day(AREA, d0, [20,21,22,23], "/root/era5_grib/so_%s_prev_s.grib" % datestr, "s")
    fetch_day(AREA, d, list(range(0,22)), "/root/era5_grib/so_%s_cur_p.grib" % datestr, "p")
    fetch_day(AREA, d, list(range(0,22)), "/root/era5_grib/so_%s_cur_s.grib" % datestr, "s")
print("SOCAL ERA5 DONE", flush=True)
PYEOF
/root/venvs/cds/bin/python /root/fetch_era5_socal.py 2>&1 | tee /root/era5_socal.log