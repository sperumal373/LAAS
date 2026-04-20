import requests, json, urllib3
urllib3.disable_warnings()

# Veeam B&R REST API (v1.1+) - port 9419
BASE = "https://172.17.74.52:9419"
USER = "sdxtest\\sekhar"
PASS = "Snaveen_373"

# 1. Auth - get token
print("=== AUTH (port 9419) ===")
try:
    r = requests.post(f"{BASE}/api/oauth2/token",
        data={"grant_type": "password", "username": USER, "password": PASS},
        headers={"x-api-version": "1.1-rev2"},
        verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    if r.ok:
        tok = r.json()
        print(f"Token type: {tok.get('token_type')}")
        print(f"Access token: {tok.get('access_token','')[:40]}...")
        AT = f"{tok['token_type']} {tok['access_token']}"
        HDR = {"Authorization": AT, "x-api-version": "1.1-rev2", "Accept": "application/json"}

        # 2. Server info
        r2 = requests.get(f"{BASE}/api/v1/serverInfo", headers=HDR, verify=False, timeout=15)
        print(f"\n=== SERVER INFO status={r2.status_code} ===")
        if r2.ok: print(json.dumps(r2.json(), indent=2, default=str)[:500])

        # 3. Jobs
        r3 = requests.get(f"{BASE}/api/v1/jobs", headers=HDR, verify=False, timeout=15)
        print(f"\n=== JOBS status={r3.status_code} ===")
        if r3.ok:
            jobs = r3.json()
            data = jobs.get("data", jobs) if isinstance(jobs, dict) else jobs
            if isinstance(data, list):
                print(f"Count: {len(data)}")
                for j in data[:5]: print(json.dumps({k: j.get(k) for k in ['id','name','type','isDisabled','description'] if k in j}, default=str))
            else:
                print(json.dumps(jobs, indent=2, default=str)[:600])

        # 4. Backup sessions
        r4 = requests.get(f"{BASE}/api/v1/sessions", headers=HDR, params={"limit": 20, "orderAsc": False}, verify=False, timeout=15)
        print(f"\n=== SESSIONS status={r4.status_code} ===")
        if r4.ok:
            sess = r4.json()
            data = sess.get("data", sess) if isinstance(sess, dict) else sess
            if isinstance(data, list):
                print(f"Count: {len(data)}")
                for s in data[:5]: print(json.dumps({k: s.get(k) for k in ['id','name','sessionType','state','result','creationTime','endTime'] if k in s}, default=str))
            else:
                print(json.dumps(sess, indent=2, default=str)[:600])

        # 5. Repositories
        r5 = requests.get(f"{BASE}/api/v1/backupInfrastructure/repositories", headers=HDR, verify=False, timeout=15)
        print(f"\n=== REPOSITORIES status={r5.status_code} ===")
        if r5.ok:
            repos = r5.json()
            data = repos.get("data", repos) if isinstance(repos, dict) else repos
            if isinstance(data, list):
                print(f"Count: {len(data)}")
                for r6 in data[:3]: print(json.dumps({k: r6.get(k) for k in ['id','name','type','capacityGB','freeGB','usedSpaceGB'] if k in r6}, default=str))
    else:
        print(f"Body: {r.text[:500]}")
except Exception as e:
    print(f"Port 9419 failed: {e}")

# Also try Enterprise Manager port 9398
print("\n\n=== TRY ENTERPRISE MANAGER (port 9398) ===")
BASE2 = "https://172.17.74.52:9398"
try:
    r = requests.post(f"{BASE2}/api/sessionMngr/?v=latest",
        headers={"Authorization": f"Basic {__import__('base64').b64encode(f'{USER}:{PASS}'.encode()).decode()}"},
        verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    if r.status_code in (200,201):
        print(f"Headers: {dict(r.headers)}")
        ses_id = r.headers.get("X-RestSvcSessionId","")
        print(f"Session ID: {ses_id[:40]}...")
    else:
        print(f"Body: {r.text[:300]}")
except Exception as e:
    print(f"Port 9398 failed: {e}")
