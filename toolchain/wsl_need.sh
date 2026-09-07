#!/usr/bin/env bash
python3 - << "PY"
import datetime, os, glob
pairs = ["so_cal_LA_basin 20150102","so_cal_LA_basin 20150807","so_cal_LA_basin 20160318","so_cal_LA_basin 20160807","so_cal_LA_basin 20171111","cent_valley_CA 20150722","cent_valley_CA 20160222","cent_valley_CA 20160908","cent_valley_CA 20170522","cent_valley_CA 20171118","permian_westTX 20151013","permian_westTX 20160319","permian_westTX 20160904","permian_westTX 20170308","permian_westTX 20171016","co_front_range 20150911","co_front_range 20160422","co_front_range 20161123","co_front_range 20170612"]
need = set()
for line in pairs:
    reg, d = line.split()
    dd = datetime.datetime.strptime(d, "%Y%m%d")
    need.add((dd - datetime.timedelta(days=1)).strftime("%Y%m%d"))
    need.add(d)
have = set(os.path.basename(x).replace("_gdas0p5","") for x in glob.glob("/root/gdas05/*_gdas0p5"))
missing = sorted(need - have)
print("needed:", len(need), "have:", len(have & need), "missing:", len(missing))
for m in missing: print("  ", m)
PY