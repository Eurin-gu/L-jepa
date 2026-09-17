import numpy as np, netCDF4, eccodes
P = 85000.0; EPS = 0.622
def es_w(T): return 611.21*np.exp(17.502*(T-273.16)/(T-32.19))
def es_i(T): return 611.21*np.exp(22.587*(T-273.16)/(T+0.7))
def q_of_e(e): return EPS*e/(P - (1-EPS)*e)

with open("/mnt/d/lagrangian-jepa-cn/met_cache/era5d/po_valley_italy/20171023_PL.GRIB","rb") as f:
    g = eccodes.codes_grib_new_from_file(f)
    la = np.array(eccodes.codes_get_array(g,"distinctLatitudes"))
    lo = np.array(eccodes.codes_get_array(g,"distinctLongitudes"))
    eccodes.codes_release(g)
print("CDS 网格: lat %.2f..%.2f  lon %.2f..%.2f  (%dx%d)" % (la.min(), la.max(), lo.min(), lo.max(), len(la), len(lo)))

q_mir = {}; t_mir = {}
for var, key, store in [("specific_humidity","q",q_mir), ("temperature","t",t_mir)]:
    ds = netCDF4.Dataset("/root/rh_test/%s_850.nc" % var)
    latm = np.array(ds.variables["latitude"][:], dtype=float)
    lonm = np.array(ds.variables["longitude"][:], dtype=float)
    v = np.array(ds.variables[key][:], dtype=float)
    if latm[0] > latm[-1]: latm = latm[::-1]; v = v[:, ::-1, :]
    store["v"] = v; store["lat"] = latm; store["lon"] = lonm
    ds.close()

def bilin(src, lat_s, lon_s, lat_t, lon_t):
    j = np.clip(np.searchsorted(lat_s, lat_t)-1, 0, len(lat_s)-2)
    i = np.clip(np.searchsorted(lon_s, lon_t)-1, 0, len(lon_s)-2)
    wj = ((lat_t - lat_s[j])/(lat_s[j+1]-lat_s[j]))[None,:,None]
    wi = ((lon_t - lon_s[i])/(lon_s[i+1]-lon_s[i]))[None,None,:]
    a = src[:, j,   :][:, :, i];   b = src[:, j,   :][:, :, i+1]
    c = src[:, j+1, :][:, :, i];   d = src[:, j+1, :][:, :, i+1]
    return a*(1-wj)*(1-wi) + b*(1-wj)*wi + c*wj*(1-wi) + d*wj*wi
q_on = bilin(q_mir["v"], q_mir["lat"], q_mir["lon"], la, lo)
t_on = bilin(t_mir["v"], t_mir["lat"], t_mir["lon"], la, lo)

r_cds = np.full((24,len(la),len(lo)), np.nan); t_cds = np.full_like(r_cds, np.nan)
with open("/mnt/d/lagrangian-jepa-cn/met_cache/era5d/po_valley_italy/20171023_PL.GRIB","rb") as f:
    while True:
        g = eccodes.codes_grib_new_from_file(f)
        if g is None: break
        sn = eccodes.codes_get(g,"shortName"); lv = eccodes.codes_get(g,"level")
        if lv==850 and sn in ("r","t"):
            hr = eccodes.codes_get(g,"dataTime")//100
            (r_cds if sn=="r" else t_cds)[hr] = eccodes.codes_get_values(g).reshape(len(la), len(lo))
        eccodes.codes_release(g)

print()
print("T 一致性 (镜像插值 vs CDS): 均值 %+.6f K  最大|差| %.6f K" % (np.nanmean(t_on-t_cds), np.nanmax(np.abs(t_on-t_cds))))
print()
print("由 CDS 的 r,t 反算 q, 与镜像 q 直接比较:")
for name, esf in [("水面饱和公式", es_w), ("冰面饱和公式", es_i)]:
    e_cds = (r_cds/100.0)*esf(t_cds)
    q_cds = q_of_e(e_cds)
    rel = (q_on - q_cds)/q_cds*100
    print("  [%s] q 相对差: 均值 %+.3f%%  中位|差| %.3f%%  90分位 %.3f%%  最大 %.3f%%"
          % (name, np.nanmean(rel), np.nanmedian(np.abs(rel)), np.nanpercentile(np.abs(rel),90), np.nanmax(np.abs(rel))))
print()
e_cds = (r_cds/100.0)*es_w(t_cds)
q_cds = q_of_e(e_cds)
print("参考量级: q 均值 %.3f g/kg ; RH 均值 %.1f%% ; T 均值 %.1f K" % (np.nanmean(q_cds)*1000, np.nanmean(r_cds), np.nanmean(t_cds)))
print("相关(镜像q, CDS反算q): %.6f" % np.corrcoef(q_on.ravel(), q_cds.ravel())[0,1])
