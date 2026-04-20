"""Explore Pure Storage FlashBlade API at 172.17.64.150"""
import requests, json, urllib3
urllib3.disable_warnings()

BASE = "https://172.17.64.150"
API_TOKEN = "T-887e8569-be10-4998-9cd0-3496260f09aa"

# Step 1: Login to get x-auth-token
print("=== Step 1: Login ===")
try:
    r = requests.post(f"{BASE}/api/login", headers={"api-token": API_TOKEN}, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    print(f"Headers: {dict(r.headers)}")
    auth_token = r.headers.get("x-auth-token", "")
    print(f"x-auth-token: {auth_token[:40]}...")
except Exception as e:
    print(f"Login failed: {e}")
    auth_token = ""

if not auth_token:
    print("No auth token, trying /api/api_version first...")
    try:
        r = requests.get(f"{BASE}/api/api_version", verify=False, timeout=10)
        print(f"API versions: {r.json()}")
        versions = r.json().get("versions", r.json().get("version", []))
        print(f"Available versions: {versions}")
        # Try versioned login
        for ver in reversed(versions[-5:]) if versions else ["2.0", "1.12"]:
            print(f"\nTrying /api/{ver}/login ...")
            try:
                r2 = requests.post(f"{BASE}/api/{ver}/login", headers={"api-token": API_TOKEN}, verify=False, timeout=15)
                print(f"  Status: {r2.status_code}")
                tok = r2.headers.get("x-auth-token", "")
                if tok:
                    auth_token = tok
                    print(f"  Got token via /api/{ver}/login!")
                    break
            except Exception as e2:
                print(f"  Failed: {e2}")
    except Exception as e:
        print(f"api_version failed: {e}")

if not auth_token:
    print("FAILED to get auth token")
    exit()

HDR = {"x-auth-token": auth_token}

# Step 2: Discover API version
print("\n=== Step 2: API Version ===")
try:
    r = requests.get(f"{BASE}/api/api_version", headers=HDR, verify=False, timeout=10)
    print(json.dumps(r.json(), indent=2))
    versions = r.json().get("versions", r.json().get("version", []))
    api_ver = str(versions[-1]) if versions else "2.0"
    print(f"Using API version: {api_ver}")
except Exception as e:
    print(f"Failed: {e}")
    api_ver = "2.0"

# Step 3: Arrays (system info)
print(f"\n=== Step 3: Arrays (system info) /api/{api_ver}/arrays ===")
try:
    r = requests.get(f"{BASE}/api/{api_ver}/arrays", headers=HDR, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    data = r.json()
    print(json.dumps(data, indent=2)[:2000])
except Exception as e:
    print(f"Failed: {e}")

# Step 4: Arrays space
print(f"\n=== Step 4: Arrays space ===")
try:
    r = requests.get(f"{BASE}/api/{api_ver}/arrays?space=true", headers=HDR, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    print(json.dumps(r.json(), indent=2)[:2000])
except Exception as e:
    print(f"Failed: {e}")

# Step 5: File systems
print(f"\n=== Step 5: File Systems ===")
try:
    r = requests.get(f"{BASE}/api/{api_ver}/file-systems", headers=HDR, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    print(f"Count: {len(items) if isinstance(items, list) else '?'}")
    if isinstance(items, list) and items:
        print("First 3:")
        for fs in items[:3]:
            print(f"  {fs.get('name','?')} — {fs.get('space',{})}")
except Exception as e:
    print(f"Failed: {e}")

# Step 6: Buckets (S3)
print(f"\n=== Step 6: Buckets (S3) ===")
try:
    r = requests.get(f"{BASE}/api/{api_ver}/buckets", headers=HDR, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    print(f"Count: {len(items) if isinstance(items, list) else '?'}")
    if isinstance(items, list) and items:
        print("First 3:")
        for b in items[:3]:
            print(f"  {b.get('name','?')} — account={b.get('account',{}).get('name','?')}")
except Exception as e:
    print(f"Failed: {e}")

# Step 7: Blades
print(f"\n=== Step 7: Blades ===")
try:
    r = requests.get(f"{BASE}/api/{api_ver}/blades", headers=HDR, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    print(f"Count: {len(items) if isinstance(items, list) else '?'}")
    if isinstance(items, list):
        for b in items[:5]:
            print(f"  {b.get('name','?')} — status={b.get('status','')} raw_cap={b.get('raw_capacity','?')}")
except Exception as e:
    print(f"Failed: {e}")

# Step 8: Network interfaces
print(f"\n=== Step 8: Network Interfaces ===")
try:
    r = requests.get(f"{BASE}/api/{api_ver}/network-interfaces", headers=HDR, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    print(f"Count: {len(items) if isinstance(items, list) else '?'}")
    if isinstance(items, list):
        for ni in items[:5]:
            print(f"  {ni.get('name','?')} — {ni.get('address','?')} type={ni.get('type','?')}")
except Exception as e:
    print(f"Failed: {e}")

# Step 9: Object store accounts
print(f"\n=== Step 9: Object Store Accounts ===")
try:
    r = requests.get(f"{BASE}/api/{api_ver}/object-store-accounts", headers=HDR, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    print(f"Count: {len(items) if isinstance(items, list) else '?'}")
    if isinstance(items, list):
        for a in items[:5]:
            print(f"  {a.get('name','?')} — created={a.get('created','?')}")
except Exception as e:
    print(f"Failed: {e}")

# Step 10: Alerts
print(f"\n=== Step 10: Alerts ===")
try:
    r = requests.get(f"{BASE}/api/{api_ver}/alerts?filter=state='open'", headers=HDR, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    print(f"Count: {len(items) if isinstance(items, list) else '?'}")
    if isinstance(items, list):
        for a in items[:5]:
            print(f"  {a.get('severity','?')}: {a.get('summary','?')}")
except Exception as e:
    print(f"Failed: {e}")

# Step 11: Performance
print(f"\n=== Step 11: Arrays Performance ===")
try:
    r = requests.get(f"{BASE}/api/{api_ver}/arrays/performance", headers=HDR, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    print(json.dumps(r.json(), indent=2)[:2000])
except Exception as e:
    print(f"Failed: {e}")

# Step 12: DNS, SMTP, NTP
print(f"\n=== Step 12: DNS ===")
try:
    r = requests.get(f"{BASE}/api/{api_ver}/dns", headers=HDR, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    print(json.dumps(r.json(), indent=2)[:500])
except Exception as e:
    print(f"Failed: {e}")

# Step 13: Policies
print(f"\n=== Step 13: Policies ===")
try:
    r = requests.get(f"{BASE}/api/{api_ver}/policies", headers=HDR, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    print(f"Count: {len(items) if isinstance(items, list) else '?'}")
    if isinstance(items, list):
        for p in items[:5]:
            print(f"  {p.get('name','?')} — enabled={p.get('enabled','?')}")
except Exception as e:
    print(f"Failed: {e}")

# Step 14: NFS exports
print(f"\n=== Step 14: NFS Export Policies ===")
try:
    r = requests.get(f"{BASE}/api/{api_ver}/file-system-snapshots", headers=HDR, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    print(f"File-system snapshots count: {len(items) if isinstance(items, list) else '?'}")
except Exception as e:
    print(f"Failed: {e}")

print("\n=== DONE ===")
