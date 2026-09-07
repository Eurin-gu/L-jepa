#!/usr/bin/env bash
set -x
cat > /root/fetch_era5.py << "PYEOF"
import cdsapi, os, datetime
PLEVS = [1000,975,950,925,900,875,850,825,800,775,750,700,650,600,550,500,450,400,350,300,250,225,200,175,150,125,100,70,50,30,20,10,7,5,3,2,1]
c = cdsapi.Client()
def base_req(days, area):
    return {"product_type": "reanalysis",
      "year": sorted({str(d.year) for d in days}), "month": sorted({("%02d" % d.month) for d in days}),
      "day": sorted({("%02d" % d.day) for d in days}), "time": ["%02d:00" % h for h in range(24)],
      "area": area, "data_format": "grib", "grid": [0.25, 0.25]}
def fetch(region, area, date, outdir):
    days = sorted({date, date - datetime.timedelta(days=1)})
    os.makedirs(outdir, exist_ok=True)
    def need(path, minsize=1000000):
        if os.path.exists(path) and os.path.getsize(path) > minsize:
            print("skip", region, os.path.basename(path), os.path.getsize(path), flush=True); return False
        try: os.remove(path)
        except OSError: pass
        return True
    if need(outdir + "/DATA.GRIB"):
        preq = base_req(days, area); preq["variable"] = ["geopotential","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity","relative_humidity"]; preq["pressure_level"] = PLEVS
        print(region, "pressure submit", flush=True)
        c.retrieve("reanalysis-era5-pressure-levels", preq, outdir + "/DATA.GRIB")
        print(region, "pressure done", flush=True)
    if need(outdir + "/SFC.GRIB"):
        sreq = base_req(days, area); sreq["variable"] = ["10m_u_component_of_wind","10m_v_component_of_wind","2m_dewpoint_temperature","2m_temperature","surface_pressure","total_cloud_cover","boundary_layer_height","convective_available_potential_energy","geopotential"]
        print(region, "sfc submit", flush=True)
        c.retrieve("reanalysis-era5-single-levels", sreq, outdir + "/SFC.GRIB")
        print(region, "sfc done", flush=True)
for region, area, datestr in [
    ("po_valley_italy", [46.5, 7.5, 43.5, 13.0], "20171023"),
    ("north_china_plain", [41.5, 113.5, 37.5, 118.5], "20170626"),
]:
    dt = datetime.datetime.strptime(datestr, "%Y%m%d")
    fetch(region, area, dt, "/root/era5_grib/" + region + "_" + datestr)
print("ALL ERA5 DONE", flush=True)
PYEOF
/root/venvs/cds/bin/python /root/fetch_era5.py 2>&1 | tee /root/era5_fetch.log