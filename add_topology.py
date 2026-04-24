# Add _detect_topology_for_all to vmware_client.py
path = r"C:\caas-dashboard\backend\vmware_client.py"
content = open(path, "r", encoding="utf-8").read()

# Check if already added
if '_detect_topology_for_all' in content:
    print("Already has topology detection")
    exit()

# Add the function before get_all_data
TOPO_CODE = '''
#  Topology Detection (Standalone vs Cluster) 
_CLUSTER_NAME_KW = re.compile(
    r'(rac\\d|rac[_-]|node[_-]?\\d|cluster|master\\d*[_-]|worker\\d*[_-]|'
    r'member|primary|secondary|replica|standby|dataguard|goldengate|'
    r'fci|wsfc|pacemaker|pcs[_-]|haproxy|keepalived|controlplane|etcd[_-]?\\d)', re.I
)
_CLUSTER_ANN_KW = re.compile(
    r'(cluster|rac\\b|node\\s*\\d|dataguard|data\\s*guard|golden\\s*gate|'
    r'always.?on|failover|ha\\s|high.?avail|replica|standby|primary|secondary)', re.I
)
_CLUSTER_APPS = {'Kubernetes', 'Container Host', 'Rancher', 'Active Directory'}
_CLUSTER_DB_KW = re.compile(r'(rac|guard|gate|replica|repl|standby|aog|fci|wsfc|cluster)', re.I)

def _detect_topology_for_all(vms: list) -> None:
    suffix_pat = re.compile(r'^(.+?)[_-]?0*(\\d{1,3})$')
    groups = {}
    vm_to_base = {}
    for vm in vms:
        name = vm.get('name', '')
        m = suffix_pat.match(name)
        if m:
            base = m.group(1).rstrip('-_ ').lower()
            if len(base) >= 4:
                groups.setdefault(base, []).append(name)
                vm_to_base[name] = base
    multi_groups = {b for b, n in groups.items() if len(n) >= 2}

    for vm in vms:
        name = vm.get('name', '')
        ann = vm.get('annotation', '') or ''
        apps = {a['app'] for a in vm.get('applications', [])}
        topo, cgroup, crole, ctype = 'Standalone', None, None, None
        nl = name.lower()

        # Signal 1: Name keywords
        if _CLUSTER_NAME_KW.search(name):
            topo = 'Cluster'
            if any(k in nl for k in ('master', 'primary', 'controlplane')): crole = 'Primary'
            elif any(k in nl for k in ('worker', 'secondary', 'replica', 'standby')): crole = 'Secondary'
            elif 'node' in nl: crole = 'Node'

        # Signal 2: Multi-instance name group
        base = vm_to_base.get(name, '').lower()
        if base in multi_groups:
            topo = 'Cluster'
            cgroup = base

        # Signal 3: Inherently clustered apps
        if apps & _CLUSTER_APPS:
            topo = 'Cluster'
            if apps & {'Kubernetes', 'Rancher'}: ctype = ctype or 'K8s'
            elif 'Active Directory' in apps: ctype = ctype or 'AD'

        # Signal 4: Database + cluster keywords
        db_apps = apps & {'Oracle DB', 'MS SQL Server', 'PostgreSQL', 'MySQL/MariaDB', 'Database'}
        if db_apps and _CLUSTER_DB_KW.search(name):
            topo = 'Cluster'
            if 'Oracle DB' in apps:
                if re.search(r'\\brac\\b', nl): ctype = 'Oracle RAC'
                elif re.search(r'guard|\\bdg\\b', nl): ctype = 'Oracle Data Guard'
                elif re.search(r'gate', nl): ctype = 'Oracle GoldenGate'
                else: ctype = ctype or 'Oracle Cluster'
            elif 'MS SQL Server' in apps:
                if re.search(r'aog|always', nl): ctype = 'SQL Always On'
                elif re.search(r'fci|wsfc|cluster', nl): ctype = 'SQL FCI'
                elif re.search(r'repl', nl): ctype = 'SQL Replication'
            elif 'MySQL/MariaDB' in apps and re.search(r'repl', nl): ctype = 'MySQL Replication'
            elif 'PostgreSQL' in apps and re.search(r'repl|standby', nl): ctype = 'PG Replication'

        # Signal 5: Annotation
        if ann and _CLUSTER_ANN_KW.search(ann):
            topo = 'Cluster'

        # Signal 6: Explicit standalone overrides
        if re.search(r'standalone|single[_-]?node', nl):
            topo = 'Standalone'
            ctype = None

        # Determine type if still missing
        if topo == 'Cluster' and not ctype:
            if any(k in nl for k in ('ocp', 'openshift')): ctype = 'OpenShift'
            elif any(k in nl for k in ('k8s', 'kube')): ctype = 'Kubernetes'
            elif 'pacemaker' in nl or nl.startswith('pcs'): ctype = 'Pacemaker HA'
            elif 'cohesity' in nl: ctype = 'Cohesity'
            elif 'isilon' in nl: ctype = 'Isilon'
            elif re.search(r'wsfc|wincluster|win.*cluster', nl): ctype = 'Windows WSFC'

        vm['topology'] = topo
        vm['cluster_group'] = cgroup
        vm['cluster_role'] = crole
        vm['cluster_type'] = ctype

'''

# Insert before get_all_data
marker = "def get_all_data():"
if marker in content:
    content = content.replace(marker, TOPO_CODE + "\n" + marker)
    # Now call _detect_topology_for_all in get_all_data after applications
    old_line = "            hosts = _hosts(si,      vid, vname)"
    new_line = "            _detect_topology_for_all(vms)\n            hosts = _hosts(si,      vid, vname)"
    content = content.replace(old_line, new_line, 1)
    open(path, "w", encoding="utf-8").write(content)
    print("Added topology detection to vmware_client.py")
else:
    print("ERROR: marker not found")
