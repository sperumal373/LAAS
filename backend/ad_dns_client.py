"""
AD & DNS Management Client
- Active Directory management via ldap3 (same server/creds as auth.py)
- DNS management via PowerShell remoting to the AD/DNS server
"""
import os, json, logging
from pathlib import Path

log = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

AD_SERVER    = os.getenv("AD_SERVER",    "172.17.65.134")
AD_DOMAIN    = os.getenv("AD_DOMAIN",    "sdxtest.local")
AD_BIND_USER = os.getenv("AD_BIND_USER", "caas@sdxtest.local")
AD_BIND_PASS = os.getenv("AD_BIND_PASS", "Wipro@123")
AD_BASE_DN   = os.getenv("AD_BASE_DN",   "DC=sdxtest,DC=local")
AD_PORT      = int(os.getenv("AD_PORT",  "389"))
# Privileged account for write operations (create/modify/delete users & groups)
AD_WRITE_USER = os.getenv("AD_WRITE_USER", os.getenv("AD_BIND_USER", "caas@sdxtest.local"))
AD_WRITE_PASS = os.getenv("AD_WRITE_PASS", os.getenv("AD_BIND_PASS", "Wipro@123"))


# â”€â”€ LDAP helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _conn():
    """Read-only LDAP connection (plain, port 389)."""
    from ldap3 import Server, Connection, ALL
    server = Server(AD_SERVER, port=AD_PORT, get_info=ALL)
    conn = Connection(server, user=AD_BIND_USER, password=AD_BIND_PASS, auto_bind=True)
    return conn


def _conn_write():
    """Privileged plain-LDAP connection for write operations (create/modify/delete)."""
    from ldap3 import Server, Connection, ALL
    server = Server(AD_SERVER, port=AD_PORT, get_info=ALL)
    conn = Connection(server, user=AD_WRITE_USER, password=AD_WRITE_PASS, auto_bind=True)
    return conn


def _conn_ssl():
    """Privileged SSL connection (port 636) – required for password set/change."""
    import ssl
    from ldap3 import Server, Connection, ALL, Tls
    tls = Tls(validate=ssl.CERT_NONE)
    server = Server(AD_SERVER, port=636, use_ssl=True, tls=tls, get_info=ALL)
    conn = Connection(server, user=AD_WRITE_USER, password=AD_WRITE_PASS, auto_bind=True)
    return conn


def _str(v):
    if v is None:
        return ""
    try:
        return str(v)
    except Exception:
        return ""


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  AD USER FUNCTIONS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def ad_list_users(search: str = "", limit: int = 500) -> dict:
    try:
        from ldap3 import SUBTREE
        conn = _conn()
        sf = (f"(&(objectCategory=person)(objectClass=user)"
              f"(|(sAMAccountName=*{search}*)(displayName=*{search}*)(mail=*{search}*)))"
              if search else
              "(&(objectCategory=person)(objectClass=user))")
        conn.search(
            AD_BASE_DN, sf, search_scope=SUBTREE,
            attributes=["sAMAccountName", "displayName", "mail", "userAccountControl",
                        "lockoutTime", "whenCreated", "memberOf", "department",
                        "title", "distinguishedName", "description"]
        )
        users = []
        for e in conn.entries[:limit]:
            uac = int(_str(e.userAccountControl) or "512")
            locked_val = _str(e.lockoutTime)
            try:
                locked = int(locked_val) != 0
            except Exception:
                locked = False
            members = []
            member_dns = []
            if e.memberOf:
                for dn in (e.memberOf.values if hasattr(e.memberOf, "values") else []):
                    dn_str = _str(dn)
                    cn = dn_str.split(",")[0].replace("CN=", "")
                    members.append(cn)
                    member_dns.append(dn_str)
            users.append({
                "username":     _str(e.sAMAccountName),
                "display_name": _str(e.displayName),
                "email":        _str(e.mail),
                "department":   _str(e.department),
                "title":        _str(e.title),
                "description":  _str(e.description),
                "enabled":      not bool(uac & 2),
                "locked":       locked,
                "pw_never_expires": bool(uac & 0x10000),
                "dn":           _str(e.distinguishedName),
                "created":      _str(e.whenCreated),
                "groups":       members,
                "group_dns":    member_dns,
            })
        conn.unbind()
        return {"users": sorted(users, key=lambda x: x["username"].lower())}
    except Exception as ex:
        log.error("ad_list_users: %s", ex)
        return {"users": [], "error": str(ex)}


