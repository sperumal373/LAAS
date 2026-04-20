"""
cmdb_client.py  –  LaaS CMDB (Configuration Management Database)
=================================================================
Collects Configuration Items (CIs) from all LaaS-managed platforms and
stores them in PostgreSQL  (table: cmdb_ci).

CI Classes (ServiceNow-aligned):
  cmdb_ci_vm_instance   – VMware VMs, Hyper-V VMs, Nutanix VMs
  cmdb_ci_esx_server    – VMware ESXi hosts
  cmdb_ci_win_server    – Hyper-V hosts (Windows Server)
  cmdb_ci_nutanix_node  – Nutanix AHV nodes
  cmdb_ci_ec2_instance  – AWS EC2 instances
  cmdb_ci_storage_device– Pure / NetApp / Dell / HPE storage arrays
  cmdb_ci_ocp_cluster   – OpenShift clusters
  cmdb_ci_ocp_node      – OpenShift nodes
  cmdb_ci_server        – Bare-metal physical servers
  cmdb_ci_ip_network    – IPAM VLANs / subnets

Fields match the ServiceNow CMDB REST Table API schema so records can
be pushed directly to  /api/now/table/<class>.
"""

import os, sys, logging, json
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

log = logging.getLogger("caas.cmdb")

# ─── PostgreSQL connection ────────────────────────────────────────────────────
def _pg():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "127.0.0.1"),
        port=int(os.getenv("PG_PORT", "5433")),
        dbname=os.getenv("PG_DB", "caas_dashboard"),
        user=os.getenv("PG_USER", "caas_app"),
        password=os.getenv("PG_PASS", "CaaS@App2024#"),
        connect_timeout=5,
        cursor_factory=RealDictCursor,
    )

