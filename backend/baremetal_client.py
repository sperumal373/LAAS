"""
baremetal_client.py — Bare Metal Server management via ILO/iDRAC/CIMC/IPMI
Stores servers in SQLite. Supports power actions via:
  - IPMI (ipmitool)  — universal fallback
  - Redfish REST API — HPE iLO 5+, Dell iDRAC 8+, Cisco CIMC
"""
import os, json, logging, subprocess, requests, time
from pathlib import Path
from datetime import datetime
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

log = logging.getLogger("caas.baremetal")

BMC_TYPES = ["ILO", "IDRAC", "CIMC", "IPMI"]

# ── DB helpers ─────────────────────────────────────────────────────────────────
def _get_db():
    import sqlite3
    db_path = Path(__file__).parent / "caas.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_baremetal_db():
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bm_servers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            ip          TEXT NOT NULL,
            bmc_type    TEXT NOT NULL DEFAULT 'IPMI',
            username    TEXT NOT NULL,
            password    TEXT NOT NULL,
            port        INTEGER DEFAULT 443,
            description TEXT DEFAULT '',
            location    TEXT DEFAULT '',
            model       TEXT DEFAULT '',
            serial      TEXT DEFAULT '',
            status      TEXT DEFAULT 'unknown',
            power_state TEXT DEFAULT 'unknown',
            added_by    TEXT NOT NULL,
            added_at    TEXT NOT NULL,
            last_seen   TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()
    log.info("Baremetal DB tables initialized")

def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# ── Server CRUD ────────────────────────────────────────────────────────────────
def list_servers():
    conn = _get_db()
    rows = conn.execute("SELECT * FROM bm_servers ORDER BY name").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d.pop("password", None)   # never return password in list
        result.append(d)
    return result