def ad_create_user(username: str, display_name: str, password: str,
                   ou_dn: str = None, email: str = "",
                   department: str = "", title: str = "",
                   pw_never_expires: bool = False,
                   must_change_pw: bool = False) -> dict:
    try:
        from ldap3 import MODIFY_REPLACE
        # Step 1: Create the account object using privileged write account
        conn = _conn_write()
        ou = ou_dn or f"CN=Users,{AD_BASE_DN}"
        dn = f"CN={display_name},{ou}"
        upn = f"{username}@{AD_DOMAIN}"
        attrs = {
            "objectClass":        ["top", "person", "organizationalPerson", "user"],
            "sAMAccountName":     username,
            "userPrincipalName":  upn,
            "displayName":        display_name,
            "userAccountControl": 514,   # disabled until password set
        }
        if email.strip():      attrs["mail"]       = email.strip()
        if department.strip(): attrs["department"] = department.strip()
        if title.strip():      attrs["title"]      = title.strip()

        ok = conn.add(dn, attributes=attrs)
        err = ""
        if not ok:
            err = conn.result.get("description", "") or conn.result.get("message", "")
            conn.unbind()
            return {"success": False, "dn": dn, "error": err}
        conn.unbind()

        # Step 2: Set password via SSL (port 636) — AD requires TLS for password ops
        try:
            sconn = _conn_ssl()
            sconn.extend.microsoft.modify_password(dn, new_password=password)
            uac = 512
            if pw_never_expires:
                uac |= 0x10000  # DONT_EXPIRE_PASSWORD
            sconn.modify(dn, {"userAccountControl": [(MODIFY_REPLACE, [uac])]})
            if must_change_pw and not pw_never_expires:
                sconn.modify(dn, {"pwdLastSet": [(MODIFY_REPLACE, [0])]})
            sconn.unbind()
        except Exception as ssl_ex:
            # If SSL fails, try unicodePwd over plain LDAP as fallback
            log.warning("SSL password set failed (%s), trying unicodePwd fallback", ssl_ex)
            pw_encoded = ('"' + password + '"').encode('utf-16-le')
            conn2 = _conn_write()
            conn2.modify(dn, {"unicodePwd": [(MODIFY_REPLACE, [pw_encoded])]})
            uac = 512
            if pw_never_expires:
                uac |= 0x10000
            conn2.modify(dn, {"userAccountControl": [(MODIFY_REPLACE, [uac])]})
            if must_change_pw and not pw_never_expires:
                conn2.modify(dn, {"pwdLastSet": [(MODIFY_REPLACE, [0])]})
            conn2.unbind()

        return {"success": True, "dn": dn, "error": ""}
    except Exception as ex:
        return {"success": False, "error": str(ex)}


def ad_set_enabled(dn: str, enabled: bool = True) -> dict:
    try:
        from ldap3 import MODIFY_REPLACE, SUBTREE
        conn = _conn_write()
        conn.search(AD_BASE_DN, f"(distinguishedName={dn})",
                    search_scope=SUBTREE, attributes=["userAccountControl"])
        if not conn.entries:
            return {"success": False, "error": "User not found"}
        uac = int(_str(conn.entries[0].userAccountControl) or "512")
        uac = (uac & ~2) if enabled else (uac | 2)
        ok = conn.modify(dn, {"userAccountControl": [(MODIFY_REPLACE, uac)]})
        err = conn.result.get("description", "") if not ok else ""
        conn.unbind()
        return {"success": ok, "error": err}
    except Exception as ex:
        return {"success": False, "error": str(ex)}


def ad_reset_password(dn: str, new_password: str) -> dict:
    try:
        # AD requires SSL (port 636) for password reset operations
        try:
            conn = _conn_ssl()
            ok = conn.extend.microsoft.modify_password(dn, new_password=new_password)
            err = conn.result.get("description", "") if not ok else ""
            conn.unbind()
        except Exception as ssl_ex:
            log.warning("SSL password reset failed (%s), trying unicodePwd fallback", ssl_ex)
            from ldap3 import MODIFY_REPLACE
            pw_encoded = ('"' + new_password + '"').encode('utf-16-le')
            conn = _conn_write()
            ok = conn.modify(dn, {"unicodePwd": [(MODIFY_REPLACE, [pw_encoded])]})
            err = conn.result.get("description", "") if not ok else ""
            conn.unbind()
        return {"success": ok, "error": err}
    except Exception as ex:
        return {"success": False, "error": str(ex)}


