"""
auth.py — Active Directory / LDAP authentication for CaaS Dashboard
Supports:
  - AD login via LDAP bind (172.17.65.134 / sdxtest.local)
  - Role resolution from AD group membership
  - Local admin fallback if AD unreachable
"""
import os, logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")
log = logging.getLogger("caas.auth")

# ── Config from .env ──────────────────────────────────────────────────────────
AD_SERVER      = os.getenv("AD_SERVER",      "172.17.65.134")
AD_DOMAIN      = os.getenv("AD_DOMAIN",      "sdxtest.local")
AD_BIND_USER   = os.getenv("AD_BIND_USER",   "caas@sdxtest.local")
AD_BIND_PASS   = os.getenv("AD_BIND_PASS",   "Wipro@123")
AD_BASE_DN     = os.getenv("AD_BASE_DN",     "DC=sdxtest,DC=local")
AD_PORT        = int(os.getenv("AD_PORT",    "389"))
AD_USE_TLS     = os.getenv("AD_USE_TLS",     "false").lower() == "true"

# AD group → role mapping
AD_GROUP_ADMIN     = os.getenv("AD_GROUP_ADMIN",     "CaaS-Admins")
AD_GROUP_OPERATOR  = os.getenv("AD_GROUP_OPERATOR",  "CaaS-Operators")
AD_GROUP_VIEWER    = os.getenv("AD_GROUP_VIEWER",    "CaaS-Viewers")
AD_GROUP_REQUESTER = os.getenv("AD_GROUP_REQUESTER", "CaaS-Requesters")

# Local fallback admin
LOCAL_ADMIN_USER = os.getenv("DASHBOARD_USER",     "admin")
LOCAL_ADMIN_PASS = os.getenv("DASHBOARD_PASSWORD", "caas@2024")

# ── LDAP helpers ──────────────────────────────────────────────────────────────
def _ldap_conn(user_dn: str = None, password: str = None):
    """Return an ldap3 Connection. Uses bind user if no creds given."""
    try:
        from ldap3 import Server, Connection, ALL, NTLM, SIMPLE, Tls
        import ssl as _ssl

        server = Server(AD_SERVER, port=AD_PORT, get_info=ALL,
                        connect_timeout=5)

        u = user_dn or AD_BIND_USER
        p = password or AD_BIND_PASS

        conn = Connection(server, user=u, password=p,
                          authentication=SIMPLE, auto_bind=True)
        return conn
    except Exception as e:
        log.warning("LDAP connect failed: %s", e)
        return None

def _get_user_info(username: str) -> dict | None:
    """Fetch display name, email and group memberships for a user."""
    conn = _ldap_conn()
    if not conn:
        return None
    try:
        from ldap3 import ALL_ATTRIBUTES
        search_filter = f"(|(sAMAccountName={username})(userPrincipalName={username}@{AD_DOMAIN}))"
        conn.search(AD_BASE_DN, search_filter,
                    attributes=["displayName", "mail", "memberOf",
                                 "sAMAccountName", "userPrincipalName"])
        if not conn.entries:
            return None
        entry = conn.entries[0]
        member_of = [str(g) for g in (entry.memberOf.values if entry.memberOf else [])]
        return {
            "dn":           str(entry.entry_dn),
            "username":     str(entry.sAMAccountName) if entry.sAMAccountName else username,
            "display_name": str(entry.displayName)    if entry.displayName    else username,
            "email":        str(entry.mail)            if entry.mail           else "",
            "member_of":    member_of,
        }
    except Exception as e:
        log.warning("LDAP user lookup failed: %s", e)
        return None
    finally:
        try: conn.unbind()
        except: pass

def _resolve_role(member_of: list) -> str:
    """Map AD group membership to CaaS role. Higher roles take priority."""
    groups_lower = [g.lower() for g in member_of]

    def in_groups(grp_name):
        return any(grp_name.lower() in g for g in groups_lower)

    if in_groups(AD_GROUP_ADMIN):     return "admin"
    if in_groups(AD_GROUP_OPERATOR):  return "operator"
    if in_groups(AD_GROUP_REQUESTER): return "requester"
    if in_groups(AD_GROUP_VIEWER):    return "viewer"
    # Default: viewer if user exists in AD but no matching group
    return "viewer"

