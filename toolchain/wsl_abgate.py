import netCDF4 as nc, numpy as np, csv, glob, os
import netCDF4 as nc
rows = {
 "so": "/root/auto_run/abmanifest_so_cal_LA_basin_20150807.csv",
 "cv": "/root/auto_run/abmanifest_cent_valley_CA_20150722.csv",
 "tx": "/root/auto_run/abmanifest_permian_westTX_20151013.csv",
 "cf": "/root/auto_run/abmanifest_co_front_range_20150911.csv",
}
for k, m in rows.items():
    with open(m) as fh:
        r = next(csv.DictReader(fh))
    ds = nc.Dataset(r["foot_nc"])
    lon = np.asarray(ds.variables["lon"][:]); lat = np.asarray(ds.variables["lat"][:])
    foot = np.asarray(ds.variables["foot"][0])
    ds.close()
    w = foot / foot.sum()
    clon = float((w * lon).sum()); clat = float((w * lat).sum())
    dlat = abs(clat - float(r["lati"])); dlon = abs(clon - float(r["long"]))
    dist_km = np.hypot(dlat*110.54, dlon*111.32*np.cos(np.radians(float(r["lati"]))))
    print(k, "n=1 CoM(%.2f,%.2f) vs rec(%.3f,%.3f) dist=%.1fkm sum=%.3f" % (clat, clon, float(r["lati"]), float(r["long"]), dist_km, float(foot.sum())))