def ad_unlock_user(dn: str) -> dict:
    try:
        from ldap3 import MODIFY_REPLACE
        conn = _conn_write()
        ok = conn.modify(dn, {"lockoutTime": [(MODIFY_REPLACE, 0)]})
        err = conn.result.get("description", "") if not ok else ""
        conn.unbind()
        return {"success": ok, "error": err}
    except Exception as ex:
        return {"success": False, "error": str(ex)}


def ad_delete_user(dn: str) -> dict:
    try:
        conn = _conn_write()
        ok = conn.delete(dn)
        err = conn.result.get("description", "") if not ok else ""
        conn.unbind()
        return {"success": ok, "error": err}
    except Exception as ex:
        return {"success": False, "error": str(ex)}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  AD GROUP FUNCTIONS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def ad_list_groups(search: str = "") -> dict:
    try:
        from ldap3 import SUBTREE
        conn = _conn()
        sf = (f"(&(objectClass=group)(|(cn=*{search}*)(sAMAccountName=*{search}*)))"
              if search else "(objectClass=group)")
        conn.search(
            AD_BASE_DN, sf, search_scope=SUBTREE,
            attributes=["cn", "sAMAccountName", "description", "member",
                        "distinguishedName", "whenCreated", "groupType"]
        )
        groups = []
        for e in conn.entries:
            members = []
            if e.member:
                raw = e.member.values if hasattr(e.member, "values") else []
                members = [_str(m).split(",")[0].replace("CN=", "") for m in raw]
            groups.append({
                "name":         _str(e.cn),
                "sam":          _str(e.sAMAccountName),
                "description":  _str(e.description),
                "dn":           _str(e.distinguishedName),
                "member_count": len(members),
                "members":      members,
                "created":      _str(e.whenCreated),
            })
        conn.unbind()
        return {"groups": sorted(groups, key=lambda x: x["name"].lower())}
    except Exception as ex:
        return {"groups": [], "error": str(ex)}


def ad_create_group(name: str, description: str = "", ou_dn: str = None) -> dict:
    try:
        conn = _conn_write()
        ou = ou_dn or f"CN=Users,{AD_BASE_DN}"
        dn = f"CN={name},{ou}"
        ok = conn.add(dn, ["top", "group"],
                      {"sAMAccountName": name, "description": description})
        err = conn.result.get("description", "") if not ok else ""
        conn.unbind()
        return {"success": ok, "dn": dn, "error": err}
    except Exception as ex:
        return {"success": False, "error": str(ex)}


def ad_group_member(group_dn: str, user_dn: str, add: bool = True) -> dict:
    try:
        from ldap3 import MODIFY_ADD, MODIFY_DELETE
        conn = _conn_write()
        op = MODIFY_ADD if add else MODIFY_DELETE
        ok = conn.modify(group_dn, {"member": [(op, user_dn)]})
        err = conn.result.get("description", "") if not ok else ""
        conn.unbind()
        return {"success": ok, "error": err}
    except Exception as ex:
        return {"success": False, "error": str(ex)}


def ad_delete_group(dn: str) -> dict:
    try:
        conn = _conn_write()
        ok = conn.delete(dn)
        err = conn.result.get("description", "") if not ok else ""
        conn.unbind()
        return {"success": ok, "error": err}
    except Exception as ex:
        return {"success": False, "error": str(ex)}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  AD OU & COMPUTER FUNCTIONS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def ad_list_ous() -> dict:
    try:
        from ldap3 import SUBTREE
        conn = _conn()
        conn.search(AD_BASE_DN, "(objectClass=organizationalUnit)",
                    search_scope=SUBTREE,
                    attributes=["ou", "distinguishedName", "description"])
        ous = [{"name": _str(e.ou), "dn": _str(e.distinguishedName),
                "description": _str(e.description)}
               for e in conn.entries]
        conn.unbind()
        return {"ous": sorted(ous, key=lambda x: x["dn"])}
    except Exception as ex:
        return {"ous": [], "error": str(ex)}


