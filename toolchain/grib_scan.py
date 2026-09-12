# grib_scan.py -- pure-python GRIB1/GRIB2 structural scanner (no eccodes)
# usage: python grib_scan.py <file.GRIB>
import sys, collections

ECMWF_T128 = {129:"z",130:"t",131:"u",132:"v",135:"w",157:"r",
              167:"t2m",165:"u10",166:"v10",164:"tcc",134:"sp",
              168:"d2m",159:"blh",59:"cape"}
G2_DISC0 = {(0,0):"t",(3,4):"z",(2,2):"u",(2,3):"v",(2,8):"w",(1,1):"r",
            (0,0, ):None}

def scan(path):
    data = open(path, "rb").read()
    n = len(data); i = 0; msgs = 0; editions = collections.Counter()
    params = collections.Counter(); levels = collections.Counter()
    dates = set(); hours = set(); grids = collections.Counter()
    while i < n - 8:
        if data[i:i+4] != b"GRIB":
            i += 1; continue
        ed = data[i+7]
        if ed == 1:
            L = int.from_bytes(data[i+4:i+7], "big")
            if L <= 8 or i + L > n: i += 1; continue
            pds_len = int.from_bytes(data[i+8:i+11], "big")
            pds = data[i+8:i+8+pds_len]
            param, ltype = pds[8], pds[9]
            lval = int.from_bytes(pds[10:12], "big")
            yy, mo, dd, hh = pds[12], pds[13], pds[14], pds[15]
            cent = pds[24] if pds_len > 24 else 21
            dates.add(((cent-1)*100 + yy)*10000 + mo*100 + dd); hours.add(hh)
            params[param] += 1; levels[(ltype, lval)] += 1
            if pds[7] & 0x80:
                g = i + 8 + pds_len
                ni = int.from_bytes(data[g+6:g+8], "big"); nj = int.from_bytes(data[g+8:g+10], "big")
                grids[(ni, nj)] += 1
            editions[1] += 1; msgs += 1; i += L
        elif ed == 2:
            L = int.from_bytes(data[i+8:i+16], "big")
            if L <= 16 or i + L > n: i += 1; continue
            off = i + 16; end = i + L
            while off < end - 4:
                slen = int.from_bytes(data[off:off+4], "big"); snum = data[off+4]
                if slen < 5: break
                if snum == 1:
                    yy = int.from_bytes(data[off+12:off+14], "big")
                    dates.add(yy*10000 + data[off+14]*100 + data[off+15]); hours.add(data[off+16])
                elif snum == 3:
                    grids[("npts", int.from_bytes(data[off+6:off+10], "big"))] += 1
                elif snum == 4:
                    cat, num = data[off+9], data[off+10]
                    lt = data[off+22]; sc = data[off+23]
                    lv = int.from_bytes(data[off+24:off+28], "big")
                    params[(cat, num)] += 1; levels[(lt, sc, lv)] += 1
                off += slen
            editions[2] += 1; msgs += 1; i += L
        else:
            i += 1
    print(f"file: {path}")
    print(f"  size={n/1e6:.2f}MB msgs={msgs} editions={dict(editions)}")
    print(f"  dates={sorted(dates)} nhours={len(hours)} hours={sorted(hours)[:6]}...")
    print(f"  grids={dict(grids)}")
    pn = {ECMWF_T128.get(p, p): c for p, c in sorted(params.items(), key=lambda x: str(x[0]))}
    print(f"  params={pn}")
    lv = sorted(levels, key=lambda x: str(x))
    print(f"  nlevel_kinds={len(levels)} levels(sample)={lv[:8]}")
    if len(lv) > 8: print(f"    ...={lv[-4:]}")
    # expected-message check for ERA5 PL/SFC day files
    exp = {"PL": 6*37*24, "SFC": 9*24}
    for k, v in exp.items():
        if msgs == v: print(f"  [OK] message count == {k} expectation ({v})")

for p in sys.argv[1:]:
    scan(p)
