import netCDF4 as nc, numpy as np, csv
rows = {
 "so": "/root/auto_run/abmanifest_so_cal_LA_basin_20150807.csv",
 "cv": "/root/auto_run/abmanifest_cent_valley_CA_20150722.csv",
 "tx": "/root/auto_run/abmanifest_permian_westTX_20151013.csv",
 "cf": "/root/auto_run/abmanifest_co_front_range_20150911.csv",
}
for k, m in rows.items():
    with open(m) as fh:
        r = next(csv.DictReader(fh))
    lat = float(r["lati"]); lon = float(r["long"])
    ds = nc.Dataset(r["foot_nc"])
    lonv = np.asarray(ds.variables["lon"][:]); latv = np.asarray(ds.variables["lat"][:])
    f = np.asarray(ds.variables["foot"][0]).astype(float); ds.close()
    w = f / f.sum()
    clon = float((w * lonv[None, :]).sum())
    clat = float((w * latv[:, None]).sum())
    dist = np.hypot(abs(clat - lat) * 110.54, abs(clon - lon) * 111.32 * np.cos(np.radians(lat)))
    print(k, "CoM(%.2f,%.2f) rec(%.3f,%.3f) dist=%.1fkm sum=%.2f nonneg=%s" % (clat, clon, lat, lon, dist, float(f.sum()), bool(np.all(f >= 0))))
