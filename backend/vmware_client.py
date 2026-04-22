from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
import ssl, os
import requests
import time
import re
import json
import datetime
from dotenv import load_dotenv
from pathlib import Path

# Always load .env from the same directory as this script
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ── vCenter registry ──────────────────────────────────────────────────────────
# .env single:  VCENTER_HOST=1.2.3.4  VCENTER_USER=admin  VCENTER_PASSWORD=pw
# .env multi:   VCENTER_HOSTS=1.2.3.4,5.6.7.8
#               VCENTER_USER=admin   VCENTER_PASSWORD=pw   (shared creds)
#   OR per-vc:  VCENTER_USER_1=a1  VCENTER_PASSWORD_1=p1
#               VCENTER_USER_2=a2  VCENTER_PASSWORD_2=p2
#   Optional:   VCENTER_NAME_1=ProdDC  VCENTER_NAME_2=DrDC

def _vcenter_list():
    raw   = os.getenv("VCENTER_HOSTS") or os.getenv("VCENTER_HOST", "")
    hosts = [h.strip() for h in raw.split(",") if h.strip()]
    out   = []
    for i, host in enumerate(hosts, 1):
        user = os.getenv(f"VCENTER_USER_{i}") or os.getenv("VCENTER_USER", "administrator@vsphere.local")
        pwd  = os.getenv(f"VCENTER_PASSWORD_{i}") or os.getenv("VCENTER_PASSWORD", "")
        port = int(os.getenv(f"VCENTER_PORT_{i}") or os.getenv("VCENTER_PORT", 443))
        name = os.getenv(f"VCENTER_NAME_{i}") or (f"vCenter-{i}" if len(hosts) > 1 else host)
        out.append({"host": host, "user": user, "pwd": pwd, "port": port, "name": name})
    return out

VCENTERS = _vcenter_list()

# Project utilization tag cache (per vCenter)
_TAG_CACHE_TTL_SECONDS = int(os.getenv("PROJECT_TAG_CACHE_TTL_SECONDS", "300"))
_TAG_CACHE_BY_VC = {}


def _extract_owner_from_tag(tag_name: str, tag_description: str) -> str:
    text = f"{tag_name or ''} {tag_description or ''}".strip()
    if not text:
        return ""

    patterns = [
        r"owner\s*[:=\-]\s*([A-Za-z0-9._@\- ]+)",
        r"owned\s+by\s*[:=\-]?\s*([A-Za-z0-9._@\- ]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return (m.group(1) or "").strip()
    return ""


def _connect(vc):
    import ssl as _ssl
    ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode    = _ssl.CERT_NONE
    return SmartConnect(host=vc["host"], user=vc["user"], pwd=vc["pwd"],
                        port=vc["port"], sslContext=ctx)


def _vms(si, vid, vname):
    rows = []
    cnt  = si.RetrieveContent().viewManager.CreateContainerView(
        si.RetrieveContent().rootFolder, [vim.VirtualMachine], True)
    for vm in cnt.view:
        # Skip vSphere Cluster Services VMs (system managed, cannot be actioned)
        if vm.name.startswith("vCLS") or vm.name.startswith("vCLS-"):
            continue
        try:
            s = vm.summary
            snaps = 0
            if vm.snapshot:
                def c(lst):
                    return sum(1 + c(x.childSnapshotList) for x in lst)
                snaps = c(vm.snapshot.rootSnapshotList)
            # Network adapters and all IPs
            all_ips, networks = [], []
            if vm.guest and vm.guest.net:
                for nic in vm.guest.net:
                    if nic.ipAddress:
                        all_ips += [ip for ip in nic.ipAddress if not ip.startswith("169.254") and ":" not in ip]
                    networks.append({"name": nic.network or "", "mac": nic.macAddress or "", "connected": nic.connected})
            # Tools
            tools_status  = str(vm.guest.toolsRunningStatus or "") if vm.guest else ""
            tools_version = str(vm.guest.toolsVersionStatus2 or "") if vm.guest else ""
            # Uptime
            uptime_sec = (s.quickStats.uptimeSeconds or 0) if s.quickStats else 0
            # Folder path
            folder = ""
            try:
                p_obj, parts = vm.parent, []
                while p_obj and hasattr(p_obj, "name"):
                    if p_obj.name not in ("vm", "Datacenters"): parts.insert(0, p_obj.name)
                    p_obj = p_obj.parent if hasattr(p_obj, "parent") else None
                folder = "/".join(parts)
            except Exception: pass
            # Datastores
            ds_names = []
            try: ds_names = [d.info.name for d in (vm.datastore or []) if hasattr(d, "info")]
            except Exception: pass
            rows.append({
                "vcenter_id":   vid, "vcenter_name": vname,
                "moid":         getattr(vm, "_moId", ""),
                "name":         s.config.name if s.config else "?",
                "status":       str(s.runtime.powerState) if s.runtime else "unknown",
                "cpu":          s.config.numCpu if s.config else 0,
                "cpu_cores_per_socket": getattr(s.config, "numCoresPerSocket", 1) if s.config else 1,
                "ram_gb":       round((s.config.memorySizeMB or 0)/1024, 1) if s.config else 0,
                "disk_gb":      round((s.storage.committed or 0)/(1024**3), 1) if s.storage else 0,
                "disk_prov_gb": round((s.storage.unshared or 0)/(1024**3), 1) if s.storage else 0,
                "host":         s.runtime.host.name if s.runtime and s.runtime.host else "N/A",
                "guest_os":     s.config.guestFullName if s.config else "",
                "guest_id":     s.config.guestId if s.config else "",
                "snapshot_count": snaps,
                "ip":           s.guest.ipAddress if s.guest else None,
                "all_ips":      all_ips,
                "networks":     networks,
                "datastores":   ds_names,
                "tools_status": tools_status,
                "tools_version":tools_version,
                "uptime_sec":   uptime_sec,
                "folder":       folder,
                "uuid":         vm.config.uuid if vm.config else "",
                "annotation":   (vm.config.annotation or "").strip() if vm.config else "",
                "vm_age_days":  _vm_age_days(vm),
            })
        except Exception:
            pass
    return rows


def _vm_age_days(vm):
    """Return VM age in days from config.createDate, or None if unavailable."""
    try:
        cd = getattr(vm.config, "createDate", None) if vm.config else None
        if cd is None:
            return None
        # createDate is timezone-aware; convert to naive UTC
        if hasattr(cd, "tzinfo") and cd.tzinfo is not None:
            import datetime as _dt
            cd = cd.astimezone(_dt.timezone.utc).replace(tzinfo=None)
        return max(0, (datetime.datetime.utcnow() - cd).days)
    except Exception:
        return None


def _hosts(si, vid, vname):
    rows = []
    cnt  = si.RetrieveContent().viewManager.CreateContainerView(
        si.RetrieveContent().rootFolder, [vim.HostSystem], True)
    for h in cnt.view:
        try:
            s  = h.summary; hw = s.hardware; q = s.quickStats
            tc = (hw.numCpuCores or 0) * (hw.cpuMhz or 0)
            uc = q.overallCpuUsage or 0
            tr = (hw.memorySize or 0) / (1024**3)
            ur = (q.overallMemoryUsage or 0) / 1024
            # Resolve cluster name: parent is ClusterComputeResource in a cluster
            try:
                parent = h.parent
                cluster_name = parent.name if isinstance(parent, vim.ClusterComputeResource) else "—"
            except Exception:
                cluster_name = "—"
            # ESXi version from product info
            esxi_version = ""
            try:
                pi = s.config.product if s.config else None
                if pi:
                    esxi_version = f"ESXi {pi.version}" if pi.version else ""
            except Exception:
                pass
            # Management IP from the first VMkernel adapter or config name
            mgmt_ip = ""
            try:
                for vnic in h.config.network.vnic:
                    if vnic.spec and vnic.spec.ip and vnic.spec.ip.ipAddress:
                        mgmt_ip = vnic.spec.ip.ipAddress
                        break
            except Exception:
                pass
            rows.append({
                "vcenter_id": vid, "vcenter_name": vname,
                "name":         s.config.name if s.config else "?",
                "cluster_name": cluster_name,
                "management_ip": mgmt_ip,
                "esxi_version": esxi_version,
                "cpu_total_mhz":tc, "cpu_used_mhz": uc,
                "cpu_free_pct": round((1-uc/tc)*100,1) if tc else 0,
                "ram_total_gb": round(tr,1), "ram_used_gb": round(ur,1),
                "ram_free_gb":  round(tr-ur,1),
                "ram_free_pct": round(((tr-ur)/tr)*100,1) if tr else 0,
                "status":       str(s.runtime.connectionState) if s.runtime else "unknown",
                "cpu_cores":    hw.numCpuCores or 0,
                "cpu_model":    hw.cpuModel or "",
            })
        except Exception:
            pass
    return rows


def _datastores(si, vid, vname):
    rows = []
    c = si.RetrieveContent()

    # Build SSD map using ESXi SMART detection
    try:
        h_view = c.viewManager.CreateContainerView(c.rootFolder, [vim.HostSystem], True)
        ds_type_map = _build_ds_type_map(h_view.view)
        h_view.Destroy()
    except Exception:
        ds_type_map = {}

    cnt = c.viewManager.CreateContainerView(c.rootFolder, [vim.Datastore], True)
    for d in cnt.view:
        try:
            s  = d.summary
            tg = round((s.capacity  or 0)/(1024**3),1)
            fg = round((s.freeSpace or 0)/(1024**3),1)
            ug = round(tg-fg,1)
            rows.append({
                "vcenter_id": vid, "vcenter_name": vname,
                "name": s.name, "type": s.type,
                "disk_type": ds_type_map.get(s.name, "HDD"),
                "total_gb": tg, "free_gb": fg, "used_gb": ug,
                "used_pct": round((ug/tg)*100,1) if tg else 0,
                "accessible": s.accessible,
            })
        except Exception:
            pass
    return rows


def _networks(si, vid, vname):
    rows = []
    cnt  = si.RetrieveContent().viewManager.CreateContainerView(
        si.RetrieveContent().rootFolder, [vim.Network], True)
    for n in cnt.view:
        try:
            rows.append({
                "vcenter_id": vid, "vcenter_name": vname,
                "name": n.name,
                "hosts_connected": len(n.host) if n.host else 0,
                "vms_connected":   len(n.vm)   if n.vm   else 0,
                "accessible": n.summary.accessible if hasattr(n,"summary") else True,
            })
        except Exception:
            pass
    return rows


def _snapshots(si, vid, vname):
    rows = []
    content = si.RetrieveContent()
    cnt = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.VirtualMachine], True)
    # Query event history for snapshot create events to get creator username
    creator_map = {}
    try:
        em = content.eventManager
        spec = vim.event.EventFilterSpec()
        spec.category = ["info"]
        spec.type = [vim.event.VmSnapshotCreateSucceededEvent]
        collector = em.CreateCollectorForEvents(spec)
        collector.SetCollectionPageSize(1000)
        while True:
            events = collector.ReadNextEvents(100)
            if not events:
                break
            for ev in events:
                vm_name = (ev.vm.name if ev.vm else "") or ""
                snap_name = getattr(ev, "snapName", "") or ""
                user = (ev.userName or "").split("\\")[-1].split("/")[-1]
                key = vm_name + "::" + snap_name
                if key and key not in creator_map:
                    creator_map[key] = user
        collector.DestroyCollector()
    except Exception:
        pass
    for vm in cnt.view:
        try:
            if not vm.snapshot:
                continue
            vn = vm.summary.config.name
            def walk(lst):
                for s in lst:
                    key = vn + "::" + s.name
                    rows.append({
                        "vcenter_id": vid, "vcenter_name": vname,
                        "vm_name": vn, "snapshot_name": s.name,
                        "description": s.description or "",
                        "created": str(s.createTime)[:19].replace("T"," "),
                        "state": str(s.state),
                        "created_by": creator_map.get(key, ""),
                    })
                    walk(s.childSnapshotList)
            walk(vm.snapshot.rootSnapshotList)
        except Exception:
            pass
    return rows



