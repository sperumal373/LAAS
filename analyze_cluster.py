import requests, json; requests.packages.urllib3.disable_warnings()
s = requests.Session(); s.verify = False
tok = s.post('https://localhost/api/auth/login', json={'username':'admin','password':'caas@2024'}).json()['token']
h = {'Authorization': 'Bearer ' + tok}
r = s.get('https://localhost/api/vmware/vms', headers=h)
vms = r.json().get('vms', [])

# Show ALL keys of first VM
print("=== ALL VM KEYS ===")
if vms:
    print(json.dumps(list(vms[0].keys()), indent=2))

# Find VMs with RAC, cluster, node patterns in name
print("\n=== CLUSTER-LIKE VM NAMES ===")
import re
cluster_patterns = re.compile(r'(rac|node|cluster|master|worker|member|primary|secondary|replica|slave|standby|dg|guard|aog|ag\d|fci|wsfc|ha\d|hana)', re.I)
suffix_pattern = re.compile(r'(.+?)[_-]?(\d{1,2})$')

# Group VMs by base name (strip trailing digits)
from collections import defaultdict
groups = defaultdict(list)
for vm in vms:
    name = vm.get('name','')
    m = suffix_pattern.match(name)
    if m:
        base = m.group(1).rstrip('-_ ')
        groups[base].append(name)

# Show groups with 2+ members
print("\nVM groups (same base name, multiple instances):")
multi = {k:v for k,v in groups.items() if len(v) >= 2}
for base, names in sorted(multi.items()):
    print(f"  {base}: {names}")

# Show VMs matching cluster keywords
print("\nVMs with cluster keywords in name:")
for vm in vms:
    name = vm.get('name','')
    if cluster_patterns.search(name):
        apps = [a['app'] for a in vm.get('applications',[])]
        print(f"  {name:35s} host={vm.get('host','?'):20s} apps={apps}")

# Check annotation field for cluster info
print("\nVMs with annotations containing cluster keywords:")
for vm in vms:
    ann = vm.get('annotation','')
    if ann and cluster_patterns.search(ann):
        print(f"  {vm['name']:35s} annotation={ann[:80]}")

# Check DRS/HA cluster from host grouping
print("\n=== VM distribution across ESXi hosts ===")
host_groups = defaultdict(list)
for vm in vms:
    host_groups[vm.get('host','?')].append(vm.get('name',''))
for host, vmlist in sorted(host_groups.items()):
    print(f"  {host}: {len(vmlist)} VMs")
