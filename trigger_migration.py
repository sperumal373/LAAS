"""
Trigger migration of sdxdclmigration to Hyper-V via SCVMM
Usage: python trigger_migration.py
"""
import requests, json, sys, time

BASE = "http://localhost:8001"

# 1. Login
r = requests.post(f"{BASE}/api/auth/login", json={"username":"admin","password":"caas@2024"})
r.raise_for_status()
token = r.json()["token"]
hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print(f"[1] Logged in OK")

# 2. Create plan
plan = {
    "plan_name": "sdxdclmigration-hyperv-test",
    "source_platform": "vmware",
    "source_vcenter": {"vcenter_id": "172.17.168.212", "vcenter_name": "vCenter-168-212"},
    "target_platform": "hyperv",
    "target_detail": {"host_id": "1", "host_name": "Microsoft HYP-V", "host": "172.17.66.35"},
    "vm_list": [{"name": "sdxdclmigration", "cpu": 2, "ram_mb": 4096, "disk_gb": 6, "os": "Linux"}],
    "network_mapping": [{"source": "default", "target": "default"}],
    "storage_mapping": [{"source": "default", "target": "F:\\Hyper-V-VM's"}],
    "migration_tool": "SCVMM V2V",
    "notes": "Test migration: sdxdclmigration (2vCPU/6GB disk) on ESXi 172.17.65.84"
}
r = requests.post(f"{BASE}/api/migration/plans", headers=hdrs, json=plan)
r.raise_for_status()
plan_id = r.json()["plan_id"]
print(f"[2] Plan created: id={plan_id}")

# 3. Skip preflight - go directly to approved
r = requests.patch(f"{BASE}/api/migration/plans/{plan_id}/status",
                   headers=hdrs, json={"status": "approved"})
r.raise_for_status()
print(f"[3] Plan approved")

# 4. Execute migration
r = requests.post(f"{BASE}/api/migration/plans/{plan_id}/execute",
                  headers=hdrs, json={"target": "hyperv"})
r.raise_for_status()
print(f"[4] Migration TRIGGERED: {r.json()}")
print(f"\nMonitor at: http://localhost:3000 -> Migration Plans -> id={plan_id}")
print(f"Or poll:    GET {BASE}/api/migration/plans/{plan_id}")
