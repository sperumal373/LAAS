"""
compliance_collector.py  --  COE Compliance Data Collector  v2
===============================================================
Data sources:
  1. VMware vCenter (loaded from backend/.env) — VMs
  2. PostgreSQL cmdb_ci table                  — Baremetal servers
  3. SSH  (Linux)   — uptime, patch date, AV  (credentials from DB vault)
  4. WinRM (Windows) — uptime, patch date, AV  (credentials from DB vault)

Usage:
  python compliance_collector.py                       # full scan
  python compliance_collector.py --dry-run             # score, no DB write
  python compliance_collector.py --no-ssh              # skip SSH/WinRM
  python compliance_collector.py --checks eol_os,uptime  # specific rules only
"""

import sys, os, argparse, hashlib, json, logging, traceback, socket
from datetime import date, datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import psycopg2, psycopg2.extras
from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from compliance_rules import score_asset, ALL_RULES

log = logging.getLogger("compliance_collector")
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

# ── PostgreSQL config ────────────────────────────────────────────────────────
PG_CONFIG = dict(
    host="127.0.0.1", port=5433, dbname="caas_dashboard",
    user="caas_app", password="CaaS@App2024#", connect_timeout=10,
)

# ── Credential vault loader ─────────────────────────────────────────────────
SSH_TIMEOUT  = 8
SSH_PORT     = 22
WINRM_PORT   = 5985

import base64 as _b64

def _deobfuscate(enc: str) -> str:
    key = b"CaaS@Cred2026#"
    byt = _b64.b64decode(enc.encode())
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(byt)).decode()

def _load_credentials(os_family: str) -> list:
    """Return list of (username, password, port) dicts for the given OS family,
    ordered by id.  Falls back to empty list — SSH step is then skipped."""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, password_enc, port FROM compliance_credentials "
                "WHERE os_family=%s ORDER BY id",
                (os_family,)
            )
            rows = cur.fetchall()
        conn.close()
        return [{"username": r["username"], "password": _deobfuscate(r["password_enc"]), "port": r["port"]} for r in rows]
    except Exception as ex:
        log.debug(f"_load_credentials({os_family}) error: {ex}")
        return []

def _load_asset_override_cred(asset_id: int) -> dict | None:
    """Return credential for a specific asset override, or None."""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT extra_data FROM compliance_assets WHERE id=%s",
                (asset_id,)
            )
            row = cur.fetchone()
        conn.close()
        if not row or not row["extra_data"]:
            return None
        cred_id = row["extra_data"].get("override_cred_id")
        if not cred_id:
            return None
        conn2 = get_db()
        with conn2.cursor() as cur2:
            cur2.execute("SELECT username, password_enc, port FROM compliance_credentials WHERE id=%s", (int(cred_id),))
            r = cur2.fetchone()
        conn2.close()
        if r:
            return {"username": r["username"], "password": _deobfuscate(r["password_enc"]), "port": r["port"]}
    except Exception as ex:
        log.debug(f"_load_asset_override_cred({asset_id}) error: {ex}")
    return None


def get_db():
    return psycopg2.connect(**PG_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)


def sf(v, d=0.0):
    try:    return float(v) if v is not None else d
    except: return d

def si(v, d=0):
    try:    return int(v) if v is not None else d
    except: return d

def asset_key(hostname, ip, atype):
    raw = f"{(hostname or '').lower().strip()}|{(ip or '').strip()}|{atype}"
    return hashlib.md5(raw.encode()).hexdigest()


# ── Load vCenters from .env ──────────────────────────────────────────────────

def _load_vcenters_from_env() -> list:
    """Parse vCenter list from backend/.env  (VCENTER_HOSTS + per-index creds)."""
    env_path = BACKEND_DIR / ".env"
    env = {}
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    except Exception as ex:
        log.warning(f"Cannot read .env: {ex}")
        return []

    hosts_str = env.get("VCENTER_HOSTS", "")
    if not hosts_str:
        return []

    hosts   = [h.strip() for h in hosts_str.split(",") if h.strip()]
    vc_user = env.get("VCENTER_USER", "administrator@vsphere.local")

    vcenters = []
    for idx, host in enumerate(hosts, 1):
        name     = env.get(f"VCENTER_NAME_{idx}",     f"vCenter-{host}")
        password = env.get(f"VCENTER_PASSWORD_{idx}", "")
        vcenters.append({
            "host":     host,
            "name":     name,
            "username": vc_user,
            "password": password,
        })
    log.info(f"Loaded {len(vcenters)} vCenters from .env: {[v['host'] for v in vcenters]}")
    return vcenters


