#!/usr/bin/env bash
set -x
cat > /root/fetch_era5.py << "PYEOF"
import cdsapi, os, sys, datetime, time
PLEVS = [1000,975,950,925,900,875,850,825,800,775,750,700,650,600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,10,7,5,3,2,1]
c = cdsapi.Client()
def hours_list(date, nback=24):
    # receptor ~20-21Z on date; need from (date-1) 20Z through date 21Z
    t = datetime.datetime(date.year, date.month, date.day, 20) - datetime.timedelta(hours=nback-1)
    out = []
    for i in range(nback+1):
        out.append(t.strftime("%H:%M")); t += datetime.timedelta(hours=1)
    return out
def fetch(region, area, date, outdir):
    y = str(date.year); m = "%02d" % date.month; d = "%02d" % date.day
    days = sorted(set([date.strftime("%Y-%m-%d"), (date - datetime.timedelta(hours=23)).strftime("%Y-%m-%d")]))
    hrs = hours_list(date)
    os.makedirs(outdir, exist_ok=True)
    # pressure levels (geopotential z, t, u, v, w, r) 37 levs
    preq = {
      "product_type": "reanalysis",
      "variable": ["geopotential","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity","relative_humidity"],
      "pressure_level": PLEVS,
      "year": [y], "month": [m], "day": [d], "time": hrs,
      "area": area, "data_format": "grib", "grid": [0.25, 0.25]
    }
    # handle days spanning (only one day needed if hours belong to date & date-1)
    preq["day"] = [x.split("-")[2] for x in days]
    print(region, "pressure submit...", flush=True)
    c.retrieve("reanalysis-era5-pressure-levels", preq, outdir + "/DATA.GRIB")
    print(region, "pressure done", flush=True)
    # single levels surface analysis (cfg subset minus accumulated)
    sreq = {
      "product_type": "reanalysis",
      "variable": ["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"],
      "year": [y], "month": [m], "day": [x.split("-")[2] for x in days], "time": hrs,
      "area": area, "data_format": "grib", "grid": [0.25, 0.25]
    }
    print(region, "sfc submit...", flush=True)
    c.retrieve("reanalysis-era5-single-levels", sreq, outdir + "/SFC.GRIB")
    print(region, "sfc done", flush=True)
for region, area, datestr in [
    ("po_valley_italy", [46.5, 7.5, 43.5, 13.0], "20171023"),
    ("north_china_plain", [41.5, 113.5, 37.5, 118.5], "20170626"),
]:
    dt = datetime.datetime.strptime(datestr, "%Y%m%d")
    fetch(region, area, dt, "/root/era5_grib/" + region + "_" + datestr)
print("ALL ERA5 ORDERS DONE", flush=True)
PYEOF
/root/venvs/cds/bin/python /root/fetch_era5.py 2>&1 | tee /root/era5_fetch.log