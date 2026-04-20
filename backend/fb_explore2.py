"""FlashBlade explore2 — capacity, FS details, bucket details"""
import requests, json, urllib3
urllib3.disable_warnings()

BASE = "https://172.17.64.150"
API_TOKEN = "T-887e8569-be10-4998-9cd0-3496260f09aa"

r = requests.post(f"{BASE}/api/login", headers={"api-token": API_TOKEN}, verify=False, timeout=15)
auth_token = r.headers.get("x-auth-token", "")
HDR = {"x-auth-token": auth_token}
V = "2.4"

# Capacity: arrays/space
print("=== Arrays Space (v1.12 - FlashBlade style) ===")
for ver in ["1.12", "1.11", "2.4"]:
    try:
        r = requests.get(f"{BASE}/api/{ver}/arrays/space", headers=HDR, verify=False, timeout=15)
        print(f"  /api/{ver}/arrays/space → {r.status_code}")
        if r.status_code == 200:
            print(json.dumps(r.json(), indent=2)[:2000])
            break
    except Exception as e:
        print(f"  Failed: {e}")

# File systems with details
print("\n=== All File Systems ===")
r = requests.get(f"{BASE}/api/{V}/file-systems", headers=HDR, verify=False, timeout=15)
fss = r.json().get("items", [])
print(f"Total: {len(fss)}")
total_prov = 0
for fs in fss:
    prov = fs.get("provisioned", 0) or 0
    total_prov += prov
    sp = fs.get("space", {})
    print(f"  {fs.get('name','?'):30s}  prov={prov/(1024**3):.1f}GB  virtual={sp.get('virtual',0)/(1024**3):.2f}GB  unique={sp.get('unique',0)/(1024**3):.2f}GB  DR={sp.get('data_reduction',0):.1f}  nfs={fs.get('nfs_enabled',False)}  smb={fs.get('smb_enabled',False)}")
print(f"Total provisioned: {total_prov/(1024**4):.2f} TB")

# Buckets with details
print("\n=== All Buckets ===")
r = requests.get(f"{BASE}/api/{V}/buckets", headers=HDR, verify=False, timeout=15)
bkts = r.json().get("items", [])
print(f"Total: {len(bkts)}")
for b in bkts:
    sp = b.get("space", {})
    print(f"  {b.get('name','?'):30s}  account={b.get('account',{}).get('name','?'):15s}  virtual={sp.get('virtual',0)/(1024**3):.2f}GB  unique={sp.get('unique',0)/(1024**3):.2f}GB  versioning={b.get('versioning','?')}")

# Hardware info
print("\n=== Hardware ===")
r = requests.get(f"{BASE}/api/{V}/hardware", headers=HDR, verify=False, timeout=15)
if r.status_code == 200:
    hw = r.json().get("items", [])
    print(f"Count: {len(hw)}")
    for h in hw[:10]:
        print(f"  {h.get('name','?'):25s}  type={h.get('type','?'):10s}  status={h.get('status','?')}")
else:
    print(f"Status: {r.status_code}")

# Blade details
print("\n=== Blades Details ===")
r = requests.get(f"{BASE}/api/{V}/blades", headers=HDR, verify=False, timeout=15)
blades = r.json().get("items", [])
healthy = sum(1 for b in blades if b.get("status")=="healthy")
unused = sum(1 for b in blades if b.get("status")=="unused")
total_raw = sum(b.get("raw_capacity",0) for b in blades)
print(f"Total blades: {len(blades)}, Healthy: {healthy}, Unused: {unused}")
print(f"Total raw capacity: {total_raw/(1024**4):.2f} TB")
for b in blades:
    if b.get("status") == "healthy":
        print(f"  {b.get('name','?')} — raw={b.get('raw_capacity',0)/(1024**4):.2f}TB  target={b.get('target','?')}")

# Object store users
print("\n=== Object Store Users ===")
r = requests.get(f"{BASE}/api/{V}/object-store-users", headers=HDR, verify=False, timeout=15)
if r.status_code == 200:
    users = r.json().get("items", [])
    print(f"Count: {len(users)}")
    for u in users[:10]:
        print(f"  {u.get('name','?')}")
else:
    print(f"Status: {r.status_code}")

# Snapshot policies
print("\n=== Snapshot Policies ===")
r = requests.get(f"{BASE}/api/{V}/policies", headers=HDR, verify=False, timeout=15)
pols = r.json().get("items", [])
for pol in pols:
    print(f"  {pol.get('name','?')} — enabled={pol.get('enabled',False)} rules={len(pol.get('rules',[]))}")

print("\n=== DONE ===")
