from vmware_client import get_vcenter_list, get_all_data

print("--- vCenter List ---")
for v in get_vcenter_list():
    print(v)

print("")
print("--- Live Connection Test ---")
d = get_all_data()
for s in d["summaries"]:
    name   = s.get("vcenter_name", "?")
    status = s.get("status", "?")
    hosts  = str(s.get("connected_hosts", 0)) + "/" + str(s.get("total_hosts", 0))
    vms    = str(s.get("running_vms", 0))
    err    = str(s.get("error", ""))[:80]
    print(name + " | " + status + " | Hosts: " + hosts + " | VMs: " + vms + " " + err)