# ─── Schema init ──────────────────────────────────────────────────────────────
def init_cmdb_db():
    conn = _pg()
    cur  = conn.cursor()

    # Main CI table  – all classes share one table (ServiceNow "flat" style)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cmdb_ci (
            id                  SERIAL PRIMARY KEY,
            -- ServiceNow identifiers
            sys_class_name      TEXT NOT NULL,          -- cmdb_ci_vm_instance …
            name                TEXT NOT NULL,
            sys_id              TEXT DEFAULT '',        -- SN sys_id after push
            correlation_id      TEXT DEFAULT '',        -- unique key: source:id
            -- Status & lifecycle
            operational_status  TEXT DEFAULT 'operational',  -- operational/retired
            install_status      TEXT DEFAULT '1',        -- 1=installed
            -- Environment / classification
            environment         TEXT DEFAULT '',        -- Production/DR/Dev/Test
            department          TEXT DEFAULT 'SDx-COE', -- from VM tag
            business_unit       TEXT DEFAULT 'SDx-COE',
            company             TEXT DEFAULT 'SDx-COE',
            location            TEXT DEFAULT '',
            -- Network
            ip_address          TEXT DEFAULT '',
            fqdn                TEXT DEFAULT '',
            mac_address         TEXT DEFAULT '',
            -- Hardware / compute
            cpu_count           INTEGER DEFAULT 0,
            cpu_core_count      INTEGER DEFAULT 0,
            ram_mb              INTEGER DEFAULT 0,
            disk_space_gb       NUMERIC(10,1) DEFAULT 0,
            -- OS / software
            os                  TEXT DEFAULT '',
            os_version          TEXT DEFAULT '',
            os_service_pack     TEXT DEFAULT '',
            -- Asset info
            serial_number       TEXT DEFAULT '',
            model_id            TEXT DEFAULT '',
            manufacturer        TEXT DEFAULT '',
            asset_tag           TEXT DEFAULT '',
            -- Source platform metadata
            source_platform     TEXT NOT NULL,          -- vmware/hyperv/aws …
            source_id           TEXT DEFAULT '',        -- moid/instance-id etc
            vcenter_id          TEXT DEFAULT '',
            cluster             TEXT DEFAULT '',
            hypervisor_host     TEXT DEFAULT '',
            -- ServiceNow push tracking
            sn_pushed_at        TIMESTAMPTZ,
            sn_push_status      TEXT DEFAULT 'pending', -- pending/ok/error
            sn_push_error       TEXT DEFAULT '',
            -- Timestamps
            collected_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen           DATE NOT NULL DEFAULT CURRENT_DATE,
            -- Extended fields (v6.3)
            manager             TEXT DEFAULT '',
            owner               TEXT DEFAULT '',
            timezone            TEXT DEFAULT 'IST',
            region              TEXT DEFAULT 'APAC',
            technology          TEXT DEFAULT '',        -- linux/windows/appliance/other
            tagging             TEXT DEFAULT '',        -- VM tag name from vCenter
            -- Extra JSON for platform-specific fields
            extra               JSONB DEFAULT '{}'
        )
    """)

    # Index for fast lookups
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cmdb_ci_class   ON cmdb_ci(sys_class_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cmdb_ci_source  ON cmdb_ci(source_platform)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cmdb_ci_corrid  ON cmdb_ci(correlation_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cmdb_ci_lastseen ON cmdb_ci(last_seen)")

    # ServiceNow configuration (one row per SN instance)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cmdb_sn_config (
            id              SERIAL PRIMARY KEY,
            instance_url    TEXT NOT NULL,              -- https://xxx.service-now.com
            username        TEXT NOT NULL,
            password        TEXT NOT NULL,
            client_id       TEXT DEFAULT '',            -- OAuth (optional)
            client_secret   TEXT DEFAULT '',
            default_company TEXT DEFAULT 'SDx-COE',
            default_bu      TEXT DEFAULT 'SDx-COE',
            push_vm         BOOLEAN DEFAULT TRUE,
            push_host       BOOLEAN DEFAULT TRUE,
            push_storage    BOOLEAN DEFAULT TRUE,
            push_network    BOOLEAN DEFAULT TRUE,
            push_physical   BOOLEAN DEFAULT TRUE,
            last_push_at    TIMESTAMPTZ,
            last_push_status TEXT DEFAULT 'never',
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    conn.commit()
    conn.close()
    log.info("CMDB DB tables initialised")


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _si(v, default=0):
    try: return int(v or default)
    except: return default

def _sf(v, default=0.0):
    try: return float(v or default)
    except: return default

def _env_tag(tags: list) -> str:
    """Guess environment from VM tag list."""
    for t in (tags or []):
        if not t: continue
        tl = str(t).lower()
        if "prod" in tl: return "PROD"
        if "dr" in tl:   return "DR"
        if "dev" in tl:  return "DEV"
        if "test" in tl or "uat" in tl: return "TEST"
        if "stage" in tl: return "STAGING"
        if "rookie" in tl: return "ROOKIE"
        if "network" in tl: return "NETWORK"
    return ""

def _env_from_name(name: str) -> str:
    """Guess environment from VM/server name when tags are empty."""
    nl = name.lower()
    if "prod" in nl: return "PROD"
    if "_dr" in nl or "-dr" in nl or "replica" in nl: return "DR"
    if "dev" in nl: return "DEV"
    if "test" in nl or "uat" in nl: return "TEST"
    if "stage" in nl: return "STAGING"
    if "training" in nl or "practice" in nl: return "DEV"
    if "rookie" in nl: return "ROOKIE"
    if "network" in nl or "switch" in nl or "router" in nl: return "NETWORK"
    return "PROD"

def _technology_from_os(os_str: str) -> str:
    """Derive technology (linux/windows) from OS string."""
    if not os_str: return ""
    ol = os_str.lower()
    if "windows" in ol: return "windows"
    if any(x in ol for x in ["linux", "red hat", "rhel", "centos", "ubuntu",
                              "debian", "suse", "oracle", "freebsd"]): return "linux"
    if "esxi" in ol or "vmkernel" in ol: return "linux"
    return "other" if os_str else ""

def _tagging_from_tags(tags: list) -> str:
    """Join VM tags into comma-separated string."""
    return ", ".join(str(t) for t in (tags or []) if t) if tags else ""

def _dept_tag(tags: list, annotation: str = "") -> str:
    """Extract department/team from VM tags or annotation."""
    for t in tags:
        tl = t.lower()
        if any(x in tl for x in ["dept:", "department:", "bu:", "team:", "project:"]):
            parts = t.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip()
    # Fall back to annotation if it has owner pattern
    if annotation:
        import re
        m = re.search(r"(?:dept|department|team|project|owner)\s*[:=]\s*([^\n,;]+)", annotation, re.I)
        if m:
            return m.group(1).strip()
    return "SDx-COE"


# ─── Collectors ───────────────────────────────────────────────────────────────

def _collect_vmware() -> list:
    """VMware VMs and ESXi hosts."""
    cis = []
    try:
        from vmware_client import get_all_data
        data = get_all_data()

        # VMs
        for vm in (data.get("vms") or []):
            tags = vm.get("tags") or []
            ann  = vm.get("annotation") or ""
            power = vm.get("status", "")
            op_status = "operational" if "poweredOn" in power else "non-operational"
            cis.append({
                "sys_class_name":     "cmdb_ci_vm_instance",
                "name":               vm.get("name", ""),
                "correlation_id":     f"vmware:vm:{vm.get('vcenter_id','')}:{vm.get('moid','')}",
                "operational_status": op_status,
                "environment":        _env_tag(tags) or _env_from_name(vm.get("name","")),
                "department":         "SDx-COE",
                "business_unit":      "SDx-COE",
                "company":            "SDx-COE",
                "technology":         _technology_from_os(vm.get("guest_os","")),
                "tagging":            _tagging_from_tags(tags),
                "timezone":           "IST",
                "region":             "APAC",
                "ip_address":         vm.get("ip") or "",
                "cpu_count":          _si(vm.get("cpu")),
                "cpu_core_count":     _si(vm.get("cpu_cores_per_socket", vm.get("cpu"))),
                "ram_mb":             int(_sf(vm.get("ram_gb", 0)) * 1024),
                "disk_space_gb":      _sf(vm.get("disk_gb")),
                "os":                 vm.get("guest_os") or "",
                "os_version":         vm.get("guest_id") or "",
                "source_platform":    "vmware",
                "source_id":          vm.get("moid") or "",
                "vcenter_id":         vm.get("vcenter_id") or "",
                "hypervisor_host":    vm.get("host") or "",
                "asset_tag":          vm.get("uuid") or "",
                "extra": json.dumps({
                    "vcenter_name":   vm.get("vcenter_name"),
                    "folder":         vm.get("folder"),
                    "snapshot_count": vm.get("snapshot_count"),
                    "tools_status":   vm.get("tools_status"),
                    "tags":           tags,
                    "annotation":     ann,
                    "uptime_sec":     vm.get("uptime_sec"),
                    "vm_age_days":    vm.get("vm_age_days"),
                    "datastores":     vm.get("datastores"),
                    "networks":       vm.get("networks"),
                }),
            })

        # ESXi Hosts
        for h in (data.get("hosts") or []):
            esxi_ver = h.get("esxi_version") or ""
            cis.append({
                "sys_class_name":     "cmdb_ci_esx_server",
                "name":               h.get("name", ""),
                "correlation_id":     f"vmware:host:{h.get('vcenter_id','')}:{h.get('name','')}",
                "operational_status": "operational" if h.get("status") == "connected" else "non-operational",
                "environment":        "PROD",
                "department":         "SDx-COE",
                "business_unit":      "SDx-COE",
                "company":            "SDx-COE",
                "technology":         "linux",
                "tagging":            "",
                "timezone":           "IST",
                "region":             "APAC",
                "ip_address":         h.get("management_ip") or h.get("name", ""),
                "os":                 esxi_ver,
                "os_version":         esxi_ver,
                "cpu_count":          _si(h.get("cpu_cores")),
                "cpu_core_count":     _si(h.get("cpu_cores")),
                "ram_mb":             int(_sf(h.get("ram_total_gb", 0)) * 1024),
                "model_id":           h.get("cpu_model") or "",
                "source_platform":    "vmware",
                "source_id":          h.get("name") or "",
                "vcenter_id":         h.get("vcenter_id") or "",
                "cluster":            h.get("cluster_name") or "",
                "extra": json.dumps({
                    "vcenter_name":    h.get("vcenter_name"),
                    "cpu_total_mhz":   h.get("cpu_total_mhz"),
                    "cpu_used_mhz":    h.get("cpu_used_mhz"),
                    "ram_total_gb":    h.get("ram_total_gb"),
                    "ram_used_gb":     h.get("ram_used_gb"),
                    "status":          h.get("status"),
                }),
            })
    except Exception as e:
        log.warning(f"CMDB: VMware collection error: {e}")
    return cis


def _collect_hyperv() -> list:
    """Hyper-V VMs and hosts."""
    cis = []
    try:
        from hyperv_client import get_all_hv_data
        data = get_all_hv_data()
        for host_data in (data.get("hosts") or []):
            hi = host_data.get("host_info") or {}
            # Host itself
            cis.append({
                "sys_class_name":     "cmdb_ci_win_server",
                "name":               hi.get("name") or hi.get("host") or "",
                "correlation_id":     f"hyperv:host:{hi.get('host','')}",
                "operational_status": "operational",
                "environment":        "PROD",
                "department":         "SDx-COE",
                "technology":         "windows",
                "timezone":           "IST",
                "region":             "APAC",
                "business_unit":      "SDx-COE",
                "company":            "SDx-COE",
                "os":                 hi.get("os_name") or "Windows Server",
                "os_version":         hi.get("os_version") or "",
                "cpu_count":          _si(hi.get("cpu_count")),
                "cpu_core_count":     _si(hi.get("cpu_count")),
                "ram_mb":             int(_sf(hi.get("ram_total_gb", 0)) * 1024),
                "ip_address":         hi.get("host") or "",
                "source_platform":    "hyperv",
                "source_id":          hi.get("host") or "",
                "extra": json.dumps(hi),
            })
            # VMs on this host
            for vm in (host_data.get("vms") or []):
                power = vm.get("state", vm.get("status", ""))
                op = "operational" if "running" in str(power).lower() else "non-operational"
                cis.append({
                    "sys_class_name":     "cmdb_ci_vm_instance",
                    "name":               vm.get("name") or vm.get("vm_name") or "",
                    "correlation_id":     f"hyperv:vm:{hi.get('host','')}:{vm.get('name',vm.get('vm_name',''))}",
                    "operational_status": op,
                    "environment":        "",
                    "department":         "SDx-COE",
                    "business_unit":      "SDx-COE",
                    "company":            "SDx-COE",
                    "cpu_count":          _si(vm.get("cpu_count")),
                    "ram_mb":             _si(vm.get("ram_mb", _si(vm.get("ram_gb", 0)) * 1024)),
                    "ip_address":         vm.get("ip") or vm.get("ip_address") or "",
                    "os":                 vm.get("os") or vm.get("guest_os") or "",
                    "source_platform":    "hyperv",
                    "source_id":          vm.get("id") or vm.get("name") or "",
                    "hypervisor_host":    hi.get("host") or "",
                    "extra": json.dumps(vm),
                })
    except Exception as e:
        log.warning(f"CMDB: Hyper-V collection error: {e}")
    return cis


def _collect_nutanix() -> list:
    """Nutanix VMs and AHV nodes."""
    cis = []
    try:
        from nutanix_client import list_prism_centrals, get_prism_central, get_pc_vms, get_pc_hosts
        pcs = list_prism_centrals()
        for pc_row in pcs:
            pc = get_prism_central(pc_row["id"])
            if not pc: continue
            # VMs
            for vm in (get_pc_vms(pc) or []):
                power = vm.get("power_state", vm.get("status", ""))
                op = "operational" if "on" in str(power).lower() else "non-operational"
                cis.append({
                    "sys_class_name":     "cmdb_ci_vm_instance",
                    "name":               vm.get("name") or vm.get("vm_name") or "",
                    "correlation_id":     f"nutanix:vm:{pc_row.get('host','')}:{vm.get('uuid', vm.get('name',''))}",
                    "operational_status": op,
                    "department":         "SDx-COE",
                    "business_unit":      "SDx-COE",
                    "company":            "SDx-COE",
                    "ip_address":         vm.get("ip_address") or vm.get("ip") or "",
                    "cpu_count":          _si(vm.get("num_vcpus_per_socket", vm.get("cpu_count", vm.get("vcpus")))),
                    "ram_mb":             _si(vm.get("memory_size_mib", _si(vm.get("ram_mb")))),
                    "os":                 vm.get("guest_os") or vm.get("operating_system") or "",
                    "source_platform":    "nutanix",
                    "source_id":          vm.get("uuid") or vm.get("name") or "",
                    "vcenter_id":         str(pc_row.get("id", "")),
                    "extra": json.dumps({k: v for k, v in vm.items() if k not in ("uuid",)}),
                })
            # Hosts/Nodes
            for h in (get_pc_hosts(pc) or []):
                cis.append({
                    "sys_class_name":     "cmdb_ci_nutanix_node",
                    "name":               h.get("name") or h.get("node_name") or "",
                    "correlation_id":     f"nutanix:host:{pc_row.get('host','')}:{h.get('uuid', h.get('name',''))}",
                    "operational_status": "operational",
                    "department":         "SDx-COE",
                    "business_unit":      "SDx-COE",
                    "company":            "SDx-COE",
                    "ip_address":         h.get("ip_address") or h.get("ip") or "",
                    "cpu_count":          _si(h.get("num_cpu_sockets", h.get("cpu_count"))),
                    "cpu_core_count":     _si(h.get("num_cpu_cores", h.get("cpu_cores"))),
                    "ram_mb":             _si(h.get("memory_size_mib", _si(h.get("ram_mb")))),
                    "model_id":           h.get("block_model_name") or h.get("model") or "",
                    "serial_number":      h.get("serial") or h.get("block_serial") or "",
                    "source_platform":    "nutanix",
                    "source_id":          h.get("uuid") or h.get("name") or "",
                    "vcenter_id":         str(pc_row.get("id", "")),
                    "extra": json.dumps(h),
                })
    except Exception as e:
        log.warning(f"CMDB: Nutanix collection error: {e}")
    return cis


def _collect_aws() -> list:
    """AWS EC2 instances."""
    cis = []
    try:
        from aws_client import get_ec2_instances
        instances = get_ec2_instances() or []
        for inst in instances:
            state = inst.get("state", inst.get("status", ""))
            op = "operational" if state in ("running", "Running") else "non-operational"
            # Extract tags
            tags_raw = inst.get("tags") or {}
            dept = "SDx-COE"  # Force default department
            env  = tags_raw.get("Environment", tags_raw.get("Env", ""))
            cis.append({
                "sys_class_name":     "cmdb_ci_ec2_instance",
                "name":               inst.get("name") or inst.get("instance_id") or "",
                "correlation_id":     f"aws:ec2:{inst.get('region','')}:{inst.get('instance_id','')}",
                "operational_status": op,
                "environment":        env,
                "department":         dept,
                "business_unit":      "SDx-COE",
                "company":            "SDx-COE",
                "location":           inst.get("region") or inst.get("availability_zone") or "",
                "ip_address":         inst.get("private_ip") or inst.get("ip") or "",
                "fqdn":               inst.get("public_dns") or inst.get("dns_name") or "",
                "os":                 inst.get("platform") or inst.get("os") or "",
                "model_id":           inst.get("instance_type") or "",
                "asset_tag":          inst.get("instance_id") or "",
                "source_platform":    "aws",
                "source_id":          inst.get("instance_id") or "",
                "extra": json.dumps({
                    "region":           inst.get("region"),
                    "az":               inst.get("availability_zone"),
                    "instance_type":    inst.get("instance_type"),
                    "ami_id":           inst.get("ami_id") or inst.get("image_id"),
                    "vpc_id":           inst.get("vpc_id"),
                    "subnet_id":        inst.get("subnet_id"),
                    "public_ip":        inst.get("public_ip"),
                    "key_name":         inst.get("key_name"),
                    "tags":             tags_raw,
                }),
            })
    except Exception as e:
        log.warning(f"CMDB: AWS collection error: {e}")
    return cis


def _collect_storage() -> list:
    """Storage arrays - read directly from SQLite (bypass live API calls that may fail)."""
    cis = []
    try:
        import sqlite3
        db_path = Path(__file__).parent / "caas.db"
        conn_s = sqlite3.connect(str(db_path))
        conn_s.row_factory = sqlite3.Row
        cur_s = conn_s.cursor()
        cur_s.execute("SELECT * FROM storage_arrays")
        rows = cur_s.fetchall()
        conn_s.close()
        for arr in rows:
            arr = dict(arr)
            name   = arr.get("name") or ""
            vendor = arr.get("vendor") or ""
            ip     = arr.get("ip") or ""
            site   = arr.get("site") or "dc"
            status = str(arr.get("status") or "").lower()
            op_status = "operational" if status in ("ok", "online", "active", "healthy", "1") else "non-operational"
            cap_tb = arr.get("capacity_tb") or 0
            cis.append({
                "sys_class_name":     "cmdb_ci_storage_device",
                "name":               name,
                "correlation_id":     f"storage:{vendor.lower()}:{ip}",
                "operational_status": op_status,
                "environment":        "PROD",
                "department":         "SDx-COE",
                "business_unit":      "SDx-COE",
                "company":            "SDx-COE",
                "ip_address":         ip,
                "manufacturer":       vendor,
                "model_id":           vendor,
                "serial_number":      "",
                "disk_space_gb":      float(cap_tb) * 1024 if cap_tb else 0,
                "source_platform":    "storage",
                "source_id":          str(arr.get("id", "")),
                "location":           site.upper(),
                "extra": json.dumps({
                    "vendor":       vendor,
                    "site":         site,
                    "capacity_tb":  cap_tb,
                    "status":       arr.get("status"),
                    "console_url":  arr.get("console_url"),
                    "last_checked": arr.get("last_checked"),
                    "port":         arr.get("port"),
                }),
            })
    except Exception as e:
        log.warning(f"CMDB: Storage collection error: {e}")
    return cis


def _collect_openshift() -> list:
    """OpenShift clusters and nodes."""
    cis = []
    try:
        from openshift_client import list_clusters, get_cluster, get_live_nodes
        clusters = list_clusters() or []
        for cl_row in clusters:
            cl = get_cluster(cl_row["id"])
            if not cl: continue
            # Cluster itself
            cis.append({
                "sys_class_name":     "cmdb_ci_ocp_cluster",
                "name":               cl.get("name") or cl.get("host") or "",
                "correlation_id":     f"ocp:cluster:{cl.get('host','')}",
                "operational_status": "operational",
                "department":         "SDx-COE",
                "business_unit":      "SDx-COE",
                "company":            "SDx-COE",
                "ip_address":         cl.get("host") or "",
                "os":                 "Red Hat OpenShift",
                "source_platform":    "openshift",
                "source_id":          str(cl_row.get("id", "")),
                "extra": json.dumps({
                    "cluster_name":   cl.get("name"),
                    "api_url":        cl.get("api_url") or cl.get("host"),
                    "version":        cl.get("version"),
                }),
            })
            # Nodes
            try:
                nodes = get_live_nodes(cl) or []
                for n in nodes:
                    roles = n.get("roles") or n.get("role") or ""
                    cis.append({
                        "sys_class_name":     "cmdb_ci_ocp_node",
                        "name":               n.get("name") or "",
                        "correlation_id":     f"ocp:node:{cl.get('host','')}:{n.get('name','')}",
                        "operational_status": "operational" if n.get("status","") in ("Ready","ready") else "non-operational",
                        "department":         "SDx-COE",
                        "business_unit":      "SDx-COE",
                        "company":            "SDx-COE",
                        "ip_address":         n.get("ip") or n.get("internal_ip") or "",
                        "os":                 n.get("os_image") or n.get("os") or "Red Hat CoreOS",
                        "os_version":         n.get("kubelet_version") or "",
                        "cpu_count":          _si(n.get("cpu")),
                        "ram_mb":             int(_sf(n.get("ram_gb", n.get("memory_gb", 0))) * 1024),
                        "source_platform":    "openshift",
                        "source_id":          n.get("uid") or n.get("name") or "",
                        "vcenter_id":         str(cl_row.get("id", "")),
                        "extra": json.dumps({
                            "roles":          roles,
                            "kernel_version": n.get("kernel_version"),
                            "arch":           n.get("architecture"),
                            "conditions":     n.get("conditions"),
                        }),
                    })
            except Exception as en:
                log.warning(f"CMDB: OCP nodes for {cl.get('name','?')}: {en}")
    except Exception as e:
        log.warning(f"CMDB: OpenShift collection error: {e}")
    return cis


def _collect_physical() -> list:
    """Physical/bare-metal servers + rack asset inventory."""
    cis = []
    try:
        from baremetal_client import list_servers
        for srv in (list_servers() or []):
            cis.append({
                "sys_class_name":     "cmdb_ci_server",
                "name":               srv.get("name") or "",
                "correlation_id":     f"baremetal:{srv.get('ip',srv.get('name',''))}",
                "operational_status": "operational" if srv.get("status","").lower() in ("ok","online","running") else "non-operational",
                "environment":        "PROD",
                "department":         "SDx-COE",
                "business_unit":      "SDx-COE",
                "company":            "SDx-COE",
                "ip_address":         srv.get("ip") or "",
                "location":           srv.get("location") or "",
                "model_id":           srv.get("model") or "",
                "serial_number":      srv.get("serial") or "",
                "source_platform":    "baremetal",
                "source_id":          str(srv.get("id", "")),
                "extra": json.dumps({
                    "bmc_type":    srv.get("bmc_type"),
                    "description": srv.get("description"),
                    "power_state": srv.get("power_state"),
                    "added_by":    srv.get("added_by"),
                    "last_seen":   srv.get("last_seen"),
                }),
            })
    except Exception as e:
        log.warning(f"CMDB: Baremetal collection error: {e}")

    # Asset Management (DC + DR Excel inventory)
    try:
        from asset_client import parse_inventory, DATA_DIR
        from pathlib import Path as _P
        for site, fname in [("DC", "dc_inventory.xlsx"), ("DR", "dr_inventory.xlsx")]:
            inv = parse_inventory(_P(DATA_DIR) / fname)
            for rack, assets in (inv.get("racks") or {}).items():
                for a in assets:
                    aname = a.get("asset_name") or a.get("hostname") or ""
                    if not aname:
                        continue
                    cis.append({
                        "sys_class_name":     "cmdb_ci_server",
                        "name":               aname,
                        "correlation_id":     f"asset:{site}:{rack}:{a.get('position','')}:{aname}",
                        "operational_status": "operational" if str(a.get("power_state","")).lower() in ("on","running","powered on","1") else "non-operational",
                        "environment":        "PROD",
                        "department":         "SDx-COE",
                        "business_unit":      "SDx-COE",
                        "company":            "SDx-COE",
                        "location":           f"{site}/{rack}",
                        "ip_address":         a.get("mgmt_ip") or a.get("os_ip") or "",
                        "os":                 a.get("os_hypervisor") or "",
                        "model_id":           a.get("model") or "",
                        "serial_number":      a.get("serial") or "",
                        "source_platform":    "asset_mgmt",
                        "source_id":          f"{site}:{rack}:{a.get('position','')}:{aname}",
                        "extra": json.dumps({
                            "rack":        rack,
                            "site":        site,
                            "position":    a.get("position"),
                            "mgmt_port":   a.get("mgmt_port"),
                            "data_ports":  a.get("data_ports"),
                            "remarks":     a.get("remarks"),
                            "switch_info": a.get("switch_info"),
                        }),
                    })
    except Exception as e:
        log.warning(f"CMDB: Asset inventory collection error: {e}")
    return cis


def _collect_ipam_networks() -> list:
    """IPAM VLANs as network CIs."""
    cis = []
    try:
        from ipam_pg import list_vlans
        for vlan in (list_vlans() or []):
            cis.append({
                "sys_class_name":     "cmdb_ci_ip_network",
                "name":               vlan.get("name") or f"VLAN-{vlan.get('vlan_id','')}",
                "correlation_id":     f"ipam:vlan:{vlan.get('vlan_id',vlan.get('id',''))}",
                "operational_status": "operational",
                "department":         "SDx-COE",
                "business_unit":      "SDx-COE",
                "company":            "SDx-COE",
                "location":           vlan.get("site") or vlan.get("location") or "",
                "source_platform":    "ipam",
                "source_id":          str(vlan.get("id") or vlan.get("vlan_id") or ""),
                "extra": json.dumps({
                    "vlan_id":      vlan.get("vlan_id"),
                    "subnet":       vlan.get("subnet") or vlan.get("network"),
                    "cidr":         vlan.get("cidr"),
                    "gateway":      vlan.get("gateway"),
                    "total_ips":    vlan.get("total_ips"),
                    "used_ips":     vlan.get("used_ips"),
                    "free_ips":     vlan.get("free_ips"),
                    "site":         vlan.get("site"),
                    "description":  vlan.get("description") or vlan.get("notes"),
                }),
            })
    except Exception as e:
        log.warning(f"CMDB: IPAM network collection error: {e}")
    return cis


# ─── Main collect + upsert ────────────────────────────────────────────────────

def collect_all_cis() -> dict:
    """
    Collect all CIs from all platforms and upsert into cmdb_ci.
    Returns a summary dict.
    """
    today = date.today()
    all_cis = []

    collectors = [
        ("VMware",     _collect_vmware),
        ("Hyper-V",    _collect_hyperv),
        ("Nutanix",    _collect_nutanix),
        ("AWS",        _collect_aws),
        ("Storage",    _collect_storage),
        ("OpenShift",  _collect_openshift),
        ("Physical",   _collect_physical),
        ("IPAM/Network", _collect_ipam_networks),
    ]

    counts_by_platform = {}
    for platform_name, fn in collectors:
        try:
            items = fn()
            all_cis.extend(items)
            counts_by_platform[platform_name] = len(items)
            log.info(f"CMDB: {platform_name} → {len(items)} CIs")
        except Exception as e:
            log.warning(f"CMDB: {platform_name} collector failed: {e}")
            counts_by_platform[platform_name] = 0

    # Upsert into PostgreSQL
    inserted = updated = 0
    conn = _pg()
    cur  = conn.cursor()
    try:
        for ci in all_cis:
            corr_id = ci.get("correlation_id", "")
            if not corr_id:
                continue

            # Check if exists
            cur.execute("SELECT id FROM cmdb_ci WHERE correlation_id = %s", (corr_id,))
            existing = cur.fetchone()

            if existing:
                cur.execute("""
                    UPDATE cmdb_ci SET
                        name               = %s,
                        sys_class_name     = %s,
                        operational_status = %s,
                        environment        = %s,
                        department         = %s,
                        business_unit      = %s,
                        company            = %s,
                        location           = %s,
                        ip_address         = %s,
                        fqdn               = %s,
                        mac_address        = %s,
                        cpu_count          = %s,
                        cpu_core_count     = %s,
                        ram_mb             = %s,
                        disk_space_gb      = %s,
                        os                 = %s,
                        os_version         = %s,
                        serial_number      = %s,
                        model_id           = %s,
                        manufacturer       = %s,
                        asset_tag          = %s,
                        source_platform    = %s,
                        source_id          = %s,
                        vcenter_id         = %s,
                        cluster            = %s,
                        hypervisor_host    = %s,
                        technology         = COALESCE(NULLIF(%s, ''), technology),
                        tagging            = COALESCE(NULLIF(%s, ''), tagging),
                        extra              = %s,
                        collected_at       = NOW(),
                        last_seen          = %s
                    WHERE correlation_id = %s
                """, (
                    ci.get("name",""), ci.get("sys_class_name",""),
                    ci.get("operational_status","operational"),
                    ci.get("environment",""), ci.get("department","SDx-COE"),
                    ci.get("business_unit","SDx-COE"), ci.get("company","SDx-COE"),
                    ci.get("location",""), ci.get("ip_address",""),
                    ci.get("fqdn",""), ci.get("mac_address",""),
                    _si(ci.get("cpu_count")), _si(ci.get("cpu_core_count")),
                    _si(ci.get("ram_mb")), _sf(ci.get("disk_space_gb",0)),
                    ci.get("os",""), ci.get("os_version",""),
                    ci.get("serial_number",""), ci.get("model_id",""),
                    ci.get("manufacturer",""), ci.get("asset_tag",""),
                    ci.get("source_platform",""), ci.get("source_id",""),
                    ci.get("vcenter_id",""), ci.get("cluster",""),
                    ci.get("hypervisor_host",""),
                    ci.get("technology",""), ci.get("tagging",""),
                    ci.get("extra","{}"),
                    today, corr_id,
                ))
                updated += 1
            else:
                cur.execute("""
                    INSERT INTO cmdb_ci
                        (sys_class_name, name, correlation_id,
                         operational_status, environment, department, business_unit, company,
                         location, ip_address, fqdn, mac_address,
                         cpu_count, cpu_core_count, ram_mb, disk_space_gb,
                         os, os_version, serial_number, model_id, manufacturer, asset_tag,
                         source_platform, source_id, vcenter_id, cluster, hypervisor_host,
                         technology, tagging, timezone, region,
                         extra, collected_at, last_seen)
                    VALUES
                        (%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s,%s,
                         %s,%s,%s,%s, %s,%s,%s,%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s,%s, %s,NOW(),%s)
                """, (
                    ci.get("sys_class_name",""), ci.get("name",""), corr_id,
                    ci.get("operational_status","operational"),
                    ci.get("environment",""), ci.get("department","SDx-COE"),
                    ci.get("business_unit","SDx-COE"), ci.get("company","SDx-COE"),
                    ci.get("location",""), ci.get("ip_address",""),
                    ci.get("fqdn",""), ci.get("mac_address",""),
                    _si(ci.get("cpu_count")), _si(ci.get("cpu_core_count")),
                    _si(ci.get("ram_mb")), _sf(ci.get("disk_space_gb",0)),
                    ci.get("os",""), ci.get("os_version",""),
                    ci.get("serial_number",""), ci.get("model_id",""),
                    ci.get("manufacturer",""), ci.get("asset_tag",""),
                    ci.get("source_platform",""), ci.get("source_id",""),
                    ci.get("vcenter_id",""), ci.get("cluster",""),
                    ci.get("hypervisor_host",""),
                    ci.get("technology",""), ci.get("tagging",""),
                    ci.get("timezone","IST"), ci.get("region","APAC"),
                    ci.get("extra","{}"), today,
                ))
                inserted += 1

        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"CMDB: DB upsert error: {e}")
        raise
    finally:
        conn.close()

    total = inserted + updated
    log.info(f"CMDB: collection complete – {total} CIs ({inserted} new, {updated} updated)")
    return {
        "total": total,
        "inserted": inserted,
        "updated": updated,
        "by_platform": counts_by_platform,
        "collected_at": datetime.utcnow().isoformat(),
    }


# ─── Read helpers (used by API) ───────────────────────────────────────────────

def list_cis(class_filter: str = None, platform_filter: str = None,
             search: str = None, limit: int = 1000, offset: int = 0) -> list:
    conn = _pg()
    cur  = conn.cursor()
    wheres, params = [], []
    if class_filter:
        wheres.append("sys_class_name = %s"); params.append(class_filter)
    if platform_filter:
        wheres.append("source_platform = %s"); params.append(platform_filter)
    if search:
        wheres.append("(name ILIKE %s OR ip_address ILIKE %s OR os ILIKE %s)")
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
    cur.execute(f"SELECT * FROM cmdb_ci {where_sql} ORDER BY sys_class_name, name LIMIT %s OFFSET %s",
                params + [limit, offset])
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    # Serialize dates
    for r in rows:
        for k, v in r.items():
            if isinstance(v, (date, datetime)):
                r[k] = v.isoformat()
    return rows


def get_ci_summary() -> dict:
    conn = _pg()
    cur  = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*)                                        AS total,
            COUNT(*) FILTER (WHERE operational_status='operational') AS operational,
            COUNT(*) FILTER (WHERE sys_class_name='cmdb_ci_vm_instance')   AS vms,
            COUNT(*) FILTER (WHERE sys_class_name='cmdb_ci_esx_server')    AS esxi_hosts,
            COUNT(*) FILTER (WHERE sys_class_name='cmdb_ci_win_server')    AS hv_hosts,
            COUNT(*) FILTER (WHERE sys_class_name='cmdb_ci_nutanix_node')  AS nutanix_nodes,
            COUNT(*) FILTER (WHERE sys_class_name='cmdb_ci_ec2_instance')  AS aws_ec2,
            COUNT(*) FILTER (WHERE sys_class_name='cmdb_ci_storage_device') AS storage_devices,
            COUNT(*) FILTER (WHERE sys_class_name='cmdb_ci_ocp_cluster')   AS ocp_clusters,
            COUNT(*) FILTER (WHERE sys_class_name='cmdb_ci_ocp_node')      AS ocp_nodes,
            COUNT(*) FILTER (WHERE sys_class_name='cmdb_ci_server')        AS physical_servers,
            COUNT(*) FILTER (WHERE sys_class_name='cmdb_ci_ip_network')    AS networks,
            COUNT(*) FILTER (WHERE sn_push_status='ok')                    AS pushed_to_sn,
            MAX(collected_at)                                               AS last_collected
        FROM cmdb_ci
    """)
    row = cur.fetchone()
    conn.close()
    result = dict(row) if row else {}
    for k, v in result.items():
        if isinstance(v, (date, datetime)):
            result[k] = v.isoformat()
    return result


