import netCDF4 as nc, numpy as np, csv, glob
rows = {
 "so": "/root/auto_run/abmanifest_so_cal_LA_basin_20150807.csv",
 "cv": "/root/auto_run/abmanifest_cent_valley_CA_20150722.csv",
 "tx": "/root/auto_run/abmanifest_permian_westTX_20151013.csv",
 "cf": "/root/auto_run/abmanifest_co_front_range_20150911.csv",
}
for k, m in rows.items():
    with open(m) as fh:
        rd = csv.DictReader(fh)
        r = next(rd)
    keys = list(r.keys())
    fkey = next((x for x in keys if "foot" in x), None)
    lkey = next((x for x in keys if "lati" in x), None)
    ngkey = next((x for x in keys if "long" in x), None)
    foot = r[fkey]; lat = float(r[lkey]); lon = float(r[ngkey])
    if not foot or not os.path.exists(foot):
        foot = glob.glob("/root/work/stilt/out/by-id/gdas0p5-v1-*-p250_*/*_foot.nc")[0]
    ds = nc.Dataset(foot)
    lonv = np.asarray(ds.variables["lon"][:]); latv = np.asarray(ds.variables["lat"][:])
    f = np.asarray(ds.variables["foot"][0]); ds.close()
    w = f / f.sum()
    clat = float((w*latv).sum()); clon = float((w*lonv).sum())
    dist = np.hypot(abs(clat-lat)*110.54, abs(clon-lon)*111.32*np.cos(np.radians(lat)))
    print(k, "CoM(%.2f,%.2f) rec(%.3f,%.3f) dist=%.1fkm sum=%.2f nonneg=%s" % (clat, clon, lat, lon, dist, float(f.sum()), bool(np.all(f>=0))))