def _summary(vid, vname, hosts, datastores, vms):
    conn = [h for h in hosts if h["status"]=="connected"]
    tc=sum(h["cpu_total_mhz"] for h in conn); uc=sum(h["cpu_used_mhz"] for h in conn)
    tr=sum(h["ram_total_gb"]  for h in conn); ur=sum(h["ram_used_gb"]  for h in conn)
    td=sum(d["total_gb"] for d in datastores); fd=sum(d["free_gb"] for d in datastores)
    return {
        "vcenter_id": vid, "vcenter_name": vname, "vcenter_host": vid,
        "total_hosts": len(hosts), "connected_hosts": len(conn),
        "total_vms": len(vms),
        "running_vms": len([v for v in vms if v["status"]=="poweredOn"]),
        "stopped_vms": len([v for v in vms if v["status"]=="poweredOff"]),
        "cpu":{"total_mhz":tc,"used_mhz":uc,"free_mhz":tc-uc,
               "free_pct":round((1-uc/tc)*100,1) if tc else 0},
        "ram":{"total_gb":round(tr,1),"used_gb":round(ur,1),"free_gb":round(tr-ur,1),
               "free_pct":round(((tr-ur)/tr)*100,1) if tr else 0},
        "storage":{"total_gb":round(td,1),"free_gb":round(fd,1),"used_gb":round(td-fd,1),
                   "free_pct":round((fd/td)*100,1) if td else 0},
        "status": "ok",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def get_vcenter_list():
    return [{"id":v["host"],"name":v["name"],"host":v["host"]} for v in VCENTERS]



#  Application Detection 
_APP_PATTERNS = [
    # Databases
    {"pattern": r"oracle|ora[0-9]|orcl",          "app": "Oracle DB",        "icon": "ora",   "category": "database"},
    {"pattern": r"mssql|sqlserver|sql.?srv",       "app": "MS SQL Server",    "icon": "mssql", "category": "database"},
    {"pattern": r"postgres|pgsql|pgdb",            "app": "PostgreSQL",       "icon": "pg",    "category": "database"},
    {"pattern": r"mysql|mariadb|maria",            "app": "MySQL/MariaDB",    "icon": "mysql", "category": "database"},
    {"pattern": r"mongo",                          "app": "MongoDB",          "icon": "mongo", "category": "database"},
    {"pattern": r"redis",                          "app": "Redis",            "icon": "redis", "category": "database"},
    {"pattern": r"cassandra",                      "app": "Cassandra",        "icon": "cass",  "category": "database"},
    {"pattern": r"elastic|elk|kibana|logstash",    "app": "Elasticsearch",    "icon": "elk",   "category": "database"},
    {"pattern": r"\bdb\b|database|\bvdb\b|\bdbs\b",  "app": "Database",         "icon": "db",    "category": "database"},
    # Web / App Servers
    {"pattern": r"apache|httpd|websvr",            "app": "Apache HTTP",      "icon": "web",   "category": "web"},
    {"pattern": r"nginx",                          "app": "Nginx",            "icon": "web",   "category": "web"},
    {"pattern": r"tomcat|catalina",                "app": "Tomcat",           "icon": "java",  "category": "web"},
    {"pattern": r"iis|webserver",                  "app": "IIS Web Server",   "icon": "iis",   "category": "web"},
    {"pattern": r"jboss|wildfly",                  "app": "JBoss/WildFly",    "icon": "java",  "category": "web"},
    {"pattern": r"weblogic|wls",                   "app": "WebLogic",         "icon": "java",  "category": "web"},
    {"pattern": r"websphere",                      "app": "WebSphere",        "icon": "java",  "category": "web"},
    # DevOps / CI-CD
    {"pattern": r"jenkins",                        "app": "Jenkins",          "icon": "ci",    "category": "devops"},
    {"pattern": r"gitlab",                         "app": "GitLab",           "icon": "ci",    "category": "devops"},
    {"pattern": r"ansible|tower|aap",              "app": "Ansible/AAP",      "icon": "auto",  "category": "devops"},
    {"pattern": r"terraform",                      "app": "Terraform",        "icon": "auto",  "category": "devops"},
    {"pattern": r"cicd|pipeline|bamboo|argo",      "app": "CI/CD Pipeline",   "icon": "ci",    "category": "devops"},
    # Container / K8s
    {"pattern": r"k8s|kube|kubernetes|ocp|openshift", "app": "Kubernetes",    "icon": "k8s",   "category": "container"},
    {"pattern": r"docker|container|podman",        "app": "Container Host",   "icon": "k8s",   "category": "container"},
    {"pattern": r"rancher",                        "app": "Rancher",          "icon": "k8s",   "category": "container"},
    # Infrastructure
    {"pattern": r"\\bdc\\b|\\bad\\b|activedirectory|domain.?controller|ldap", "app": "Active Directory", "icon": "ad", "category": "infra"},
    {"pattern": r"\\bdns\\b|named|bind9",      "app": "DNS Server",       "icon": "dns",   "category": "infra"},
    {"pattern": r"\\bdhcp\\b",                  "app": "DHCP Server",      "icon": "net",   "category": "infra"},
    {"pattern": r"ntp|chrony|timeserver",          "app": "NTP Server",       "icon": "net",   "category": "infra"},
    {"pattern": r"vcsa|vcenter|vsphere",           "app": "vCenter/VCSA",     "icon": "vmw",   "category": "infra"},
    {"pattern": r"esxi|hypervisor",                "app": "ESXi Nested",      "icon": "vmw",   "category": "infra"},
    {"pattern": r"nfs|cifs|samba|fileserver|nas",  "app": "File Server",      "icon": "stor",  "category": "infra"},
    {"pattern": r"\\bvpn\\b|firewall|pfsense|fortigate", "app": "Network/Firewall", "icon": "net", "category": "infra"},
    # Monitoring
    {"pattern": r"nagios|zabbix|prometheus|grafana|splunk|solarwinds|prtg", "app": "Monitoring", "icon": "mon", "category": "monitoring"},
    # Mail
    {"pattern": r"exchange|smtp|postfix|sendmail|mail", "app": "Mail Server", "icon": "mail", "category": "mail"},
    # Backup
    {"pattern": r"veeam|cohesity|rubrik|networker|commvault|backup", "app": "Backup", "icon": "bak", "category": "backup"},
]

def _detect_applications(vm: dict) -> list[dict]:
    """Detect applications from VM name, guest OS, annotation, tags, and folder."""
    found = []
    seen = set()
    # Build search corpus from all available signals
    corpus = " ".join([
        (vm.get("name") or ""),
        (vm.get("guest_os") or ""),
        (vm.get("guest_id") or ""),
        (vm.get("annotation") or ""),
        (vm.get("folder") or ""),
        " ".join(vm.get("tags") or []),
    ]).lower()
    for rule in _APP_PATTERNS:
        if rule["app"] in seen:
            continue
        if re.search(rule["pattern"], corpus, re.IGNORECASE):
            found.append({"app": rule["app"], "icon": rule["icon"], "category": rule["category"]})
            seen.add(rule["app"])
    return found



#  Topology Detection (Standalone vs Cluster) 
_CLUSTER_NAME_KW = re.compile(
    r'(rac\d|rac[_-]|node[_-]?\d|cluster|master\d*[_-]|worker\d*[_-]|'
    r'member|primary|secondary|replica|standby|dataguard|goldengate|'
    r'fci|wsfc|pacemaker|pcs[_-]|haproxy|keepalived|controlplane|etcd[_-]?\d)', re.I
)
_CLUSTER_ANN_KW = re.compile(
    r'(cluster|rac\b|node\s*\d|dataguard|data\s*guard|golden\s*gate|'
    r'always.?on|failover|ha\s|high.?avail|replica|standby|primary|secondary)', re.I
)
_CLUSTER_APPS = {'Kubernetes', 'Container Host', 'Rancher', 'Active Directory'}
_CLUSTER_DB_KW = re.compile(r'(rac|guard|gate|replica|repl|standby|aog|fci|wsfc|cluster)', re.I)

def _detect_topology_for_all(vms: list) -> None:
    suffix_pat = re.compile(r'^(.+?)[_-]?0*(\d{1,3})$')
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
                if re.search(r'\brac\b', nl): ctype = 'Oracle RAC'
                elif re.search(r'guard|\bdg\b', nl): ctype = 'Oracle Data Guard'
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


def get_all_data():
    all_vms=[];all_hosts=[];all_ds=[];all_nets=[];all_snaps=[];all_summ=[]
    for vc in VCENTERS:
        vid=vc["host"]; vname=vc["name"]
        try:
            si    = _connect(vc)
            vms   = _vms(si,        vid, vname)
            # Fetch VM tags from vCenter REST API and attach to each VM
            try:
                vm_moids = [v.get("moid","") for v in vms if v.get("moid")]
                tag_map, _tag_owners = _fetch_vm_tags_for_vcenter(vc, vm_moids)
                for v in vms:
                    v["tags"] = tag_map.get(v.get("moid",""), [])
            except Exception:
                for v in vms:
                    v.setdefault("tags", [])
            # Detect applications for each VM
            for v in vms:
                v["applications"] = _detect_applications(v)
            _detect_topology_for_all(vms)
            hosts = _hosts(si,      vid, vname)
            ds    = _datastores(si, vid, vname)
            nets  = _networks(si,   vid, vname)
            snaps = _snapshots(si,  vid, vname)
            summ  = _summary(vid, vname, hosts, ds, vms)
            Disconnect(si)
            all_vms+=vms; all_hosts+=hosts; all_ds+=ds
            all_nets+=nets; all_snaps+=snaps
            all_summ.append(summ)
        except Exception as e:
            all_summ.append({
                "vcenter_id":vid,"vcenter_name":vname,"vcenter_host":vid,
                "status":"error","error":str(e),
                "total_hosts":0,"connected_hosts":0,"total_vms":0,
                "running_vms":0,"stopped_vms":0,
                "cpu":{"total_mhz":0,"used_mhz":0,"free_mhz":0,"free_pct":0},
                "ram":{"total_gb":0,"used_gb":0,"free_gb":0,"free_pct":0},
                "storage":{"total_gb":0,"free_gb":0,"used_gb":0,"free_pct":0},
            })
    return {"vms":all_vms,"hosts":all_hosts,"datastores":all_ds,
            "networks":all_nets,"snapshots":all_snaps,"summaries":all_summ}


def _fetch_vm_tags_for_vcenter(vc: dict, vm_moids: list[str]) -> dict:
    """
    Returns mapping: { "vm-123": ["Tag A", "Tag B"], ... }
    Uses vCenter REST tagging APIs. Best-effort; returns empty map on failure.
    """
    if not vm_moids:
        return {}, {}

    vcid = vc["host"]
    now = time.time()
    cached = _TAG_CACHE_BY_VC.get(vcid)
    if cached and (now - cached.get("ts", 0) <= _TAG_CACHE_TTL_SECONDS):
        mapping = cached.get("mapping", {})
        owners = cached.get("owners", {})
        return {moid: mapping.get(moid, []) for moid in vm_moids}, owners

    base = f"https://{vc['host']}:{vc['port']}"
    sess = requests.Session()
    sess.verify = False
    sess.auth = (vc["user"], vc["pwd"])

    try:
        # Login to REST session
        r = sess.post(f"{base}/rest/com/vmware/cis/session", timeout=5)
        if r.status_code >= 300:
            return {}, {}

        # Get all tags once
        rt = sess.get(f"{base}/rest/com/vmware/cis/tagging/tag", timeout=8)
        if rt.status_code >= 300:
            return {}, {}
        tag_ids = rt.json().get("value", []) or []

        full_mapping = {}
        tag_owner_by_name = {}
        vm_set = set(vm_moids)

        for tid in tag_ids:
            try:
                rn = sess.get(f"{base}/rest/com/vmware/cis/tagging/tag/id:{tid}", timeout=6)
                if rn.status_code >= 300:
                    continue
                tag_val = rn.json().get("value", {}) or {}
                tag_name = (tag_val.get("name") or tid).strip()
                tag_desc = (tag_val.get("description") or "").strip()
                if not tag_name:
                    continue

                if tag_name not in tag_owner_by_name:
                    tag_owner_by_name[tag_name] = _extract_owner_from_tag(tag_name, tag_desc)

                ro = sess.post(
                    f"{base}/rest/com/vmware/cis/tagging/tag-association?~action=list-attached-objects",
                    json={"tag_id": tid},
                    timeout=8,
                )
                if ro.status_code >= 300:
                    continue
                objs = ro.json().get("value", []) or []
                for obj in objs:
                    oid = (obj.get("id") or {}).get("id")
                    otype = (obj.get("id") or {}).get("type")
                    if otype != "VirtualMachine" or oid not in vm_set:
                        continue
                    full_mapping.setdefault(oid, []).append(tag_name)
            except Exception:
                continue

        # Compatibility fallback: some vCenter privilege models may not allow
        # list-attached-objects for tags, but do allow per-VM list-attached-tags.
        if not full_mapping and vm_moids:
            tag_name_cache = {}
            tag_owner_cache = {}
            for moid in vm_moids:
                try:
                    body = {"object_id": {"id": moid, "type": "VirtualMachine"}}
                    rt_vm = sess.post(
                        f"{base}/rest/com/vmware/cis/tagging/tag-association?~action=list-attached-tags",
                        json=body,
                        timeout=8,
                    )
                    if rt_vm.status_code >= 300:
                        continue

                    vm_tag_ids = rt_vm.json().get("value", []) or []
                    for tid in vm_tag_ids:
                        if tid not in tag_name_cache:
                            rn_vm = sess.get(f"{base}/rest/com/vmware/cis/tagging/tag/id:{tid}", timeout=6)
                            if rn_vm.status_code >= 300:
                                tag_name_cache[tid] = tid
                                tag_owner_cache[tid] = ""
                            else:
                                tag_val_vm = rn_vm.json().get("value", {}) or {}
                                t_name = (tag_val_vm.get("name") or tid).strip()
                                t_desc = (tag_val_vm.get("description") or "").strip()
                                tag_name_cache[tid] = t_name
                                tag_owner_cache[tid] = _extract_owner_from_tag(t_name, t_desc)

                        tname = tag_name_cache.get(tid)
                        if tname:
                            full_mapping.setdefault(moid, []).append(tname)
                            if tname not in tag_owner_by_name and tag_owner_cache.get(tid):
                                tag_owner_by_name[tname] = tag_owner_cache[tid]
                except Exception:
                    continue

            _TAG_CACHE_BY_VC[vcid] = {"ts": now, "mapping": full_mapping, "owners": tag_owner_by_name}
            return {moid: full_mapping.get(moid, []) for moid in vm_moids}, tag_owner_by_name
    except Exception:
            return {}, {}
    finally:
        try:
            sess.delete(f"{base}/rest/com/vmware/cis/session", timeout=5)
        except Exception:
            pass
        try:
            sess.close()
        except Exception:
            pass


_PRICING_FILE_PATH = Path(__file__).parent / "pricing.json"
_INTERNET_FILE_PATH = Path(__file__).parent / "internet_vms.json"
_DEFAULT_PRICING_CB = {
    "cpu_per_core_month_inr":      500,
    "ram_per_gb_month_inr":        200,
    "ssd_per_gb_month_inr":        15,
    "hdd_per_gb_month_inr":        8,
    "disk_per_gb_month_inr":       8,
    "windows_license_month_inr":   12500,
    "rhel_license_month_inr":      10000,
    "internet_per_vm_month_inr":   1500,   # on-prem internet per VM per month
    "usd_rate": 83.5,
}

def _os_license_type(guest_os: str) -> str:
    """Detect OS license category from vCenter guest_os string.
    Returns: 'windows' | 'rhel' | '' (no license fee)
    """
    g = (guest_os or "").lower()
    if "windows" in g:
        return "windows"
    if "red hat" in g or "rhel" in g:
        return "rhel"
    return ""  # Ubuntu, CentOS, Debian, etc. — open-source, no fee

def _load_pricing_for_cb():
    try:
        if _PRICING_FILE_PATH.exists():
            return json.loads(_PRICING_FILE_PATH.read_text())
    except Exception:
        pass
    return _DEFAULT_PRICING_CB.copy()

_DEFAULT_INTERNET_CONFIG = {"mode": "all_powered_on", "excluded": [], "extra": []}

def _load_internet_config() -> dict:
    """Load internet VM config from internet_vms.json.
    mode='all_powered_on'  → all poweredOn VMs get internet charge by default.
    excluded: list of VM names forcibly excluded from internet charge.
    extra: list of VM names forcibly included regardless of power state.
    """
    try:
        if _INTERNET_FILE_PATH.exists():
            cfg = json.loads(_INTERNET_FILE_PATH.read_text())
            cfg.setdefault("mode", "all_powered_on")
            cfg.setdefault("excluded", [])
            cfg.setdefault("extra", [])
            return cfg
    except Exception:
        pass
    return _DEFAULT_INTERNET_CONFIG.copy()

def _has_internet_charge(vm_name: str, vm_status: str, cfg: dict) -> bool:
    """Determine whether a VM should be charged for internet access."""
    excluded = set(cfg.get("excluded") or [])
    extra    = set(cfg.get("extra")    or [])
    if vm_name in excluded:
        return False
    if vm_name in extra:
        return True
    if cfg.get("mode") == "all_powered_on" and vm_status == "poweredOn":
        return True
    return False


def get_project_utilization(vms: list, vcenter_id: str = None, owner_overrides: dict = None, datastores: list = None) -> dict:
    """
    Aggregate VM resource utilization by VMware tag name.
    If a VM has multiple tags, its resources are counted under each tag.
    disk_type (SSD/HDD) is sourced from the ESXi-detected datastore data.
    """
    # Build datastore_name -> disk_type map from the collected datastores
    _ds_type_cache = {}
    for ds in (datastores or []):
        name = ds.get("name", "")
        if name:
            _ds_type_cache[name] = ds.get("disk_type", "HDD")

    def _resolve_disk_type(ds_names: list) -> str:
        """Return SSD if primary datastore is SSD (from ESXi detection), else HDD."""
        primary = (ds_names[0] if ds_names else "")
        if primary in _ds_type_cache:
            return _ds_type_cache[primary]
        # Fallback: name heuristic
        return "SSD" if "ssd" in primary.lower() else "HDD"
    scoped = [v for v in (vms or []) if not vcenter_id or vcenter_id == "all" or v.get("vcenter_id") == vcenter_id]

    # Build moid list per vCenter
    moids_by_vc = {}
    for vm in scoped:
        moid = (vm.get("moid") or "").strip()
        vcid = vm.get("vcenter_id")
        if moid and vcid:
            moids_by_vc.setdefault(vcid, set()).add(moid)

    # Fetch tags per vCenter
    tags_by_vc = {}
    owners_by_tag = {}
    for vc in VCENTERS:
        vcid = vc["host"]
        if vcid not in moids_by_vc:
            continue
        vm_tags, tag_owners = _fetch_vm_tags_for_vcenter(vc, list(moids_by_vc[vcid]))
        tags_by_vc[vcid] = vm_tags
        for tag_name, owner in (tag_owners or {}).items():
            if owner and tag_name not in owners_by_tag:
                owners_by_tag[tag_name] = owner

    owner_overrides = owner_overrides or {}

    # Aggregate utilization per tag
    by_tag = {}
    for vm in scoped:
        vcid = vm.get("vcenter_id")
        moid = vm.get("moid") or ""
        names = (tags_by_vc.get(vcid, {}).get(moid, []) if vcid and moid else [])
        if not names:
            continue

        for tag in names:
            rec = by_tag.setdefault(tag, {
                "tag": tag,
                "owner": owners_by_tag.get(tag, ""),
                "owner_email": "",
                "vm_count": 0,
                "running_vms": 0,
                "stopped_vms": 0,
                "cpu_cores": 0,
                "ram_gb": 0.0,
                "disk_gb": 0.0,
                "vms": [],
            })

            override = owner_overrides.get(tag) or {}
            if override.get("owner_name"):
                rec["owner"] = (override.get("owner_name") or "").strip()
            if override.get("owner_email"):
                rec["owner_email"] = (override.get("owner_email") or "").strip()

            rec["vm_count"] += 1
            if vm.get("status") == "poweredOn":
                rec["running_vms"] += 1
            elif vm.get("status") == "poweredOff":
                rec["stopped_vms"] += 1
            rec["cpu_cores"] += int(vm.get("cpu") or 0)
            rec["ram_gb"] += float(vm.get("ram_gb") or 0)
            rec["disk_gb"] += float(vm.get("disk_gb") or 0)
            rec["vms"].append({
                "name": vm.get("name") or "",
                "status": vm.get("status") or "unknown",
                "cpu": int(vm.get("cpu") or 0),
                "ram_gb": float(vm.get("ram_gb") or 0),
                "disk_gb": float(vm.get("disk_gb") or 0),
                "guest_os": vm.get("guest_os") or "",
                "host": vm.get("host") or "",
                "vcenter_name": vm.get("vcenter_name") or "",
                "vm_age_days": vm.get("vm_age_days"),
                "datastores": vm.get("datastores") or [],
                "disk_type": _resolve_disk_type(vm.get("datastores") or []),
                "license_type": _os_license_type(vm.get("guest_os") or ""),
                "has_internet": False,  # will be filled in chargeback loop below
            })

    pricing = _load_pricing_for_cb()
    cpu_rate      = float(pricing.get("cpu_per_core_month_inr")    or 500)
    ram_rate      = float(pricing.get("ram_per_gb_month_inr")      or 200)
    ssd_rate      = float(pricing.get("ssd_per_gb_month_inr")      or 15)
    hdd_rate      = float(pricing.get("hdd_per_gb_month_inr")      or
                          pricing.get("disk_per_gb_month_inr")     or 8)
    win_lic_rate  = float(pricing.get("windows_license_month_inr") or 12500)
    rhel_lic_rate = float(pricing.get("rhel_license_month_inr")    or 10000)
    internet_rate = float(pricing.get("internet_per_vm_month_inr") or 1500)
    usd_rate      = float(pricing.get("usd_rate")                  or 83.5)
    internet_cfg  = _load_internet_config()

    tags = []
    for rec in by_tag.values():
        vm_rows = rec.get("vms", [])
        max_cpu = max((v.get("cpu", 0) for v in vm_rows), default=0)
        max_ram = max((v.get("ram_gb", 0) for v in vm_rows), default=0)
        max_disk = max((v.get("disk_gb", 0) for v in vm_rows), default=0)

        ranked_vms = []
        tag_chargeback_inr = 0.0
        for v in vm_rows:
            cpu_n = (v.get("cpu", 0) / max_cpu) if max_cpu else 0
            ram_n = (v.get("ram_gb", 0) / max_ram) if max_ram else 0
            disk_n = (v.get("disk_gb", 0) / max_disk) if max_disk else 0
            score = round((cpu_n * 0.4 + ram_n * 0.3 + disk_n * 0.3) * 100, 1)
            # Chargeback for this VM — use SSD or HDD rate
            disk_type = v.get("disk_type", "HDD")
            disk_rate = ssd_rate if disk_type == "SSD" else hdd_rate
            license_type = v.get("license_type", "")
            lic_cost = (win_lic_rate if license_type == "windows"
                        else rhel_lic_rate if license_type == "rhel"
                        else 0.0)
            has_internet = _has_internet_charge(
                v.get("name", ""), v.get("status", ""), internet_cfg
            )
            inet_cost = internet_rate if has_internet else 0.0
            monthly = (int(v.get("cpu") or 0) * cpu_rate
                       + float(v.get("ram_gb") or 0) * ram_rate
                       + float(v.get("disk_gb") or 0) * disk_rate
                       + lic_cost
                       + inet_cost)
            age_days = v.get("vm_age_days")
            months = max(1.0, float(age_days) / 30.0) if age_days is not None else 1.0
            vm_chargeback_inr = round(monthly * months, 2)
            tag_chargeback_inr += vm_chargeback_inr
            ranked_vms.append({**v,
                "utilization_score": score,
                "chargeback_inr": vm_chargeback_inr,
                "chargeback_usd": round(vm_chargeback_inr / usd_rate, 2) if usd_rate else 0,
                "vm_age_days": age_days,
                "disk_type": v.get("disk_type", "HDD"),
                "disk_rate_inr": ssd_rate if v.get("disk_type") == "SSD" else hdd_rate,
                "license_type": license_type,
                "license_cost_inr": round(lic_cost * months, 2),
                "guest_os": v.get("guest_os", ""),
                "has_internet": has_internet,
                "internet_cost_inr": round(inet_cost * months, 2),
            })

        ranked_vms.sort(key=lambda x: x.get("utilization_score", 0), reverse=True)
        tag_cb_inr = round(tag_chargeback_inr, 2)

        tags.append({
            "tag": rec["tag"],
            "owner": rec.get("owner", ""),
            "owner_email": rec.get("owner_email", ""),
            "vm_count": rec["vm_count"],
            "running_vms": rec.get("running_vms", 0),
            "stopped_vms": rec.get("stopped_vms", 0),
            "cpu_cores": rec["cpu_cores"],
            "ram_gb": round(rec["ram_gb"], 1),
            "disk_gb": round(rec["disk_gb"], 1),
            "chargeback_inr": tag_cb_inr,
            "chargeback_usd": round(tag_cb_inr / usd_rate, 2) if usd_rate else 0,
            "vms": ranked_vms,
        })

    tags.sort(key=lambda x: x["vm_count"], reverse=True)
    return {
        "tags": tags,
        "count": len(tags),
        "scope_vcenter_id": vcenter_id or "all",
        "note": "Only VMs with VMware tags are included. If a VM has multiple tags, its resources are counted under each tag.",
    }


def get_alerts(hosts, datastores):
    CT=int(os.getenv("CPU_ALERT_PCT",85))
    RT=int(os.getenv("RAM_ALERT_PCT",85))
    DT=int(os.getenv("DISK_ALERT_PCT",80))
    alerts=[]
    for h in hosts:
        if h["status"] in ("notResponding","disconnected"):
            alerts.append({"severity":"error","type":"HOST",
                "vcenter_id":h["vcenter_id"],"vcenter_name":h["vcenter_name"],
                "resource":h["name"],"message":f"Host {h['name']} is {h['status']}"})
            continue
        if h["status"]!="connected": continue
        cu=round(100-h["cpu_free_pct"],1)
        ru=round((h["ram_used_gb"]/h["ram_total_gb"])*100,1) if h["ram_total_gb"] else 0
        if cu>=CT:
            alerts.append({"severity":"error" if cu>=95 else "warn","type":"CPU",
                "vcenter_id":h["vcenter_id"],"vcenter_name":h["vcenter_name"],
                "resource":h["name"],"message":f"CPU {cu}% (threshold {CT}%)"})
        if ru>=RT:
            alerts.append({"severity":"error" if ru>=95 else "warn","type":"RAM",
                "vcenter_id":h["vcenter_id"],"vcenter_name":h["vcenter_name"],
                "resource":h["name"],"message":f"RAM {ru}% — {h['ram_used_gb']}GB/{h['ram_total_gb']}GB"})
    for d in datastores:
        if d["used_pct"]>=DT:
            alerts.append({"severity":"error" if d["used_pct"]>=90 else "warn","type":"DISK",
                "vcenter_id":d["vcenter_id"],"vcenter_name":d["vcenter_name"],
                "resource":d["name"],"message":f"Datastore {d['used_pct']}% full ({d['free_gb']}GB free)"})
    if not alerts:
        alerts.append({"severity":"info","type":"OK","vcenter_id":"all","vcenter_name":"All",
            "resource":"All","message":"All resources within normal thresholds"})
    return alerts


# ── VM Power Actions ──────────────────────────────────────────────────────────
def vm_power_action(vcenter_id: str, vm_name: str, action: str):
    """
    Perform power action on a VM.
    action: "start" | "stop" | "restart"
    Returns: {"success": True/False, "message": "..."}
    """
    vc = next((v for v in VCENTERS if v["host"] == vcenter_id), None)
    if not vc:
        return {"success": False, "message": f"vCenter {vcenter_id} not found"}

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    si = None
    try:
        si = SmartConnect(host=vc["host"], user=vc["user"], pwd=vc["pwd"],
                          port=vc["port"], sslContext=ctx)
        content_si = si.RetrieveContent()

        # Search for VM by name
        container = content_si.rootFolder
        view_type = [vim.VirtualMachine]
        recursive = True
        container_view = content_si.viewManager.CreateContainerView(
            container, view_type, recursive)
        vms = container_view.view
        container_view.Destroy()

        target_vm = next((v for v in vms if v.name == vm_name), None)
        if not target_vm:
            return {"success": False, "message": f"VM '{vm_name}' not found"}

        current_state = target_vm.runtime.powerState

        if action == "start":
            if current_state == vim.VirtualMachinePowerState.poweredOn:
                return {"success": False, "message": f"VM '{vm_name}' is already powered on"}
            task = target_vm.PowerOn()
        elif action == "stop":
            if current_state == vim.VirtualMachinePowerState.poweredOff:
                return {"success": False, "message": f"VM '{vm_name}' is already powered off"}
            task = target_vm.PowerOff()
        elif action == "restart":
            if current_state != vim.VirtualMachinePowerState.poweredOn:
                return {"success": False, "message": f"VM '{vm_name}' must be powered on to restart"}
            task = target_vm.ResetVM_Task()
        else:
            return {"success": False, "message": f"Unknown action: {action}"}

        # Wait for task (max 30s)
        import time
        for _ in range(60):
            if task.info.state in ["success", "error"]:
                break
            time.sleep(0.5)

        if task.info.state == "success":
            return {"success": True, "message": f"VM '{vm_name}' {action} successful"}
        else:
            err = str(task.info.error.msg) if task.info.error else "Unknown error"
            return {"success": False, "message": f"Task failed: {err}"}

    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if si:
            try: Disconnect(si)
            except: pass

# ── Shared helpers ─────────────────────────────────────────────────────────────
def _connect(vc: dict):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    return SmartConnect(host=vc["host"], user=vc["user"], pwd=vc["pwd"],
                        port=vc["port"], sslContext=ctx)

def _find_vm(content_si, vm_name: str):
    view = content_si.viewManager.CreateContainerView(
        content_si.rootFolder, [vim.VirtualMachine], True)
    vm = next((v for v in view.view if v.name == vm_name), None)
    view.Destroy()
    return vm

def _wait_task(task, timeout=120):
    import time
    for _ in range(timeout * 2):
        if task.info.state in ("success", "error"):
            break
        time.sleep(0.5)
    if task.info.state == "success":
        return {"success": True,  "message": "Task completed successfully"}
    err = str(task.info.error.msg) if task.info.error else "Unknown error"
    return {"success": False, "message": f"Task failed: {err}"}

def _vc_by_id(vcenter_id: str):
    return next((v for v in VCENTERS if v["host"] == vcenter_id), None)

# ── Snapshot ───────────────────────────────────────────────────────────────────
def vm_snapshot(vcenter_id: str, vm_name: str, snap_name: str,
                description: str = "", memory: bool = False, quiesce: bool = False):
    vc = _vc_by_id(vcenter_id)
    if not vc:
        return {"success": False, "message": f"vCenter {vcenter_id} not found"}
    si = None
    try:
        si = _connect(vc)
        c  = si.RetrieveContent()
        vm = _find_vm(c, vm_name)
        if not vm:
            return {"success": False, "message": f"VM '{vm_name}' not found"}
        task = vm.CreateSnapshot_Task(
            name=snap_name, description=description,
            memory=memory, quiesce=quiesce)
        result = _wait_task(task)
        if result["success"]:
            result["message"] = f"Snapshot '{snap_name}' created successfully on '{vm_name}'"
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if si:
            try: Disconnect(si)
            except: pass

# ── Clone ──────────────────────────────────────────────────────────────────────
def vm_clone(vcenter_id: str, vm_name: str, clone_name: str,
             dest_host: str = None, dest_datastore: str = None,
             dest_vcenter_id: str = None, power_on: bool = False):
    """
    Clone a VM within same vCenter or to a different vCenter.
    dest_vcenter_id: if set and different, performs cross-vCenter clone via OVF export/import workaround.
    For same-vCenter clone, uses native CloneVM_Task.
    """
    # Same-vCenter clone
    target_vc_id = dest_vcenter_id or vcenter_id
    if target_vc_id == vcenter_id:
        return _clone_same_vc(vcenter_id, vm_name, clone_name,
                              dest_host, dest_datastore, power_on)
    else:
        return {"success": False,
                "message": "Cross-vCenter clone requires both vCenters to be connected. Use Migrate for cross-vCenter moves."}

def _clone_same_vc(vcenter_id, vm_name, clone_name, dest_host, dest_datastore, power_on):
    vc = _vc_by_id(vcenter_id)
    if not vc:
        return {"success": False, "message": f"vCenter {vcenter_id} not found"}
    si = None
    try:
        si = _connect(vc)
        c  = si.RetrieveContent()
        vm = _find_vm(c, vm_name)
        if not vm:
            return {"success": False, "message": f"VM '{vm_name}' not found"}

        # Destination folder — same as source
        folder = vm.parent

        # Resolve datastore
        ds = None
        if dest_datastore:
            ds_view = c.viewManager.CreateContainerView(
                c.rootFolder, [vim.Datastore], True)
            ds = next((d for d in ds_view.view if d.name == dest_datastore), None)
            ds_view.Destroy()
        if not ds:
            ds = vm.datastore[0] if vm.datastore else None
        if not ds:
            return {"success": False, "message": "No datastore available"}

        # Resolve host
        host_obj = None
        if dest_host:
            h_view = c.viewManager.CreateContainerView(
                c.rootFolder, [vim.HostSystem], True)
            host_obj = next((h for h in h_view.view if h.name == dest_host), None)
            h_view.Destroy()

        # Build relocate spec
        relocate = vim.vm.RelocateSpec(datastore=ds)
        if host_obj:
            relocate.host = host_obj
            relocate.pool = host_obj.parent.resourcePool

        clone_spec = vim.vm.CloneSpec(
            location=relocate,
            powerOn=power_on,
            template=False)

        task = vm.Clone(folder=folder, name=clone_name, spec=clone_spec)
        result = _wait_task(task, timeout=300)
        if result["success"]:
            result["message"] = f"VM '{vm_name}' cloned to '{clone_name}' successfully"
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if si:
            try: Disconnect(si)
            except: pass

# ── Migrate ────────────────────────────────────────────────────────────────────
def vm_migrate(vcenter_id: str, vm_name: str,
               dest_host: str = None, dest_datastore: str = None,
               dest_vcenter_id: str = None):
    """
    Migrate (vMotion/Storage vMotion) a VM.
    Same vCenter: uses MigrateVM_Task (vMotion for host, storage vMotion for datastore).
    Cross-vCenter: uses RelocateVM_Task with cross-vc spec (requires vSphere 6+).
    """
    target_vc_id = dest_vcenter_id or vcenter_id
    if target_vc_id == vcenter_id:
        return _migrate_same_vc(vcenter_id, vm_name, dest_host, dest_datastore)
    else:
        return _migrate_cross_vc(vcenter_id, vm_name, dest_vcenter_id, dest_host, dest_datastore)

def _get_resource_pool(host_obj):
    """Safely get resource pool for a host (works for both cluster and standalone)."""
    try:
        parent = host_obj.parent  # ClusterComputeResource or ComputeResource
        return parent.resourcePool
    except Exception:
        return None

def _migrate_same_vc(vcenter_id, vm_name, dest_host, dest_datastore):
    vc = _vc_by_id(vcenter_id)
    if not vc:
        return {"success": False, "message": f"vCenter {vcenter_id} not found"}
    si = None
    try:
        si = _connect(vc)
        c  = si.RetrieveContent()
        vm = _find_vm(c, vm_name)
        if not vm:
            return {"success": False, "message": f"VM '{vm_name}' not found"}

        if not dest_host and not dest_datastore:
            return {"success": False, "message": "Provide a destination host and/or datastore"}

        # Resolve host
        host_obj = None
        if dest_host:
            h_view = c.viewManager.CreateContainerView(c.rootFolder, [vim.HostSystem], True)
            host_obj = next((h for h in h_view.view if h.name == dest_host), None)
            h_view.Destroy()
            if not host_obj:
                return {"success": False, "message": f"Host '{dest_host}' not found in vCenter"}

        # Resolve datastore
        ds_obj = None
        if dest_datastore:
            ds_view = c.viewManager.CreateContainerView(c.rootFolder, [vim.Datastore], True)
            ds_obj = next((d for d in ds_view.view if d.name == dest_datastore), None)
            ds_view.Destroy()
            if not ds_obj:
                return {"success": False, "message": f"Datastore '{dest_datastore}' not found in vCenter"}

        relocate = vim.vm.RelocateSpec()
        if host_obj:
            relocate.host = host_obj
            pool = _get_resource_pool(host_obj)
            if pool:
                relocate.pool = pool
        if ds_obj:
            relocate.datastore = ds_obj

        task = vm.RelocateVM_Task(spec=relocate)
        mig_type = "vMotion" if host_obj and not ds_obj else                    "Storage vMotion" if ds_obj and not host_obj else                    "Full vMotion"
        result = _wait_task(task, timeout=600)
        if result["success"]:
            result["message"] = f"{mig_type} of '{vm_name}' completed successfully"
        return result
    except Exception as e:
        return {"success": False, "message": f"Migration failed: {str(e)}"}
    finally:
        if si:
            try: Disconnect(si)
            except: pass

def _migrate_cross_vc(src_vc_id, vm_name, dst_vc_id, dest_host, dest_datastore):
    src_vc = _vc_by_id(src_vc_id)
    dst_vc = _vc_by_id(dst_vc_id)
    if not src_vc:
        return {"success": False, "message": f"Source vCenter {src_vc_id} not found"}
    if not dst_vc:
        return {"success": False, "message": f"Destination vCenter {dst_vc_id} not found"}
    si_src = si_dst = None
    try:
        si_src = _connect(src_vc)
        si_dst = _connect(dst_vc)
        c_src  = si_src.RetrieveContent()
        c_dst  = si_dst.RetrieveContent()

        vm = _find_vm(c_src, vm_name)
        if not vm:
            return {"success": False, "message": f"VM '{vm_name}' not found in source vCenter"}

        # Destination host
        h_view = c_dst.viewManager.CreateContainerView(c_dst.rootFolder, [vim.HostSystem], True)
        host_obj = next((h for h in h_view.view if h.name == dest_host), None) if dest_host else h_view.view[0] if h_view.view else None
        h_view.Destroy()
        if not host_obj:
            return {"success": False, "message": f"Destination host not found in target vCenter"}

        # Destination datastore
        ds_view = c_dst.viewManager.CreateContainerView(c_dst.rootFolder, [vim.Datastore], True)
        ds_obj = next((d for d in ds_view.view if d.name == dest_datastore), None) if dest_datastore else ds_view.view[0] if ds_view.view else None
        ds_view.Destroy()
        if not ds_obj:
            return {"success": False, "message": "Destination datastore not found in target vCenter"}

        # Destination folder
        folder = c_dst.rootFolder.childEntity[0].vmFolder

        # Cross-VC relocate spec
        relocate = vim.vm.RelocateSpec(
            host=host_obj,
            datastore=ds_obj,
            pool=host_obj.parent.resourcePool,
            folder=folder,
            service=vim.ServiceLocator(
                credential=vim.ServiceLocatorNamePassword(
                    username=dst_vc["user"], password=dst_vc["pwd"]),
                instanceUuid=c_dst.about.instanceUuid,
                sslThumbprint=c_dst.about.apiVersion,
                url=f"https://{dst_vc['host']}:443/sdk"))

        task = vm.RelocateVM_Task(spec=relocate)
        result = _wait_task(task, timeout=900)
        if result["success"]:
            result["message"] = f"VM '{vm_name}' migrated across vCenters successfully"
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        for si in [si_src, si_dst]:
            if si:
                try: Disconnect(si)
                except: pass


# ── List VM templates for a vCenter (for request form dropdown) ───────────────
def get_vc_templates(vcenter_id: str):
    """Return list of VM templates available in a vCenter."""
    v = _vc_by_id(vcenter_id)
    if not v:
        return {"templates": []}
    si = None
    try:
        si = _connect(v)
        c  = si.RetrieveContent()
        view = c.viewManager.CreateContainerView(c.rootFolder, [vim.VirtualMachine], True)
        templates = []
        for vm in view.view:
            try:
                if vm.config and vm.config.template:
                    templates.append({
                        "name":     vm.name,
                        "guest_os": vm.config.guestFullName or vm.config.guestId or "Unknown",
                        "cpu":      vm.config.hardware.numCPU,
                        "ram_gb":   round(vm.config.hardware.memoryMB / 1024, 1),
                        "disk_gb":  round(sum(
                            d.capacityInBytes for d in vm.config.hardware.device
                            if hasattr(d, 'capacityInBytes') and d.capacityInBytes
                        ) / 1024**3, 1),
                    })
            except Exception:
                continue
        view.Destroy()
        return {"templates": sorted(templates, key=lambda x: x["name"])}
    except Exception as e:
        return {"templates": [], "error": str(e)}
    finally:
        if si:
            try: Disconnect(si)
            except: pass

# ── Guest Customization (IP assignment via VMware Tools) ──────────────────────
def apply_guest_customization(vcenter_id: str, vm_name: str, ip_config: dict) -> dict:
    """
    Apply VMware Guest Customization Spec to a cloned VM to set static IP/DHCP.
    ip_config keys:
      mode        : "static" | "dhcp"
      ip_address  : "x.x.x.x"      (static only)
      subnet_mask : "255.255.255.0" (static only)
      gateway     : "x.x.x.x"      (static only)
      dns1        : "x.x.x.x"
      dns2        : "x.x.x.x"      (optional)
      hostname    : str
      domain      : str             (optional, e.g. sdxtest.local)
    Supports both Windows (Sysprep) and Linux (LinuxPrep).
    VM must be powered off and have VMware Tools installed.
    """
    vc = _vc_by_id(vcenter_id)
    if not vc:
        return {"success": False, "message": f"vCenter {vcenter_id} not found"}
    si = None
    try:
        si = _connect(vc)
        c  = si.RetrieveContent()
        vm = _find_vm(c, vm_name)
        if not vm:
            return {"success": False, "message": f"VM '{vm_name}' not found"}

        # Detect OS family from guest ID
        guest_id = (vm.config.guestId or "").lower()
        is_windows = any(x in guest_id for x in ["windows", "win", "winLong", "winNet"])

        # Build IP settings
        mode = (ip_config.get("mode") or "dhcp").lower()
        dns_list = [x for x in [ip_config.get("dns1",""), ip_config.get("dns2","")] if x]

        if mode == "static":
            ip_settings = vim.vm.customization.IPSettings(
                ip=vim.vm.customization.FixedIp(ipAddress=ip_config["ip_address"]),
                subnetMask=ip_config.get("subnet_mask","255.255.255.0"),
                gateway=[ip_config["gateway"]] if ip_config.get("gateway") else [],
                dnsServerList=dns_list,
            )
        else:
            ip_settings = vim.vm.customization.IPSettings(
                ip=vim.vm.customization.DhcpIpGenerator(),
                dnsServerList=dns_list,
            )

        # NIC mapping — apply to first NIC
        adapter_map = vim.vm.customization.AdapterMapping(adapter=ip_settings)

        # Global network settings
        global_ip = vim.vm.customization.GlobalIPSettings(
            dnsServerList=dns_list,
            dnsSuffixList=[ip_config.get("domain","")],
        )

        hostname = (ip_config.get("hostname") or vm_name).replace(" ","-")

        if is_windows:
            # Windows Sysprep identity
            identity = vim.vm.customization.Sysprep(
                guiUnattended=vim.vm.customization.GuiUnattended(
                    autoLogon=False, autoLogonCount=0,
                    timeZone=4,  # Eastern — adjust via env if needed
                ),
                userData=vim.vm.customization.UserData(
                    computerName=vim.vm.customization.FixedName(name=hostname[:15]),  # NetBIOS limit
                    fullName="CaaS Admin",
                    orgName="CaaS",
                    productId="",  # Leave blank for volume-licensed templates
                ),
                identification=vim.vm.customization.Identification(
                    domainAdmin="",
                    domainAdminPassword=None,
                    joinWorkgroup="WORKGROUP",
                ),
                licenseFilePrintData=vim.vm.customization.LicenseFilePrintData(
                    autoMode=vim.vm.customization.LicenseFilePrintData.AutoMode.perServer,
                    autoUsers=5,
                ),
            )
        else:
            # Linux LinuxPrep identity
            identity = vim.vm.customization.LinuxPrep(
                hostName=vim.vm.customization.FixedName(name=hostname),
                domain=ip_config.get("domain","localdomain"),
                hwClockUTC=True,
                timeZone="UTC",
            )

        spec = vim.vm.customization.Specification(
            identity=identity,
            globalIPSettings=global_ip,
            nicSettingMap=[adapter_map],
        )

        task = vm.CustomizeVM_Task(spec=spec)
        result = _wait_task(task, timeout=120)
        if result["success"]:
            result["message"] = (
                f"Guest customization applied to '{vm_name}' — "
                f"{'Static IP: '+ip_config.get('ip_address','') if mode=='static' else 'DHCP'}"
            )
        return result
    except Exception as e:
        return {"success": False, "message": f"Guest customization failed: {str(e)}"}
    finally:
        if si:
            try: Disconnect(si)
            except: pass


def _build_ds_type_map(h_view_list):
    """
    Build a mapping  datastore_name -> "SSD" | "HDD"  by inspecting every
    ESXi host's HostStorageSystem.  Detection uses the SMART/ATA 'ssd' flag
    on each ScsiDisk, then maps it to VMFS datastore names via extent LUN IDs.
    NFS / vSAN datastores that cannot be verified default to "HDD".
    A datastore is marked "SSD" only when ALL backing extents are SSD.
    """
    ds_type = {}   # datastore_name -> "SSD" | "HDD"

    for h in h_view_list:
        try:
            ss = h.configManager.storageSystem  # HostStorageSystem
            if ss is None:
                continue

            # Step 1 – collect canonical names of SSD LUNs on this host
            ssd_luns = set()
            try:
                for disk in (ss.storageDeviceInfo.scsiDisk or []):
                    if getattr(disk, "ssd", False):
                        ssd_luns.add(disk.canonicalName)
            except Exception:
                pass

            # Step 2 – walk VMFS extents to map datastore → SSD/HDD
            try:
                for mount in (ss.fileSystemVolumeInfo.mountInfo or []):
                    vol = mount.volume
                    # Only VMFS volumes have extents backed by local LUNs
                    if not hasattr(vol, "extent"):
                        continue
                    ds_name = vol.name
                    try:
                        extents = vol.extent or []
                        if not extents:
                            continue
                        # SSD only if EVERY extent is on an SSD LUN
                        all_ssd = all(
                            (getattr(ext, "diskName", None) or "") in ssd_luns
                            for ext in extents
                        )
                        # Only upgrade HDD→SSD; never downgrade an already-SSD result
                        if ds_name not in ds_type:
                            ds_type[ds_name] = "SSD" if all_ssd else "HDD"
                        elif all_ssd:
                            ds_type[ds_name] = "SSD"
                    except Exception:
                        continue
            except Exception:
                pass
        except Exception:
            continue

    return ds_type


def get_vc_resources(vcenter_id: str):
    """
    Return hosts, all datastores, all networks for a vCenter.
    Each host also carries its own datastores[] and networks[] lists
    so the frontend can filter dropdowns when a host is selected.
    disk_type ("SSD"|"HDD") is detected via ESXi SMART/ATA ScsiDisk.ssd flag.
    """
    vc = _vc_by_id(vcenter_id)
    if not vc:
        return {"hosts": [], "datastores": [], "networks": []}
    si = None
    try:
        si = _connect(vc)
        c  = si.RetrieveContent()

        # ── Collect all hosts (need them for SSD detection too) ────────────────
        h_view = c.viewManager.CreateContainerView(c.rootFolder, [vim.HostSystem], True)
        h_list = list(h_view.view)

        # ── Build datastore → disk_type map using ESXi SMART detection ────────
        ds_type_map = _build_ds_type_map(h_list)

        hosts = []
        for h in h_list:
            try:
                total_mhz    = h.hardware.cpuInfo.hz * h.hardware.cpuInfo.numCpuCores / 1_000_000
                used_mhz     = h.summary.quickStats.overallCpuUsage or 0
                cpu_free_pct = round((1 - used_mhz / total_mhz) * 100, 1) if total_mhz > 0 else 100
                ram_total_gb = round(h.hardware.memorySize / 1024**3, 1)
                ram_used_gb  = round((h.summary.quickStats.overallMemoryUsage or 0) / 1024, 1)
                ram_free_gb  = round(ram_total_gb - ram_used_gb, 1)
            except Exception:
                cpu_free_pct = 100; ram_total_gb = 0; ram_free_gb = 0

            # Datastores mounted on this host — include detected disk_type
            host_ds = []
            try:
                for ds in (h.datastore or []):
                    try:
                        ds_name = ds.name
                        host_ds.append({
                            "name":      ds_name,
                            "free_gb":   round(ds.summary.freeSpace / 1024**3, 1),
                            "total_gb":  round(ds.summary.capacity  / 1024**3, 1),
                            "disk_type": ds_type_map.get(ds_name, "HDD"),
                        })
                    except Exception:
                        continue
            except Exception:
                pass

            # Networks (portgroups) accessible by this host
            host_nets = []
            try:
                for n in (h.network or []):
                    try:
                        net_type = "DVS" if isinstance(n, vim.dvs.DistributedVirtualPortgroup) else "Standard"
                        host_nets.append({"name": n.name, "type": net_type})
                    except Exception:
                        continue
                host_nets.sort(key=lambda x: x["name"])
            except Exception:
                pass

            hosts.append({
                "name":         h.name,
                "status":       str(h.runtime.connectionState),
                "cpu_free_pct": cpu_free_pct,
                "ram_total_gb": ram_total_gb,
                "ram_free_gb":  ram_free_gb,
                "datastores":   host_ds,    # host-specific, with disk_type
                "networks":     host_nets,  # host-specific
            })
        h_view.Destroy()

        # ── All datastores (fallback when no host selected) — include disk_type ─
        ds_view = c.viewManager.CreateContainerView(c.rootFolder, [vim.Datastore], True)
        all_ds = []
        seen_ds = set()
        for d in ds_view.view:
            try:
                if d.name in seen_ds: continue
                seen_ds.add(d.name)
                all_ds.append({
                    "name":      d.name,
                    "free_gb":   round(d.summary.freeSpace / 1024**3, 1),
                    "total_gb":  round(d.summary.capacity  / 1024**3, 1),
                    "disk_type": ds_type_map.get(d.name, "HDD"),
                })
            except Exception:
                continue
        ds_view.Destroy()

        # ── All networks (fallback when no host selected) ──────────────────────
        net_view = c.viewManager.CreateContainerView(c.rootFolder, [vim.Network], True)
        all_nets = []
        seen_nets = set()
        for n in net_view.view:
            try:
                if n.name in seen_nets: continue
                seen_nets.add(n.name)
                net_type = "DVS" if isinstance(n, vim.dvs.DistributedVirtualPortgroup) else "Standard"
                all_nets.append({"name": n.name, "type": net_type})
            except Exception:
                continue
        net_view.Destroy()
        all_nets.sort(key=lambda x: x["name"])

        return {"hosts": hosts, "datastores": all_ds, "networks": all_nets}
    except Exception as e:
        return {"hosts": [], "datastores": [], "networks": [], "error": str(e)}
    finally:
        if si:
            try: Disconnect(si)
            except: pass

# ── Quick action test ─────────────────────────────────────────────────────────
# Run: python vmware_client.py
# Prints vCenter IDs and tests vm_power_action lookup
if __name__ == "__main__":
    print("vCenter list:")
    for vc in get_vcenter_list():
        print(f"  id={vc['id']}  name={vc['name']}  host={vc['host']}")
    
    if VCENTERS:
        vc = VCENTERS[0]
        result = _vc_by_id(vc["host"])
        print(f"\n_vc_by_id('{vc['host']}') -> {'FOUND' if result else 'NOT FOUND'}")

# ── VM Provisioning (called on request approval) ───────────────────────────────
def provision_vm(data: dict) -> dict:
    """
    Provision a new VM from a template or as a blank VM.
    data: vcenter_id, vm_name, cpu, ram_gb, disk_gb, os_template,
          host, datastore, network
    """
    vc = _vc_by_id(data["vcenter_id"])
    if not vc:
        return {"success": False, "message": f"vCenter {data['vcenter_id']} not found"}
    si = None
    try:
        si = _connect(vc)
        c  = si.RetrieveContent()

        # Find template VM by os_template name
        template_vm = _find_vm(c, data["os_template"])

        if template_vm:
            # Clone from template
            result = _clone_same_vc(
                vcenter_id    = data["vcenter_id"],
                vm_name       = data["os_template"],
                clone_name    = data["vm_name"],
                dest_host     = data.get("host") or None,
                dest_datastore= data.get("datastore") or None,
                power_on      = False
            )
            if not result["success"]:
                return result

            # After clone, reconfigure CPU/RAM
            new_vm = _find_vm(c, data["vm_name"])
            if new_vm:
                spec = vim.vm.ConfigSpec(
                    numCPUs      = int(data["cpu"]),
                    memoryMB     = int(data["ram_gb"]) * 1024,
                    numCoresPerSocket = 1
                )
                task = new_vm.ReconfigVM_Task(spec=spec)
                _wait_task(task, timeout=60)

            result["message"] = f"VM '{data['vm_name']}' provisioned from template '{data['os_template']}'"
            return result
        else:
            # No template found — create blank VM
            # Find destination host
            h_view = c.viewManager.CreateContainerView(c.rootFolder, [vim.HostSystem], True)
            host_obj = None
            if data.get("host"):
                host_obj = next((h for h in h_view.view if h.name == data["host"]), None)
            if not host_obj and h_view.view:
                host_obj = h_view.view[0]
            h_view.Destroy()
            if not host_obj:
                return {"success": False, "message": "No host available for provisioning"}

            # Find datastore
            ds_view = c.viewManager.CreateContainerView(c.rootFolder, [vim.Datastore], True)
            ds_obj = None
            if data.get("datastore"):
                ds_obj = next((d for d in ds_view.view if d.name == data["datastore"]), None)
            if not ds_obj and ds_view.view:
                ds_obj = ds_view.view[0]
            ds_view.Destroy()
            if not ds_obj:
                return {"success": False, "message": "No datastore available"}

            # Find network
            net_view = c.viewManager.CreateContainerView(
                c.rootFolder, [vim.Network], True)
            net_obj = None
            if data.get("network"):
                net_obj = next((n for n in net_view.view if n.name == data["network"]), None)
            net_view.Destroy()

            # Build VM config
            vm_folder = c.rootFolder.childEntity[0].vmFolder
            resource_pool = host_obj.parent.resourcePool

            config = vim.vm.ConfigSpec(
                name         = data["vm_name"],
                numCPUs      = int(data["cpu"]),
                memoryMB     = int(data["ram_gb"]) * 1024,
                numCoresPerSocket = 1,
                guestId      = "otherGuest64",
                files        = vim.vm.FileInfo(vmPathName=f"[{ds_obj.name}]"),
            )

            # Add disk
            disk_spec = vim.vm.device.VirtualDeviceSpec()
            disk_spec.operation     = vim.vm.device.VirtualDeviceSpec.Operation.add
            disk_spec.fileOperation = vim.vm.device.VirtualDeviceSpec.FileOperation.create
            disk              = vim.vm.device.VirtualDisk()
            disk.capacityInKB = int(data["disk_gb"]) * 1024 * 1024
            disk.unitNumber   = 0
            disk_backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
            disk_backing.diskMode   = "persistent"
            disk_backing.datastore  = ds_obj
            disk.backing            = disk_backing
            controller = vim.vm.device.VirtualLsiLogicController()
            controller.key    = 1000
            controller.busNumber = 0
            controller.sharedBus = vim.vm.device.VirtualSCSIController.Sharing.noSharing
            ctrl_spec = vim.vm.device.VirtualDeviceSpec()
            ctrl_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
            ctrl_spec.device    = controller
            disk.controllerKey  = 1000
            disk_spec.device    = disk
            config.deviceChange = [ctrl_spec, disk_spec]

            # Add network adapter if found
            if net_obj:
                nic_spec   = vim.vm.device.VirtualDeviceSpec()
                nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                nic        = vim.vm.device.VirtualVmxnet3()
                nic_backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
                nic_backing.network    = net_obj
                nic_backing.deviceName = data["network"]
                nic.backing  = nic_backing
                nic_spec.device = nic
                config.deviceChange.append(nic_spec)

            task = vm_folder.CreateVM_Task(config=config, pool=resource_pool, host=host_obj)
            result = _wait_task(task, timeout=120)
            if result["success"]:
                result["message"] = f"VM '{data['vm_name']}' created successfully (blank VM — no template '{data['os_template']}' found)"
            return result

    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if si:
            try: Disconnect(si)
            except: pass

# ── Delete Snapshot ────────────────────────────────────────────────────────────
def vm_delete_snapshot(vcenter_id: str, vm_name: str, snap_name: str) -> dict:
    vc = _vc_by_id(vcenter_id)
    if not vc: return {"success": False, "message": f"vCenter {vcenter_id} not found"}
    si = None
    try:
        si = _connect(vc)
        c  = si.RetrieveContent()
        vm = _find_vm(c, vm_name)
        if not vm: return {"success": False, "message": f"VM '{vm_name}' not found"}

        def _find_snap(snap_list, name):
            for s in snap_list:
                if s.name == name: return s.snapshot
                found = _find_snap(s.childSnapshotList, name)
                if found: return found
            return None

        root = vm.snapshot
        if not root: return {"success": False, "message": "VM has no snapshots"}
        snap = _find_snap(root.rootSnapshotList, snap_name)
        if not snap: return {"success": False, "message": f"Snapshot '{snap_name}' not found"}

        task = snap.RemoveSnapshot_Task(removeChildren=False)
        _wait_task(task, timeout=120)
        return {"success": True, "message": f"Snapshot '{snap_name}' deleted from '{vm_name}'"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if si:
            try: Disconnect(si)
            except: pass

# ── VM Reconfig (CPU / RAM / Disk) ────────────────────────────────────────────
def vm_reconfig(vcenter_id: str, vm_name: str, cpu: int, ram_gb: int, disk_gb: int) -> dict:
    vc = _vc_by_id(vcenter_id)
    if not vc: return {"success": False, "message": f"vCenter {vcenter_id} not found"}
    si = None
    try:
        si = _connect(vc)
        c  = si.RetrieveContent()
        vm = _find_vm(c, vm_name)
        if not vm: return {"success": False, "message": f"VM '{vm_name}' not found"}

        # CPU + RAM reconfig
        spec = vim.vm.ConfigSpec(
            numCPUs  = int(cpu),
            memoryMB = int(ram_gb) * 1024,
        )
        task = vm.ReconfigVM_Task(spec=spec)
        _wait_task(task, timeout=60)

        # Disk resize — find first virtual disk and extend if larger
        current_disk_kb = 0
        disk_device = None
        for dev in vm.config.hardware.device:
            if isinstance(dev, vim.vm.device.VirtualDisk):
                current_disk_kb = dev.capacityInKB
                disk_device = dev
                break

        new_disk_kb = disk_gb * 1024 * 1024
        if disk_device and new_disk_kb > current_disk_kb:
            disk_device.capacityInKB = new_disk_kb
            disk_spec = vim.vm.device.VirtualDeviceSpec()
            disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            disk_spec.device = disk_device
            disk_config = vim.vm.ConfigSpec(deviceChange=[disk_spec])
            task2 = vm.ReconfigVM_Task(spec=disk_config)
            _wait_task(task2, timeout=60)

        return {"success": True, "message": f"VM '{vm_name}' reconfigured: {cpu} vCPUs, {ram_gb}GB RAM, {disk_gb}GB disk"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if si:
            try: Disconnect(si)
            except: pass

# ── Host Actions (reboot / shutdown / maintenance) ────────────────────────────
def vm_host_action(vcenter_id: str, host_name: str, action: str) -> dict:
    vc = _vc_by_id(vcenter_id)
    if not vc: return {"success": False, "message": f"vCenter {vcenter_id} not found"}
    si = None
    try:
        si = _connect(vc)
        c  = si.RetrieveContent()
        h_view = c.viewManager.CreateContainerView(c.rootFolder, [vim.HostSystem], True)
        host = next((h for h in h_view.view if h.name == host_name), None)
        h_view.Destroy()
        if not host: return {"success": False, "message": f"Host '{host_name}' not found"}

        if action == "maintenance":
            task = host.EnterMaintenanceMode_Task(timeout=0, evacuatePoweredOffVms=False)
            _wait_task(task, timeout=120)
        elif action == "exit_maintenance":
            task = host.ExitMaintenanceMode_Task(timeout=0)
            _wait_task(task, timeout=120)
        elif action == "reboot":
            host.RebootHost_Task(force=False)
        elif action == "shutdown":
            host.ShutdownHost_Task(force=False)
        else:
            return {"success": False, "message": f"Unknown action: {action}"}

        return {"success": True, "message": f"Host '{host_name}' {action} initiated"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if si:
            try: Disconnect(si)
            except: pass

# ── VM Delete from Disk ────────────────────────────────────────────────────────
def vm_delete_from_disk(vcenter_id: str, vm_name: str) -> dict:
    vc = _vc_by_id(vcenter_id)
    if not vc:
        return {"success": False, "message": f"vCenter {vcenter_id} not found"}
    try:
        si = _connect(vc)
        cnt = si.RetrieveContent().viewManager.CreateContainerView(
            si.RetrieveContent().rootFolder, [vim.VirtualMachine], True)
        vm = next((v for v in cnt.view if v.name == vm_name), None)
        if not vm:
            return {"success": False, "message": f"VM '{vm_name}' not found"}
        # Power off first if running
        if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
            task = vm.PowerOff()
            _wait_task(task)
        task = vm.Destroy_Task()
        _wait_task(task)
        return {"success": True, "message": f"VM '{vm_name}' deleted from disk"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# ── vCenter Add / Delete / Test / Reload ──────────────────────────────────────
def _env_path():
    return Path(__file__).parent / ".env"

def _read_env():
    p = _env_path()
    return p.read_text(encoding="utf-8") if p.exists() else ""

def _write_env(text):
    _env_path().write_text(text, encoding="utf-8")

def test_vcenter_connection(host, user, password, port=443):
    try:
        si = SmartConnect(host=host, user=user, pwd=password, port=port,
                         sslContext=__import__('ssl').create_default_context())
        si.content  # access to confirm
        return {"success": True, "message": f"Connected to {host} OK"}
    except Exception:
        pass
    try:
        import ssl as _ssl
        ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False; ctx.verify_mode = _ssl.CERT_NONE
        si = SmartConnect(host=host, user=user, pwd=password, port=port, sslContext=ctx)
        si.content
        return {"success": True, "message": f"Connected to {host} OK (self-signed cert)"}
    except Exception as e:
        return {"success": False, "message": f"Cannot connect: {e}"}

def admin_add_vcenter(host, name, user, password, port=443):
    global VCENTERS
    # Test connection first
    test = test_vcenter_connection(host, user, password, port)
    if not test.get("success"):
        return test
    if any(v["host"] == host for v in VCENTERS):
        return {"success": False, "message": f"vCenter {host} already exists"}
    # Count existing entries to pick next index
    env = _read_env()
    idx = len(VCENTERS) + 1
    # Append to .env
    block = (f"\n# vCenter added via GUI\n"
             f"VCENTER_HOSTS={','.join([v['host'] for v in VCENTERS] + [host])}\n"
             if idx == 1 else "")
    # Simpler: just update VCENTER_HOSTS line and add per-vc entries
    import re
    hosts_line = ",".join([v["host"] for v in VCENTERS] + [host])
    if re.search(r"^VCENTER_HOSTS=", env, re.MULTILINE):
        env = re.sub(r"^VCENTER_HOSTS=.*$", f"VCENTER_HOSTS={hosts_line}", env, flags=re.MULTILINE)
    elif re.search(r"^VCENTER_HOST=", env, re.MULTILINE):
        env = re.sub(r"^VCENTER_HOST=.*$", f"VCENTER_HOSTS={hosts_line}", env, flags=re.MULTILINE)
    else:
        env += f"\nVCENTER_HOSTS={hosts_line}\n"
    env += (f"VCENTER_NAME_{idx}={name}\n"
            f"VCENTER_USER_{idx}={user}\n"
            f"VCENTER_PASSWORD_{idx}={password}\n")
    if port != 443:
        env += f"VCENTER_PORT_{idx}={port}\n"
    _write_env(env)
    VCENTERS.append({"host": host, "user": user, "pwd": password, "port": port, "name": name})
    return {"success": True, "message": f"vCenter {name} ({host}) added", "vcenters": get_vcenter_list()}

def admin_delete_vcenter(vcenter_id):
    global VCENTERS
    vc = next((v for v in VCENTERS if v["host"] == vcenter_id), None)
    if not vc:
        return {"success": False, "message": f"vCenter {vcenter_id} not found"}
    VCENTERS = [v for v in VCENTERS if v["host"] != vcenter_id]
    # Rewrite .env VCENTER_HOSTS line
    import re
    env = _read_env()
    hosts_line = ",".join(v["host"] for v in VCENTERS)
    if hosts_line:
        env = re.sub(r"^VCENTER_HOST[S]?=.*$", f"VCENTER_HOSTS={hosts_line}", env, flags=re.MULTILINE)
    else:
        env = re.sub(r"^VCENTER_HOST[S]?=.*\n?", "", env, flags=re.MULTILINE)
    _write_env(env)
    return {"success": True, "message": f"vCenter {vcenter_id} removed", "vcenters": get_vcenter_list()}

def reload_vcenters():
    global VCENTERS
    load_dotenv(dotenv_path=_env_path(), override=True)
    VCENTERS = _vcenter_list()
    return VCENTERS


# ── Topology helpers ──────────────────────────────────────────────────────────

def get_vm_topology(vcenter_id: str, vm_name: str):
    """Fetch full topology for a single VM: disks→datastores, NICs→portgroup→vSwitch/DVS→VLAN."""
    vc = next((v for v in VCENTERS if v["host"] == vcenter_id), None)
    if not vc:
        return {"error": "vCenter not found"}
    si = None
    try:
        si = _connect(vc)
        content = si.RetrieveContent()
        cnt = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        vm = next((v for v in cnt.view if v.summary.config and v.summary.config.name == vm_name), None)
        if not vm:
            return {"error": f"VM '{vm_name}' not found"}

        s = vm.summary
        host_obj = s.runtime.host if s.runtime else None

        result = {
            "name": vm_name,
            "vcenter_id": vcenter_id,
            "vcenter_name": vc["name"],
            "status": str(s.runtime.powerState) if s.runtime else "unknown",
            "cpu": s.config.numCpu if s.config else 0,
            "ram_gb": round((s.config.memorySizeMB or 0) / 1024, 1) if s.config else 0,
            "guest_os": s.config.guestFullName if s.config else "",
            "host": host_obj.name if host_obj else "N/A",
            "uuid": vm.config.uuid if vm.config else "",
            "annotation": (vm.config.annotation or "").strip() if vm.config else "",
            "tools_status": str(vm.guest.toolsRunningStatus or "") if vm.guest else "",
            "uptime_sec": (s.quickStats.uptimeSeconds or 0) if s.quickStats else 0,
            "disks": [],
            "nics": [],
        }

        if vm.config and vm.config.hardware:
            # ── Disks ────────────────────────────────────────────────
            for dev in vm.config.hardware.device:
                if isinstance(dev, vim.vm.device.VirtualDisk):
                    ds_name, file_path, thin = "", "", False
                    try:
                        if hasattr(dev.backing, "fileName"):
                            file_path = dev.backing.fileName
                            m = re.match(r"\[([^\]]+)\]", file_path)
                            if m:
                                ds_name = m.group(1)
                        thin = getattr(dev.backing, "thinProvisioned", False)
                    except Exception:
                        pass
                    result["disks"].append({
                        "label": dev.deviceInfo.label if dev.deviceInfo else "Disk",
                        "capacity_gb": round((dev.capacityInKB or 0) / (1024 * 1024), 1),
                        "datastore": ds_name,
                        "file_path": file_path,
                        "thin": bool(thin),
                    })

            # ── NICs ─────────────────────────────────────────────────
            for dev in vm.config.hardware.device:
                if not isinstance(dev, vim.vm.device.VirtualEthernetCard):
                    continue
                nic_type = type(dev).__name__.replace("Virtual", "")
                pg_name, vlan_id, switch_name, switch_type = "", "—", "—", "—"
                try:
                    if isinstance(dev.backing, vim.vm.device.VirtualEthernetCard.NetworkBackingInfo):
                        pg_name = dev.backing.deviceName or ""
                        switch_type = "vSwitch"
                        if host_obj and pg_name:
                            for vs in (host_obj.config.network.vswitch or []):
                                for pg in (host_obj.config.network.portgroup or []):
                                    if pg.spec.name == pg_name and pg.spec.vswitchName == vs.name:
                                        switch_name = vs.name
                                        vlan_id = str(pg.spec.vlanId) if pg.spec.vlanId else "0"
                                        break
                                if switch_name != "—":
                                    break
                    elif isinstance(dev.backing, vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
                        switch_type = "DVS"
                        pg_key = dev.backing.port.portgroupKey
                        cnt2 = content.viewManager.CreateContainerView(
                            content.rootFolder, [vim.dvs.DistributedVirtualPortgroup], True)
                        for dpg in cnt2.view:
                            if dpg.key == pg_key:
                                pg_name = dpg.name
                                try:
                                    vlan_cfg = dpg.config.defaultPortConfig.vlan
                                    if hasattr(vlan_cfg, "vlanId"):
                                        vlan_id = str(vlan_cfg.vlanId)
                                    elif hasattr(vlan_cfg, "ranges"):
                                        vlan_id = ",".join(f"{r.start}-{r.end}" for r in vlan_cfg.ranges)
                                except Exception:
                                    pass
                                try:
                                    switch_name = dpg.config.distributedVirtualSwitch.name
                                except Exception:
                                    switch_name = "DVS"
                                break
                except Exception:
                    pass

                mac = dev.macAddress or ""
                connected, ip_list = False, []
                if vm.guest and vm.guest.net:
                    for gn in vm.guest.net:
                        if gn.macAddress and gn.macAddress.lower() == mac.lower():
                            connected = gn.connected
                            ip_list = [ip for ip in (gn.ipAddress or [])
                                       if not ip.startswith("169.254") and ":" not in ip]
                            break

                result["nics"].append({
                    "label": dev.deviceInfo.label if dev.deviceInfo else "NIC",
                    "type": nic_type,
                    "mac": mac,
                    "portgroup": pg_name,
                    "vlan": vlan_id,
                    "switch": switch_name,
                    "switch_type": switch_type,
                    "connected": connected,
                    "ips": ip_list,
                })

        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        if si:
            try:
                from pyVim.connect import Disconnect as _D; _D(si)
            except Exception:
                pass


def get_host_topology(vcenter_id: str, host_name: str):
    """Fetch full topology for a single ESXi host: VMs, pNICs, vSwitches, DVS, VMkernels."""
    vc = next((v for v in VCENTERS if v["host"] == vcenter_id), None)
    if not vc:
        return {"error": "vCenter not found"}
    si = None
    try:
        si = _connect(vc)
        content = si.RetrieveContent()
        cnt = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True)
        host = next((h for h in cnt.view if h.summary.config and h.summary.config.name == host_name), None)
        if not host:
            return {"error": f"Host '{host_name}' not found"}

        s = host.summary; hw = s.hardware; q = s.quickStats
        tc = (hw.numCpuCores or 0) * (hw.cpuMhz or 0)
        uc = q.overallCpuUsage or 0
        tr = round((hw.memorySize or 0) / (1024 ** 3), 1)
        ur = round((q.overallMemoryUsage or 0) / 1024, 1)

        result = {
            "name": host_name,
            "vcenter_id": vcenter_id,
            "vcenter_name": vc["name"],
            "status": str(s.runtime.connectionState) if s.runtime else "unknown",
            "cpu_model": hw.cpuModel if hw else "",
            "cpu_cores": hw.numCpuCores if hw else 0,
            "cpu_used_pct": round((uc / tc) * 100, 1) if tc else 0,
            "ram_total_gb": tr,
            "ram_used_gb": ur,
            "ram_free_pct": round(((tr - ur) / tr) * 100, 1) if tr else 0,
            "vms": [],
            "vswitches": [],
            "dvs_uplinks": [],
            "pnics": [],
            "vmknics": [],
        }

        # VMs running on this host
        vm_cnt = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        for vm in vm_cnt.view:
            try:
                if vm.summary.runtime.host and vm.summary.runtime.host.name == host_name:
                    if not (vm.name.startswith("vCLS") or vm.name.startswith("vCLS-")):
                        result["vms"].append({
                            "name": vm.summary.config.name,
                            "status": str(vm.summary.runtime.powerState),
                            "cpu": vm.summary.config.numCpu,
                            "ram_gb": round((vm.summary.config.memorySizeMB or 0) / 1024, 1),
                        })
            except Exception:
                pass

        if host.config and host.config.network:
            net = host.config.network

            # CDP / LLDP neighbor hints  (QueryNetworkHint per pNIC)
            cdp_map = {}
            try:
                net_sys = host.configManager.networkSystem
                devices = [p.device for p in (net.pnic or [])]
                hints = net_sys.QueryNetworkHint(device=devices) if devices else []
                for hint in (hints or []):
                    entry = {}
                    # CDP
                    csp = getattr(hint, "connectedSwitchPort", None)
                    if csp:
                        entry = {
                            "protocol":    "CDP",
                            "device_id":   getattr(csp, "devId",            "") or "",
                            "port_id":     getattr(csp, "portId",           "") or "",
                            "hw_platform": getattr(csp, "hardwarePlatform", "") or "",
                            "system_name": getattr(csp, "systemName",       "") or "",
                            "mgmt_addr":   getattr(csp, "mgmtAddr",         "") or "",
                        }
                    # LLDP (vim.host.PhysicalNic.LldpInfo)
                    lldp = getattr(hint, "lldpInfo", None)
                    if lldp:
                        params = {p.key: p.value for p in (getattr(lldp, "parameter", []) or [])}
                        entry = {
                            "protocol":    "LLDP",
                            "device_id":   getattr(lldp, "chassisId",    "") or "",
                            "port_id":     getattr(lldp, "portId",       "") or "",
                            "hw_platform": params.get("System Description", params.get("systemDescription", "")) or "",
                            "system_name": params.get("System Name",        params.get("systemName", ""))        or "",
                            "mgmt_addr":   params.get("Management Address", params.get("managementAddress", "")) or "",
                        }
                    if entry:
                        cdp_map[hint.device] = entry
            except Exception:
                pass

            # Physical NICs
            for pnic in (net.pnic or []):
                speed = 0
                try:
                    speed = pnic.linkSpeed.speedMb if pnic.linkSpeed else 0
                except Exception:
                    pass
                neighbor = cdp_map.get(pnic.device, {})
                result["pnics"].append({
                    "device":      pnic.device,
                    "mac":         pnic.mac or "",
                    "speed_mb":    speed,
                    "driver":      pnic.driver or "",
                    "neighbor":    neighbor,   # CDP/LLDP switch info
                })

            # Standard vSwitches
            for vs in (net.vswitch or []):
                portgroups = []
                for pg in (net.portgroup or []):
                    if pg.spec.vswitchName == vs.name:
                        portgroups.append({
                            "name": pg.spec.name,
                            "vlan": pg.spec.vlanId,
                        })
                uplinks = []
                try:
                    if hasattr(vs.spec, "bridge") and hasattr(vs.spec.bridge, "nicDevice"):
                        uplinks = list(vs.spec.bridge.nicDevice)
                except Exception:
                    pass
                result["vswitches"].append({
                    "name": vs.name,
                    "uplinks": uplinks,
                    "portgroups": portgroups,
                    "mtu": getattr(vs.spec, "mtu", 1500),
                    "num_ports": getattr(vs.spec, "numPorts", 0),
                })

            # DVS proxy switches (distributed)
            for proxy in (net.proxySwitch or []):
                uplinks = []
                try:
                    for spec in (proxy.spec.backing.pnicSpec or []):
                        uplinks.append(spec.pnicDevice)
                except Exception:
                    pass
                pg_list = []
                try:
                    dvs_cnt = content.viewManager.CreateContainerView(
                        content.rootFolder, [vim.dvs.DistributedVirtualPortgroup], True)
                    for dpg in dvs_cnt.view:
                        try:
                            if dpg.config.distributedVirtualSwitch and \
                               hasattr(proxy, "dvsUuid") and \
                               dpg.config.distributedVirtualSwitch.uuid == proxy.dvsUuid:
                                vlan_id = "—"
                                try:
                                    vlan_cfg = dpg.config.defaultPortConfig.vlan
                                    if hasattr(vlan_cfg, "vlanId"):
                                        vlan_id = str(vlan_cfg.vlanId)
                                    elif hasattr(vlan_cfg, "ranges"):
                                        vlan_id = ",".join(f"{r.start}-{r.end}" for r in vlan_cfg.ranges)
                                except Exception:
                                    pass
                                pg_list.append({"name": dpg.name, "vlan": vlan_id})
                        except Exception:
                            pass
                except Exception:
                    pass
                result["dvs_uplinks"].append({
                    "dvs_name": getattr(proxy, "dvsName", "DVS"),
                    "uplinks": uplinks,
                    "num_ports": getattr(proxy, "numPorts", 0),
                    "portgroups": pg_list,
                })

            # VMkernel adapters
            for vnic in (net.vnic or []):
                pg_name, vlan = "", 0
                try:
                    pg_name = vnic.spec.portgroup if hasattr(vnic.spec, "portgroup") else ""
                    for pg in (net.portgroup or []):
                        if pg.spec.name == pg_name:
                            vlan = pg.spec.vlanId
                            break
                except Exception:
                    pass
                result["vmknics"].append({
                    "device": vnic.device,
                    "ip": vnic.spec.ip.ipAddress if vnic.spec and vnic.spec.ip else "",
                    "mac": getattr(vnic.spec, "mac", ""),
                    "portgroup": pg_name,
                    "vlan": vlan,
                    "mtu": getattr(vnic.spec, "mtu", 1500),
                })

        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        if si:
            try:
                from pyVim.connect import Disconnect as _D; _D(si)
            except Exception:
                pass


def get_volume_vcenter_mapping(naa_id: str = "", wwn: str = "",
                               storage_iqns: list = None,
                               storage_wwns: list = None) -> list:
    """
    Query all configured vCenters IN PARALLEL for ESXi hosts that see a
    storage LUN identified by its NAA canonical name or WWN.
    Returns a list of dicts per matching ESXi host:
      { vcenter, vcenter_ip, esxi_host,
        datastores:[{name,type,total_gb,free_gb}],
        esxi_iqns:[str], hba_wwpns:[str],
        matched_iqns:[str], matched_wwns:[str],
        lun_seen:bool, match_type:str }
    Safe / best-effort — never raises.
    """
    import concurrent.futures as _cfe
    import socket as _sock

    if not naa_id and not wwn and not storage_iqns:
        return []

    naa_lower  = (naa_id or "").lower().replace(" ", "")
    wwn_lower  = (wwn    or "").lower().replace(":", "").replace(" ", "")
    stor_iqns  = [q.lower().strip() for q in (storage_iqns or []) if q]
    stor_wwns  = [w.lower().replace(":", "").strip() for w in (storage_wwns or []) if w]
    # Build list of all NAA variants to search (full canonical + serial-only)
    naa_variants = [v for v in [naa_lower] if v]
    if naa_lower and naa_lower.startswith("naa.624a9370"):
        # Also accept the bare-serial form in case vCenter reports it
        naa_variants.append("naa." + naa_lower[len("naa.624a9370"):])
    elif naa_lower and naa_lower.startswith("naa.") and not naa_lower.startswith("naa.624a9370"):
        # Check if this could be a Pure serial — add vendor-prefixed form too
        bare = naa_lower[4:]
        naa_variants.append("naa.624a9370" + bare)

    def _scan_vc(vc_cfg):
        """Scan one vCenter; scan all hosts in parallel. Returns list of matching host dicts."""
        vc_results = []
        si = None
        try:
            old_to = _sock.getdefaulttimeout()
            _sock.setdefaulttimeout(6)
            try:
                si = _connect(vc_cfg)
            finally:
                _sock.setdefaulttimeout(old_to)

            content  = si.RetrieveContent()
            h_view   = content.viewManager.CreateContainerView(
                content.rootFolder, [vim.HostSystem], True)

            vc_name = vc_cfg.get("name", vc_cfg.get("host", ""))
            vc_ip   = vc_cfg.get("host", "")
            hosts   = list(h_view.view)

            def _scan_host(host):
                """Scan one ESXi host for NAA/WWN match; return dict or None."""
                try:
                    hname = ""
                    try: hname = host.summary.config.name
                    except Exception: pass

                    seen_naa  = False
                    hba_wwpns = []
                    esxi_iqns = []
                    ds_names  = []

                    ss = None
                    try: ss = host.configManager.storageSystem
                    except Exception: pass

                    if ss:
                        try:
                            sd = ss.storageDeviceInfo  # single RPC fetch
                            # Check scsiLun for any NAA variant match
                            seen_naa_val = ""
                            for lun in (sd.scsiLun or []):
                                cn  = (getattr(lun, "canonicalName", "") or "").lower()
                                uid = (getattr(lun, "uuid",          "") or "").lower()
                                for nv in naa_variants:
                                    if nv and (nv in cn or nv in uid):
                                        seen_naa = True
                                        seen_naa_val = cn or uid
                                        break
                                if seen_naa:
                                    break
                            # Collect IQNs + WWPNs from HBAs
                            for hba in (sd.hostBusAdapter or []):
                                iqn = getattr(hba, "iScsiName", None)
                                if iqn:
                                    esxi_iqns.append(iqn)
                                wp = getattr(hba, "portWorldWideName", None)
                                if wp:
                                    hba_wwpns.append(
                                        format(wp, "016x") if isinstance(wp, int)
                                        else str(wp).replace(":", "").lower()
                                    )
                        except Exception:
                            pass

                        # Map LUN -> datastores via VMFS extents using all NAA variants
                        try:
                            for mount in (ss.fileSystemVolumeInfo.mountInfo or []):
                                mvol = mount.volume
                                if not hasattr(mvol, "extent"):
                                    continue
                                for ext in (mvol.extent or []):
                                    dn = (getattr(ext, "diskName", "") or "").lower()
                                    for nv in naa_variants:
                                        if nv and nv in dn:
                                            ds_names.append(mvol.name)
                                            seen_naa = True  # LUN confirmed via VMFS extent
                                            break
                                    else:
                                        continue
                                    break
                        except Exception:
                            pass

                    # WWN match check (any variant)
                    seen_wwn = any(wwn_lower in w for w in hba_wwpns) if wwn_lower else False

                    # IQN cross-match: ESXi IQN in storage-side IQN list
                    matched_iqns = []
                    if stor_iqns:
                        for eq in esxi_iqns:
                            eql = eq.lower()
                            for sq in stor_iqns:
                                if eql == sq or eql in sq or sq in eql:
                                    matched_iqns.append(eq)
                                    break
                    seen_iqn = bool(matched_iqns)

                    # WWN cross-match
                    matched_wwns = [w for w in hba_wwpns if any(sv in w for sv in stor_wwns)] if stor_wwns else []

                    # Must match by at least one method
                    if not (seen_naa or seen_wwn or seen_iqn or matched_wwns):
                        return None

                    match_type = "naa" if seen_naa else ("iqn" if seen_iqn else "wwn")

                    # Build datastore detail list
                    # If we have NAA-backed ds_names, use them; otherwise for IQN matches
                    # scan all VMFS extents for any array NAA to find the datastore
                    if not ds_names and (seen_iqn or seen_wwn) and ss:
                        try:
                            for mount in (ss.fileSystemVolumeInfo.mountInfo or []):
                                mvol = mount.volume
                                if not hasattr(mvol, "extent"):
                                    continue
                                # Accept any NAA that looks like an array LUN
                                for ext in (mvol.extent or []):
                                    dn = (getattr(ext, "diskName", "") or "").lower()
                                    if dn.startswith("naa."):
                                        ds_names.append(mvol.name)
                                        break
                        except Exception:
                            pass

                    ds_detail = []
                    try:
                        all_ds_map = {}
                        for ds in (host.datastore or []):
                            try:
                                sv = ds.summary
                                all_ds_map[sv.name] = sv
                            except Exception:
                                pass
                        if ds_names:
                            # Show only datastores linked to this LUN
                            for dsn in dict.fromkeys(ds_names):  # dedup, preserve order
                                if dsn in all_ds_map:
                                    sv = all_ds_map[dsn]
                                    ds_detail.append({
                                        "name":     sv.name,
                                        "type":     sv.type,
                                        "total_gb": round((sv.capacity  or 0) / 1024**3, 1),
                                        "free_gb":  round((sv.freeSpace or 0) / 1024**3, 1),
                                        "naa_backed": True,
                                    })
                        else:
                            # Fallback: show all VMFS datastores on this host
                            for dsn, sv in all_ds_map.items():
                                if (sv.type or "").upper() == "VMFS":
                                    ds_detail.append({
                                        "name":     sv.name,
                                        "type":     sv.type,
                                        "total_gb": round((sv.capacity  or 0) / 1024**3, 1),
                                        "free_gb":  round((sv.freeSpace or 0) / 1024**3, 1),
                                        "naa_backed": False,
                                    })
                    except Exception:
                        pass

                    return {
                        "vcenter":      vc_name,
                        "vcenter_ip":   vc_ip,
                        "esxi_host":    hname,
                        "datastores":   ds_detail,
                        "esxi_iqns":    esxi_iqns,
                        "hba_wwpns":    hba_wwpns,
                        "matched_iqns": matched_iqns,
                        "matched_wwns": matched_wwns,
                        "lun_seen":     seen_naa,
                        "match_type":   match_type,
                    }
                except Exception:
                    return None

            # Scan all hosts in this vCenter in parallel
            max_w = min(30, len(hosts)) if hosts else 1
            with _cfe.ThreadPoolExecutor(max_workers=max_w) as hex_:
                host_futs = [hex_.submit(_scan_host, h) for h in hosts]
                try:
                    for hf in _cfe.as_completed(host_futs, timeout=40):
                        try:
                            res = hf.result(timeout=1)
                            if res:
                                vc_results.append(res)
                        except Exception:
                            pass
                except _cfe.TimeoutError:
                    for hf in host_futs:
                        if hf.done():
                            try:
                                res = hf.result(timeout=1)
                                if res:
                                    vc_results.append(res)
                            except Exception:
                                pass

            try: h_view.Destroy()
            except Exception: pass

        except Exception:
            pass
        finally:
            if si:
                try:
                    from pyVim.connect import Disconnect as _D; _D(si)
                except Exception:
                    pass
        return vc_results

    # ── Scan all vCenters in parallel; collect whatever finishes in 50s ──
    all_results = []
    if not VCENTERS:
        return all_results
    import time as _time
    with _cfe.ThreadPoolExecutor(max_workers=len(VCENTERS)) as ex:
        futs = [ex.submit(_scan_vc, vc) for vc in VCENTERS]
        # Collect results as they complete; stop waiting after 50s total
        try:
            for fut in _cfe.as_completed(futs, timeout=50):
                try:
                    all_results.extend(fut.result(timeout=1))
                except Exception:
                    pass
        except _cfe.TimeoutError:
            # Grab any already-done futures that weren't yielded before timeout
            for fut in futs:
                if fut.done():
                    try:
                        all_results.extend(fut.result(timeout=1))
                    except Exception:
                        pass

    return all_results