# ── SSH helpers (Linux) ──────────────────────────────────────────────────────

def _ssh_get_info(ip: str, creds: list | None = None) -> dict:
    """Connect via SSH and gather: uptime_days, last_patch (ISO), av_present.
    creds: list of {username, password, port} dicts — tried in order.
    ssh_auth_failed key is set True if all creds were rejected (vs network error)."""
    result = {"uptime_days": None, "last_patch": None, "av_present": None, "ssh_auth_failed": False}
    if not ip:
        return result
    try:
        import paramiko
    except ImportError:
        log.debug("paramiko not installed — SSH skipped")
        return result

    if not creds:
        creds = _load_credentials("linux")
    if not creds:
        log.debug(f"SSH {ip}: no credentials configured — skipping")
        return result

    last_auth_err = False
    for cred in creds:
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(ip, port=cred.get("port", SSH_PORT),
                        username=cred["username"], password=cred["password"],
                        timeout=SSH_TIMEOUT, banner_timeout=SSH_TIMEOUT, auth_timeout=SSH_TIMEOUT)
            last_auth_err = False
            break   # success
        except paramiko.AuthenticationException:
            last_auth_err = True
            log.debug(f"SSH {ip}: auth failed for {cred['username']}")
            continue
        except Exception as ex:
            log.debug(f"SSH {ip}: connection error — {ex}")
            return result  # network/port issue — no point trying more creds
    else:
        result["ssh_auth_failed"] = last_auth_err
        return result

    try:

        def run(cmd):
            _, stdout, _ = cli.exec_command(cmd, timeout=SSH_TIMEOUT)
            return stdout.read().decode(errors="ignore").strip()

        # Uptime in seconds → days
        up_sec = run("cat /proc/uptime 2>/dev/null | awk '{print int($1)}'")
        if up_sec.isdigit():
            result["uptime_days"] = int(up_sec) // 86400

        # Last patch date (yum/dnf/apt)
        last_patch = run(
            "rpm -qa --last 2>/dev/null | head -1 | awk '{print $2,$3,$4,$5}'"
            " || grep -m1 'Upgrade\\|Install' /var/log/dpkg.log 2>/dev/null | awk '{print $1}'"
        )
        if last_patch and len(last_patch) > 4:
            try:
                from dateutil import parser as dparser
                dt = dparser.parse(last_patch, fuzzy=True)
                result["last_patch"] = dt.replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                pass

        # AV/EDR check
        av_check = run(
            "systemctl is-active falcon-sensor csagent ds_agent xagt mfetpd 2>/dev/null | grep -c '^active'"
            " || ps aux 2>/dev/null | grep -cE 'falcon|csagent|ds_agent|xagt|mfetpd' | grep -v grep"
        )
        result["av_present"] = (av_check.strip() not in ("", "0"))
        cli.close()
        log.debug(f"SSH {ip}: uptime={result['uptime_days']}d patch={result['last_patch']} av={result['av_present']}")
    except Exception as ex:
        log.debug(f"SSH {ip} post-auth error: {type(ex).__name__}: {ex}")
    return result


# ── WinRM helpers (Windows) ──────────────────────────────────────────────────

