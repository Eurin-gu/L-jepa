#!/usr/bin/env bash
set -x
cat > /root/fetch_era5_queue.py << "PYEOF"
import cdsapi, os, datetime
PLEVS=[1000,975,950,925,900,875,850,825,800,775,750,700,650,600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,10,7,5,3,2,1]
c=cdsapi.Client()
def get_day(area, day, out, kind):
    if os.path.exists(out) and os.path.getsize(out) > 500000:
        print("skip", out, flush=True); return
    req={"product_type":"reanalysis","year":str(day.year),"month":"%02d"%day.month,"day":"%02d"%day.day,"time":["%02d:00"%h for h in range(24)],"area":area,"data_format":"grib","grid":[0.25,0.25]}
    if kind=="p":
        req["variable"]=["geopotential","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity","relative_humidity"]; req["pressure_level"]=PLEVS
        c.retrieve("reanalysis-era5-pressure-levels", req, out)
    else:
        req["variable"]=["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"]
        c.retrieve("reanalysis-era5-single-levels", req, out)
    print("done", out, flush=True)
R = {
 "so_cal_LA_basin": ([35.0,-119.0,31.5,-115.5], ["20150102","20150807","20160217","20160807"]),
 "cent_valley_CA": ([40.5,-123.0,34.0,-117.5], ["20150111","20150722","20160222","20160908","20170522","20171118"]),
 "permian_westTX": ([34.0,-105.0,29.5,-99.5], ["20150128","20151013","20160319","20160904","20170308","20171016"]),
 "co_front_range": ([41.5,-107.0,37.5,-103.0], ["20150128","20150911","20160422","20161123","20170612"]),
}
for reg,(area, dates) in R.items():
    for ds in dates:
        d = datetime.datetime.strptime(ds, "%Y%m%d")
        d0 = d - datetime.timedelta(days=1)
        for dd in (d0, d):
            key = "%s_%s" % (reg[:3], dd.strftime("%Y%m%d"))
            get_day(area, dd, "/root/era5_grib/%s_p.grib" % key, "p")
            get_day(area, dd, "/root/era5_grib/%s_s.grib" % key, "s")
print("QUEUE DONE", flush=True)
PYEOF
/root/venvs/cds/bin/python /root/fetch_era5_queue.py 2>&1 | tee /root/era5_queue.log