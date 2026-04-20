import requests, json, urllib3
urllib3.disable_warnings()

BASE = "https://172.17.74.52:9419"
API_VER = "1.3-rev1"

# Auth with exact parameters user specified
print("=== AUTH ===")
r = requests.post(f"{BASE}/api/oauth2/token",
    data={"grant_type": "password", "username": "sekhar", "password": "Snaveen_373"},
    headers={"x-api-version": API_VER, "Content-Type": "application/x-www-form-urlencoded"},
    verify=False, timeout=30)
print(f"Status: {r.status_code}")
if not r.ok:
    print(f"Body: {r.text[:500]}")
    exit()

tok = r.json()
AT = f"{tok['token_type']} {tok['access_token']}"
HDR = {"Authorization": AT, "x-api-version": API_VER, "Accept": "application/json"}
print(f"Token OK: {tok['access_token'][:30]}...")

# 1. Server info
r2 = requests.get(f"{BASE}/api/v1/serverInfo", headers=HDR, verify=False, timeout=30)
print(f"\n=== SERVER INFO ({r2.status_code}) ===")
if r2.ok: print(json.dumps(r2.json(), indent=2, default=str)[:400])

# 2. Jobs
r3 = requests.get(f"{BASE}/api/v1/jobs", headers=HDR, verify=False, timeout=60)
print(f"\n=== JOBS ({r3.status_code}) ===")
if r3.ok:
    jobs = r3.json()
    data = jobs.get("data", jobs) if isinstance(jobs, dict) else jobs
    if isinstance(data, list):
        print(f"Count: {len(data)}")
        for j in data[:5]: print(json.dumps({k: j.get(k) for k in ['id','name','type','isDisabled','virtualMachines'] if k in j}, default=str))
    else:
        print(json.dumps(jobs, indent=2, default=str)[:800])

# 3. Sessions
r4 = requests.get(f"{BASE}/api/v1/sessions", headers=HDR, params={"limit": 20}, verify=False, timeout=60)
print(f"\n=== SESSIONS ({r4.status_code}) ===")
if r4.ok:
    sess = r4.json()
    data = sess.get("data", sess) if isinstance(sess, dict) else sess
    if isinstance(data, list):
        print(f"Count: {len(data)}")
        for s in data[:5]: print(json.dumps({k: s.get(k) for k in ['id','name','sessionType','state','result','creationTime','endTime'] if k in s}, default=str))
    else:
        print(json.dumps(sess, indent=2, default=str)[:800])

# 4. Repositories
r5 = requests.get(f"{BASE}/api/v1/backupInfrastructure/repositories", headers=HDR, verify=False, timeout=60)
print(f"\n=== REPOSITORIES ({r5.status_code}) ===")
if r5.ok:
    repos = r5.json()
    data = repos.get("data", repos) if isinstance(repos, dict) else repos
    if isinstance(data, list):
        print(f"Count: {len(data)}")
        for rr in data[:5]: print(json.dumps({k: rr.get(k) for k in ['id','name','type','capacityGB','freeGB','usedSpaceGB','description'] if k in rr}, default=str))
    else:
        print(json.dumps(repos, indent=2, default=str)[:800])

# 5. Managed Servers
r6 = requests.get(f"{BASE}/api/v1/backupInfrastructure/managedServers", headers=HDR, verify=False, timeout=60)
print(f"\n=== MANAGED SERVERS ({r6.status_code}) ===")
if r6.ok:
    ms = r6.json()
    data = ms.get("data", ms) if isinstance(ms, dict) else ms
    if isinstance(data, list):
        print(f"Count: {len(data)}")
        for m in data[:5]: print(json.dumps({k: m.get(k) for k in ['id','name','type','description'] if k in m}, default=str))
    else:
        print(json.dumps(ms, indent=2, default=str)[:500])

# 6. Proxies
r7 = requests.get(f"{BASE}/api/v1/backupInfrastructure/proxies", headers=HDR, verify=False, timeout=60)
print(f"\n=== PROXIES ({r7.status_code}) ===")
if r7.ok:
    px = r7.json()
    data = px.get("data", px) if isinstance(px, dict) else px
    if isinstance(data, list):
        print(f"Count: {len(data)}")
        for pp in data[:3]: print(json.dumps({k: pp.get(k) for k in ['id','name','type','server'] if k in pp}, default=str))
