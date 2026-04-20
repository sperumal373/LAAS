import requests, json, urllib3
urllib3.disable_warnings()

BASE = "https://172.17.74.52:9419"
USER = "sdxtest\\sekhar"
PASS = "Snaveen_373"

r = requests.post(f"{BASE}/api/oauth2/token",
    data={"grant_type": "password", "username": USER, "password": PASS},
    headers={"x-api-version": "1.1-rev2"}, verify=False, timeout=30)
tok = r.json()
HDR = {"Authorization": f"{tok['token_type']} {tok['access_token']}", "x-api-version": "1.1-rev2", "Accept": "application/json"}

# Repository states (capacity)
print("=== REPO STATES ===")
try:
    r = requests.get(f"{BASE}/api/v1/backupInfrastructure/repositories/states", headers=HDR, verify=False, timeout=60)
    print(f"Status: {r.status_code}")
    if r.ok:
        data = r.json().get("data", r.json()) if isinstance(r.json(), dict) else r.json()
        if isinstance(data, list):
            print(f"Count: {len(data)}")
            for rp in data[:5]: print(json.dumps(rp, indent=2, default=str)[:400])
        else:
            print(str(r.json())[:800])
except Exception as e:
    print(f"Failed: {e}")

# Backup Objects (protected VMs)
print("\n=== BACKUP OBJECTS ===")
try:
    r = requests.get(f"{BASE}/api/v1/backupObjects", headers=HDR, params={"limit": 50}, verify=False, timeout=60)
    print(f"Status: {r.status_code}")
    if r.ok:
        data = r.json().get("data", r.json()) if isinstance(r.json(), dict) else r.json()
        if isinstance(data, list):
            print(f"Count: {len(data)}")
            for o in data[:5]:
                print(json.dumps({k: o.get(k) for k in ['objectId','name','type','platformName','viType','jobId'] if k in o}, default=str))
except Exception as e:
    print(f"Failed: {e}")

# Restore points
print("\n=== RESTORE POINTS ===")
try:
    r = requests.get(f"{BASE}/api/v1/objectRestorePoints", headers=HDR, params={"limit": 10}, verify=False, timeout=60)
    print(f"Status: {r.status_code}")
    if r.ok:
        data = r.json().get("data", r.json()) if isinstance(r.json(), dict) else r.json()
        if isinstance(data, list):
            print(f"Count: {len(data)}")
            for rp in data[:5]:
                print(json.dumps({k: rp.get(k) for k in ['id','name','platformName','creationTime','backupId'] if k in rp}, default=str))
except Exception as e:
    print(f"Failed: {e}")

# Job states
print("\n=== JOB STATES ===")
try:
    r = requests.get(f"{BASE}/api/v1/jobs/states", headers=HDR, verify=False, timeout=60)
    print(f"Status: {r.status_code}")
    if r.ok:
        data = r.json().get("data", r.json()) if isinstance(r.json(), dict) else r.json()
        if isinstance(data, list):
            print(f"Count: {len(data)}")
            for js in data[:5]:
                print(json.dumps({k: js.get(k) for k in ['id','name','type','status','lastResult','lastRun','nextRun'] if k in js}, default=str))
        else:
            print(str(r.json())[:800])
except Exception as e:
    print(f"Failed: {e}")

# Credentials (for managed servers)
print("\n=== CREDENTIALS ===")
try:
    r = requests.get(f"{BASE}/api/v1/credentials", headers=HDR, verify=False, timeout=60)
    print(f"Status: {r.status_code}")
    if r.ok:
        data = r.json().get("data", r.json()) if isinstance(r.json(), dict) else r.json()
        if isinstance(data, list):
            print(f"Count: {len(data)}")
except Exception as e:
    print(f"Failed: {e}")