def update_ci(ci_id: int, fields: dict) -> dict:
    """Admin-only update of a CI record."""
    allowed = {
        "name","operational_status","environment","department","business_unit",
        "company","location","ip_address","fqdn","os","os_version",
        "serial_number","model_id","manufacturer","asset_tag",
        "cpu_count","cpu_core_count","ram_mb","disk_space_gb",
        "manager","owner","timezone","region","technology","tagging",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return {"error": "no valid fields"}
    conn = _pg()
    cur  = conn.cursor()
    set_clause = ", ".join(f"{k}=%s" for k in updates)
    cur.execute(f"UPDATE cmdb_ci SET {set_clause} WHERE id=%s RETURNING id",
                list(updates.values()) + [ci_id])
    r = cur.fetchone()
    conn.commit()
    conn.close()
    return {"updated": bool(r), "id": ci_id}


# ─── ServiceNow config ────────────────────────────────────────────────────────

def get_sn_config() -> dict:
    conn = _pg()
    cur  = conn.cursor()
    cur.execute("SELECT id,instance_url,username,default_company,default_bu,push_vm,push_host,push_storage,push_network,push_physical,last_push_at,last_push_status FROM cmdb_sn_config ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        return {}
    r = dict(row)
    for k, v in r.items():
        if isinstance(v, (date, datetime)):
            r[k] = v.isoformat()
    return r


def save_sn_config(cfg: dict) -> dict:
    conn = _pg()
    cur  = conn.cursor()
    cur.execute("SELECT id FROM cmdb_sn_config ORDER BY id DESC LIMIT 1")
    existing = cur.fetchone()
    if existing:
        cur.execute("""
            UPDATE cmdb_sn_config SET
                instance_url=%s, username=%s, password=%s,
                client_id=%s, client_secret=%s,
                default_company=%s, default_bu=%s,
                push_vm=%s, push_host=%s, push_storage=%s,
                push_network=%s, push_physical=%s
            WHERE id=%s
        """, (
            cfg.get("instance_url",""), cfg.get("username",""), cfg.get("password",""),
            cfg.get("client_id",""), cfg.get("client_secret",""),
            cfg.get("default_company","SDx-COE"), cfg.get("default_bu","SDx-COE"),
            cfg.get("push_vm", True), cfg.get("push_host", True),
            cfg.get("push_storage", True), cfg.get("push_network", True),
            cfg.get("push_physical", True),
            existing["id"],
        ))
    else:
        cur.execute("""
            INSERT INTO cmdb_sn_config
                (instance_url,username,password,client_id,client_secret,
                 default_company,default_bu,push_vm,push_host,push_storage,push_network,push_physical)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            cfg.get("instance_url",""), cfg.get("username",""), cfg.get("password",""),
            cfg.get("client_id",""), cfg.get("client_secret",""),
            cfg.get("default_company","SDx-COE"), cfg.get("default_bu","SDx-COE"),
            cfg.get("push_vm", True), cfg.get("push_host", True),
            cfg.get("push_storage", True), cfg.get("push_network", True),
            cfg.get("push_physical", True),
        ))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── ServiceNow push ──────────────────────────────────────────────────────────

# SN class → REST table name mapping (ITSM standard)
_SN_TABLE_MAP = {
    "cmdb_ci_vm_instance":    "cmdb_ci_vm_instance",
    "cmdb_ci_esx_server":     "cmdb_ci_esx_server",
    "cmdb_ci_win_server":     "cmdb_ci_win_server",
    "cmdb_ci_nutanix_node":   "cmdb_ci_server",          # no native Nutanix class
    "cmdb_ci_ec2_instance":   "cmdb_ci_ec2_instance",
    "cmdb_ci_storage_device": "cmdb_ci_storage_device",
    "cmdb_ci_ocp_cluster":    "cmdb_ci_server",
    "cmdb_ci_ocp_node":       "cmdb_ci_server",
    "cmdb_ci_server":         "cmdb_ci_server",
    "cmdb_ci_ip_network":     "cmdb_ci_ip_network",
}

def _ci_to_sn_payload(ci: dict) -> dict:
    """Convert a cmdb_ci row to a ServiceNow Table API payload."""
    extra = {}
    try:
        extra = json.loads(ci.get("extra") or "{}")
    except Exception:
        pass

    payload = {
        "name":               ci.get("name",""),
        "operational_status": ci.get("operational_status","1"),
        "environment":        ci.get("environment",""),
        "department":         ci.get("department",""),
        "company":            ci.get("company",""),
        "location":           ci.get("location",""),
        "ip_address":         ci.get("ip_address",""),
        "fqdn":               ci.get("fqdn",""),
        "mac_address":        ci.get("mac_address",""),
        "cpu_count":          str(ci.get("cpu_count",0) or 0),
        "cpu_core_count":     str(ci.get("cpu_core_count",0) or 0),
        "ram":                str(ci.get("ram_mb",0) or 0),
        "disk_space":         str(ci.get("disk_space_gb",0) or 0),
        "os":                 ci.get("os",""),
        "os_version":         ci.get("os_version",""),
        "serial_number":      ci.get("serial_number",""),
        "model_id":           ci.get("model_id",""),
        "manufacturer":       ci.get("manufacturer",""),
        "asset_tag":          ci.get("asset_tag",""),
        "correlation_id":     ci.get("correlation_id",""),
        "discovery_source":   "LaaS Dashboard",
        "u_source_platform":  ci.get("source_platform",""),
        "short_description":  f"Discovered by LaaS from {ci.get('source_platform','').upper()}",
    }
    # Remove empty strings to avoid overwriting SN defaults
    return {k: v for k, v in payload.items() if v not in ("", "0", None)}


def push_to_servicenow(dry_run: bool = False) -> dict:
    """
    Push all CIs to ServiceNow via Table API.
    Uses existing sys_id if already pushed (UPDATE), else INSERT.
    """
    cfg = get_sn_config()
    if not cfg.get("instance_url"):
        return {"error": "ServiceNow not configured. Please add credentials first."}

    import requests as _req
    base = cfg["instance_url"].rstrip("/")
    auth = (cfg["username"], cfg.get("password",""))  # basic auth or token

    # Determine which classes to push based on config
    class_filter_map = {
        "cmdb_ci_vm_instance":    cfg.get("push_vm", True),
        "cmdb_ci_esx_server":     cfg.get("push_host", True),
        "cmdb_ci_win_server":     cfg.get("push_host", True),
        "cmdb_ci_nutanix_node":   cfg.get("push_host", True),
        "cmdb_ci_ec2_instance":   cfg.get("push_vm", True),
        "cmdb_ci_storage_device": cfg.get("push_storage", True),
        "cmdb_ci_ocp_cluster":    cfg.get("push_host", True),
        "cmdb_ci_ocp_node":       cfg.get("push_host", True),
        "cmdb_ci_server":         cfg.get("push_physical", True),
        "cmdb_ci_ip_network":     cfg.get("push_network", True),
    }

    all_cis = list_cis(limit=10000)
    pushed = errors = skipped = 0
    error_samples = []

    conn = _pg()
    cur  = conn.cursor()

    for ci in all_cis:
        cls = ci.get("sys_class_name","")
        if not class_filter_map.get(cls, True):
            skipped += 1
            continue

        sn_table = _SN_TABLE_MAP.get(cls, "cmdb_ci")
        payload  = _ci_to_sn_payload(ci)
        sys_id   = ci.get("sys_id","")

        if dry_run:
            pushed += 1
            continue

        try:
            if sys_id:
                url = f"{base}/api/now/table/{sn_table}/{sys_id}"
                r = _req.patch(url, json=payload, auth=auth,
                               headers={"Content-Type":"application/json","Accept":"application/json"},
                               verify=False, timeout=15)
            else:
                url = f"{base}/api/now/table/{sn_table}"
                r = _req.post(url, json=payload, auth=auth,
                              headers={"Content-Type":"application/json","Accept":"application/json"},
                              verify=False, timeout=15)

            if r.status_code in (200, 201):
                new_sys_id = (r.json().get("result") or {}).get("sys_id","")
                cur.execute("UPDATE cmdb_ci SET sys_id=%s, sn_pushed_at=NOW(), sn_push_status='ok', sn_push_error='' WHERE id=%s",
                            (new_sys_id, ci["id"]))
                pushed += 1
            else:
                err_msg = f"HTTP {r.status_code}: {r.text[:200]}"
                cur.execute("UPDATE cmdb_ci SET sn_push_status='error', sn_push_error=%s WHERE id=%s",
                            (err_msg, ci["id"]))
                errors += 1
                if len(error_samples) < 3:
                    error_samples.append({"ci": ci["name"], "error": err_msg})
        except Exception as ex:
            err_msg = str(ex)[:200]
            cur.execute("UPDATE cmdb_ci SET sn_push_status='error', sn_push_error=%s WHERE id=%s",
                        (err_msg, ci["id"]))
            errors += 1
            if len(error_samples) < 3:
                error_samples.append({"ci": ci["name"], "error": err_msg})

    # Update last_push_at on config
    status = "ok" if errors == 0 else ("partial" if pushed > 0 else "error")
    cur.execute("UPDATE cmdb_sn_config SET last_push_at=NOW(), last_push_status=%s WHERE id=%s",
                (status, cfg["id"]))
    conn.commit()
    conn.close()

    return {
        "pushed": pushed,
        "errors": errors,
        "skipped": skipped,
        "status": status,
        "dry_run": dry_run,
        "error_samples": error_samples,
    }


# ─── CSV export ─────────────────────────────────────────────────────────────
def export_csv(class_filter=None, platform_filter=None, search=None):
    """Return CMDB data as CSV string for download."""
    import csv, io
    rows = list_cis(class_filter, platform_filter, search, limit=10000, offset=0)
    if not rows:
        return "No data"
    buf = io.StringIO()
    cols = ["name","ip_address","operational_status","technology","os",
            "manager","owner","environment","timezone","region",
            "department","tagging","sys_class_name","source_platform",
            "cpu_count","ram_mb","disk_space_gb","serial_number",
            "manufacturer","model_id","location","cluster",
            "hypervisor_host","collected_at","last_seen"]
    headers = ["Server Name","IP Address","Status","Technology","OS",
               "Manager","Owner","Environment","Timezone","Region",
               "Department","Tagging","CI Class","Platform",
               "CPU","RAM (MB)","Disk (GB)","Serial Number",
               "Manufacturer","Model","Location","Cluster",
               "Hypervisor Host","Collected At","Last Seen"]
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        status = "On" if r.get("operational_status") == "operational" else "Off"
        w.writerow([r.get(c, "") if c != "operational_status" else status for c, _ in zip(cols, headers)])
    return buf.getvalue()
