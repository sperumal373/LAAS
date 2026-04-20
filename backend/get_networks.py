import requests, urllib3, json
urllib3.disable_warnings()
VC = "https://172.17.168.212"
s = requests.Session()
s.verify = False
r = s.post(f"{VC}/api/session", auth=("administrator@vsphere.local", "Sdxdc@168-212"), timeout=10)
s.headers["vmware-api-session-id"] = r.text.strip('"')

# Get VM NIC details
r2 = s.get(f"{VC}/api/vcenter/vm/vm-268873")
vm = r2.json()
for nid, nic in vm.get("nics", {}).items():
    backing = nic.get("backing", {})
    print(f"NIC {nid}: type={backing.get('type')} port={backing.get('distributed_port')} switch={backing.get('distributed_switch_uuid')}")
    # Get the port group
    if backing.get("type") == "DISTRIBUTED_PORT_GROUP":
        # Need to find portgroup name/id
        pass

# List networks
r3 = s.get(f"{VC}/api/vcenter/network")
print(f"\nNetworks ({len(r3.json())}):")
for n in r3.json():
    print(f"  {n.get('name'):40s} type={n.get('type'):25s} id={n.get('network')}")
