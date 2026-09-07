#!/usr/bin/env bash
set -x
/root/venvs/cds/bin/pip install -q requests 2>&1 | tail -1
mkdir -p /root/gdas05
cat > /root/gdas05/dl.py << "PYEOF"
import requests, threading, time, os
P = {"http":"http://127.0.0.1:17891","https":"http://127.0.0.1:17891"}
UA = {"User-Agent":"Mozilla/5.0"}
base = "https://www.ready.noaa.gov/data/archives/gdas0p5/"
for p in ["2017/10/20171022_gdas0p5", "2017/10/20171023_gdas0p5"]:
    fn = p.split("/")[-1]
    dst = "/root/gdas05/" + fn
    if os.path.exists(dst) and os.path.getsize(dst) > 500_000_000:
        print("skip", fn); continue
    h = requests.head(base+p, headers=UA, proxies=P, timeout=60)
    total = int(h.headers.get("Content-Length", 0))
    N = 8; seg = total // N
    res = [0]*N
    def w(i):
        s = i*seg; e = total-1 if i == N-1 else s+seg-1
        try:
            with requests.get(base+p, headers={**UA, "Range":"bytes=%d-%d"%(s,e)}, proxies=P, stream=True, timeout=300) as r:
                if r.status_code not in (200,206): res[i]=-1; return
                with open(dst+".p%d"%i, "wb") as f:
                    for c in r.iter_content(1<<20): f.write(c)
                res[i] = e-s+1
        except Exception as ex:
            res[i]=-2; print("err", i, str(ex)[:90])
    t0=time.time()
    ts=[threading.Thread(target=w, args=(i,)) for i in range(N)]
    [t.start() for t in ts]; [t.join() for t in ts]
    if sum(1 for x in res if x>0) != N:
        print("FAIL", fn); continue
    with open(dst, "wb") as out:
        for i in range(N):
            with open(dst+".p%d"%i, "rb") as fh:
                while True:
                    b = fh.read(1<<20)
                    if not b: break
                    out.write(b)
            os.remove(dst+".p%d"%i)
    print("OK", fn, os.path.getsize(dst), "%.0fs" % (time.time()-t0), flush=True)
print("DONE")
PYEOF
cd /root/gdas05 && /root/venvs/cds/bin/python dl.py 2>&1 | tail -6
ls -la /root/gdas05/