def ad_list_computers(search: str = "") -> dict:
    try:
        from ldap3 import SUBTREE
        conn = _conn()
        sf = (f"(&(objectClass=computer)(cn=*{search}*))" if search
              else "(objectClass=computer)")
        conn.search(AD_BASE_DN, sf, search_scope=SUBTREE,
                    attributes=["cn", "dNSHostName", "operatingSystem",
                                "userAccountControl", "distinguishedName",
                                "whenCreated", "operatingSystemVersion"])
        computers = []
        for e in conn.entries:
            uac = int(_str(e.userAccountControl) or "4096")
            computers.append({
                "name":       _str(e.cn),
                "dns":        _str(e.dNSHostName),
                "os":         _str(e.operatingSystem),
                "os_version": _str(e.operatingSystemVersion),
                "dn":         _str(e.distinguishedName),
                "enabled":    not bool(uac & 2),
                "created":    _str(e.whenCreated),
            })
        conn.unbind()
        return {"computers": sorted(computers, key=lambda x: x["name"].lower())}
    except Exception as ex:
        return {"computers": [], "error": str(ex)}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  DNS FUNCTIONS â€” via LDAP3 (AD-integrated DNS, no WinRM required)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
import struct
import socket as _socket

# DNS record type number â†” name
_RTYPE = {1:"A", 28:"AAAA", 5:"CNAME", 12:"PTR", 15:"MX",
          2:"NS", 6:"SOA", 16:"TXT", 33:"SRV"}
_RTYPE_REV = {v: k for k, v in _RTYPE.items()}

_SKIP_ZONES = {"RootDNSServers", "..TrustAnchors"}

# All AD DNS partitions — every one is scanned so no zone is missed
_DNS_ROOTS = [
    "CN=MicrosoftDNS,DC=DomainDnsZones,{base}",
    "CN=MicrosoftDNS,DC=ForestDnsZones,{base}",
    "CN=MicrosoftDNS,CN=System,{base}",
]


def _all_dns_conns(write: bool = False):
    """Yield (root_dn, conn) for every partition that actually contains zones."""
    from ldap3 import SUBTREE
    conn = _conn_write() if write else _conn()
    found = []
    for tpl in _DNS_ROOTS:
        root = tpl.format(base=AD_BASE_DN)
        try:
            conn.search(root, "(objectClass=dnsZone)", search_scope=SUBTREE,
                        attributes=["dc"], size_limit=1)
            if conn.entries:
                found.append(root)
        except Exception:
            pass
    return found, conn


def _dns_search_root(write: bool = False) -> tuple[str, object]:
    """Return (partition_dn, conn) for the primary partition (DomainDnsZones)."""
    from ldap3 import SUBTREE
    conn = _conn_write() if write else _conn()
    primary = _DNS_ROOTS[0].format(base=AD_BASE_DN)
    for tpl in _DNS_ROOTS:
        root = tpl.format(base=AD_BASE_DN)
        conn.search(root, "(objectClass=dnsZone)", search_scope=SUBTREE,
                    attributes=["dc"], size_limit=1)
        if conn.entries:
            return root, conn
    return primary, conn


def _parse_dns_name(data: bytes, offset: int = 0) -> str:
    """Parse MS-DNSP DNS_COUNT_NAME from `data` starting at `offset`.

    MS-DNSP DNS_COUNT_NAME layout (CNAME/PTR/NS at data[0]):
      [cBytes: 1 byte]  – total byte length of following encoded name
      [cLabels: 1 byte] – number of labels  
      [labelLen][label] ... (standard DNS wire labels)
      [0x00] null terminator

    Callers pass `offset` pointing to the cBytes byte.
    This function skips cBytes + cLabels and parses the wire labels.
    """
    if not data or offset + 1 >= len(data):
        return ""
    # skip cBytes and cLabels
    offset += 2
    labels, itr = [], 0
    while offset < len(data) and itr < 128:
        length = data[offset]; offset += 1
        if length == 0:
            break
        labels.append(data[offset:offset + length].decode("utf-8", errors="replace"))
        offset += length; itr += 1
    return ".".join(labels)



def _encode_dns_name(name: str) -> bytes:
    out = b""
    for lbl in name.rstrip(".").split("."):
        enc = lbl.encode("utf-8")
        out += bytes([len(enc)]) + enc
    return out + b"\x00"


def _build_record_blob(rtype_id: int, data_bytes: bytes, ttl: int = 3600) -> bytes:
    """Construct a dnsRecord attribute blob (MS-DNSP wire format)."""
    flags = (5) | (0xF0 << 8)   # version=5, rank=0xF0 (zone record)
    hdr = (struct.pack("<H", len(data_bytes))   # DataLength LE
         + struct.pack("<H", rtype_id)           # Type LE
         + struct.pack("<I", flags)              # dwFlags
         + struct.pack("<I", 0)                  # dwSerial
         + struct.pack(">I", ttl)                # TTL big-endian
         + struct.pack("<I", 0)                  # dwReserved
         + struct.pack("<I", 0))                 # dwTimeStamp (0 = static)
    return hdr + data_bytes


