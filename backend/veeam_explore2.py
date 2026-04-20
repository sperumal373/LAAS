import requests, json, urllib3
urllib3.disable_warnings()

BASE = "https://172.17.74.52:9419"
USER = "sdxtest\\sekhar"
PASS = "Snaveen_373"

# Auth
r = requests.post(f"{BASE}/api/oauth2/token",
    data={"grant_type": "password", "username": USER, "password": PASS},
    headers={"x-api-version": "1.1-rev2"},
    verify=False, timeout=30)
tok = r.json()
AT = f"{tok['token_type']} {tok['access_token']}"
HDR = {"Authorization": AT, "x-api-version": "1.1-rev2", "Accept": "application/json"}
print("Auth OK")

# Jobs
print("\n=== JOBS ===")
try:
    r = requests.get(f"{BASE}/api/v1/jobs", headers=HDR, verify=False, timeout=60)
    print(f"Status: {r.status_code}")
    if r.ok:
        jobs = r.json()
        data = jobs.get("data", jobs) if isinstance(jobs, dict) else jobs
        if isinstance(data, list):
            print(f"Count: {len(data)}")
            for j in data[:5]:
                print(json.dumps({k: j.get(k) for k in ['id','name','type','isDisabled','virtualMachines'] if k in j}, default=str))
        else:
            print(str(jobs)[:800])
except Exception as e:
    print(f"Failed: {e}")

# Sessions
print("\n=== SESSIONS ===")
try:
    r = requests.get(f"{BASE}/api/v1/sessions", headers=HDR, params={"limit": 10}, verify=False, timeout=60)
    print(f"Status: {r.status_code}")
    if r.ok:
        sess = r.json()
        data = sess.get("data", sess) if isinstance(sess, dict) else sess
        if isinstance(data, list):
            print(f"Count: {len(data)}")
            for s in data[:5]:
                print(json.dumps({k: s.get(k) for k in ['id','name','sessionType','state','result','creationTime','endTime','progressPercent'] if k in s}, default=str))
        else:
            print(str(sess)[:800])
except Exception as e:
    print(f"Failed: {e}")

# Repositories
print("\n=== REPOSITORIES ===")
try:
    r = requests.get(f"{BASE}/api/v1/backupInfrastructure/repositories", headers=HDR, verify=False, timeout=60)
    print(f"Status: {r.status_code}")
    if r.ok:
        repos = r.json()
        data = repos.get("data", repos) if isinstance(repos, dict) else repos
        if isinstance(data, list):
            print(f"Count: {len(data)}")
            for rp in data[:5]:
                print(json.dumps({k: rp.get(k) for k in ['id','name','type','capacityGB','freeGB','usedSpaceGB','description'] if k in rp}, default=str))
        else:
            print(str(repos)[:800])
except Exception as e:
    print(f"Failed: {e}")

# Managed servers
print("\n=== MANAGED SERVERS ===")
try:
    r = requests.get(f"{BASE}/api/v1/backupInfrastructure/managedServers", headers=HDR, verify=False, timeout=60)
    print(f"Status: {r.status_code}")
    if r.ok:
        ms = r.json()
        data = ms.get("data", ms) if isinstance(ms, dict) else ms
        if isinstance(data, list):
            print(f"Count: {len(data)}")
            for m in data[:5]:
                print(json.dumps({k: m.get(k) for k in ['id','name','type','description'] if k in m}, default=str))
except Exception as e:
    print(f"Failed: {e}")

# Proxies
print("\n=== PROXIES ===")
try:
    r = requests.get(f"{BASE}/api/v1/backupInfrastructure/proxies", headers=HDR, verify=False, timeout=60)
    print(f"Status: {r.status_code}")
    if r.ok:
        px = r.json()
        data = px.get("data", px) if isinstance(px, dict) else px
        if isinstance(data, list):
            print(f"Count: {len(data)}")
            for p in data[:3]:
                print(json.dumps({k: p.get(k) for k in ['id','name','type','server','maxTaskCount'] if k in p}, default=str))
except Exception as e:
    print(f"Failed: {e}")
