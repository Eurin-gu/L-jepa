import json, urllib.request, os, collections
cfg = dict(l.split(":",1) for l in open("/root/.cdsapirc").read().strip().splitlines() if ":" in l)
URL = cfg["url"].strip(); KEY = cfg["key"].strip()
def api(path, timeout=60):
    req = urllib.request.Request(URL + path)
    req.add_header("PRIVATE-TOKEN", KEY)
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.load(r)
done = set()
if os.path.exists("/root/harvested_v2.txt"):
    done = set(l.strip() for l in open("/root/harvested_v2.txt") if l.strip())
jobs = api("/retrieve/v1/jobs?limit=50").get("jobs", [])
print("CDS 队列共 %d 个 job (harvested_v2 记录 %d 个已收割)" % (len(jobs), len(done)))
print()
cnt = collections.Counter()
rows = []
for j in jobs:
    st = j.get("status"); jid = j.get("jobID","?")
    cnt[st] += 1
    rows.append((st, jid, j.get("created","")[:19], jid in done))
print("状态分布: %s" % dict(cnt))
print()
for st, jid, created, harvested in sorted(rows, key=lambda r: r[2], reverse=True)[:40]:
    print("  %-12s %s  %s  %s" % (st, jid[:8], created, "已收割" if harvested else ("*待收割*" if st=="successful" else "未收割")))
print()
unharvested_success = [r for r in rows if r[0]=="successful" and not r[3]]
print("成功但未收割: %d 个  (这些数据会被收割器取回)" % len(unharvested_success))
active = [r for r in rows if r[0] in ("accepted","running")]
print("排队/运行中: %d 个  (占着免费额度 -> 新请求被拒的原因)" % len(active))