def _parse_record_blob(raw: bytes) -> dict | None:
    """Parse one dnsRecord blob â†’ {"type":str,"data":str,"ttl":int} or None."""
    if not raw or len(raw) < 24:
        return None
    try:
        dlen     = struct.unpack_from("<H", raw, 0)[0]
        rtype_id = struct.unpack_from("<H", raw, 2)[0]
        ttl      = struct.unpack_from(">I", raw, 12)[0]
        data     = raw[24: 24 + dlen]
        rname    = _RTYPE.get(rtype_id, f"TYPE{rtype_id}")

        if rtype_id == 1:      # A
            if len(data) < 4: return None
            rdata = _socket.inet_ntoa(data[:4])
        elif rtype_id == 28:   # AAAA
            if len(data) < 16: return None
            rdata = _socket.inet_ntop(_socket.AF_INET6, data[:16])
        elif rtype_id in (5, 12, 2):   # CNAME, PTR, NS
            # MS-DNSP DNS_COUNT_NAME: [cBytes][cLabels][labels...][0x00]
            rdata = _parse_dns_name(data, 0)
        elif rtype_id == 15:   # MX
            # MS-DNSP MX: [pref: 2 bytes][cBytes: 1][cLabels: 1][wire name]
            if len(data) < 4: return None
            pref  = struct.unpack_from(">H", data, 0)[0]
            rdata = f"{pref} {_parse_dns_name(data, 2)}"
        elif rtype_id == 16:   # TXT
            rdata = data[1: 1 + data[0]].decode("utf-8", errors="replace") if data else ""
        elif rtype_id == 6:    # SOA â€” skip (clutters view)
            return None
        elif rtype_id == 33:   # SRV
            # MS-DNSP SRV: [priority 2][weight 2][port 2][cBytes 1][cLabels 1][wire name]
            if len(data) < 8: return None
            pri, w, port = struct.unpack_from(">HHH", data, 0)
            tgt = _parse_dns_name(data, 6)   # skip 6 bytes header, then cBytes+cLabels auto-skipped
            rdata = f"{pri} {w} {port} {tgt}"
        else:
            rdata = data.hex()

        return {"type": rname, "data": rdata, "ttl": ttl}
    except Exception:
        return None


# â”€â”€ Public DNS API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def dns_list_zones() -> dict:
    """Return every DNS zone from ALL AD-integrated partitions (Domain, Forest, System)."""
    try:
        from ldap3 import SUBTREE
        conn = _conn()
        zones = []
        seen = set()
        for tpl in _DNS_ROOTS:
            root = tpl.format(base=AD_BASE_DN)
            try:
                conn.search(root, "(objectClass=dnsZone)",
                            search_scope=SUBTREE,
                            attributes=["dc", "distinguishedName"],
                            size_limit=0)
                for e in conn.entries:
                    name = _str(e.dc)
                    if not name or name in _SKIP_ZONES or name in seen:
                        continue
                    seen.add(name)
                    zones.append({
                        "name":         name,
                        "dn":           _str(e.distinguishedName),
                        "partition_dn": root,
                        "type":         "Primary",
                        "ds_integrated": True,
                        "is_reverse":   "in-addr.arpa" in name or "ip6.arpa" in name,
                    })
            except Exception as ex:
                log.warning("dns_list_zones partition %s: %s", root, ex)
        conn.unbind()
        return {"zones": sorted(zones, key=lambda x: (x["is_reverse"], x["name"]))}
    except Exception as ex:
        log.error("dns_list_zones: %s", ex)
        return {"zones": [], "error": str(ex)}


def _zone_partition(zone: str, conn) -> str:
    """Return the partition_dn that contains the given zone, checking all partitions."""
    from ldap3 import SUBTREE
    for tpl in _DNS_ROOTS:
        root = tpl.format(base=AD_BASE_DN)
        try:
            conn.search(root, f"(&(objectClass=dnsZone)(dc={zone}))",
                        search_scope=SUBTREE, attributes=["dc"], size_limit=1)
            if conn.entries:
                return root
        except Exception:
            pass
    # Default fallback
    return _DNS_ROOTS[0].format(base=AD_BASE_DN)


