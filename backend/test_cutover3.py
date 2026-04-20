import requests, urllib3, json, time
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

uuid = "ece9a675-ed90-40ba-9d14-4a7c9b29ec2e"  # LaaS-laastest-14

# Step 1: Suspend
print("1. Suspending...")
r1 = s.post(f"https://172.16.146.117/move/v2/plans/{uuid}/suspend", json=None, timeout=15)
print(f"   {r1.status_code}: {r1.text[:200]}")
time.sleep(5)

# Check state
r2 = s.get(f"https://172.16.146.117/move/v2/plans/{uuid}", timeout=10)
meta = r2.json().get("MetaData", {})
print(f"   State: {meta.get('StateString')} VMStateCounts: {meta.get('VMStateCounts')}")

# Step 2: Resume
print("\n2. Resuming...")
r3 = s.post(f"https://172.16.146.117/move/v2/plans/{uuid}/resume", json=None, timeout=15)
print(f"   {r3.status_code}: {r3.text[:200]}")
time.sleep(5)

# Check state
r4 = s.get(f"https://172.16.146.117/move/v2/plans/{uuid}", timeout=10)
meta = r4.json().get("MetaData", {})
print(f"   State: {meta.get('StateString')} VMStateCounts: {meta.get('VMStateCounts')}")

# Step 3: Try start after resume
print("\n3. Attempting start...")
r5 = s.post(f"https://172.16.146.117/move/v2/plans/{uuid}/start", json={"Spec":{"Time":0}}, timeout=15)
print(f"   {r5.status_code}: {r5.text[:300]}")
time.sleep(10)

# Final check
r6 = s.get(f"https://172.16.146.117/move/v2/plans/{uuid}", timeout=10)
meta = r6.json().get("MetaData", {})
print(f"\nFinal: State={meta.get('StateString')} VMStateCounts={meta.get('VMStateCounts')}")
print(f"Schedule: {meta.get('Schedule')}")
