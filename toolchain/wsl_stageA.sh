#!/usr/bin/env bash
set -x
mkdir -p /root/gdas05 /root/met_gdas05
cat > /root/gdas05/dlA.py << "PYEOF"
import requests, threading, time, os
P = {"http":"http://127.0.0.1:17891","https":"http://127.0.0.1:17891"}
UA = {"User-Agent":"Mozilla/5.0"}
base = "https://www.ready.noaa.gov/data/archives/gdas0p5/"
for p in ["2015/08/20150806_gdas0p5", "2015/08/20150807_gdas0p5"]:
    fn = p.split("/")[-1]; dst = "/root/gdas05/" + fn
    if os.path.exists(dst) and os.path.getsize(dst) > 500_000_000: print("skip", fn); continue
    h = requests.head(base+p, headers=UA, proxies=P, timeout=60)
    total = int(h.headers.get("Content-Length", 0)); N = 8; seg = total // N
    res = [0]*N
    def w(i):
        s = i*seg; e = total-1 if i == N-1 else s+seg-1
        try:
            with requests.get(base+p, headers={**UA, "Range":"bytes=%d-%d"%(s,e)}, proxies=P, stream=True, timeout=300) as r:
                if r.status_code not in (200,206): res[i]=-1; return
                with open(dst+".p%d"%i, "wb") as f:
                    for c in r.iter_content(1<<20): f.write(c)
                res[i] = e-s+1
        except Exception as ex: res[i]=-2; print("err", str(ex)[:80])
    t0=time.time()
    ts=[threading.Thread(target=w, args=(i,)) for i in range(N)]
    [t.start() for t in ts]; [t.join() for t in ts]
    if sum(1 for x in res if x>0) != N: print("FAIL", fn); continue
    with open(dst,"wb") as out:
        for i in range(N):
            with open(dst+".p%d"%i,"rb") as fh:
                while True:
                    b=fh.read(1<<20)
                    if not b: break
                    out.write(b)
            os.remove(dst+".p%d"%i)
    print("OK", fn, os.path.getsize(dst), "%.0fs"%(time.time()-t0), flush=True)
print("DL DONE")
PYEOF
cd /root/gdas05 && /root/venvs/cds/bin/python dlA.py 2>&1 | tail -4
cp /root/gdas05/20150806_gdas0p5 /root/gdas05/20150807_gdas0p5 /root/met_gdas05/
ls -la /root/met_gdas05/
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/so_cal_LA_basin/receptors_20150807_n120_maximin.csv --stilt-wd /root/work/stilt --met /root/met_gdas05 --jobs 24 --numpar 250 --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 3 --tag gdas0p5-v1-so_cal_LA_basin-20150807-p250 --timeout 3600 --log-dir /root/auto_run/logs_soA --manifest /root/auto_run/manifest_soA_gdas05_p250.csv > /root/auto_run/soA_gdas05.out 2>&1
echo "rc=$?"; tail -3 /root/auto_run/soA_gdas05.out