def _dns_query_all_records(zone: str) -> list:
    """
    Use dnspython to enumerate ALL records actually served by the DNS server.
    This catches records stored in local zone files that never replicated to LDAP/AD.
    Results are cached for 5 minutes to avoid slow repeated scans.
    """
    import time as _time

    # ── In-memory cache (zone -> (timestamp, records)) ──
    cache = _dns_query_all_records._cache
    if zone in cache:
        ts, cached = cache[zone]
        if _time.time() - ts < 300:   # 5-minute TTL
            return cached

    try:
        import dns.resolver as _dres
        import dns.reversename as _drev
        import concurrent.futures as _cf
        import re as _re

        resolver = _dres.Resolver()
        resolver.nameservers = [AD_SERVER]
        resolver.timeout = 1
        resolver.lifetime = 2

        records = []
        seen = set()  # (hostname, type, data)

        def _add(hostname, rtype, data, ttl):
            key = (hostname.lower(), rtype, str(data))
            if key not in seen:
                seen.add(key)
                records.append({"hostname": hostname, "type": rtype,
                                 "data": str(data), "ttl": str(ttl)})

        def _forward_lookups(hostname: str):
            """Query A, AAAA, CNAME, MX, TXT, SRV for a hostname in this zone."""
            fqdn = hostname if hostname.endswith(".") else f"{hostname}.{zone}."
            results = []
            for qtype in ("A", "AAAA", "CNAME", "MX", "TXT", "NS"):
                try:
                    ans = resolver.resolve(fqdn, qtype)
                    for rd in ans:
                        if qtype == "MX":
                            results.append((hostname, qtype, f"{rd.preference} {rd.exchange}", ans.ttl))
                        elif qtype == "TXT":
                            results.append((hostname, qtype, " ".join(s.decode() for s in rd.strings), ans.ttl))
                        else:
                            results.append((hostname, qtype, str(rd), ans.ttl))
                except Exception:
                    pass
            return results

        def _ptr_lookup(ip: str):
            try:
                rev = _drev.from_address(ip)
                ans = resolver.resolve(rev, "PTR")
                host = str(list(ans)[0]).rstrip(".")
                # Strip zone suffix if present
                short = host.replace("." + zone, "") if host.endswith("." + zone) else host
                return (ip, short, int(ans.ttl))
            except Exception:
                return None

        is_reverse = "in-addr.arpa" in zone or "ip6.arpa" in zone

        if not is_reverse:
            # ── Forward zone ──────────────────────────────────────────────────
            # Step 1: Scan known active subnets via reverse PTR to discover hostnames.
            # Only scan subnets confirmed to have records (reduces scan time drastically).
            ACTIVE_17 = [3, 64, 65, 66, 70, 71, 73, 74, 77, 80, 81, 83, 85, 86, 90, 92, 101, 114, 168, 198]
            ACTIVE_16 = [4, 6]
            ips = [f"172.17.{t}.{h}" for t in ACTIVE_17 for h in range(1, 255)]
            ips += [f"172.16.{t}.{h}" for t in ACTIVE_16 for h in range(1, 255)]

            found_hosts = {}  # ip -> (short_hostname, ttl)
            with _cf.ThreadPoolExecutor(max_workers=200) as ex:
                for res in ex.map(_ptr_lookup, ips):
                    if res:
                        ip, short, ttl = res
                        found_hosts[ip] = (short, ttl)
                        # Record the PTR → A mapping
                        _add(short, "A", ip, ttl)

            # Step 2: Forward lookups for all discovered hostnames + any unique ones
            unique_hosts = set(h for h, _ in found_hosts.values())
            with _cf.ThreadPoolExecutor(max_workers=100) as ex:
                for fwd_list in ex.map(_forward_lookups, unique_hosts):
                    for (hn, qt, dat, ttl) in fwd_list:
                        if qt != "A":  # A records already added from PTR
                            _add(hn, qt, dat, ttl)

            # Step 3: Also query well-known zone-level records
            for qtype in ("SOA", "NS", "MX", "TXT"):
                try:
                    ans = resolver.resolve(zone + ".", qtype)
                    for rd in ans:
                        if qtype == "MX":
                            _add("@", qtype, f"{rd.preference} {rd.exchange}", ans.ttl)
                        elif qtype == "TXT":
                            _add("@", qtype, " ".join(s.decode() for s in rd.strings), ans.ttl)
                        elif qtype == "SOA":
                            _add("@", qtype, f"{rd.mname} {rd.rname} {rd.serial}", ans.ttl)
                        else:
                            _add("@", qtype, str(rd), ans.ttl)
                except Exception:
                    pass

        else:
            # ── Reverse zone ──────────────────────────────────────────────────
            # Parse the zone name to determine IP range, e.g. "70.17.172.in-addr.arpa"
            m = _re.match(r'^([\d.]+)\.in-addr\.arpa$', zone)
            if m:
                parts = m.group(1).split(".")[::-1]  # reverse: e.g. ["172","17","70"]
                if len(parts) == 3:
                    prefix = ".".join(parts)
                    ips_rev = [f"{prefix}.{i}" for i in range(1, 255)]
                elif len(parts) == 2:
                    third_start = int(parts[-1]) if parts else 0
                    ips_rev = [f"{'.'.join(parts)}.{t}.{h}" for t in range(0, 256) for h in range(1, 255)]
                else:
                    ips_rev = []
                with _cf.ThreadPoolExecutor(max_workers=100) as ex:
                    for res in ex.map(_ptr_lookup, ips_rev if len(parts) == 3 else []):
                        if res:
                            ip, short, ttl = res
                            # For reverse zone, hostname is the last octet
                            last_octet = ip.split(".")[-1]
                            _add(last_octet, "PTR", short + "." + zone.replace("in-addr.arpa", "").rstrip("."), ttl)

        cache[zone] = (_time.time(), records)
        return records

    except Exception as ex:
        log.warning("_dns_query_all_records(%s): %s", zone, ex)
        return []


