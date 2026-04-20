"""
SolarWinds IPAM integration via SWIS (SolarWinds Information Service) API.
Reads IPAM subnet / VLAN data and caches results to avoid repeated vCenter-style latency.
"""

import os, ssl, json, base64, http.client, time, logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")
log = logging.getLogger("caas.ipam")

IPAM_HOST     = os.getenv("IPAM_HOST",     "172.17.66.121")
IPAM_PORT     = int(os.getenv("IPAM_PORT", "17774"))
IPAM_USER     = os.getenv("IPAM_USER",     "sdxcoe")
IPAM_PASS     = os.getenv("IPAM_PASS",     "Wipro@123")
IPAM_CACHE_TTL = int(os.getenv("IPAM_CACHE_TTL_SECONDS", "300"))  # 5 min

_SWIS_PATH = "/SolarWinds/InformationService/v3/Json/Query"

_ipam_cache: dict = {"data": None, "ts": 0.0, "error": None}


def _swis_query(query: str) -> dict:
    """Execute a SWQL query against the SolarWinds SWIS API."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    cred = base64.b64encode(f"{IPAM_USER}:{IPAM_PASS}".encode()).decode()
    conn = http.client.HTTPSConnection(IPAM_HOST, IPAM_PORT, context=ctx, timeout=20)
    try:
        body = json.dumps({"query": query}).encode()
        conn.request(
            "POST", _SWIS_PATH, body=body,
            headers={"Authorization": f"Basic {cred}", "Content-Type": "application/json"}
        )
        r = conn.getresponse()
        raw = r.read().decode()
        data = json.loads(raw)
        if r.status != 200:
            raise RuntimeError(f"SWIS HTTP {r.status}: {data.get('Message','')[:200]}")
        return data
    finally:
        conn.close()


def get_ipam_subnets(force: bool = False) -> dict:
    """
    Return all real subnets from SolarWinds IPAM.
    Result is cached for IPAM_CACHE_TTL seconds.
    Returns:
        {
          "subnets": [ {SubnetId, FriendlyName, address_cidr, vlan, ...}, ... ],
          "summary": { total, total_ips, used_ips, available_ips, reserved_ips },
          "cached_at": <unix timestamp>,
          "error": None or str
        }
    """
    now = time.time()
    if not force and _ipam_cache["data"] and (now - _ipam_cache["ts"]) < IPAM_CACHE_TTL:
        return _ipam_cache["data"]

    try:
        result = _swis_query(
            """SELECT SubnetId, FriendlyName, Address, CIDR, VLAN,
                      AllocSize, UsedCount, AvailableCount, ReservedCount, PercentUsed,
                      Comments, Location, StatusName, Description
               FROM IPAM.Subnet
               WHERE Address IS NOT NULL AND CIDR > 0
               ORDER BY VLAN, Address"""
        )

        rows = result.get("results", [])
        subnets = []
        total_ips = used = available = reserved = 0

        for r in rows:
            alloc   = int(r.get("AllocSize")   or 0)
            u       = int(r.get("UsedCount")    or 0)
            av      = int(r.get("AvailableCount") or 0)
            res     = int(r.get("ReservedCount") or 0)
            pct     = float(r.get("PercentUsed") or 0.0)
            cidr    = r.get("CIDR")
            addr    = r.get("Address") or ""
            vlan    = (r.get("VLAN") or "").strip()
            # Normalise VLAN — strip "VLAN " prefix if present
            if vlan.upper().startswith("VLAN "):
                vlan = vlan[5:].strip()

            total_ips += alloc
            used      += u
            available += av
            reserved  += res

            subnets.append({
                "subnet_id":     r.get("SubnetId"),
                "name":          (r.get("FriendlyName") or "").strip(),
                "address":       addr,
                "cidr":          cidr,
                "address_cidr":  f"{addr}/{cidr}" if addr and cidr else addr,
                "vlan":          vlan,
                "total":         alloc,
                "used":          u,
                "available":     av,
                "reserved":      res,
                "percent_used":  round(pct, 1),
                "location":      (r.get("Location") or "").strip(),
                "comments":      (r.get("Comments") or "").strip(),
                "description":   (r.get("Description") or "").strip(),
                "status":        (r.get("StatusName") or "").strip(),
            })

        data = {
            "subnets": subnets,
            "summary": {
                "total_subnets": len(subnets),
                "total_ips":     total_ips,
                "used_ips":      used,
                "available_ips": available,
                "reserved_ips":  reserved,
                "percent_used":  round((used / total_ips * 100) if total_ips else 0, 1),
            },
            "cached_at": now,
            "error": None,
        }
        _ipam_cache["data"] = data
        _ipam_cache["ts"]   = now
        _ipam_cache["error"] = None
        log.info("IPAM cache refreshed — %d subnets", len(subnets))
        return data

    except Exception as e:
        log.error("IPAM fetch failed: %s", e)
        error_resp = {
            "subnets": [],
            "summary": {"total_subnets": 0, "total_ips": 0, "used_ips": 0,
                        "available_ips": 0, "reserved_ips": 0, "percent_used": 0},
            "cached_at": now,
            "error": str(e),
        }
        # Return stale cache if available rather than an error
        if _ipam_cache["data"]:
            stale = dict(_ipam_cache["data"])
            stale["error"] = f"IPAM refresh failed — showing cached data: {e}"
            return stale
        return error_resp


# Per-subnet IP cache
_ip_cache: dict = {}  # subnet_id -> {data, ts}

STATUS_MAP = {0: "Unknown", 1: "Used", 2: "Free", 4: "Reserved", 8: "Transient"}


def get_ipam_subnet_ips(subnet_id: int, force: bool = False) -> dict:
    """
    Return all IP addresses for a specific subnet from SolarWinds IPAM.
    Cached per-subnet for IPAM_CACHE_TTL seconds.
    """
    now = time.time()
    cached = _ip_cache.get(subnet_id)
    if not force and cached and (now - cached["ts"]) < IPAM_CACHE_TTL:
        return cached["data"]

    # Find parent subnet info from the subnets cache for context
    subnet_info = {}
    if _ipam_cache.get("data"):
        subnet_info = next(
            (s for s in _ipam_cache["data"].get("subnets", []) if s["subnet_id"] == subnet_id),
            {}
        )

    try:
        result = _swis_query(
            f"""SELECT IpNodeId, IPAddress, Status, DnsBackward, SysName,
                       MAC, Description, Comments, Alias, LastSync
                FROM IPAM.IPNode
                WHERE SubnetId = {int(subnet_id)}
                ORDER BY IPAddressN"""
        )

        rows = result.get("results", [])
        ips = []
        used = free = reserved = transient = unknown = 0

        for r in rows:
            status_code = r.get("Status") or 0
            status_name = STATUS_MAP.get(status_code, "Unknown")
            if status_code == 1:   used      += 1
            elif status_code == 2: free      += 1
            elif status_code == 4: reserved  += 1
            elif status_code == 8: transient += 1
            else:                  unknown   += 1

            last_sync = ""
            if r.get("LastSync"):
                try:
                    last_sync = str(r["LastSync"])[:19].replace("T", " ")
                except Exception:
                    pass

            ips.append({
                "ip":          r.get("IPAddress") or "",
                "status_code": status_code,
                "status":      status_name,
                "hostname":    (r.get("DnsBackward") or r.get("SysName") or r.get("Alias") or "").strip(),
                "mac":         (r.get("MAC") or "").strip(),
                "description": (r.get("Description") or "").strip(),
                "comments":    (r.get("Comments") or "").strip(),
                "last_sync":   last_sync,
            })

        data = {
            "subnet_id":   subnet_id,
            "subnet_info": subnet_info,
            "ips":         ips,
            "summary": {
                "total":     len(ips),
                "used":      used,
                "free":      free,
                "reserved":  reserved,
                "transient": transient,
                "unknown":   unknown,
                "percent_used": round((used / len(ips) * 100) if ips else 0, 1),
            },
            "cached_at": now,
            "error": None,
        }
        _ip_cache[subnet_id] = {"data": data, "ts": now}
        log.info("IPAM subnet %d IPs loaded: %d total, %d used, %d free", subnet_id, len(ips), used, free)
        return data

    except Exception as e:
        log.error("IPAM subnet %d IP fetch failed: %s", subnet_id, e)
        if cached:
            stale = dict(cached["data"])
            stale["error"] = f"Refresh failed — showing cached data: {e}"
            return stale
        return {
            "subnet_id": subnet_id, "subnet_info": subnet_info,
            "ips": [], "summary": {"total":0,"used":0,"free":0,"reserved":0,"transient":0,"unknown":0,"percent_used":0},
            "cached_at": now, "error": str(e),
        }
