import json, urllib.request, collections, datetime, statistics, os, re
cfg = dict(l.split(":",1) for l in open("/root/.cdsapirc").read().strip().splitlines() if ":" in l)
URL = cfg["url"].strip(); KEY = cfg["key"].strip()
def api(path, timeout=60):
    req = urllib.request.Request(URL + path); req.add_header("PRIVATE-TOKEN", KEY)
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.load(r)
jobs = api("/retrieve/v1/jobs?limit=100").get("jobs", [])
def ts(s):
    if not s: return None
    return datetime.datetime.fromisoformat(s.replace("Z","+00:00")).replace(tzinfo=None)
lat = []
per_ds = collections.Counter()
for j in jobs:
    try:
        d = api("/retrieve/v1/jobs/" + j["jobID"])
    except Exception: continue
    per_ds[d.get("processID","?")] += 1
    c, f = ts(d.get("created")), ts(d.get("finished"))
    if d.get("status")=="successful" and c and f:
        lat.append(((f-c).total_seconds()/60.0, d.get("created")))
print("=== CDS job 统计 (最近 100 个) ===")
print("数据集分布:")
for k,v in per_ds.most_common(): print("   %-40s %d" % (k, v))
print()
print("成功 job 数: %d" % len(lat))
if lat:
    secs = sorted(x[0] for x in lat)
    print("端到端时延 (created -> finished), 分钟:")
    print("   最快 %.1f   中位 %.1f   平均 %.1f   最慢 %.1f" % (secs[0], statistics.median(secs), statistics.mean(secs), secs[-1]))
    print("   >1h 的比例: %.0f%%   >3h 的比例: %.0f%%" % (100*sum(1 for s in secs if s>60)/len(secs), 100*sum(1 for s in secs if s>180)/len(secs)))
print()
print("=== 吞吐: 成功 job 按小时分布 (最近 24h, 本地时间) ===")
byh = collections.Counter()
for j in jobs:
    if j.get("status")=="successful":
        c = ts(j.get("created"))
        if c: byh[c.strftime("%m-%d %H")] += 1
now = datetime.datetime.utcnow()
for h in sorted(byh)[-26:]: print("   %s   %d" % (h, byh[h]))
print()
print("=== 看到的限流原文 ===")
seen = set()
for lg in ["/root/era5_72all.log", "/root/era5_batch.log", "/root/era5_guard.log"]:
    if not os.path.exists(lg): continue
    s = open(lg, encoding="utf-8", errors="replace").read()
    for m in re.findall(r"[^\n]*(?:rejected|limited|queued requests|Too many|quota)[^\n]*", s, re.I):
        m = m.strip()[:180]
        if m not in seen:
            seen.add(m); print("   [%s] %s" % (os.path.basename(lg), m))
        if len(seen) > 12: break