_dns_query_all_records._cache = {}


def dns_list_records(zone: str) -> dict:
    """
    Return ALL records for a zone using a hybrid approach:
    1. Direct DNS queries (dnspython) — catches records in local zone files
    2. LDAP/AD — catches AD-replicated records and metadata
    Results are merged and deduplicated.
    """
    try:
        from ldap3 import SUBTREE

        # ── Source 1: Direct DNS queries (primary — gets everything the server serves) ──
        dns_records = _dns_query_all_records(zone)

        # ── Source 2: LDAP/AD records (may have additional metadata / types) ──
        ldap_records = []
        try:
            conn = _conn()
            root = _zone_partition(zone, conn)
            zone_dn = f"DC={zone},{root}"
            conn.search(zone_dn, "(objectClass=dnsNode)",
                        search_scope=SUBTREE,
                        attributes=["dc", "dnsRecord"],
                        size_limit=0, paged_size=1000)
            all_entries = list(conn.entries)
            # Collect remaining pages
            cookie = conn.result.get("controls", {}).get(
                "1.2.840.113556.1.4.319", {}).get("value", {}).get("cookie", "")
            while cookie:
                conn.search(zone_dn, "(objectClass=dnsNode)",
                            search_scope=SUBTREE,
                            attributes=["dc", "dnsRecord"],
                            size_limit=0, paged_size=1000, paged_cookie=cookie)
                all_entries.extend(conn.entries)
                cookie = conn.result.get("controls", {}).get(
                    "1.2.840.113556.1.4.319", {}).get("value", {}).get("cookie", "")
            conn.unbind()

            for e in all_entries:
                hostname = _str(e.dc)
                raws = list(e.dnsRecord.values) if hasattr(e.dnsRecord, "values") else []
                if not raws and e.dnsRecord.value:
                    raws = [e.dnsRecord.value]
                for raw in raws:
                    parsed = _parse_record_blob(raw)
                    if parsed:
                        ldap_records.append({"hostname": hostname, **parsed,
                                             "ttl": str(parsed["ttl"])})
        except Exception as ex:
            log.warning("dns_list_records LDAP fallback: %s", ex)

        # ── Merge: start with DNS query results, add any LDAP-only records ──
        seen = set()
        records = []
        for r in dns_records:
            key = (r["hostname"].lower(), r["type"], str(r["data"]))
            if key not in seen:
                seen.add(key)
                records.append(r)
        for r in ldap_records:
            key = (r["hostname"].lower(), r["type"], str(r["data"]))
            if key not in seen:
                seen.add(key)
                records.append(r)

        records.sort(key=lambda x: (x["hostname"].lower(), x["type"]))
        return {"records": records}
    except Exception as ex:
        log.error("dns_list_records: %s", ex)
        return {"records": [], "error": str(ex)}