def get_server(server_id: int, include_password=False):
    conn = _get_db()
    row = conn.execute("SELECT * FROM bm_servers WHERE id=?", (server_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if not include_password:
        d.pop("password", None)
    return d

def add_server(data: dict, added_by: str) -> dict:
    conn = _get_db()
    now = _now()
    try:
        cur = conn.execute("""
            INSERT INTO bm_servers
              (name, ip, bmc_type, username, password, port,
               description, location, model, serial,
               status, power_state, added_by, added_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data["name"], data["ip"],
            data.get("bmc_type","IPMI").upper(),
            data["username"], data["password"],
            int(data.get("port", 443)),
            data.get("description",""), data.get("location",""),
            data.get("model",""), data.get("serial",""),
            "unknown", "unknown",
            added_by, now
        ))
        conn.commit()
        row = conn.execute("SELECT * FROM bm_servers WHERE id=?", (cur.lastrowid,)).fetchone()
        d = dict(row)
        d.pop("password", None)
        return d
    except Exception as e:
        raise ValueError(str(e))
    finally:
        conn.close()

def update_server(server_id: int, data: dict) -> dict:
    conn = _get_db()
    fields, vals = [], []
    for k in ("name","ip","bmc_type","username","password","port",
              "description","location","model","serial"):
        if k in data and data[k] is not None:
            fields.append(f"{k}=?")
            v = data[k].upper() if k == "bmc_type" else data[k]
            vals.append(v)
    if not fields:
        conn.close()
        return get_server(server_id)
    vals.append(server_id)
    conn.execute(f"UPDATE bm_servers SET {','.join(fields)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return get_server(server_id)

def delete_server(server_id: int) -> bool:
    conn = _get_db()
    r = conn.execute("DELETE FROM bm_servers WHERE id=?", (server_id,))
    conn.commit()
    conn.close()
    return r.rowcount > 0

def _update_status(server_id, status, power_state=None):
    conn = _get_db()
    if power_state:
        conn.execute(
            "UPDATE bm_servers SET status=?,power_state=?,last_seen=? WHERE id=?",
            (status, power_state, _now(), server_id)
        )
    else:
        conn.execute(
            "UPDATE bm_servers SET status=?,last_seen=? WHERE id=?",
            (status, _now(), server_id)
        )
    conn.commit()
    conn.close()

# ── Redfish REST API (HPE iLO / Dell iDRAC / Cisco CIMC) ──────────────────────
class RedfishClient:
    def __init__(self, ip, username, password, port=443):
        self.base = f"https://{ip}:{port}"
        self.auth = (username, password)
        self.sess = requests.Session()
        self.sess.verify = False
        self.sess.auth   = self.auth
        self.sess.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
        self.timeout = 15

    def get(self, path):
        return self.sess.get(f"{self.base}{path}", timeout=self.timeout)

    def post(self, path, body=None):
        return self.sess.post(f"{self.base}{path}", json=body or {}, timeout=self.timeout)

    def _system_path(self):
        """Find the Systems member path."""
        r = self.get("/redfish/v1/Systems")
        r.raise_for_status()
        members = r.json().get("Members", [])
        if not members:
            raise RuntimeError("No Systems members found in Redfish")
        return members[0]["@odata.id"]

    def get_power_state(self):
        path = self._system_path()
        r = self.get(path)
        r.raise_for_status()
        d = r.json()
        return {
            "power_state":   d.get("PowerState", "Unknown"),
            "model":         d.get("Model", ""),
            "serial":        d.get("SerialNumber", ""),
            "manufacturer":  d.get("Manufacturer", ""),
            "bios_version":  d.get("BiosVersion", ""),
            "hostname":      d.get("HostName", ""),
            "processors":    d.get("ProcessorSummary", {}).get("Count", ""),
            "memory_gb":     d.get("MemorySummary", {}).get("TotalSystemMemoryGiB", ""),
        }

    def power_action(self, action: str):
        """
        action: On, ForceOff, GracefulShutdown, ForceRestart,
                GracefulRestart, Nmi, PushPowerButton
        """
        path = self._system_path()
        reset_url = f"{path}/Actions/ComputerSystem.Reset"
        r = self.post(reset_url, {"ResetType": action})
        if r.status_code in (200, 202, 204):
            return {"success": True, "message": f"Action '{action}' accepted"}
        return {"success": False, "message": f"HTTP {r.status_code}: {r.text[:200]}"}

    def get_health(self):
        """Get system health summary."""
        try:
            path = self._system_path()
            r = self.get(path)
            r.raise_for_status()
            d = r.json()
            status = d.get("Status", {})
            return {
                "health":       status.get("Health", "Unknown"),
                "health_rollup":status.get("HealthRollup", "Unknown"),
                "state":        status.get("State", "Unknown"),
            }
        except Exception as e:
            return {"health": "Unknown", "error": str(e)}

    def get_sensors(self):
        """Get thermal and power sensors (best-effort)."""
        result = {"temperature": [], "fans": [], "power": []}
        try:
            chassis_r = self.get("/redfish/v1/Chassis")
            chassis_r.raise_for_status()
            members = chassis_r.json().get("Members", [])
            if not members:
                return result
            chassis_path = members[0]["@odata.id"]
            # Thermal
            try:
                t = self.get(f"{chassis_path}/Thermal")
                if t.ok:
                    td = t.json()
                    for temp in td.get("Temperatures", []):
                        result["temperature"].append({
                            "name":    temp.get("Name",""),
                            "reading": temp.get("ReadingCelsius",""),
                            "state":   temp.get("Status",{}).get("State",""),
                            "health":  temp.get("Status",{}).get("Health",""),
                        })
                    for fan in td.get("Fans", []):
                        result["fans"].append({
                            "name":    fan.get("Name",""),
                            "reading": fan.get("Reading",""),
                            "units":   fan.get("ReadingUnits","RPM"),
                            "health":  fan.get("Status",{}).get("Health",""),
                        })
            except Exception:
                pass
            # Power
            try:
                p = self.get(f"{chassis_path}/Power")
                if p.ok:
                    pd = p.json()
                    for psu in pd.get("PowerControl", []):
                        result["power"].append({
                            "name":         psu.get("Name",""),
                            "consumed_watts":psu.get("PowerConsumedWatts",""),
                            "limit_watts":  psu.get("PowerLimit",{}).get("LimitInWatts",""),
                        })
            except Exception:
                pass
        except Exception:
            pass
        return result

    def get_bios_settings(self):
        """Return key BIOS attributes (best-effort)."""
        try:
            path = self._system_path()
            r = self.get(f"{path}/Bios")
            if r.ok:
                attrs = r.json().get("Attributes", {})
                # Return a safe subset
                keys = ["SystemBootOrder","BootMode","HyperThreading",
                        "NUMAGroupSizeOpt","VirtualizationTechnology",
                        "IntelVirtualizationTechnology"]
                return {k: attrs[k] for k in keys if k in attrs}
        except Exception:
            pass
        return {}

    def get_event_log(self, limit=20):
        """Return recent system event log entries (best-effort)."""
        entries = []
        try:
            r = self.get("/redfish/v1/Systems")
            sys_path = r.json()["Members"][0]["@odata.id"]
            log_r = self.get(f"{sys_path}/LogServices")
            if not log_r.ok:
                return entries
            log_members = log_r.json().get("Members", [])
            for lm in log_members[:2]:
                entries_r = self.get(f"{lm['@odata.id']}/Entries?$top={limit}")
                if entries_r.ok:
                    for e in entries_r.json().get("Members", []):
                        entries.append({
                            "id":       e.get("Id",""),
                            "severity": e.get("Severity",""),
                            "message":  e.get("Message",""),
                            "created":  e.get("Created",""),
                        })
        except Exception:
            pass
        return entries[:limit]


# ── IPMI fallback (ipmitool) ───────────────────────────────────────────────────
def _ipmi_cmd(ip, username, password, args: list, timeout=20) -> tuple[bool, str]:
    cmd = ["ipmitool", "-I", "lanplus",
           "-H", ip, "-U", username, "-P", password] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            return True, r.stdout.strip()
        return False, r.stderr.strip() or r.stdout.strip()
    except FileNotFoundError:
        return False, "ipmitool not installed on this server"
    except subprocess.TimeoutExpired:
        return False, "IPMI command timed out"
    except Exception as e:
        return False, str(e)

def _ipmi_power_state(ip, username, password):
    ok, out = _ipmi_cmd(ip, username, password, ["power", "status"])
    if ok:
        return "On" if "on" in out.lower() else "Off"
    return "Unknown"

# ── Public API ─────────────────────────────────────────────────────────────────
def get_power_state(server: dict) -> dict:
    """Return current power state for a server. Tries Redfish first, falls back to IPMI."""
    bmc = server.get("bmc_type","IPMI").upper()
    ip  = server["ip"]
    u   = server["username"]
    p   = server["password"]
    port = int(server.get("port", 443))

    if bmc in ("ILO","IDRAC","CIMC"):
        try:
            rf = RedfishClient(ip, u, p, port)
            info = rf.get_power_state()
            _update_status(server["id"], "online", info["power_state"])
            return {"success": True, **info}
        except Exception as e:
            log.warning(f"Redfish failed for {ip}: {e}, falling back to IPMI")

    # IPMI fallback
    ok, out = _ipmi_cmd(ip, u, p, ["power", "status"])
    if ok:
        ps = "On" if "on" in out.lower() else "Off"
        _update_status(server["id"], "online", ps)
        return {"success": True, "power_state": ps}
    _update_status(server["id"], "unreachable")
    return {"success": False, "power_state": "Unknown", "message": out}


# ── Action map ─────────────────────────────────────────────────────────────────
# Maps our action name -> (Redfish ResetType, IPMI subcommand)
_ACTION_MAP = {
    "power_on":           ("On",               "on"),
    "power_off":          ("ForceOff",          "off"),
    "graceful_shutdown":  ("GracefulShutdown",  "soft"),
    "reboot":             ("ForceRestart",      "reset"),
    "graceful_reboot":    ("GracefulRestart",   "reset"),
    "power_cycle":        ("PowerCycle",        "cycle"),
    "nmi":                ("Nmi",               None),
    "pxe_boot":           (None,                None),   # handled separately
}

def power_action(server: dict, action: str) -> dict:
    """
    Perform a power/boot action on a bare metal server.
    action: power_on | power_off | graceful_shutdown | reboot |
            graceful_reboot | power_cycle | nmi | pxe_boot
    """
    if action not in _ACTION_MAP:
        return {"success": False, "message": f"Unknown action: {action}. Valid: {list(_ACTION_MAP.keys())}"}

    bmc  = server.get("bmc_type","IPMI").upper()
    ip   = server["ip"]
    u    = server["username"]
    p    = server["password"]
    port = int(server.get("port", 443))
    redfish_action, ipmi_action = _ACTION_MAP[action]

    # PXE boot — special case
    if action == "pxe_boot":
        return _set_pxe_boot(server)

    if bmc in ("ILO","IDRAC","CIMC") and redfish_action:
        try:
            rf = RedfishClient(ip, u, p, port)
            result = rf.power_action(redfish_action)
            if result["success"]:
                _update_status(server["id"], "online")
            return result
        except Exception as e:
            log.warning(f"Redfish action failed for {ip}: {e}, trying IPMI")

    # IPMI fallback
    if ipmi_action:
        ok, out = _ipmi_cmd(ip, u, p, ["power", ipmi_action])
        if ok:
            _update_status(server["id"], "online")
            return {"success": True, "message": f"IPMI power {ipmi_action} sent: {out}"}
        return {"success": False, "message": out}

    return {"success": False, "message": f"Action '{action}' not supported via IPMI for {bmc}"}


def _set_pxe_boot(server: dict) -> dict:
    """Set next boot to PXE then power cycle."""
    bmc  = server.get("bmc_type","IPMI").upper()
    ip   = server["ip"]
    u    = server["username"]
    p    = server["password"]
    port = int(server.get("port", 443))

    if bmc in ("ILO","IDRAC","CIMC"):
        try:
            rf = RedfishClient(ip, u, p, port)
            sys_path = rf._system_path()
            # Set boot override
            r = rf.sess.patch(
                f"{rf.base}{sys_path}",
                json={"Boot": {"BootSourceOverrideEnabled": "Once",
                               "BootSourceOverrideTarget": "Pxe"}},
                timeout=15
            )
            if r.status_code not in (200,202,204):
                raise RuntimeError(f"Patch failed: {r.status_code}")
            # Power on/reset
            rf.power_action("ForceRestart")
            return {"success": True, "message": "PXE boot set and system reset initiated"}
        except Exception as e:
            log.warning(f"Redfish PXE boot failed: {e}")

    # IPMI
    ok1, o1 = _ipmi_cmd(ip, u, p, ["chassis", "bootdev", "pxe"])
    ok2, o2 = _ipmi_cmd(ip, u, p, ["power", "reset"])
    if ok1 and ok2:
        return {"success": True, "message": "PXE boot set via IPMI and system reset"}
    return {"success": False, "message": f"IPMI: {o1} / {o2}"}


def get_server_info(server: dict) -> dict:
    """Full server info: power, health, sensors (Redfish only)."""
    bmc  = server.get("bmc_type","IPMI").upper()
    ip   = server["ip"]
    u    = server["username"]
    p    = server["password"]
    port = int(server.get("port", 443))

    if bmc in ("ILO","IDRAC","CIMC"):
        try:
            rf     = RedfishClient(ip, u, p, port)
            power  = rf.get_power_state()
            health = rf.get_health()
            sensors= rf.get_sensors()
            # Update DB with discovered model/serial
            conn = _get_db()
            conn.execute(
                "UPDATE bm_servers SET model=?,serial=?,power_state=?,status=?,last_seen=? WHERE id=?",
                (power.get("model",""), power.get("serial",""),
                 power.get("power_state",""), "online", _now(), server["id"])
            )
            conn.commit()
            conn.close()
            return {
                "success":  True,
                "power":    power,
                "health":   health,
                "sensors":  sensors,
            }
        except Exception as e:
            _update_status(server["id"], "unreachable")
            return {"success": False, "message": str(e)}

    # IPMI basic
    ps = _ipmi_power_state(ip, u, p)
    ok, fru = _ipmi_cmd(ip, u, p, ["fru"])
    return {
        "success":    True,
        "power":      {"power_state": ps},
        "health":     {},
        "sensors":    {},
        "fru":        fru if ok else "",
    }


def get_event_log(server: dict, limit: int = 20) -> dict:
    """Fetch system event log."""
    bmc  = server.get("bmc_type","IPMI").upper()
    ip   = server["ip"]
    u    = server["username"]
    p    = server["password"]
    port = int(server.get("port", 443))

    if bmc in ("ILO","IDRAC","CIMC"):
        try:
            rf = RedfishClient(ip, u, p, port)
            return {"success": True, "logs": rf.get_event_log(limit)}
        except Exception as e:
            pass

    # IPMI SEL
    ok, out = _ipmi_cmd(ip, u, p, ["sel", "list"])
    if ok:
        lines = out.splitlines()[-limit:]
        return {"success": True, "logs": [{"message": l} for l in lines]}
    return {"success": False, "logs": [], "message": out}


def test_connection(ip: str, username: str, password: str,
                    bmc_type: str = "IPMI", port: int = 443) -> dict:
    """Test connectivity before adding a server."""
    bmc = bmc_type.upper()
    if bmc in ("ILO","IDRAC","CIMC"):
        try:
            rf = RedfishClient(ip, username, password, port)
            info = rf.get_power_state()
            return {
                "success": True,
                "message": f"Connected via Redfish. Power: {info.get('power_state','?')}",
                "info":    info
            }
        except Exception as e:
            pass  # fall through to IPMI

    ok, out = _ipmi_cmd(ip, username, password, ["power", "status"])
    if ok:
        return {"success": True, "message": f"Connected via IPMI. {out}"}
    return {"success": False, "message": f"Cannot connect via Redfish or IPMI: {out}"}