def _winrm_get_info(ip: str, creds: list | None = None) -> dict:
    """Connect via WinRM and gather: uptime_days, last_patch (ISO), av_present.
    creds: list of {username, password, port} dicts — tried in order."""
    result = {"uptime_days": None, "last_patch": None, "av_present": None, "ssh_auth_failed": False}
    if not ip:
        return result
    try:
        import winrm
    except ImportError:
        log.debug("pywinrm not installed — WinRM skipped")
        return result

    if not creds:
        creds = _load_credentials("windows")
    if not creds:
        log.debug(f"WinRM {ip}: no credentials configured — skipping")
        return result

    s = None
    for cred in creds:
        try:
            s = winrm.Session(f"http://{ip}:{cred.get('port', WINRM_PORT)}/wsman",
                              auth=(cred["username"], cred["password"]),
                              transport="ntlm",
                              server_cert_validation="ignore",
                              operation_timeout_sec=SSH_TIMEOUT,
                              read_timeout_sec=SSH_TIMEOUT + 2)
            # test connectivity
            tr = s.run_ps("echo ok")
            if tr.status_code == 0:
                break
            s = None
        except Exception as ex:
            log.debug(f"WinRM {ip} cred {cred['username']} error: {ex}")
            s = None
    if s is None:
        result["ssh_auth_failed"] = True
        return result

    try:

        # Uptime in seconds
        r = s.run_ps("(Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime | Select -Expand TotalDays")
        if r.status_code == 0:
            try:
                result["uptime_days"] = int(float(r.std_out.decode().strip()))
            except Exception:
                pass

        # Last patch date
        r2 = s.run_ps(
            "(Get-HotFix | Sort-Object InstalledOn -Descending | Select -First 1 -Expand InstalledOn)"
            ".ToString('yyyy-MM-ddTHH:mm:ss')"
        )
        if r2.status_code == 0 and r2.std_out:
            try:
                from dateutil import parser as dparser
                dt = dparser.parse(r2.std_out.decode().strip())
                result["last_patch"] = dt.replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                pass

        # AV/EDR check
        r3 = s.run_ps(
            "Get-Service -Name 'CSFalconService','WinDefend','ds_agent','xagt','mfemms' "
            "-ErrorAction SilentlyContinue | Where Status -eq Running | Measure-Object | Select -Expand Count"
        )
        if r3.status_code == 0:
            try:
                result["av_present"] = int(r3.std_out.decode().strip()) > 0
            except Exception:
                result["av_present"] = True

        log.debug(f"WinRM {ip}: uptime={result['uptime_days']}d, last_patch={result['last_patch']}, av={result['av_present']}")
    except Exception as ex:
        log.debug(f"WinRM {ip} failed: {type(ex).__name__}: {ex}")
    return result


def _get_remote_info(ip: str, os_family: str, use_ssh: bool = True, asset_id: int | None = None) -> dict:
    """Try SSH for Linux, WinRM for Windows. Returns uptime/patch/av dict.
    If asset_id is given, checks for an asset-level credential override first."""
    if not use_ssh or not ip:
        return {"uptime_days": None, "last_patch": None, "av_present": None, "ssh_auth_failed": False}

    # Asset-level credential override takes priority
    override = _load_asset_override_cred(asset_id) if asset_id else None
    creds    = [override] if override else None   # None → load by os_family inside helper

    # Quick port reachability check first
    check_port = SSH_PORT if os_family == "linux" else WINRM_PORT
    try:
        s = socket.create_connection((ip, check_port), timeout=3)
        s.close()
    except Exception:
        log.debug(f"Port {check_port} not reachable on {ip} — skipping remote info")
        return {"uptime_days": None, "last_patch": None, "av_present": None, "ssh_auth_failed": False}

    if os_family == "linux":
        return _ssh_get_info(ip, creds)
    elif os_family == "windows":
        return _winrm_get_info(ip, creds)
    return {"uptime_days": None, "last_patch": None, "av_present": None, "ssh_auth_failed": False}


# ── vCenter VM collection ────────────────────────────────────────────────────

def _os_family(os_str: str) -> str:
    s = (os_str or "").lower()
    if "windows" in s:                              return "windows"
    if any(x in s for x in ("linux","rhel","centos","ubuntu","suse","debian","oracle","fedora","rocky","alma")): return "linux"
    return "other"