# ── Main auth function ────────────────────────────────────────────────────────
def authenticate(username: str, password: str) -> dict | None:
    """
    Returns user dict on success, None on failure.
    User dict: {username, display_name, email, role, auth_source}
    """
    # 1. Local admin fallback (always works even if AD down)
    if username == LOCAL_ADMIN_USER and password == LOCAL_ADMIN_PASS:
        log.info("Local admin login: %s", username)
        return {
            "username":     username,
            "display_name": "Local Admin",
            "email":        "",
            "role":         "admin",
            "auth_source":  "local",
        }

    # 1b. Local DB users (created by admin as AD-down fallback)
    try:
        from db import verify_local_user
        local = verify_local_user(username, password)
        if local:
            log.info("Local DB user login: %s", username)
            return {
                "username":     local["username"],
                "display_name": local.get("display_name") or username,
                "email":        local.get("email") or "",
                "role":         local["role"],
                "auth_source":  "local",
            }
    except Exception as e:
        log.warning("Local DB user check failed: %s", e)

    # 2. Try AD authentication
    try:
        from ldap3 import Server, Connection, SIMPLE, ALL
        # Try binding as the user directly
        upn = f"{username}@{AD_DOMAIN}" if "@" not in username else username
        server = Server(AD_SERVER, port=AD_PORT, get_info=ALL, connect_timeout=5)
        conn   = Connection(server, user=upn, password=password,
                            authentication=SIMPLE, auto_bind=True)
        conn.unbind()
        log.info("AD auth success: %s", username)
    except Exception as e:
        log.warning("AD auth failed for %s: %s", username, e)
        return None

    # 3. Fetch user info + groups using service account
    info = _get_user_info(username)
    if info:
        role = _resolve_role(info["member_of"])
        return {
            "username":     info["username"],
            "display_name": info["display_name"],
            "email":        info["email"],
            "role":         role,
            "auth_source":  "ad",
        }
    else:
        # Auth succeeded but couldn't fetch groups — give viewer role
        log.warning("Could not fetch groups for %s — defaulting to viewer", username)
        return {
            "username":     username,
            "display_name": username,
            "email":        "",
            "role":         "viewer",
            "auth_source":  "ad",
        }

def check_ad_connectivity() -> dict:
    """Health check for AD connectivity."""
    try:
        conn = _ldap_conn()
        if conn:
            conn.unbind()
            return {"status": "ok", "server": AD_SERVER, "domain": AD_DOMAIN}
        return {"status": "error", "message": "Could not connect"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def search_ad_users(query: str, limit: int = 15) -> list:
    """Search AD for users matching query string (by sAMAccountName or displayName)."""
    if not query or len(query.strip()) < 2:
        return []
    q = query.strip().replace("*", "").replace("(", "").replace(")", "")
    try:
        from ldap3 import ALL_ATTRIBUTES
        conn = _ldap_conn()
        if not conn:
            return []
        search_filter = (
            f"(&(objectClass=user)(objectCategory=person)"
            f"(|(sAMAccountName=*{q}*)(displayName=*{q}*)(givenName=*{q}*)(sn=*{q}*)))"
        )
        conn.search(
            AD_BASE_DN,
            search_filter,
            attributes=["sAMAccountName", "displayName", "mail", "memberOf"],
            size_limit=limit,
        )
        results = []
        for entry in conn.entries:
            try:
                username     = str(entry.sAMAccountName)
                display_name = str(entry.displayName)   if entry.displayName  else username
                email        = str(entry.mail)          if entry.mail         else ""
                # Determine CaaS group membership → role
                member_of = [str(g).lower() for g in (entry.memberOf if entry.memberOf else [])]
                if any("caas-admins" in g for g in member_of):
                    role = "admin"
                elif any("caas-operators" in g for g in member_of):
                    role = "operator"
                elif any("caas-requesters" in g for g in member_of):
                    role = "requester"
                else:
                    role = "viewer"
                results.append({
                    "username":     username,
                    "display_name": display_name,
                    "email":        email,
                    "role":         role,
                    "auth_source":  "ad",
                    "last_login":   None,
                })
            except Exception:
                continue
        conn.unbind()
        return results
    except Exception as e:
        print(f"[AD search] error: {e}")
        return []
