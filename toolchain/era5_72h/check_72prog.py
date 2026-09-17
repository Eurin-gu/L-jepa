import os, datetime, json
BASE = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d"
TARGETS = {
  "po_valley_italy": ["20150211","20150721","20150813","20160115","20160221","20160714","20160909","20170101","20170327","20170421","20171023"],
  "north_china_plain": ["20150301","20150520","20150605","20151103","20160106","20160209","20160310","20160506","20161123","20161216","20170626"],
  "so_cal_LA_basin": ["20150102","20150807","20160217","20160318","20160807","20171111"],
  "cent_valley_CA": ["20150111","20150722","20160222","20160908","20170522","20171118"],
  "permian_westTX": ["20150128","20151013","20160319","20160904","20170308","20171016"],
  "co_front_range": ["20150128","20150911","20160422","20161123","20170612"],
}
print("=" * 76)
print("72h 后向数据覆盖率 (统一目标)")
print("=" * 76)
tn = tm = 0
print("%-20s %-8s %-10s %-10s %s" % ("region","需72h","完整天","缺天","进度"))
print("-" * 76)
for reg, dates in TARGETS.items():
    need = set()
    for t in dates:
        dt = datetime.datetime.strptime(t, "%Y%m%d")
        for k in range(4):
            need.add((dt - datetime.timedelta(days=k)).strftime("%Y%m%d"))
    d = os.path.join(BASE, reg)
    full = set()
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.endswith("_PL.GRIB"):
                day = f[:8]
                if os.path.exists(os.path.join(d, day+"_SFC.GRIB")): full.add(day)
    have = len(need & full); total = len(need); miss = total - have
    tn += total; tm += miss
    pct = 100.0 * have / total
    bar = "#" * int(pct/5)
    print("%-20s %-8d %-10d %-10d [%-20s] %.0f%%" % (reg, total, have, miss, bar, pct))
print("-" * 76)
print("合计: 需 %d 天, 缺 %d 天 (%.0f%% 完成)" % (tn, tm, 100.0*(tn-tm)/tn))
print()
print("提示: 单请求 35-111 分钟属正常; 预计还需 %.0f 小时" % (tm*2/2*50/60))