def dns_add_record(zone: str, hostname: str, rtype: str,
                   data: str, ttl: int = 3600) -> dict:
    rtype = rtype.upper()
    rtype_id = _RTYPE_REV.get(rtype)
    if rtype_id is None:
        return {"success": False, "error": f"Unsupported record type: {rtype}"}
    try:
        # Build the record data bytes
        if rtype == "A":
            data_bytes = _socket.inet_aton(data.strip())
        elif rtype == "AAAA":
            data_bytes = _socket.inet_pton(_socket.AF_INET6, data.strip())
        elif rtype in ("CNAME", "PTR", "NS"):
            wire = _encode_dns_name(data.strip())
            label_count = data.strip().rstrip(".").count(".") + 1
            # MS-DNSP DNS_COUNT_NAME: [cBytes: total bytes of encoded name][cLabels][wire...]
            data_bytes = bytes([len(wire) + 1]) + bytes([label_count]) + wire
        elif rtype == "MX":
            parts = data.strip().split(None, 1)
            pref = int(parts[0]) if len(parts) == 2 else 10
            mx   = parts[1] if len(parts) == 2 else parts[0]
            wire = _encode_dns_name(mx)
            label_count = mx.rstrip(".").count(".") + 1
            # MS-DNSP MX: [pref][cBytes][cLabels][wire name]
            data_bytes = struct.pack(">H", pref) + bytes([len(wire) + 1]) + bytes([label_count]) + wire
        elif rtype == "TXT":
            enc = data.encode("utf-8")[:255]
            data_bytes = bytes([len(enc)]) + enc
        else:
            return {"success": False, "error": f"Unsupported type: {rtype}"}

        blob = _build_record_blob(rtype_id, data_bytes, ttl)

        from ldap3 import SUBTREE, MODIFY_ADD, MODIFY_REPLACE
        conn = _conn_write()
        root = _zone_partition(zone, conn)
        zone_dn = f"DC={zone},{root}"
        node_dn = f"DC={hostname},{zone_dn}"

        # Check if node already exists
        conn.search(zone_dn, f"(dc={hostname})", search_scope=SUBTREE,
                    attributes=["dnsRecord"], size_limit=0)
        if conn.entries:
            # Add to existing node
            ok = conn.modify(node_dn, {"dnsRecord": [(MODIFY_ADD, [blob])]})
        else:
            # Create new dnsNode
            ok = conn.add(node_dn, ["top", "dnsNode"],
                          {"dnsRecord": [blob], "dc": hostname})
        err = conn.result.get("description", "") if not ok else ""
        conn.unbind()
        return {"success": ok, "error": err}
    except Exception as ex:
        return {"success": False, "error": str(ex)}


def dns_delete_record(zone: str, hostname: str, rtype: str, data: str = "") -> dict:
    """Delete all records of the given type for a hostname (or specific data match)."""
    try:
        from ldap3 import SUBTREE, MODIFY_DELETE, MODIFY_REPLACE
        conn = _conn_write()
        root = _zone_partition(zone, conn)
        zone_dn = f"DC={zone},{root}"
        node_dn = f"DC={hostname},{zone_dn}"
        conn.search(zone_dn, f"(dc={hostname})", search_scope=SUBTREE,
                    attributes=["dnsRecord"], size_limit=0)
        if not conn.entries:
            conn.unbind()
            return {"success": False, "error": "Record/node not found"}

        existing = conn.entries[0]
        raws = list(existing.dnsRecord.values) if hasattr(existing.dnsRecord, "values") else []
        if existing.dnsRecord.value and not raws:
            raws = [existing.dnsRecord.value]

        rtype_id = _RTYPE_REV.get(rtype.upper())
        # Filter out records matching the type (and data if provided)
        to_keep = []
        to_del  = []
        for raw in raws:
            p = _parse_record_blob(raw)
            if p and p["type"] == rtype.upper():
                if not data or p["data"] == data:
                    to_del.append(raw)
                    continue
            to_keep.append(raw)

        if not to_del:
            conn.unbind()
            return {"success": False, "error": "No matching records found"}

        if to_keep:
            ok = conn.modify(node_dn, {"dnsRecord": [(MODIFY_REPLACE, to_keep)]})
        else:
            # No records left â€” delete the node entirely
            ok = conn.delete(node_dn)
        err = conn.result.get("description", "") if not ok else ""
        conn.unbind()
        return {"success": ok, "error": err}
    except Exception as ex:
        return {"success": False, "error": str(ex)}


def dns_flush_cache() -> dict:
    """Flush the DNS server cache via LDAP by clearing the cache partition node."""
    # Note: true cache flush requires WinRM/dnscmd. Report not supported via LDAP.
    return {"success": False,
            "error": "DNS cache flush requires direct server access (WinRM not available). "
                     "Please run 'Clear-DnsServerCache -Force' on the DNS server directly."}


# â”€ end of ad_dns_client.py â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_LEGACY_WINRM_REMOVED = True   # placeholder so nothing follows the new functions