def _collect_vms_from_vcenter(vc: dict, use_ssh: bool = True) -> list:
    """Collect VM inventory from one vCenter using vmware_client._connect + _vms."""
    log.info(f"  Collecting from vCenter {vc['name']} ({vc['host']})…")
    vms_raw = []
    try:
        from vmware_client import _connect, _vms
        vc_dict = {"host": vc["host"], "user": vc.get("username", vc.get("user", "")),
                   "pwd": vc.get("password", vc.get("pwd", "")), "port": int(vc.get("port", 443))}
        vc_si   = _connect(vc_dict)
        # _vms(si, vcenter_id, vcenter_name) → list of dicts
        vms_raw = _vms(vc_si, vc["host"], vc.get("name", vc["host"])) or []
        log.info(f"  → {len(vms_raw)} VMs from {vc['host']}")
    except Exception as ex:
        log.warning(f"  vCenter {vc['host']} collection failed: {ex}")
        return []

    # ── Fetch VM tags from vCenter REST API ────────────────────────────────
    tag_map = {}   # moid → [tag_strings]
    try:
        from vmware_client import _fetch_vm_tags_for_vcenter
        moids = [vm.get("moid", "") for vm in vms_raw if vm.get("moid")]
        if moids:
            vc_dict_tags = {"host": vc["host"], "user": vc.get("username", vc.get("user", "")),
                            "pwd": vc.get("password", vc.get("pwd", "")), "port": int(vc.get("port", 443))}
            result = _fetch_vm_tags_for_vcenter(vc_dict_tags, moids)
            # Returns (tag_map_dict, owners_dict) tuple — unpack safely
            if isinstance(result, tuple):
                tag_map = result[0] or {}
            elif isinstance(result, dict):
                tag_map = result
            else:
                tag_map = {}
            if not isinstance(tag_map, dict):
                tag_map = {}
            log.info(f"  → Tags fetched for {len(tag_map)} VMs from {vc['host']}")
    except Exception as ex:
        log.warning(f"  Tag fetch failed for {vc['host']}: {ex}")

    assets = []
    for vm in vms_raw:
        raw_ip  = vm.get("ip") or (vm.get("all_ips") or [""])[0]
        ip      = raw_ip.strip() if raw_ip and raw_ip.strip() else None
        os_name = vm.get("guest_os", "")
        os_fam  = _os_family(os_name)
        moid    = vm.get("moid", "")

        # Uptime from vCenter quickStats (seconds → days)
        uptime_sec  = vm.get("uptime_sec", 0) or 0
        power_state = vm.get("status", "")
        # Only treat uptime as valid when VM is powered on AND uptime_sec > 0
        if power_state == "poweredOn" and uptime_sec > 0:
            vc_uptime  = uptime_sec // 86400          # days (may be 0 if < 1 day)
            # Calculate absolute boot time so rules can derive patch_age_days
            from datetime import datetime, timezone, timedelta
            boot_iso = (datetime.now(timezone.utc) - timedelta(seconds=uptime_sec)).isoformat()
        else:
            vc_uptime = None
            boot_iso  = None

        # Snapshot info
        snap_count = vm.get("snapshot_count", 0) or 0
        snap_age   = vm.get("snapshot_age_days", None)

        # Remote info via SSH/WinRM (overrides vCenter uptime/boot if available)
        remote = _get_remote_info(ip, os_fam, use_ssh=use_ssh)
        uptime_days = remote["uptime_days"] if remote["uptime_days"] is not None else vc_uptime
        last_boot   = remote.get("last_boot") or boot_iso   # SSH > vCenter estimate
        last_patch  = remote["last_patch"]   # Only set when SSH actually returned patch date
        # NOTE: boot_iso is intentionally NOT used as last_patch proxy
        # Uptime ≠ patch age: live-kernel patches / Windows updates don't always reboot

        # VM tags from REST API tag_map
        vm_tags = tag_map.get(moid, [])

        assets.append({
            "hostname":          vm.get("name", ""),
            "ip_address":        ip,
            "os_name":           os_name,
            "os_version":        vm.get("guest_id", ""),
            "os_family":         os_fam,
            "asset_type":        "vm",
            "vcenter":           vc.get("name") or vc["host"],
            "cluster":           vm.get("cluster", ""),
            "hypervisor_host":   vm.get("host", ""),
            "datastore":         ", ".join(vm.get("datastores", []) or []),
            "vm_id":             moid,
            "cpu_count":         si(vm.get("cpu", 0)),
            "memory_gb":         round(sf(vm.get("ram_gb", 0)), 2),
            "disk_gb":           sf(vm.get("disk_gb", 0)),
            "power_state":       power_state,
            "tools_version":     vm.get("tools_version", ""),
            "tools_status":      vm.get("tools_status", ""),
            "hw_version":        vm.get("hw_version", ""),
            "last_boot":         last_boot,
            "last_patch":        last_patch,
            "uptime_days":       uptime_days,
            "snapshot_age_days": snap_age,
            "snapshot_count":    snap_count,
            "av_present":        remote["av_present"],
            "ssh_auth_failed":   remote.get("ssh_auth_failed", False),
            "environment":       vm.get("annotation", ""),
            "owner_team":        "",
            "vm_tags":           vm_tags,
        })
    return assets


