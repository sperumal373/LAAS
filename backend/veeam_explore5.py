import requests, json, urllib3
urllib3.disable_warnings()

BASE = "https://172.17.74.52:9419"
API_VER = "1.3-rev1"

r = requests.post(f"{BASE}/api/oauth2/token",
    data={"grant_type": "password", "username": "sekhar", "password": "Snaveen_373"},
    headers={"x-api-version": API_VER, "Content-Type": "application/x-www-form-urlencoded"},
    verify=False, timeout=30)
tok = r.json()
AT = f"{tok['token_type']} {tok['access_token']}"
HDR = {"Authorization": AT, "x-api-version": API_VER, "Accept": "application/json"}

# 1. Backup objects  
r1 = requests.get(f"{BASE}/api/v1/backupObjects", headers=HDR, params={"limit": 50}, verify=False, timeout=60)
print(f"=== BACKUP OBJECTS ({r1.status_code}) ===")
if r1.ok:
    bo = r1.json()
    data = bo.get("data", bo) if isinstance(bo, dict) else bo
    if isinstance(data, list):
        print(f"Count: {len(data)}")
        for o in data[:5]: print(json.dumps({k: o.get(k) for k in ['objectId','name','type','platformName','viType','size','path','jobId'] if k in o}, default=str))

# 2. Restore points
r2 = requests.get(f"{BASE}/api/v1/restorePoints", headers=HDR, params={"limit": 20}, verify=False, timeout=60)
print(f"\n=== RESTORE POINTS ({r2.status_code}) ===")
if r2.ok:
    rp = r2.json()
    data = rp.get("data", rp) if isinstance(rp, dict) else rp
    if isinstance(data, list):
        print(f"Count: {len(data)}")
        for p in data[:5]: print(json.dumps({k: p.get(k) for k in ['id','name','creationTime','backupId','platformName','platformId'] if k in p}, default=str))

# 3. One job detail
r3 = requests.get(f"{BASE}/api/v1/jobs", headers=HDR, verify=False, timeout=60)
if r3.ok:
    jobs = r3.json().get("data", r3.json()) if isinstance(r3.json(), dict) else r3.json()
    if isinstance(jobs, list) and len(jobs) > 0:
        jid = jobs[0]["id"]
        # Get job details
        r4 = requests.get(f"{BASE}/api/v1/jobs/{jid}", headers=HDR, verify=False, timeout=30)
        print(f"\n=== JOB DETAIL ({r4.status_code}) ===")
        if r4.ok:
            jd = r4.json()
            keys = ['id','name','type','isDisabled','schedule','storage','guestProcessing']
            print(json.dumps({k: jd.get(k) for k in keys if k in jd}, indent=2, default=str)[:600])

# 4. Job stats summary
active = sum(1 for j in jobs if not j.get("isDisabled"))
disabled = sum(1 for j in jobs if j.get("isDisabled"))
types = {}
for j in jobs:
    t = j.get("type","?")
    types[t] = types.get(t,0) + 1
print(f"\n=== JOB SUMMARY ===")
print(f"Total={len(jobs)} Active={active} Disabled={disabled}")
for t,c in sorted(types.items(), key=lambda x:-x[1]): print(f"  {t}: {c}")

# 5. Repository stats detail
r5 = requests.get(f"{BASE}/api/v1/backupInfrastructure/repositories/states", headers=HDR, verify=False, timeout=60)
print(f"\n=== REPO STATES ({r5.status_code}) ===")
if r5.ok:
    rs = r5.json()
    data = rs.get("data", rs) if isinstance(rs, dict) else rs
    if isinstance(data, list):
        for r6 in data[:5]: print(json.dumps({k: r6.get(k) for k in list(r6.keys())[:10] if k in r6}, default=str))
    else:
        print(json.dumps(rs, indent=2, default=str)[:600])
