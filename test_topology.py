# _detect_topology: Determine if a VM is Standalone or part of a Cluster
# Uses REAL signals: VM name patterns, name grouping, annotations, applications, keywords

import re
from collections import defaultdict

# Patterns that strongly indicate cluster membership
_CLUSTER_NAME_KEYWORDS = re.compile(
    r'(rac\d|rac[_-]|node[_-]?\d|cluster|master\d*[_-]|worker\d*[_-]|'
    r'member|primary|secondary|replica|standby|dataguard|goldengate|'
    r'fci|wsfc|pacemaker|pcs[_-]|haproxy|keepalived|'
    r'controlplane|etcd[_-]?\d)', re.I
)

# Patterns in annotation that indicate cluster
_CLUSTER_ANN_KEYWORDS = re.compile(
    r'(cluster|rac\b|node\s*\d|dataguard|data\s*guard|golden\s*gate|'
    r'always.?on|failover|ha\s|high.?avail|replica|standby|primary|secondary)', re.I
)

# Applications that are inherently clustered
_CLUSTER_APPS = {'Kubernetes', 'Container Host', 'Rancher', 'Active Directory'}

# These app types commonly run in cluster mode
_CLUSTER_DB_KEYWORDS = re.compile(r'(rac|guard|gate|replica|repl|standby|aog|fci|wsfc|cluster)', re.I)


def _detect_topology_for_all(vms: list) -> None:
    """Enrich each VM dict with 'topology' field: 'Cluster' or 'Standalone'.
    Also adds 'cluster_group' (base name) and 'cluster_role' when applicable."""
    
    # Step 1: Group VMs by base name (strip trailing digits/suffixes)
    suffix_pat = re.compile(r'^(.+?)[_-]?0*(\d{1,3})$')
    groups = defaultdict(list)
    vm_to_base = {}
    
    for vm in vms:
        name = vm.get('name', '')
        m = suffix_pat.match(name)
        if m:
            base = m.group(1).rstrip('-_ ').lower()
            # Avoid grouping by very short bases or just numbers
            if len(base) >= 4:
                groups[base].append(name)
                vm_to_base[name] = base
    
    # Bases with 2+ VMs = potential cluster group
    multi_groups = {base for base, names in groups.items() if len(names) >= 2}
    
    for vm in vms:
        name = vm.get('name', '')
        annotation = vm.get('annotation', '') or ''
        apps = vm.get('applications', [])
        app_names = {a['app'] for a in apps}
        
        topology = 'Standalone'
        cluster_group = None
        cluster_role = None
        cluster_type = None
        
        # Signal 1: VM name contains cluster keywords
        if _CLUSTER_NAME_KEYWORDS.search(name):
            topology = 'Cluster'
            # Try to determine role
            name_lower = name.lower()
            if any(k in name_lower for k in ('master', 'primary', 'controlplane')):
                cluster_role = 'Primary'
            elif any(k in name_lower for k in ('worker', 'secondary', 'replica', 'standby', 'slave')):
                cluster_role = 'Secondary'
            elif 'node' in name_lower:
                cluster_role = 'Node'
        
        # Signal 2: Part of a multi-instance name group
        base = vm_to_base.get(name, '').lower()
        if base in multi_groups:
            if topology != 'Cluster':
                topology = 'Cluster'
            cluster_group = base
        
        # Signal 3: Apps that are inherently clustered
        if app_names & _CLUSTER_APPS:
            topology = 'Cluster'
            if 'Kubernetes' in app_names or 'Rancher' in app_names:
                cluster_type = 'K8s'
            elif 'Active Directory' in app_names:
                cluster_type = 'AD'
        
        # Signal 4: Database + cluster keywords in name
        if app_names & {'Oracle DB', 'MS SQL Server', 'PostgreSQL', 'MySQL/MariaDB', 'Database'}:
            if _CLUSTER_DB_KEYWORDS.search(name):
                topology = 'Cluster'
                if 'Oracle DB' in app_names:
                    if re.search(r'rac', name, re.I):
                        cluster_type = 'Oracle RAC'
                    elif re.search(r'guard|dg', name, re.I):
                        cluster_type = 'Oracle Data Guard'
                    elif re.search(r'gate', name, re.I):
                        cluster_type = 'Oracle GoldenGate'
                elif 'MS SQL Server' in app_names:
                    if re.search(r'aog|ag\d|always', name, re.I):
                        cluster_type = 'SQL Always On'
                    elif re.search(r'fci|wsfc|cluster', name, re.I):
                        cluster_type = 'SQL FCI'
                    elif re.search(r'repl', name, re.I):
                        cluster_type = 'SQL Replication'
        
        # Signal 5: Annotation contains cluster keywords
        if annotation and _CLUSTER_ANN_KEYWORDS.search(annotation):
            if topology != 'Cluster':
                topology = 'Cluster'
        
        # Signal 6: Explicit "standalone" in name
        if re.search(r'standalone|single[_-]?node', name, re.I):
            topology = 'Standalone'
            cluster_type = None
        
        # Determine cluster_type from name patterns if not yet set
        if topology == 'Cluster' and not cluster_type:
            name_lower = name.lower()
            if any(k in name_lower for k in ('ocp', 'openshift')):
                cluster_type = 'OpenShift'
            elif any(k in name_lower for k in ('k8s', 'kube')):
                cluster_type = 'Kubernetes'
            elif 'pacemaker' in name_lower or 'pcs' in name_lower:
                cluster_type = 'Pacemaker HA'
            elif 'cohesity' in name_lower:
                cluster_type = 'Cohesity'
            elif 'isilon' in name_lower:
                cluster_type = 'Isilon'
            elif re.search(r'wsfc|wincluster|win.*cluster', name_lower):
                cluster_type = 'Windows WSFC'
        
        vm['topology'] = topology
        vm['cluster_group'] = cluster_group
        vm['cluster_role'] = cluster_role
        vm['cluster_type'] = cluster_type


# === TEST against real data ===
import requests, json
requests.packages.urllib3.disable_warnings()
s = requests.Session(); s.verify = False
tok = s.post('https://localhost/api/auth/login', json={'username':'admin','password':'caas@2024'}).json()['token']
h = {'Authorization': 'Bearer ' + tok}
vms = s.get('https://localhost/api/vmware/vms', headers=h).json().get('vms', [])

_detect_topology_for_all(vms)

clustered = [v for v in vms if v['topology'] == 'Cluster']
standalone = [v for v in vms if v['topology'] == 'Standalone']

print(f"Total VMs: {len(vms)}")
print(f"Cluster: {len(clustered)}  |  Standalone: {len(standalone)}")

print(f"\n=== CLUSTERED VMs ({len(clustered)}) ===")
for v in sorted(clustered, key=lambda x: (x.get('cluster_type') or '', x['name'])):
    ct = v.get('cluster_type') or ''
    cr = v.get('cluster_role') or ''
    cg = v.get('cluster_group') or ''
    apps = [a['app'] for a in v.get('applications',[])]
    print(f"  {v['name']:45s} type={ct:20s} role={cr:10s} group={cg:30s} apps={apps}")

print(f"\n=== Standalone VMs with DB apps (verify not missed) ===")
for v in standalone:
    apps = [a['app'] for a in v.get('applications',[])]
    if any(a in ['Oracle DB','MS SQL Server','PostgreSQL','MySQL/MariaDB'] for a in apps):
        print(f"  {v['name']:45s} apps={apps}")