def _collect_baremetal_from_cmdb(use_ssh: bool = True) -> list:
    """Pull servers from cmdb_ci (PostgreSQL). Actual column names verified."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        name           AS hostname,
                        ip_address,
                        os             AS os_name,
                        os_version,
                        CASE
                            WHEN os ILIKE '%windows%' THEN 'windows'
                            WHEN os ILIKE '%linux%' OR os ILIKE '%rhel%'
                              OR os ILIKE '%ubuntu%' OR os ILIKE '%centos%'
                              OR os ILIKE '%red hat%' THEN 'linux'
                            ELSE 'other'
                        END            AS os_family,
                        'baremetal'    AS asset_type,
                        NULL           AS vcenter,
                        location       AS cluster,
                        cpu_count,
                        ram_mb,
                        disk_space_gb  AS disk_gb,
                        operational_status AS power_state,
                        environment,
                        department     AS owner_team
                    FROM cmdb_ci
                    WHERE sys_class_name ILIKE '%server%'
                      OR  sys_class_name ILIKE '%bare%'
                      AND operational_status != 'retired'
                    LIMIT 500
                """)
                rows = cur.fetchall()
        servers = []
        for r in rows:
            d = dict(r)
            ip = d.get("ip_address") or ""
            os_fam = d.get("os_family") or _os_family(d.get("os_name") or "")
            remote = _get_remote_info(ip, os_fam, use_ssh=use_ssh)
            d.update({
                "vm_id": None, "hypervisor_host": None, "datastore": None,
                "tools_version": None, "tools_status": None, "hw_version": None,
                "last_boot": None, "snapshot_age_days": None,
                "memory_gb": round(sf(d.get("ram_mb", 0)) / 1024, 2),
                "last_patch":  remote["last_patch"],
                "uptime_days": remote["uptime_days"],
                "av_present":  remote["av_present"],
            })
            servers.append(d)
        log.info(f"CMDB: {len(servers)} baremetal servers")
        return servers
    except Exception as ex:
        log.warning(f"CMDB baremetal collection failed: {ex}\n{traceback.format_exc()[:300]}")
        return []


