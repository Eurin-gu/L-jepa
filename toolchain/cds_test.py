import cdsapi, json, time
c = cdsapi.Client()
req = {
  "product_type": "reanalysis",
  "variable": "2m_temperature",
  "year": "2020",
  "month": "01",
  "day": "01",
  "time": "00:00",
  "data_format": "netcdf",
  "area": [45, 8, 44, 12],
}
try:
  r = c.retrieve("reanalysis-era5-single-levels", req, target="/tmp/cds_test.nc")
  print("retrieve accepted:", r)
  print("done")
except Exception as e:
  print("CDS TEST ERROR:", type(e).__name__, str(e)[:300])