def _ensure_extra_columns():
    """Add extra columns if missing (idempotent)."""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE compliance_assets
                    ADD COLUMN IF NOT EXISTS extra_data JSONB DEFAULT '{}',
                    ADD COLUMN IF NOT EXISTS ssh_auth_failed BOOLEAN DEFAULT FALSE
            """)
            cur.execute("""
                ALTER TABLE compliance_results
                    ADD COLUMN IF NOT EXISTS uptime_days INTEGER
            """)
        conn.commit(); conn.close()
    except Exception as ex:
        log.debug(f"_ensure_extra_columns: {ex}")

_ensure_extra_columns()


# ── DB write helpers ─────────────────────────────────────────────────────────

def _upsert_asset(cur, asset: dict) -> int:
    key = asset_key(asset.get("hostname",""), asset.get("ip_address") or "", asset.get("asset_type","vm"))
    cur.execute("""
        INSERT INTO compliance_assets (
            asset_key, hostname, ip_address, os_name, os_version, os_family,
            asset_type, vcenter, cluster, hypervisor_host, datastore, vm_id,
            cpu_count, memory_gb, disk_gb, power_state, tools_version, tools_status,
            hw_version, environment, owner_team, last_seen, is_active, ssh_auth_failed,
            vm_tags, missing_patches
        ) VALUES (
            %(key)s,%(hostname)s,%(ip)s,%(os_name)s,%(os_ver)s,%(os_fam)s,
            %(atype)s,%(vc)s,%(cl)s,%(hh)s,%(ds)s,%(vmid)s,
            %(cpu)s,%(mem)s,%(disk)s,%(power)s,%(tv)s,%(ts)s,
            %(hw)s,%(env)s,%(owner)s,CURRENT_DATE,TRUE,%(ssh_fail)s,
            %(vm_tags)s,%(missing_patches)s
        )
        ON CONFLICT (asset_key) DO UPDATE SET
            hostname=EXCLUDED.hostname, ip_address=EXCLUDED.ip_address,
            os_name=EXCLUDED.os_name, os_version=EXCLUDED.os_version,
            os_family=EXCLUDED.os_family, vcenter=EXCLUDED.vcenter,
            cluster=EXCLUDED.cluster, hypervisor_host=EXCLUDED.hypervisor_host,
            cpu_count=EXCLUDED.cpu_count, memory_gb=EXCLUDED.memory_gb,
            disk_gb=EXCLUDED.disk_gb, power_state=EXCLUDED.power_state,
            tools_version=EXCLUDED.tools_version, tools_status=EXCLUDED.tools_status,
            hw_version=EXCLUDED.hw_version, environment=EXCLUDED.environment,
            owner_team=EXCLUDED.owner_team, last_seen=CURRENT_DATE, is_active=TRUE,
            ssh_auth_failed=EXCLUDED.ssh_auth_failed,
            vm_tags=EXCLUDED.vm_tags, missing_patches=EXCLUDED.missing_patches
        RETURNING id
    """, {
        "key": key, "hostname": asset.get("hostname",""),
        "ip": asset.get("ip_address") or None, "os_name": asset.get("os_name",""),
        "os_ver": asset.get("os_version",""), "os_fam": asset.get("os_family","other"),
        "atype": asset.get("asset_type","vm"), "vc": asset.get("vcenter",""),
        "cl": asset.get("cluster",""), "hh": asset.get("hypervisor_host",""),
        "ds": asset.get("datastore",""), "vmid": asset.get("vm_id",""),
        "cpu": si(asset.get("cpu_count")), "mem": sf(asset.get("memory_gb")),
        "disk": sf(asset.get("disk_gb")), "power": asset.get("power_state",""),
        "tv": asset.get("tools_version",""), "ts": asset.get("tools_status",""),
        "hw": asset.get("hw_version",""), "env": asset.get("environment",""),
        "owner": asset.get("owner_team",""),
        "ssh_fail": bool(asset.get("ssh_auth_failed", False)),
        "vm_tags": asset.get("vm_tags", []) or [],
        "missing_patches": si(asset.get("missing_patches", 0)),
    })
    return cur.fetchone()["id"]


def _insert_result(cur, scan_id, asset_id, scored):
    cur.execute("""
        INSERT INTO compliance_results (
            scan_id, asset_id, scanned_at, score, status, checks,
            patch_age_days, uptime_days, tools_ok, hw_version_ok,
            snapshot_ok, eol_os, missing_patches
        ) VALUES (
            %s,%s,NOW(),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
    """, (
        scan_id, asset_id, scored["score"], scored["status"],
        json.dumps(scored["checks"]),
        scored.get("patch_age_days"), scored.get("uptime_days"),
        scored.get("tools_ok"), scored.get("hw_version_ok"),
        scored.get("snapshot_ok"), scored.get("eol_os", False),
        scored.get("missing_patches", 0),
    ))


def _update_trend(cur, summary):
    cur.execute("""
        INSERT INTO compliance_trend
            (trend_date, total_assets, compliant, warning, non_compliant, avg_score, computed_at)
        VALUES (CURRENT_DATE,%s,%s,%s,%s,%s,NOW())
        ON CONFLICT (trend_date) DO UPDATE SET
            total_assets=EXCLUDED.total_assets, compliant=EXCLUDED.compliant,
            warning=EXCLUDED.warning, non_compliant=EXCLUDED.non_compliant,
            avg_score=EXCLUDED.avg_score, computed_at=NOW()
    """, (summary["total"], summary["compliant"], summary["warning"],
          summary["non_compliant"], summary["avg_score"]))


# ── Main orchestrator ────────────────────────────────────────────────────────

def run_compliance_scan(triggered_by="scheduler", dry_run=False,
                        target_vcenter=None, enabled_checks=None,
                        use_ssh=True) -> dict:
    import time
    t0 = time.time()
    log.info(f"=== CompliSphere scan started (by={triggered_by}, ssh={use_ssh}) ===")

    # 1. Collect assets
    all_assets = []
    vcenters = _load_vcenters_from_env()
    if target_vcenter:
        vcenters = [v for v in vcenters if v["host"] == target_vcenter or v.get("name") == target_vcenter]

    for vc in vcenters:
        vms = _collect_vms_from_vcenter(vc, use_ssh=use_ssh)
        all_assets.extend(vms)

    baremetal = _collect_baremetal_from_cmdb(use_ssh=use_ssh)
    all_assets.extend(baremetal)

    log.info(f"Total assets collected: {len(all_assets)}")

    if not all_assets:
        log.warning("No assets collected — check vCenter connectivity")
        return {"total": 0, "compliant": 0, "warning": 0, "non_compliant": 0, "avg_score": 0}

    # 2. Score
    scored_assets = []
    for asset in all_assets:
        try:
            result = score_asset(asset, enabled_checks=enabled_checks)
            scored_assets.append((asset, result))
        except Exception as ex:
            log.warning(f"Score error {asset.get('hostname')}: {ex}")

    total = len(scored_assets)
    counts = {"compliant": 0, "warning": 0, "non_compliant": 0}
    total_score = 0
    for _, r in scored_assets:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        total_score += r["score"]
    avg_score = round(total_score / total, 1) if total else 0
    summary = {"total": total, "avg_score": avg_score, **counts}

    if dry_run:
        log.info(f"DRY RUN result: {summary}")
        return summary

    # 3. Write to PostgreSQL
    try:
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO compliance_scans
                (scanned_at, scan_date, triggered_by, status,
                 total_assets, compliant, warning, non_compliant)
            VALUES (NOW(), CURRENT_DATE, %s, 'running', %s, %s, %s, %s)
            ON CONFLICT (scan_date, triggered_by) DO UPDATE SET
                scanned_at=NOW(), status='running',
                total_assets=%s, compliant=%s, warning=%s, non_compliant=%s
            RETURNING id
        """, (triggered_by, total, counts["compliant"], counts["warning"], counts["non_compliant"],
               total, counts["compliant"], counts["warning"], counts["non_compliant"]))
        scan_id = cur.fetchone()["id"]

        written = 0
        for asset, scored in scored_assets:
            try:
                aid = _upsert_asset(cur, asset)
                _insert_result(cur, scan_id, aid, scored)
                written += 1
            except Exception as ex:
                log.warning(f"DB write error {asset.get('hostname')}: {ex}")

        duration = round(time.time() - t0, 2)
        cur.execute("""
            UPDATE compliance_scans
            SET status='completed', duration_sec=%s,
                total_assets=%s, compliant=%s, warning=%s, non_compliant=%s
            WHERE id=%s
        """, (duration, total, counts["compliant"], counts["warning"], counts["non_compliant"], scan_id))

        _update_trend(cur, summary)
        conn.commit()
        cur.close()
        conn.close()
        log.info(f"Scan complete — {written}/{total} assets in {duration}s | {summary}")
    except Exception as ex:
        log.error(f"DB error: {ex}\n{traceback.format_exc()[:500]}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--no-ssh",   action="store_true")
    parser.add_argument("--vcenter",  default=None)
    parser.add_argument("--checks",   default=None, help="Comma-separated rule ids")
    parser.add_argument("--trigger",  default="manual")
    args = parser.parse_args()
    checks = args.checks.split(",") if args.checks else None
    result = run_compliance_scan(
        triggered_by=args.trigger, dry_run=args.dry_run,
        target_vcenter=args.vcenter, enabled_checks=checks,
        use_ssh=not args.no_ssh,
    )
    print(json.dumps(result, indent=2))
