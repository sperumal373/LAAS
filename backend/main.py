from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv
import os, io, csv, threading, time, logging, json, secrets

load_dotenv(dotenv_path=Path(__file__).parent / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("caas")

from vmware_client import get_vcenter_list, get_all_data, get_alerts, vm_power_action, \
                          vm_snapshot, vm_delete_snapshot, vm_clone, vm_migrate, \
                          get_vc_resources, get_vc_templates, apply_guest_customization, \
                          provision_vm, vm_reconfig, vm_host_action, get_project_utilization, \
                          get_vm_topology, get_host_topology, get_volume_vcenter_mapping
from ipam_client import get_ipam_subnets, get_ipam_subnet_ips
import ipam_pg as _ipam_pg
from asset_client import parse_inventory, save_inventory, ping_many, power_action, DATA_DIR, DC_FILE, DR_FILE
from auth import authenticate, check_ad_connectivity, search_ad_users
from db   import (init_db, get_conn, upsert_user, get_user, list_users, update_user_role, delete_user,
                  create_local_user, upsert_ad_user,
                  create_vm_request, get_vm_request, list_vm_requests,
                  review_vm_request, update_request_status, audit, list_audit,
                  get_project_tag_owner_map, upsert_project_tag_owner)

# Ã¢â€â‚¬Ã¢â€â‚¬ Cache Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
_cache   = {"data":None,"alerts":[],"last_ok":None,"fetching":False,"error":None}
_lock    = threading.Lock()
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS","120"))

# Topology results cache (keyed by "vm|vcid|name" or "host|vcid|name", TTL 5 min)
_topo_cache: dict = {}
_TOPO_CACHE_TTL = int(os.getenv("TOPO_CACHE_TTL_SECONDS", "300"))

# Storage volume topology cache (keyed by "arr_id|volume", TTL 2 min)
_stor_topo_cache: dict = {}
_STOR_TOPO_TTL = int(os.getenv("STOR_TOPO_CACHE_TTL_SECONDS", "120"))

# Per-array live data cache (keyed by arr_id, TTL 3 min)
# Populated by /data endpoint, reused by /topology to avoid double API calls
_arr_data_cache: dict = {}
_ARR_DATA_TTL = int(os.getenv("ARR_DATA_CACHE_TTL_SECONDS", "180"))

def _get_topo_cached(kind: str, vcenter_id: str, name: str):
    key = f"{kind}|{vcenter_id}|{name}"
    entry = _topo_cache.get(key)
    if entry and (time.time() - entry["ts"]) < _TOPO_CACHE_TTL:
        return entry["data"]
    return None

def _set_topo_cached(kind: str, vcenter_id: str, name: str, data: dict):
    _topo_cache[f"{kind}|{vcenter_id}|{name}"] = {"data": data, "ts": time.time()}

def _do_fetch():
    with _lock:
        if _cache["fetching"]: return
        _cache["fetching"] = True
    try:
        data = get_all_data()
        alrt = get_alerts(data["hosts"], data["datastores"])
        with _lock:
            _cache["data"]=data; _cache["alerts"]=alrt
            _cache["last_ok"]=time.time(); _cache["error"]=None
        log.info("Cache refresh done Ã¢â‚¬â€ %d VMs", len(data.get("vms",[])))
    except Exception as e:
        with _lock: _cache["error"]=str(e)
        log.error("Cache refresh failed: %s", e)
    finally:
        with _lock: _cache["fetching"]=False

def _background_loop():
    _do_fetch()
    while True:
        time.sleep(CACHE_TTL); _do_fetch()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from openshift_client import init_openshift_db
    from baremetal_client  import init_baremetal_db
    from nutanix_client   import init_nutanix_db
    from ansible_client   import init_aap_db
    from storage_client   import init_storage_db
    from rubrik_client    import init_rubrik_db
    from cohesity_client   import init_cohesity_db
    from veeam_client      import init_veeam_db
    init_openshift_db()
    init_baremetal_db()
    init_nutanix_db()
    init_aap_db()
    init_storage_db()
    init_rubrik_db()
    init_cohesity_db()
    init_veeam_db()
    threading.Thread(target=_background_loop, daemon=True).start()
    # Pre-warm local LLM so first user query is instant
    def _warm_llm():
        try:
            if os.path.exists(_LLAMA_MODEL_PATH):
                _get_llm()
                log.info("LaaS AI model pre-warmed and ready.")
            else:
                log.warning(f"LaaS AI model not found at {_LLAMA_MODEL_PATH} Ã¢â‚¬â€ skipping pre-warm.")
        except Exception as _e:
            log.warning(f"LaaS AI pre-warm failed: {_e}")
    threading.Thread(target=_warm_llm, daemon=True).start()
    log.info("CaaS Dashboard v5.0 started")
    yield

# Ã¢â€â‚¬Ã¢â€â‚¬ App Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
app = FastAPI(title="CaaS Dashboard API", version="5.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
    allow_origins=[
        "https://localhost", "https://localhost:8443", "http://localhost", "http://localhost:8001",
        "https://127.0.0.1", "https://127.0.0.1:8443", "http://127.0.0.1:8001",
    ],
    allow_origin_regex=r"https?://(172\\.17\\..+|10\\..+|192\\.168\\..+|.*\\.sdxtest\\.local|.*\\.trycloudflare\\.com)(:\\d+)?",
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Ã¢â€â‚¬Ã¢â€â‚¬ Simple token store (in-memory, TTL 8h) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

# -- Rate limiter (brute-force protection) -------------------
_login_attempts = {}   # ip -> [timestamps]
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX    = 5

def _check_rate_limit(ip):
    now = time.time()
    attempts = [t for t in _login_attempts.get(ip, []) if now - t < RATE_LIMIT_WINDOW]
    if len(attempts) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again in 60s.")
    attempts.append(now)
    _login_attempts[ip] = attempts

_tokens: dict[str, dict] = {}  # token -> {username, role, display_name, exp}
TOKEN_TTL = 8 * 3600
security  = HTTPBearer(auto_error=False)

def _make_token(user: dict) -> str:
    tok = secrets.token_hex(32)
    _tokens[tok] = {**user, "exp": time.time() + TOKEN_TTL}
    return tok

def _resolve_token(tok: str) -> dict | None:
    t = _tokens.get(tok)
    if not t: return None
    if time.time() > t["exp"]:
        del _tokens[tok]; return None
    return t

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = _resolve_token(creds.credentials)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user

def require_role(*roles):
    def dep(u=Depends(get_current_user)):
        if u["role"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                detail=f"Role '{u['role']}' not allowed. Required: {roles}")
        return u
    return dep

def _get_cached():
    with _lock: data=_cache["data"]; last_ok=_cache["last_ok"]; fetching=_cache["fetching"]; err=_cache["error"]
    stale = last_ok is None or (time.time()-last_ok) > CACHE_TTL
    if stale and not fetching:
        threading.Thread(target=_do_fetch, daemon=True).start()
    return data, err

def _require_data():
    data, err = _get_cached()
    if data is None:
        for _ in range(150):
            time.sleep(2); data,err=_get_cached()
            if data: break
    if data is None:
        raise HTTPException(503, detail=f"Data loading… {err or ''}")
    return data

def _filter(rows, vcenter_id):
    if vcenter_id and vcenter_id != "all":
        return [r for r in rows if r.get("vcenter_id")==vcenter_id]
    return rows

def _csv(rows, fields, filename):
    buf=io.StringIO()
    w=csv.DictWriter(buf,fieldnames=fields,extrasaction="ignore")
    w.writeheader(); w.writerows(rows); buf.seek(0)
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition":f"attachment; filename={filename}"})

# Ã¢â€â‚¬Ã¢â€â‚¬ Auth endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class LoginReq(BaseModel):
    username: str
    password: str
    totp_code: str | None = None

@app.post("/api/auth/login")
def login(req: LoginReq, request: Request):
    ip = request.client.host if request.client else ""
    _check_rate_limit(ip)
    user = authenticate(req.username, req.password)
    if not user:
        audit(req.username, "LOGIN_FAIL", detail="Bad credentials", ip=ip, result="fail")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    # Upsert into DB
    db_user = upsert_user(user["username"], user["display_name"],
                          user.get("email",""), user["role"], user["auth_source"])
    # MFA check (optional - only if user enabled it)
    if user["username"] in _totp_secrets:
        if not req.totp_code:
            return {"mfa_required": True, "message": "Enter your 6-digit authenticator code"}
        if not _verify_totp(_totp_secrets[user["username"]], str(req.totp_code)):
            audit(user["username"], "MFA_FAIL", ip=ip, result="fail")
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
    tok = _make_token({**user, "user_id": db_user["id"] if db_user else 0})
    audit(user["username"], "LOGIN", role=user["role"], ip=ip)
    return {"token": tok, "user": {
        "username":     user["username"],
        "display_name": user["display_name"],
        "email":        user.get("email",""),
        "role":         user["role"],
        "auth_source":  user["auth_source"],
    }}

@app.post("/api/auth/logout")
def logout(u=Depends(get_current_user)):
    # Invalidate token
    for tok, data in list(_tokens.items()):
        if data.get("username") == u["username"]:
            del _tokens[tok]; break
    audit(u["username"], "LOGOUT", role=u["role"])
    return {"status": "ok"}

# -- MFA / TOTP (Google Authenticator) -----------------------
_totp_secrets = {}  # username -> base32 secret

def _init_mfa_table():
    with _get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS user_mfa (
            username TEXT PRIMARY KEY, totp_secret TEXT NOT NULL,
            enabled INTEGER DEFAULT 1, created_at TEXT DEFAULT (""" + '"' + "date" + "time('now')" + '"' + """))""")
        for row in conn.execute("SELECT username, totp_secret FROM user_mfa WHERE enabled=1"):
            _totp_secrets[row[0]] = row[1]

try:
    _init_mfa_table()
except Exception:
    pass

def _verify_totp(secret, code):
    import hmac, hashlib, struct, base64
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    for offset in [-1, 0, 1]:
        counter = struct.pack(">Q", int(time.time() / 30) + offset)
        h = hmac.new(key, counter, hashlib.sha1).digest()
        o = h[-1] & 0x0F
        otp = str(struct.unpack(">I", h[o:o+4])[0] & 0x7FFFFFFF).zfill(10)[-6:]
        if otp == code.strip():
            return True
    return False

@app.post("/api/auth/mfa/setup")
def mfa_setup(u=Depends(get_current_user)):
    import base64 as _b64, os as _os
    secret = _b64.b32encode(_os.urandom(20)).decode().rstrip("=")
    with _get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO user_mfa (username,totp_secret,enabled) VALUES(?,?,1)", (u["username"], secret))
    _totp_secrets[u["username"]] = secret
    uri = f"otpauth://totp/Veekshan:{u['username']}?secret={secret}&issuer=Veekshan&digits=6&period=30"
    audit(u["username"], "MFA_SETUP", role=u["role"])
    return {"secret": secret, "provisioning_uri": uri, "message": "Scan QR or enter secret in Google Authenticator"}

@app.post("/api/auth/mfa/disable")
def mfa_disable(u=Depends(require_role("admin"))):
    with _get_db() as conn:
        conn.execute("UPDATE user_mfa SET enabled=0 WHERE username=?", (u["username"],))
    _totp_secrets.pop(u["username"], None)
    audit(u["username"], "MFA_DISABLE", role=u["role"])
    return {"ok": True, "message": "MFA disabled"}

@app.get("/api/auth/mfa/status")
def mfa_status(u=Depends(get_current_user)):
    return {"enabled": u["username"] in _totp_secrets}


@app.get("/api/auth/me")
def me(u=Depends(get_current_user)):
    return u

@app.get("/api/auth/ad-status")
def ad_status(u=Depends(require_role("admin"))):
    return check_ad_connectivity()

# Ã¢â€â‚¬Ã¢â€â‚¬ Health Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/health")
def health():
    with _lock:
        last=_cache["last_ok"]; fetch=_cache["fetching"]; err=_cache["error"]
    return {"status":"ok","version":"5.0.0",
            "cache_age":round(time.time()-last,0) if last else None,
            "last_ok": round(last, 3) if last else None,
            "fetching":fetch,"error":err,"cache_ttl":CACHE_TTL}

@app.get("/api/data/version")
def data_version():
    """Lightweight no-auth endpoint Ã¢â‚¬â€ returns last cache refresh timestamp.
    Frontend polls this every 5s to detect when backend data is fresh."""
    with _lock: last=_cache["last_ok"]; fetch=_cache["fetching"]
    return {"last_ok": round(last, 3) if last else None, "fetching": fetch}

@app.get("/api/cache/status")
def cache_status(u=Depends(get_current_user)):
    with _lock: last=_cache["last_ok"]; fetch=_cache["fetching"]; err=_cache["error"]; data=_cache["data"]
    return {"last_refreshed":time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(last)) if last else None,
            "cache_age_seconds":round(time.time()-last,0) if last else None,
            "is_fetching":fetch,"error":err,
            "vms_cached":len(data["vms"]) if data else 0,
            "hosts_cached":len(data["hosts"]) if data else 0}

@app.post("/api/cache/refresh")
def cache_refresh(u=Depends(require_role("admin","operator"))):
    with _lock: already=_cache["fetching"]
    if not already: threading.Thread(target=_do_fetch,daemon=True).start()
    return {"status":"refresh started" if not already else "already refreshing"}

# Ã¢â€â‚¬Ã¢â€â‚¬ vCenters Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/vcenters")
def vcenters(u=Depends(get_current_user)):
    return {"vcenters": get_vcenter_list()}

# Ã¢â€â‚¬Ã¢â€â‚¬ VMware data Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
def _agg(summs):
    from functools import reduce
    def a(x,y):
        return {"vcenter_id":"all","vcenter_name":"All vCenters","vcenter_host":"all","status":"ok",
                "total_hosts":x["total_hosts"]+y["total_hosts"],
                "connected_hosts":x["connected_hosts"]+y["connected_hosts"],
                "total_vms":x["total_vms"]+y["total_vms"],
                "running_vms":x["running_vms"]+y["running_vms"],
                "stopped_vms":x["stopped_vms"]+y["stopped_vms"],
                "cpu":{"total_mhz":x["cpu"]["total_mhz"]+y["cpu"]["total_mhz"],
                       "used_mhz":x["cpu"]["used_mhz"]+y["cpu"]["used_mhz"],
                       "free_mhz":x["cpu"]["free_mhz"]+y["cpu"]["free_mhz"],"free_pct":0},
                "ram":{"total_gb":round(x["ram"]["total_gb"]+y["ram"]["total_gb"],1),
                       "used_gb":round(x["ram"]["used_gb"]+y["ram"]["used_gb"],1),
                       "free_gb":round(x["ram"]["free_gb"]+y["ram"]["free_gb"],1),"free_pct":0},
                "storage":{"total_gb":round(x["storage"]["total_gb"]+y["storage"]["total_gb"],1),
                           "free_gb":round(x["storage"]["free_gb"]+y["storage"]["free_gb"],1),
                           "used_gb":round(x["storage"]["used_gb"]+y["storage"]["used_gb"],1),"free_pct":0}}
    r=reduce(a,summs)
    for k,tf,ff in [("cpu","total_mhz","free_mhz"),("ram","total_gb","free_gb"),("storage","total_gb","free_gb")]:
        t=r[k][tf]; f=r[k][ff]; r[k]["free_pct"]=round((f/t)*100,1) if t else 0
    return r

@app.get("/api/vmware/summary")
def summary(vcenter_id:str=None, u=Depends(get_current_user)):
    data=_require_data(); summs=data["summaries"]
    if vcenter_id and vcenter_id!="all": summs=[s for s in summs if s["vcenter_id"]==vcenter_id]
    if not summs: raise HTTPException(404,"No data")
    return summs[0] if len(summs)==1 else _agg(summs)

@app.get("/api/vmware/vms")
def vms(vcenter_id:str=None, u=Depends(get_current_user)):
    rows=_filter(_require_data()["vms"],vcenter_id); return {"vms":rows,"count":len(rows)}

@app.get("/api/vmware/hosts")
def hosts(vcenter_id:str=None, u=Depends(get_current_user)):
    rows=_filter(_require_data()["hosts"],vcenter_id); return {"hosts":rows,"count":len(rows)}

@app.get("/api/vmware/datastores")
def datastores(vcenter_id:str=None, u=Depends(get_current_user)):
    rows=_filter(_require_data()["datastores"],vcenter_id); return {"datastores":rows,"count":len(rows)}

@app.get("/api/vmware/networks")
def networks(vcenter_id:str=None, u=Depends(get_current_user)):
    rows=_filter(_require_data()["networks"],vcenter_id); return {"networks":rows,"count":len(rows)}

@app.get("/api/vmware/snapshots")
def snapshots(vcenter_id:str=None, u=Depends(get_current_user)):
    rows=_filter(_require_data()["snapshots"],vcenter_id)
    try:
        snap_logs=list_audit(limit=10000)
        creator_map={}
        for al in snap_logs:
            if al.get("action")!="VM_SNAPSHOT": continue
            vm=al.get("target","")
            det=al.get("detail","")
            snap_name=""
            for part in det.split():
                if part.startswith("snap="):
                    snap_name=part[5:]; break
            key=vm+"::"+snap_name
            if key not in creator_map:
                creator_map[key]=al.get("username","")
        for r in rows:
            key=(r.get("vm_name") or "")+"::"+(r.get("snapshot_name") or "")
            r["created_by"]=r.get("created_by") or creator_map.get(key,"")
    except Exception:
        pass
    return {"snapshots":rows,"count":len(rows)}

@app.get("/api/vmware/topology/vm")
def vm_topology_ep(vcenter_id: str, vm_name: str, u=Depends(get_current_user)):
    cached = _get_topo_cached("vm", vcenter_id, vm_name)
    if cached is not None:
        return cached
    data = get_vm_topology(vcenter_id, vm_name)
    if "error" in data: raise HTTPException(404, data["error"])
    _set_topo_cached("vm", vcenter_id, vm_name, data)
    return data

@app.get("/api/vmware/topology/host")
def host_topology_ep(vcenter_id: str, host_name: str, u=Depends(get_current_user)):
    cached = _get_topo_cached("host", vcenter_id, host_name)
    if cached is not None:
        return cached
    data = get_host_topology(vcenter_id, host_name)
    if "error" in data: raise HTTPException(404, data["error"])
    _set_topo_cached("host", vcenter_id, host_name, data)
    return data

@app.get("/api/vmware/project-utilization")
def project_utilization(vcenter_id:str=None, u=Depends(get_current_user)):
    cached = _require_data()
    rows = cached["vms"]
    datastores = cached.get("datastores", [])
    scope = None if not vcenter_id or vcenter_id == "all" else vcenter_id
    scope_key = scope or "all"
    owner_map = get_project_tag_owner_map(scope_key)
    return get_project_utilization(rows, scope, owner_map, datastores)


class TagOwnerReq(BaseModel):
    tag: str
    owner_name: str = ""
    owner_email: str = ""
    vcenter_scope: str = "all"


@app.patch("/api/vmware/project-utilization/owner")
def update_project_tag_owner(req: TagOwnerReq, u=Depends(require_role("admin", "operator"))):
    tag = (req.tag or "").strip()
    if not tag:
        raise HTTPException(400, detail="tag is required")
    scope = (req.vcenter_scope or "all").strip() or "all"
    owner_name = (req.owner_name or "").strip()
    owner_email = (req.owner_email or "").strip()

    upsert_project_tag_owner(tag, scope, owner_name, owner_email, u.get("username", ""))
    audit(u["username"], "PROJECT_TAG_OWNER_UPDATE", target=tag,
          detail=f"scope={scope}; owner={owner_name}; email={owner_email}", role=u["role"], result="ok")
    return {"status": "ok", "tag": tag, "vcenter_scope": scope,
            "owner_name": owner_name, "owner_email": owner_email}

@app.get("/api/alerts")
def alerts(vcenter_id:str=None, u=Depends(get_current_user)):
    with _lock: rows=list(_cache["alerts"])
    if vcenter_id and vcenter_id!="all": rows=[r for r in rows if r.get("vcenter_id") in (vcenter_id,"all")]
    return {"alerts":rows,"count":len(rows)}

# Ã¢â€â‚¬Ã¢â€â‚¬ VM Actions Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class PowerReq(BaseModel):
    vcenter_id:str; vm_name:str; action:str

class SnapReq(BaseModel):
    vcenter_id:str; vm_name:str; snap_name:str
    description:str=""; memory:bool=False; quiesce:bool=False

class CloneReq(BaseModel):
    vcenter_id:str; vm_name:str; clone_name:str
    dest_host:str|None=None; dest_datastore:str|None=None; dest_vcenter_id:str|None=None; power_on:bool=False

class MigrateReq(BaseModel):
    vcenter_id:str; vm_name:str
    dest_host:str|None=None; dest_datastore:str|None=None; dest_vcenter_id:str|None=None

def _action_guard(u, allowed=("admin","operator")):
    if u["role"] not in allowed:
        raise HTTPException(403, detail="Insufficient permissions for VM actions")

@app.post("/api/vmware/power")
def vm_power(req:PowerReq, u=Depends(get_current_user)):
    _action_guard(u)
    if req.action not in ("start","stop","restart"):
        raise HTTPException(400, detail="action must be start|stop|restart")
    result = vm_power_action(req.vcenter_id, req.vm_name, req.action)
    audit(u["username"],"VM_POWER",target=req.vm_name,
          detail=f"action={req.action} vc={req.vcenter_id}",
          role=u["role"], result="ok" if result["success"] else "fail")
    if not result["success"]: raise HTTPException(500, detail=result["message"])
    threading.Thread(target=_do_fetch,daemon=True).start()
    return result

@app.post("/api/vmware/snapshot")
def create_snapshot(req:SnapReq, u=Depends(get_current_user)):
    _action_guard(u)
    result = vm_snapshot(req.vcenter_id,req.vm_name,req.snap_name,req.description,req.memory,req.quiesce)
    audit(u["username"],"VM_SNAPSHOT",target=req.vm_name,
          detail=f"snap={req.snap_name} vc={req.vcenter_id}",role=u["role"],
          result="ok" if result["success"] else "fail")
    if not result["success"]: raise HTTPException(500, detail=result["message"])
    return result

@app.post("/api/vmware/clone")
def clone_vm(req:CloneReq, u=Depends(get_current_user)):
    _action_guard(u)
    result = vm_clone(req.vcenter_id,req.vm_name,req.clone_name,
                      req.dest_host,req.dest_datastore,req.dest_vcenter_id,req.power_on)
    audit(u["username"],"VM_CLONE",target=req.vm_name,
          detail=f"clone={req.clone_name}",role=u["role"],result="ok" if result["success"] else "fail")
    if not result["success"]: raise HTTPException(500, detail=result["message"])
    threading.Thread(target=_do_fetch,daemon=True).start()
    return result

@app.post("/api/vmware/migrate")
def migrate_vm(req:MigrateReq, u=Depends(get_current_user)):
    _action_guard(u)
    result = vm_migrate(req.vcenter_id,req.vm_name,req.dest_host,req.dest_datastore,req.dest_vcenter_id)
    audit(u["username"],"VM_MIGRATE",target=req.vm_name,
          detail=f"dest_host={req.dest_host} dest_vc={req.dest_vcenter_id}",
          role=u["role"],result="ok" if result["success"] else "fail")
    if not result["success"]: raise HTTPException(500, detail=result["message"])
    threading.Thread(target=_do_fetch,daemon=True).start()
    return result

@app.get("/api/vmware/resources/{vcenter_id}")
def vc_resources(vcenter_id:str, u=Depends(get_current_user)):
    return get_vc_resources(vcenter_id)

@app.get("/api/vmware/templates/{vcenter_id}")
def vc_templates(vcenter_id:str, u=Depends(get_current_user)):
    return get_vc_templates(vcenter_id)

# Ã¢â€â‚¬Ã¢â€â‚¬ Delete Snapshot Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class SnapDeleteReq(BaseModel):
    vcenter_id:str; vm_name:str; snap_name:str

@app.post("/api/vmware/snapshot/delete")
def delete_snapshot_ep(req:SnapDeleteReq, u=Depends(get_current_user)):
    _action_guard(u)
    result = vm_delete_snapshot(req.vcenter_id, req.vm_name, req.snap_name)
    audit(u["username"],"VM_SNAPSHOT_DELETE",target=req.vm_name,
          detail=f"snap={req.snap_name}",role=u["role"],
          result="ok" if result["success"] else "fail")
    if not result["success"]: raise HTTPException(500, detail=result["message"])
    threading.Thread(target=_do_fetch,daemon=True).start()
    return result

# Ã¢â€â‚¬Ã¢â€â‚¬ VM Reconfig Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class ReconfigReq(BaseModel):
    vcenter_id:str; vm_name:str; cpu:int; ram_gb:int; disk_gb:int

@app.post("/api/vmware/reconfig")
def reconfig_vm_ep(req:ReconfigReq, u=Depends(get_current_user)):
    _action_guard(u)
    result = vm_reconfig(req.vcenter_id, req.vm_name, req.cpu, req.ram_gb, req.disk_gb)
    audit(u["username"],"VM_RECONFIG",target=req.vm_name,
          detail=f"cpu={req.cpu} ram={req.ram_gb}GB disk={req.disk_gb}GB",
          role=u["role"],result="ok" if result["success"] else "fail")
    if not result["success"]: raise HTTPException(500, detail=result["message"])
    threading.Thread(target=_do_fetch,daemon=True).start()
    return result

# Ã¢â€â‚¬Ã¢â€â‚¬ Bulk VM Power Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class BulkVMItem(BaseModel):
    vcenter_id:str; vm_name:str

class BulkPowerReq(BaseModel):
    vms: list[BulkVMItem]; action:str

@app.post("/api/vmware/bulk-power")
def bulk_power(req:BulkPowerReq, u=Depends(get_current_user)):
    _action_guard(u)
    if req.action not in ("start","stop","restart"):
        raise HTTPException(400, detail="action must be start|stop|restart")
    succeeded=0; failed=0; errors=[]
    for item in req.vms:
        r = vm_power_action(item.vcenter_id, item.vm_name, req.action)
        if r["success"]: succeeded+=1
        else: failed+=1; errors.append(f"{item.vm_name}: {r['message']}")
    audit(u["username"],"VM_BULK_POWER",
          detail=f"action={req.action} total={len(req.vms)} ok={succeeded} fail={failed}",
          role=u["role"],result="ok" if failed==0 else "fail")
    threading.Thread(target=_do_fetch,daemon=True).start()
    return {"succeeded":succeeded,"failed":failed,"errors":errors}

# Ã¢â€â‚¬Ã¢â€â‚¬ Host Actions Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class HostActionReq(BaseModel):
    vcenter_id:str; host_name:str; action:str

class BulkHostItem(BaseModel):
    vcenter_id:str; host_name:str

class BulkHostReq(BaseModel):
    hosts: list[BulkHostItem]; action:str

@app.post("/api/vmware/host-action")
def host_action_ep(req:HostActionReq, u=Depends(require_role("admin"))):
    if req.action not in ("reboot","shutdown","maintenance","exit_maintenance"):
        raise HTTPException(400, detail="Invalid host action")
    result = vm_host_action(req.vcenter_id, req.host_name, req.action)
    audit(u["username"],"HOST_ACTION",target=req.host_name,
          detail=f"action={req.action}",role=u["role"],
          result="ok" if result["success"] else "fail")
    if not result["success"]: raise HTTPException(500, detail=result["message"])
    threading.Thread(target=_do_fetch,daemon=True).start()
    return result

@app.post("/api/vmware/bulk-host-action")
def bulk_host_action_ep(req:BulkHostReq, u=Depends(require_role("admin"))):
    if req.action not in ("reboot","shutdown","maintenance","exit_maintenance"):
        raise HTTPException(400, detail="Invalid host action")
    succeeded=0; failed=0
    for item in req.hosts:
        r = vm_host_action(item.vcenter_id, item.host_name, req.action)
        if r["success"]: succeeded+=1
        else: failed+=1
    audit(u["username"],"HOST_BULK_ACTION",
          detail=f"action={req.action} total={len(req.hosts)} ok={succeeded} fail={failed}",
          role=u["role"],result="ok" if failed==0 else "fail")
    threading.Thread(target=_do_fetch,daemon=True).start()
    return {"succeeded":succeeded,"failed":failed}

# Ã¢â€â‚¬Ã¢â€â‚¬ VM Requests Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class VMRequestCreate(BaseModel):
    vcenter_id:  str
    vm_name:     str
    cpu:         int
    ram_gb:      int
    disk_gb:     int
    os_template: str = "custom"   # optional Ã¢â‚¬â€ admin can assign later
    host:        str = ""
    datastore:   str = ""
    network:     str = ""
    notes:       str = ""
    include_license: bool = False   # whether OS license cost is included
    license_type:    str  = ""     # "windows" | "rhel" | ""
    include_internet: bool = False  # whether internet access is required
    # IP / Guest Customization
    ip_mode:     str = "dhcp"     # dhcp | static
    ip_address:  str = ""
    subnet_mask: str = "255.255.255.0"
    gateway:     str = ""
    dns1:        str = ""
    dns2:        str = ""
    hostname:    str = ""
    domain:      str = ""

class VMRequestReview(BaseModel):
    decision:    str          # approved | declined
    admin_notes: str = ""
    overrides:   dict = {}    # optional resource modifications

@app.post("/api/requests")
def submit_request(body: VMRequestCreate, u=Depends(get_current_user)):
    data = body.dict(); data["requester"] = u["username"]
    req  = create_vm_request(data)
    audit(u["username"],"VM_REQUEST_SUBMIT",target=req["req_number"],
          detail=f"vm={body.vm_name} cpu={body.cpu} ram={body.ram_gb}GB",role=u["role"])
    return req

@app.get("/api/requests")
def get_requests(u=Depends(get_current_user)):
    # Admins/operators see all; requesters see only their own
    if u["role"] in ("admin","operator"):
        return {"requests": list_vm_requests()}
    return {"requests": list_vm_requests(requester=u["username"])}

@app.get("/api/requests/pending")
def get_pending(u=Depends(require_role("admin","operator"))):
    return {"requests": list_vm_requests(status="pending")}

@app.post("/api/requests/{req_number}/review")
def review_request(req_number:str, body:VMRequestReview, u=Depends(require_role("admin"))):
    if body.decision not in ("approved","declined"):
        raise HTTPException(400, detail="decision must be approved or declined")
    req = review_vm_request(req_number, u["username"], body.decision,
                            body.admin_notes, body.overrides)
    if not req: raise HTTPException(404, detail="Request not found")
    audit(u["username"],f"VM_REQUEST_{body.decision.upper()}",
          target=req_number,detail=body.admin_notes,role=u["role"])

    # Auto-provision if approved
    if body.decision == "approved":
        def _provision():
            update_request_status(req_number, "provisioning")
            platform = req.get("platform", "vmware")

            if platform == "nutanix":
                # Ã¢â€â‚¬Ã¢â€â‚¬ Nutanix provisioning path Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
                try:
                    pc_id = req.get("ntx_pc_id")
                    pc = get_prism_central(int(pc_id)) if pc_id else None
                    if not pc:
                        update_request_status(req_number, "failed")
                        audit(u["username"], "VM_PROVISIONED", target=req_number,
                              detail="Prism Central not found", role=u["role"], result="fail")
                        return
                    import json
                    raw_disks = req.get("ntx_disks") or "[]"
                    raw_nics  = req.get("ntx_nics")  or "[]"
                    disks = json.loads(raw_disks) if isinstance(raw_disks, str) else raw_disks
                    nics  = json.loads(raw_nics)  if isinstance(raw_nics,  str) else raw_nics
                    spec = {
                        "vm_name":           req["vm_name"],
                        "cluster_uuid":      req.get("ntx_cluster_uuid", ""),
                        "num_vcpus":         req.get("approved_cpu")    or req["cpu"],
                        "num_cores_per_vcpu":req.get("num_cores_per_vcpu", 1),
                        "memory_mib":        (req.get("approved_ram_gb") or req["ram_gb"]) * 1024,
                        "disks":             disks,
                        "nics":              nics,
                    }
                    result = provision_nutanix_vm(pc, spec)
                    new_status = "done" if result["success"] else "failed"
                    update_request_status(req_number, new_status)
                    audit(u["username"], "NTX_VM_PROVISIONED", target=req_number,
                          detail=result["message"], role=u["role"],
                          result="ok" if result["success"] else "fail")
                except Exception as ex:
                    update_request_status(req_number, "failed")
                    audit(u["username"], "NTX_VM_PROVISIONED", target=req_number,
                          detail=str(ex), role=u["role"], result="fail")
            else:
                # Use approved overrides if set, else original values
                prov_data = {
                    "vcenter_id": req["vcenter_id"],
                    "vm_name":    req["vm_name"],
                    "cpu":        req["approved_cpu"]     or req["cpu"],
                    "ram_gb":     req["approved_ram_gb"]  or req["ram_gb"],
                    "disk_gb":    req["approved_disk_gb"] or req["disk_gb"],
                    "os_template":req["os_template"] or "custom",
                    "host":       (req["approved_host"]    or req["host"])    or None,
                    "datastore":  (req["approved_ds"]      or req["datastore"]) or None,
                    "network":    (req["approved_network"] or req["network"])  or None,
                }
                result = provision_vm(prov_data)
                if result["success"]:
                    # Apply guest customization if IP config was requested
                    ip_mode = req.get("ip_mode","dhcp")
                    has_ip  = ip_mode == "static" and req.get("ip_address")
                    has_dns = req.get("dns1")
                    if has_ip or has_dns or ip_mode == "static":
                        ip_config = {
                            "mode":        ip_mode,
                            "ip_address":  req.get("ip_address",""),
                            "subnet_mask": req.get("subnet_mask","255.255.255.0"),
                            "gateway":     req.get("gateway",""),
                            "dns1":        req.get("dns1",""),
                            "dns2":        req.get("dns2",""),
                            "hostname":    req.get("hostname","") or req["vm_name"],
                            "domain":      req.get("domain",""),
                        }
                        cust_result = apply_guest_customization(
                            req["vcenter_id"], req["vm_name"], ip_config)
                        log.info(f"[provision] customization: {cust_result}")
                        if not cust_result["success"]:
                            result["message"] += f" (IP customization warning: {cust_result['message']})"
                new_status = "done" if result["success"] else "failed"
                update_request_status(req_number, new_status)
                audit(u["username"],"VM_PROVISIONED",target=req_number,
                      detail=result["message"],role=u["role"],
                      result="ok" if result["success"] else "fail")
                _do_fetch()
        threading.Thread(target=_provision, daemon=True).start()

    return req

# Ã¢â€â‚¬Ã¢â€â‚¬ Users / Admin Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/users")
def get_users(u=Depends(require_role("admin"))):
    return {"users": list_users()}

@app.get("/api/users/search")
def search_users(q: str = "", current_user=Depends(require_role("admin"))):
    """Search AD directory for users matching query (2+ chars), merged with local DB."""
    if len(q.strip()) < 2:
        return {"users": []}
    # 1. Search AD live
    ad_results = search_ad_users(q.strip(), limit=15)
    # 2. Also filter local DB users
    all_local = list_users()
    ql = q.strip().lower()
    local_matches = [
        row for row in all_local
        if ql in (row.get("username") or "").lower()
        or ql in (row.get("display_name") or "").lower()
        or ql in (row.get("email") or "").lower()
    ]
    # 3. Merge: AD first (richer data), then local-only additions
    seen = {r["username"] for r in ad_results}
    for row in local_matches:
        if row["username"] not in seen:
            ad_results.append(row)
            seen.add(row["username"])
    return {"users": ad_results[:15]}

class RoleUpdate(BaseModel):
    role: str

@app.patch("/api/users/{username}/role")
def update_role(username:str, body:RoleUpdate, u=Depends(require_role("admin"))):
    if body.role not in ("admin","operator","viewer","requester"):
        raise HTTPException(400, detail="Invalid role")
    update_user_role(username, body.role)
    audit(u["username"],"USER_ROLE_UPDATE",target=username,
          detail=f"new_role={body.role}",role=u["role"])
    return {"status":"ok","username":username,"role":body.role}

@app.delete("/api/users/{username}")
def delete_user_ep(username: str, u=Depends(require_role("admin"))):
    if username == u["username"]:
        raise HTTPException(400, detail="You cannot delete your own user")
    if username == "admin":
        raise HTTPException(400, detail="Local fallback admin cannot be deleted")
    existing = get_user(username)
    if not existing:
        raise HTTPException(404, detail="User not found")
    ok = delete_user(username)
    if not ok:
        raise HTTPException(404, detail="User not found")
    audit(u["username"], "USER_DELETE", target=username,
          detail=f"auth_source={existing.get('auth_source','')}", role=u["role"])
    return {"status": "ok", "username": username}

class LocalUserCreate(BaseModel):
    username:     str
    display_name: str = ""
    email:        str = ""
    role:         str
    password:     str

@app.post("/api/users/local")
def create_local_user_ep(body: LocalUserCreate, u=Depends(require_role("admin"))):
    if body.role not in ("admin","operator","viewer","requester"):
        raise HTTPException(400, detail="Invalid role")
    if len(body.password) < 6:
        raise HTTPException(400, detail="Password must be at least 6 characters")
    if not body.username.strip():
        raise HTTPException(400, detail="Username required")
    existing = get_user(body.username.strip())
    if existing and existing.get("auth_source") == "ad":
        raise HTTPException(400, detail="Username already exists as an AD user")
    user = create_local_user(body.username.strip(), body.display_name.strip(),
                             body.email.strip(), body.role, body.password)
    audit(u["username"], "LOCAL_USER_CREATE", target=body.username.strip(),
          detail=f"role={body.role}", role=u["role"])
    return {"status": "ok", "user": user}

class ADUserAdd(BaseModel):
    username:     str
    display_name: str = ""
    email:        str = ""
    role:         str

@app.post("/api/users/ad")
def add_ad_user_ep(body: ADUserAdd, u=Depends(require_role("admin"))):
    if body.role not in ("admin","operator","viewer","requester"):
        raise HTTPException(400, detail="Invalid role")
    if not body.username.strip():
        raise HTTPException(400, detail="Username required")
    user = upsert_ad_user(body.username.strip(), body.display_name.strip(),
                          body.email.strip(), body.role)
    audit(u["username"], "USER_ROLE_UPDATE", target=body.username.strip(),
          detail=f"role={body.role}", role=u["role"])
    return {"status": "ok", "user": user}

# Ã¢â€â‚¬Ã¢â€â‚¬ Audit Log Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/audit")
def get_audit(limit:int=200, u=Depends(require_role("admin","operator"))):
    return {"logs": list_audit(limit=limit)}

@app.get("/api/audit/me")
def get_my_audit(u=Depends(get_current_user)):
    return {"logs": list_audit(limit=100, username=u["username"])}

# Ã¢â€â‚¬Ã¢â€â‚¬ CSV exports Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/export/vms")
def export_vms(vcenter_id:str=None, u=Depends(get_current_user)):
    return _csv(_filter(_require_data()["vms"],vcenter_id),
        ["vcenter_name","name","status","cpu","ram_gb","disk_gb","host","guest_os","snapshot_count","ip"],
        "vms_export.csv")

@app.get("/api/export/hosts")
def export_hosts(vcenter_id:str=None, u=Depends(get_current_user)):
    return _csv(_filter(_require_data()["hosts"],vcenter_id),
        ["vcenter_name","name","cluster_name","status","cpu_cores","cpu_total_mhz","cpu_used_mhz","cpu_free_pct",
         "ram_total_gb","ram_used_gb","ram_free_gb"],"hosts_export.csv")

@app.get("/api/export/datastores")
def export_datastores(vcenter_id:str=None, u=Depends(get_current_user)):
    return _csv(_filter(_require_data()["datastores"],vcenter_id),
        ["vcenter_name","name","type","total_gb","used_gb","free_gb","used_pct","accessible"],
        "datastores_export.csv")

# Ã¢â€â‚¬Ã¢â€â‚¬ VM Delete from Disk (Admin only) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class VMDeleteReq(BaseModel):
    vcenter_id: str
    vm_name: str

@app.post("/api/vmware/delete")
def delete_vm_from_disk(req: VMDeleteReq, u=Depends(require_role("admin"))):
    from vmware_client import vm_delete_from_disk
    r = vm_delete_from_disk(req.vcenter_id, req.vm_name)
    if not r.get("success"):
        raise HTTPException(400, detail=r.get("message","Delete failed"))
    audit(u["username"], "VM_DELETE_DISK", target=req.vm_name,
          detail=f"vcenter={req.vcenter_id}", role=u["role"])
    _do_fetch()
    return r

# Ã¢â€â‚¬Ã¢â€â‚¬ VM Snapshots for a single VM Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/vmware/vm-snapshots")
def get_vm_snapshots(vcenter_id: str, vm_name: str, u=Depends(get_current_user)):
    data = _require_data()
    snaps = [s for s in data.get("snapshots", [])
             if s["vcenter_id"] == vcenter_id and s["vm_name"] == vm_name]
    return {"snapshots": snaps}

# Ã¢â€â‚¬Ã¢â€â‚¬ Admin: vCenter Management Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class VCenterAddReq(BaseModel):
    host: str
    name: str
    user: str
    password: str
    port: int = 443

class VCenterDeleteReq(BaseModel):
    vcenter_id: str

@app.post("/api/admin/vcenters")
def admin_add_vcenter(req: VCenterAddReq, u=Depends(require_role("admin"))):
    from vmware_client import admin_add_vcenter as _add
    r = _add(req.host, req.name, req.user, req.password, req.port)
    if not r.get("success"):
        raise HTTPException(400, detail=r.get("message","Failed to add vCenter"))
    audit(u["username"], "VCENTER_ADD", target=req.host,
          detail=f"name={req.name}", role=u["role"])
    return r

@app.post("/api/admin/vcenters/delete")
def admin_delete_vcenter(req: VCenterDeleteReq, u=Depends(require_role("admin"))):
    from vmware_client import admin_delete_vcenter as _del
    r = _del(req.vcenter_id)
    if not r.get("success"):
        raise HTTPException(400, detail=r.get("message","Failed to delete vCenter"))
    audit(u["username"], "VCENTER_DELETE", target=req.vcenter_id, role=u["role"])
    return r

@app.post("/api/admin/vcenters/test")
def admin_test_vcenter(req: VCenterAddReq, u=Depends(require_role("admin"))):
    from vmware_client import test_vcenter_connection
    r = test_vcenter_connection(req.host, req.user, req.password, req.port)
    return r

@app.post("/api/admin/vcenters/reload")
def admin_reload_vcenters(u=Depends(require_role("admin"))):
    from vmware_client import reload_vcenters
    reload_vcenters()
    _do_fetch()
    return {"status": "ok", "message": "vCenters reloaded from .env"}

# Ã¢â€â‚¬Ã¢â€â‚¬ Admin: Pricing Config Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
_PRICING_FILE = Path(__file__).parent / "pricing.json"
_DEFAULT_PRICING = {
    "cpu_per_core_month_inr":       500,
    "ram_per_gb_month_inr":         200,
    "ssd_per_gb_month_inr":         15,
    "hdd_per_gb_month_inr":         8,
    "disk_per_gb_month_inr":        8,   # kept for backward compat (= HDD rate)
    "windows_license_month_inr":    12500,  # Windows Server Standard SPLA avg
    "rhel_license_month_inr":       10000,  # RHEL subscription avg
    "internet_per_vm_month_inr":    1500,   # on-prem internet access per VM per month
    "usd_rate": 83.5,
    "updated_by": "system",
    "updated_at": ""
}

def _load_pricing():
    base = _DEFAULT_PRICING.copy()
    if _PRICING_FILE.exists():
        try:
            saved = json.loads(_PRICING_FILE.read_text())
            base.update(saved)   # merge: saved values override defaults, new defaults fill missing keys
        except Exception:
            pass
    return base

@app.get("/api/admin/pricing")
def get_pricing(u=Depends(get_current_user)):
    return _load_pricing()

class PricingUpdate(BaseModel):
    cpu_per_core_month_inr:      float
    ram_per_gb_month_inr:        float
    ssd_per_gb_month_inr:        float = 15.0
    hdd_per_gb_month_inr:        float = 8.0
    disk_per_gb_month_inr:       float = 8.0   # kept for backward compat
    windows_license_month_inr:   float = 12500.0
    rhel_license_month_inr:      float = 10000.0
    internet_per_vm_month_inr:   float = 1500.0
    usd_rate:                    float

@app.post("/api/admin/pricing")
def save_pricing(body: PricingUpdate, u=Depends(require_role("admin"))):
    import datetime
    data = body.dict()
    # Keep disk_per_gb_month_inr in sync with HDD rate for backward compatibility
    data["disk_per_gb_month_inr"] = data.get("hdd_per_gb_month_inr", data.get("disk_per_gb_month_inr", 8.0))
    # Ensure defaults exist if not sent
    data.setdefault("windows_license_month_inr", 12500.0)
    data.setdefault("rhel_license_month_inr",    10000.0)
    data.setdefault("internet_per_vm_month_inr", 1500.0)
    data["updated_by"] = u["username"]
    data["updated_at"]  = datetime.datetime.utcnow().isoformat()
    _PRICING_FILE.write_text(json.dumps(data, indent=2))
    audit(u["username"], "PRICING_UPDATE", detail=str(data), role=u["role"])
    return {"status": "ok", "pricing": data}


# Ã¢â€â‚¬Ã¢â€â‚¬ Admin: Internet VM Config Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
_INTERNET_FILE  = Path(__file__).parent / "internet_vms.json"
_DEFAULT_INTERNET = {"mode": "all_powered_on", "excluded": [], "extra": []}

def _load_internet_cfg():
    base = _DEFAULT_INTERNET.copy()
    if _INTERNET_FILE.exists():
        try:
            saved = json.loads(_INTERNET_FILE.read_text())
            base.update(saved)
        except Exception:
            pass
    return base

@app.get("/api/admin/internet-vms")
def get_internet_vms(u=Depends(get_current_user)):
    return _load_internet_cfg()

class InternetVMToggle(BaseModel):
    vm_name: str
    enabled: bool

@app.post("/api/admin/internet-vms/toggle")
def toggle_internet_vm(body: InternetVMToggle, u=Depends(require_role("admin"))):
    """Admin: enable or disable internet charge for a specific VM."""
    cfg = _load_internet_cfg()
    excluded = list(cfg.get("excluded") or [])
    extra    = list(cfg.get("extra")    or [])
    vn = body.vm_name.strip()
    if not vn:
        raise HTTPException(400, detail="vm_name required")

    if body.enabled:
        if vn in excluded: excluded.remove(vn)
        if vn not in extra: extra.append(vn)
    else:
        if vn in extra: extra.remove(vn)
        if vn not in excluded: excluded.append(vn)

    cfg["excluded"] = excluded
    cfg["extra"]    = extra
    _INTERNET_FILE.write_text(json.dumps(cfg, indent=2))
    audit(u["username"], "INTERNET_VM_TOGGLE", target=vn,
          detail=f"enabled={body.enabled}", role=u["role"])
    return {"status": "ok", "config": cfg}


# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
# APPEND THESE BLOCKS TO THE BOTTOM OF main.py
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â

# Ã¢â€â‚¬Ã¢â€â‚¬ OpenShift routes Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
from openshift_client import (
    init_openshift_db, list_clusters, get_cluster, create_cluster,
    update_cluster, delete_cluster, find_cluster_by_url,
    test_cluster_connection,
    get_live_nodes, get_pods, get_namespaces,
    get_cluster_operators, get_events, get_cluster_overview,
    node_action as ocp_node_action_fn,
    get_pod_detail, get_namespace_detail, get_pod_logs, get_storage_classes,
    get_routes,
    get_persistent_volumes, get_persistent_volume_claims,
    describe_persistent_volume, describe_persistent_volume_claim, describe_storage_class,
    delete_persistent_volume, delete_persistent_volume_claim, delete_storage_class,
    create_persistent_volume_claim, get_storage_resource_events,
    get_deployments, get_deployment_configs, get_statefulsets,
    get_daemonsets, get_replicasets, get_secrets, get_configmaps,
    describe_workload_resource, delete_workload_resource, get_workload_pod_logs,
    create_ocp_vm_req, list_ocp_vm_reqs, get_ocp_vm_req, review_ocp_vm_req,
)

def _ocp_seed_from_env():
    """Auto-seed an OCP cluster from env vars if not already in DB."""
    api_url  = os.getenv("OCP_API_URL", "").strip()
    username = os.getenv("OCP_USERNAME", "").strip()
    password = os.getenv("OCP_PASSWORD", "").strip()
    name     = os.getenv("OCP_NAME", "OpenShift Cluster").strip()
    console  = os.getenv("OCP_CONSOLE_URL", "").strip()
    if api_url and username and password:
        existing = find_cluster_by_url(api_url)
        if not existing:
            create_cluster({
                "name": name, "api_url": api_url,
                "console_url": console, "username": username,
                "password": password, "created_by": "system",
            })
            log.info(f"OCP cluster '{name}' auto-seeded from env")
        else:
            # Update credentials if changed
            update_cluster(existing["id"], {"username": username, "password": password,
                                            "console_url": console or existing.get("console_url","")})

try:
    init_openshift_db()
    _ocp_seed_from_env()
except Exception as _ocp_e:
    log.warning(f"OCP init: {_ocp_e}")

class OCPClusterCreate(BaseModel):
    name:        str
    api_url:     str
    console_url: str = ""
    ai_url:      str = ""
    version:     str = ""
    description: str = ""
    username:    str = ""
    password:    str = ""
    token:       str = ""

class OCPClusterUpdate(BaseModel):
    name:        str | None = None
    api_url:     str | None = None
    console_url: str | None = None
    ai_url:      str | None = None
    version:     str | None = None
    description: str | None = None
    username:    str | None = None
    password:    str | None = None
    token:       str | None = None
    status:      str | None = None

class OCPNodeActionBody(BaseModel):
    action: str   # cordon | uncordon | drain | describe

# Ã¢â€â‚¬Ã¢â€â‚¬ Cluster CRUD Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/openshift/clusters")
def ocp_list_clusters(u=Depends(require_role("admin","operator","viewer"))):
    return {"clusters": list_clusters()}

@app.post("/api/openshift/clusters")
def ocp_create_cluster(body: OCPClusterCreate, u=Depends(require_role("admin"))):
    data = body.dict()
    data["created_by"] = u["username"]
    cluster = create_cluster(data)
    audit(u["username"], "OCP_CLUSTER_ADD", target=body.name,
          detail=f"api={body.api_url}", role=u["role"])
    return cluster

@app.get("/api/openshift/clusters/{cluster_id}")
def ocp_get_cluster(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    from openshift_client import _safe
    return _safe(c)

@app.patch("/api/openshift/clusters/{cluster_id}")
def ocp_update_cluster(cluster_id: int, body: OCPClusterUpdate, u=Depends(require_role("admin"))):
    data = {k: v for k, v in body.dict().items() if v is not None}
    c = update_cluster(cluster_id, data)
    if not c: raise HTTPException(404, detail="Cluster not found")
    audit(u["username"], "OCP_CLUSTER_UPDATE", target=str(cluster_id),
          detail=str({k:v for k,v in data.items() if k!="password"}), role=u["role"])
    return c

@app.delete("/api/openshift/clusters/{cluster_id}")
def ocp_delete_cluster(cluster_id: int, u=Depends(require_role("admin"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    delete_cluster(cluster_id)
    audit(u["username"], "OCP_CLUSTER_DELETE", target=c["name"], role=u["role"])
    return {"status": "ok"}

@app.post("/api/openshift/clusters/{cluster_id}/test")
def ocp_test_cluster(cluster_id: int, u=Depends(require_role("admin","operator"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    result = test_cluster_connection(c)
    status = "connected" if result["reachable"] else "error"
    update_cluster(cluster_id, {"status": status})
    return result

# Ã¢â€â‚¬Ã¢â€â‚¬ Live data endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/openshift/clusters/{cluster_id}/overview")
def ocp_overview(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    return get_cluster_overview(c)

@app.get("/api/openshift/clusters/{cluster_id}/live/nodes")
def ocp_live_nodes(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    nodes = get_live_nodes(c)
    update_cluster(cluster_id, {"status": "connected"})
    return {"nodes": nodes, "count": len(nodes)}

@app.get("/api/openshift/clusters/{cluster_id}/live/pods")
def ocp_live_pods(cluster_id: int, namespace: str = "", u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    pods = get_pods(c, namespace)
    return {"pods": pods, "count": len(pods)}

@app.get("/api/openshift/clusters/{cluster_id}/live/namespaces")
def ocp_live_namespaces(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    return {"namespaces": get_namespaces(c)}

@app.get("/api/openshift/clusters/{cluster_id}/live/operators")
def ocp_live_operators(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    return {"operators": get_cluster_operators(c)}

@app.get("/api/openshift/clusters/{cluster_id}/live/events")
def ocp_live_events(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    return {"events": get_events(c)}

@app.get("/api/openshift/clusters/{cluster_id}/live/pods/{namespace}/{pod_name}/logs")
def ocp_pod_logs(cluster_id: int, namespace: str, pod_name: str,
                 container: str = "", tail: int = 200,
                 u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    return get_pod_logs(c, namespace, pod_name, container, tail)

@app.get("/api/openshift/clusters/{cluster_id}/live/pods/{namespace}/{pod_name}/detail")
def ocp_pod_detail(cluster_id: int, namespace: str, pod_name: str,
                   u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    return get_pod_detail(c, namespace, pod_name)

@app.get("/api/openshift/clusters/{cluster_id}/live/namespaces/{ns_name}/detail")
def ocp_namespace_detail(cluster_id: int, ns_name: str,
                         u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    return get_namespace_detail(c, ns_name)

@app.get("/api/openshift/clusters/{cluster_id}/live/storageclasses")
def ocp_storage_classes(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    return {"storage_classes": get_storage_classes(c)}

@app.get("/api/openshift/clusters/{cluster_id}/live/storageclasses/{sc_name}/describe")
def ocp_describe_sc(cluster_id: int, sc_name: str, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        return describe_storage_class(c, sc_name)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/openshift/clusters/{cluster_id}/live/storageclasses/{sc_name}")
def ocp_delete_sc(cluster_id: int, sc_name: str, u=Depends(require_role("admin","operator"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        return delete_storage_class(c, sc_name)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/clusters/{cluster_id}/live/pvs")
def ocp_list_pvs(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    return {"pvs": get_persistent_volumes(c)}

@app.get("/api/openshift/clusters/{cluster_id}/live/pvs/{pv_name}/describe")
def ocp_describe_pv(cluster_id: int, pv_name: str, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        return describe_persistent_volume(c, pv_name)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/openshift/clusters/{cluster_id}/live/pvs/{pv_name}")
def ocp_delete_pv(cluster_id: int, pv_name: str, u=Depends(require_role("admin","operator"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        return delete_persistent_volume(c, pv_name)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/clusters/{cluster_id}/live/pvs/{pv_name}/events")
def ocp_pv_events(cluster_id: int, pv_name: str, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    return {"events": get_storage_resource_events(c, pv_name, namespace=None, kind="PersistentVolume")}

@app.get("/api/openshift/clusters/{cluster_id}/live/pvcs")
def ocp_list_pvcs(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    return {"pvcs": get_persistent_volume_claims(c)}

@app.get("/api/openshift/clusters/{cluster_id}/live/pvcs/{namespace}/{pvc_name}/describe")
def ocp_describe_pvc(cluster_id: int, namespace: str, pvc_name: str, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        return describe_persistent_volume_claim(c, namespace, pvc_name)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/openshift/clusters/{cluster_id}/live/pvcs/{namespace}/{pvc_name}")
def ocp_delete_pvc(cluster_id: int, namespace: str, pvc_name: str, u=Depends(require_role("admin","operator"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        return delete_persistent_volume_claim(c, namespace, pvc_name)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/clusters/{cluster_id}/live/pvcs/{namespace}/{pvc_name}/events")
def ocp_pvc_events(cluster_id: int, namespace: str, pvc_name: str, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    return {"events": get_storage_resource_events(c, pvc_name, namespace=namespace, kind="PersistentVolumeClaim")}

class CreatePVCRequest(BaseModel):
    namespace:     str
    name:          str
    storage:       str = "1Gi"
    access_mode:   str = "ReadWriteOnce"
    storage_class: str = ""
    volume_mode:   str = "Filesystem"

@app.post("/api/openshift/clusters/{cluster_id}/live/pvcs")
def ocp_create_pvc(cluster_id: int, body: CreatePVCRequest, u=Depends(require_role("admin","operator"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        return create_persistent_volume_claim(
            c, body.namespace, body.name, body.storage,
            body.access_mode, body.storage_class, body.volume_mode)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/clusters/{cluster_id}/live/routes")
def ocp_live_routes(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    routes = get_routes(c)
    return {"routes": routes, "count": len(routes)}

# Ã¢â€â‚¬Ã¢â€â‚¬ Workloads Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/openshift/clusters/{cluster_id}/live/workloads/deployments")
def ocp_list_deployments(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        data = get_deployments(c)
        return {"items": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/clusters/{cluster_id}/live/workloads/deploymentconfigs")
def ocp_list_deploymentconfigs(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        data = get_deployment_configs(c)
        return {"items": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/clusters/{cluster_id}/live/workloads/statefulsets")
def ocp_list_statefulsets(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        data = get_statefulsets(c)
        return {"items": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/clusters/{cluster_id}/live/workloads/daemonsets")
def ocp_list_daemonsets(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        data = get_daemonsets(c)
        return {"items": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/clusters/{cluster_id}/live/workloads/replicasets")
def ocp_list_replicasets(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        data = get_replicasets(c)
        return {"items": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/clusters/{cluster_id}/live/workloads/secrets")
def ocp_list_secrets(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        data = get_secrets(c)
        return {"items": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/clusters/{cluster_id}/live/workloads/configmaps")
def ocp_list_configmaps(cluster_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        data = get_configmaps(c)
        return {"items": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/clusters/{cluster_id}/live/workloads/{kind}/{namespace}/{name}/describe")
def ocp_describe_workload(cluster_id: int, kind: str, namespace: str, name: str,
                          u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        return describe_workload_resource(c, kind, namespace, name)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/openshift/clusters/{cluster_id}/live/workloads/{kind}/{namespace}/{name}")
def ocp_delete_workload(cluster_id: int, kind: str, namespace: str, name: str,
                        u=Depends(require_role("admin","operator"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        result = delete_workload_resource(c, kind, namespace, name)
        audit(u["username"], "OCP_WORKLOAD_DELETE", target=name,
              detail=f"kind={kind} ns={namespace} cluster={c['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/clusters/{cluster_id}/live/workloads/{kind}/{namespace}/{name}/logs")
def ocp_workload_logs(cluster_id: int, kind: str, namespace: str, name: str,
                      u=Depends(require_role("admin","operator","viewer"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    try:
        return get_workload_pod_logs(c, kind, namespace, name)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/openshift/clusters/{cluster_id}/nodes/{node_name}/action")
def ocp_node_action(cluster_id: int, node_name: str, body: OCPNodeActionBody,
                    u=Depends(require_role("admin","operator"))):
    c = get_cluster(cluster_id)
    if not c: raise HTTPException(404, detail="Cluster not found")
    result = ocp_node_action_fn(c, node_name, body.action)
    audit(u["username"], "OCP_NODE_ACTION", target=node_name,
          detail=f"action={body.action} cluster={c['name']}", role=u["role"])
    if not result["success"]:
        raise HTTPException(500, detail=result["message"])
    return result


# Ã¢â€â‚¬Ã¢â€â‚¬ OCP VM Requests Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class OCPVMReqCreate(BaseModel):
    cluster_id:           int
    cluster_name:         str  = ""
    namespace:            str  = "default"
    vm_name:              str
    description:          str  = ""
    os_template:          str  = "rhel9"
    cpu_sockets:          int  = 1
    cpu_cores:            int  = 2
    cpu_threads:          int  = 1
    memory_gi:            int  = 4
    boot_disk_size:       str  = "30Gi"
    boot_disk_sc:         str  = ""
    boot_disk_interface:  str  = "virtio"
    additional_disks:     list = []
    network_type:         str  = "masquerade"
    network_interface:    str  = "virtio"
    network_name:         str  = "Pod Networking"
    cloud_init_enabled:   bool = True
    ssh_public_key:       str  = ""
    root_password:        str  = ""
    start_on_create:      bool = True
    notes:                str  = ""

class OCPVMReqReview(BaseModel):
    decision:     str   # approved | declined
    review_notes: str = ""

@app.post("/api/openshift/vm-requests")
def ocp_create_vm_request(body: OCPVMReqCreate, u=Depends(get_current_user)):
    data = body.dict()
    data["requester"] = u["username"]
    try:
        req = create_ocp_vm_req(data)
        audit(u["username"], "OCP_VM_REQUEST", target=data["vm_name"],
              detail=f"cluster={data['cluster_name']} ns={data['namespace']}",
              role=u["role"])
        return req
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/openshift/vm-requests")
def ocp_list_vm_requests(u=Depends(get_current_user)):
    if u["role"] in ("admin", "operator"):
        reqs = list_ocp_vm_reqs()
    else:
        reqs = list_ocp_vm_reqs(requester=u["username"])
    return {"requests": reqs}

@app.get("/api/openshift/vm-requests/{req_id}")
def ocp_get_vm_request(req_id: int, u=Depends(get_current_user)):
    req = get_ocp_vm_req(req_id)
    if not req: raise HTTPException(404, detail="Request not found")
    if u["role"] not in ("admin", "operator") and req.get("requester") != u["username"]:
        raise HTTPException(403, detail="Permission denied")
    return req

@app.patch("/api/openshift/vm-requests/{req_id}/review")
def ocp_review_vm_request(req_id: int, body: OCPVMReqReview,
                          u=Depends(require_role("admin","operator"))):
    if body.decision not in ("approved", "declined"):
        raise HTTPException(400, detail="decision must be 'approved' or 'declined'")
    req = review_ocp_vm_req(req_id, u["username"], body.decision, body.review_notes)
    if not req: raise HTTPException(404, detail="Request not found")
    audit(u["username"], f"OCP_VM_REQ_{body.decision.upper()}",
          target=req.get("vm_name",""),
          detail=f"req={req.get('req_number','')} cluster={req.get('cluster_name','')}",
          role=u["role"])
    return req


# Ã¢â€â‚¬Ã¢â€â‚¬ Baremetal routes Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
from baremetal_client import (
    init_baremetal_db, list_servers, get_server, add_server,
    update_server, delete_server, get_power_state, power_action,
    get_server_info, get_event_log, test_connection, BMC_TYPES
)

class BMServerAdd(BaseModel):
    name:        str
    ip:          str
    bmc_type:    str = "IPMI"   # ILO | IDRAC | CIMC | IPMI
    username:    str
    password:    str
    port:        int = 443
    description: str = ""
    location:    str = ""
    model:       str = ""
    serial:      str = ""

class BMServerUpdate(BaseModel):
    name:        str | None = None
    ip:          str | None = None
    bmc_type:    str | None = None
    username:    str | None = None
    password:    str | None = None
    port:        int | None = None
    description: str | None = None
    location:    str | None = None
    model:       str | None = None

class BMActionReq(BaseModel):
    action: str   # power_on|power_off|graceful_shutdown|reboot|graceful_reboot|power_cycle|nmi|pxe_boot

class BMTestReq(BaseModel):
    ip:       str
    username: str
    password: str
    bmc_type: str = "IPMI"
    port:     int = 443

@app.get("/api/baremetal/servers")
def bm_list(u=Depends(require_role("admin","operator","viewer"))):
    return {"servers": list_servers()}

@app.post("/api/baremetal/servers")
def bm_add(body: BMServerAdd, u=Depends(require_role("admin"))):
    if body.bmc_type.upper() not in BMC_TYPES:
        raise HTTPException(400, detail=f"bmc_type must be one of {BMC_TYPES}")
    server = add_server(body.dict(), u["username"])
    audit(u["username"], "BM_SERVER_ADD", target=body.name,
          detail=f"ip={body.ip} type={body.bmc_type}", role=u["role"])
    return server

@app.get("/api/baremetal/servers/{server_id}")
def bm_get(server_id: int, u=Depends(require_role("admin","operator","viewer"))):
    s = get_server(server_id)
    if not s: raise HTTPException(404, detail="Server not found")
    return s

@app.patch("/api/baremetal/servers/{server_id}")
def bm_update(server_id: int, body: BMServerUpdate, u=Depends(require_role("admin"))):
    data = {k: v for k, v in body.dict().items() if v is not None}
    s = update_server(server_id, data)
    if not s: raise HTTPException(404, detail="Server not found")
    audit(u["username"], "BM_SERVER_UPDATE", target=str(server_id), role=u["role"])
    return s

@app.delete("/api/baremetal/servers/{server_id}")
def bm_delete(server_id: int, u=Depends(require_role("admin"))):
    s = get_server(server_id)
    if not s: raise HTTPException(404, detail="Server not found")
    delete_server(server_id)
    audit(u["username"], "BM_SERVER_DELETE", target=s["name"], role=u["role"])
    return {"status": "ok"}

@app.get("/api/baremetal/servers/{server_id}/power")
def bm_power_state(server_id: int, u=Depends(require_role("admin","operator","viewer"))):
    s = get_server(server_id, include_password=True)
    if not s: raise HTTPException(404, detail="Server not found")
    return get_power_state(s)

@app.post("/api/baremetal/servers/{server_id}/action")
def bm_action(server_id: int, body: BMActionReq, u=Depends(require_role("admin","operator"))):
    s = get_server(server_id, include_password=True)
    if not s: raise HTTPException(404, detail="Server not found")
    result = power_action(s, body.action)
    audit(u["username"], "BM_POWER_ACTION", target=s["name"],
          detail=f"action={body.action}", role=u["role"],
          result="ok" if result["success"] else "fail")
    if not result["success"]:
        raise HTTPException(500, detail=result["message"])
    return result

@app.get("/api/baremetal/servers/{server_id}/info")
def bm_info(server_id: int, u=Depends(require_role("admin","operator","viewer"))):
    s = get_server(server_id, include_password=True)
    if not s: raise HTTPException(404, detail="Server not found")
    return get_server_info(s)

@app.get("/api/baremetal/servers/{server_id}/logs")
def bm_logs(server_id: int, limit: int = 20,
            u=Depends(require_role("admin","operator","viewer"))):
    s = get_server(server_id, include_password=True)
    if not s: raise HTTPException(404, detail="Server not found")
    return get_event_log(s, limit)

@app.post("/api/baremetal/test")
def bm_test_connection(body: BMTestReq, u=Depends(require_role("admin"))):
    return test_connection(body.ip, body.username, body.password,
                           body.bmc_type, body.port)


# Ã¢â€â‚¬Ã¢â€â‚¬ Notifications (admin publishes, all users read) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
_NOTIF_FILE = Path(__file__).parent / "notifications.json"

def _load_notifs():
    try:
        if _NOTIF_FILE.exists():
            return json.loads(_NOTIF_FILE.read_text())
    except Exception:
        pass
    return []

@app.get("/api/notifications")
def get_notifications(u=Depends(get_current_user)):
    return {"notifications": _load_notifs()}

class NotifSaveReq(BaseModel):
    notifications: list

@app.post("/api/notifications")
def save_notifications(body: NotifSaveReq, u=Depends(require_role("admin"))):
    _NOTIF_FILE.write_text(json.dumps(body.notifications, indent=2))
    audit(u["username"], "NOTIFICATIONS_UPDATE", detail=f"{len(body.notifications)} items")
    return {"status": "ok", "count": len(body.notifications)}

# Ã¢â€â‚¬Ã¢â€â‚¬ IPAM Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
import json as _json

IPAM_MANUAL_FILE = Path(__file__).parent / "ipam_manual.json"

def _load_manual_subnets():
    try:
        if IPAM_MANUAL_FILE.exists():
            return _json.loads(IPAM_MANUAL_FILE.read_text())
    except Exception:
        pass
    return []

def _save_manual_subnets(entries):
    IPAM_MANUAL_FILE.write_text(_json.dumps(entries, indent=2))

@app.get("/api/ipam/subnets")
def ipam_subnets(u=Depends(get_current_user)):
    """Return all IPAM subnets from SolarWinds (cached 5 min) + manual entries."""
    data = get_ipam_subnets()
    manual = _load_manual_subnets()
    if manual:
        data["subnets"] = list(data.get("subnets", [])) + manual
    return data

@app.post("/api/ipam/refresh")
def ipam_refresh(u=Depends(require_role("admin", "operator"))):
    """Force-refresh the IPAM subnet cache."""
    data = get_ipam_subnets(force=True)
    return {"status": "ok", "subnets": len(data.get("subnets", [])), "error": data.get("error")}

@app.get("/api/ipam/subnet/{subnet_id}/ips")
def ipam_subnet_ips(subnet_id: int, u=Depends(get_current_user)):
    """Return all IP addresses for a specific subnet (cached 5 min)."""
    data = get_ipam_subnet_ips(subnet_id)
    return data

class IPAMManualSubnet(BaseModel):
    vlan: str = ""
    address_cidr: str
    name: str = ""
    location: str = ""
    comments: str = ""
    status: str = "Up"

@app.post("/api/ipam/manual")
def ipam_add_manual(req: IPAMManualSubnet, u=Depends(require_role("admin"))):
    """Add a manual IPAM subnet entry (admin only)."""
    entries = _load_manual_subnets()
    import time as _time
    new_id = f"manual_{int(_time.time()*1000)}"
    entry = {**req.dict(), "subnet_id": new_id, "is_manual": True,
             "total": 0, "used": 0, "available": 0, "reserved": 0, "percent_used": 0}
    entries.append(entry)
    _save_manual_subnets(entries)
    return {"status": "ok", "entry": entry}

@app.put("/api/ipam/manual/{subnet_id}")
def ipam_edit_manual(subnet_id: str, req: IPAMManualSubnet, u=Depends(require_role("admin"))):
    """Edit a manual IPAM subnet entry (admin only)."""
    entries = _load_manual_subnets()
    updated = False
    for i, e in enumerate(entries):
        if str(e.get("subnet_id")) == subnet_id:
            entries[i] = {**e, **req.dict()}
            updated = True
            break
    if not updated:
        raise HTTPException(status_code=404, detail="Manual subnet not found")
    _save_manual_subnets(entries)
    return {"status": "ok"}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  IPAM v2 â€” Self-hosted PostgreSQL IPAM  (DC / DR VLANs + IP management)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Initialize schema once on startup
try:
    _ipam_pg.init_ipam_schema()
except Exception as _e:
    log.warning(f"[ipam2] Schema init deferred: {_e}")

class IPAMv2UpdateIP(BaseModel):
    status:       str = None
    hostname:     str = None
    mac_address:  str = None
    device_type:  str = None
    dns_forward:  str = None
    dns_reverse:  str = None
    owner:        str = None
    description:  str = None
    remarks:      str = None

class IPAMv2BulkUpdate(BaseModel):
    ip_ids: list
    update: IPAMv2UpdateIP

class IPAMv2CreateVLAN(BaseModel):
    site:        str
    vlan_id:     int
    name:        str = ""
    subnet:      str
    gateway:     str = ""
    description: str = ""
    notes:       str = ""
    vrf:         str = ""

class IPAMv2UpdateVLAN(BaseModel):
    name:        str = ""
    description: str = ""
    notes:       str = ""
    vrf:         str = ""

@app.get("/api/ipam2/summary")
def ipam2_summary(u=Depends(get_current_user)):
    """Overall IPAM statistics."""
    try:
        return _ipam_pg.get_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ipam2/vlans")
def ipam2_vlans(site: str = None, u=Depends(get_current_user)):
    """List all VLANs with IP counts per status."""
    try:
        return _ipam_pg.list_vlans(site=site)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ipam2/vlans")
def ipam2_create_vlan(body: IPAMv2CreateVLAN, u=Depends(require_role("admin"))):
    """Create a new VLAN and seed its IPs."""
    try:
        row = _ipam_pg.create_vlan(body.dict())
        audit(u["username"], "IPAM2_VLAN_CREATE", detail=f"{body.site} VLAN {body.vlan_id} {body.subnet}")
        return row
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/ipam2/vlans/{vlan_db_id}")
def ipam2_update_vlan(vlan_db_id: int, body: IPAMv2UpdateVLAN, u=Depends(require_role("admin"))):
    """Update VLAN metadata."""
    try:
        row = _ipam_pg.update_vlan(vlan_db_id, body.dict())
        if not row:
            raise HTTPException(status_code=404, detail="VLAN not found")
        audit(u["username"], "IPAM2_VLAN_UPDATE", detail=f"id={vlan_db_id}")
        return row
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/ipam2/vlans/{vlan_db_id}")
def ipam2_delete_vlan(vlan_db_id: int, u=Depends(require_role("admin"))):
    """Delete a VLAN and all its IPs."""
    try:
        ok = _ipam_pg.delete_vlan(vlan_db_id)
        if not ok:
            raise HTTPException(status_code=404, detail="VLAN not found")
        audit(u["username"], "IPAM2_VLAN_DELETE", detail=f"id={vlan_db_id}")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ipam2/vlans/{vlan_db_id}/ips")
def ipam2_list_ips(vlan_db_id: int, status: str = None, q: str = None, u=Depends(get_current_user)):
    """List IP addresses in a VLAN."""
    try:
        return _ipam_pg.list_ips(vlan_db_id, status=status, q=q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/ipam2/ips/{ip_id}")
def ipam2_update_ip(ip_id: int, body: IPAMv2UpdateIP, u=Depends(require_role("admin", "operator"))):
    """Update a single IP address record."""
    try:
        data = {k: v for k, v in body.dict().items() if v is not None}
        row = _ipam_pg.update_ip(ip_id, data, changed_by=u["username"])
        if not row:
            raise HTTPException(status_code=404, detail="IP not found")
        audit(u["username"], "IPAM2_IP_UPDATE", detail=f"id={ip_id} {data}")
        return row
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ipam2/ips/bulk-update")
def ipam2_bulk_update(body: IPAMv2BulkUpdate, u=Depends(require_role("admin", "operator"))):
    """Bulk-update multiple IP records."""
    try:
        data = {k: v for k, v in body.update.dict().items() if v is not None}
        count = _ipam_pg.bulk_update_ips(body.ip_ids, data, changed_by=u["username"])
        audit(u["username"], "IPAM2_BULK_UPDATE", detail=f"{count} IPs {data}")
        return {"updated": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

_ipam2_scan_state: dict = {}  # vlan_db_id -> {running, done_at, up, down}

@app.post("/api/ipam2/vlans/{vlan_db_id}/ping")
def ipam2_ping(vlan_db_id: int, u=Depends(require_role("admin", "operator"))):
    """Start background ping scan; returns immediately. Poll /ping/status."""
    import threading as _t
    state = _ipam2_scan_state.get(vlan_db_id, {})
    if state.get("running"):
        return {"status": "running", "vlan_db_id": vlan_db_id}
    _ipam2_scan_state[vlan_db_id] = {"running": True, "up": 0, "down": 0, "done_at": None}
    def _run():
        try:
            results = _ipam_pg.ping_and_save(vlan_db_id)
            up   = sum(1 for v in results.values() if v["status"] == "up")
            down = sum(1 for v in results.values() if v["status"] == "down")
            _ipam2_scan_state[vlan_db_id] = {"running": False, "up": up, "down": down,
                                              "done_at": __import__("time").time()}
        except Exception as e:
            log.error(f"[ipam2] ping failed: {e}")
            _ipam2_scan_state[vlan_db_id] = {"running": False, "up": 0, "down": 0, "done_at": 0}
    _t.Thread(target=_run, daemon=True).start()
    return {"status": "started", "vlan_db_id": vlan_db_id}

@app.get("/api/ipam2/vlans/{vlan_db_id}/ping/status")
def ipam2_ping_status(vlan_db_id: int, u=Depends(get_current_user)):
    """Poll scan status: running | done."""
    s = _ipam2_scan_state.get(vlan_db_id, {"running": False, "done_at": None})
    return {"running": s.get("running", False), "done_at": s.get("done_at"),
            "up": s.get("up", 0), "down": s.get("down", 0)}
@app.post("/api/ipam2/vlans/{vlan_db_id}/dns-lookup")
def ipam2_dns_lookup(vlan_db_id: int, u=Depends(require_role("admin", "operator"))):
    """Run DNS lookups for all IPs in a VLAN (runs in background)."""
    import threading as _threading
    def _do_dns():
        try:
            _ipam_pg.dns_lookup_and_save(vlan_db_id, changed_by=u["username"])
        except Exception as e:
            log.error(f"[ipam2] dns lookup failed: {e}")
    t = _threading.Thread(target=_do_dns, daemon=True)
    t.start()
    return {"status": "started", "vlan_db_id": vlan_db_id}

@app.get("/api/ipam2/changelog")
def ipam2_changelog(vlan_db_id: int = None, limit: int = 200, u=Depends(get_current_user)):
    """Return IPAM change history."""
    try:
        return _ipam_pg.list_changelog(vlan_db_id=vlan_db_id, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ipam2/conflicts")
def ipam2_conflicts(u=Depends(get_current_user)):
    """Detect duplicate IPs or hostname conflicts."""
    try:
        return _ipam_pg.list_conflicts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/ipam/manual/{subnet_id}")
def ipam_delete_manual(subnet_id: str, u=Depends(require_role("admin"))):
    """Delete a manual IPAM subnet entry (admin only)."""
    entries = _load_manual_subnets()
    before = len(entries)
    entries = [e for e in entries if str(e.get("subnet_id")) != subnet_id]
    if len(entries) == before:
        raise HTTPException(status_code=404, detail="Manual subnet not found")
    _save_manual_subnets(entries)
    return {"status": "ok"}


# Ã¢â€â‚¬Ã¢â€â‚¬ Asset Management Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class AssetActionReq(BaseModel):
    mgmt_ip: str
    action: str          # poweron | reboot | shutdown
    username: str
    password: str
    asset_name: str = ""
    model: str = ""

class AssetRowReq(BaseModel):
    site: str            # dc | dr
    sheet_name: str
    asset: dict

class AssetDeleteReq(BaseModel):
    site: str
    sheet_name: str
    asset_id: str        # _id field

class AssetPingReq(BaseModel):
    ips: list

@app.get("/api/assets/inventory")
def asset_inventory(site: str = "dc", u=Depends(get_current_user)):
    """Return full rack inventory for DC or DR."""
    filepath = DC_FILE if site.lower() == "dc" else DR_FILE
    data = parse_inventory(filepath)
    return data

@app.post("/api/assets/ping")
def asset_ping(body: AssetPingReq, u=Depends(get_current_user)):
    """Ping a list of management IPs (no credentials needed Ã¢â‚¬â€ direct network access)."""
    results = ping_many([str(ip) for ip in body.ips if ip])
    return {"results": results}

@app.post("/api/assets/action")
def asset_action(body: AssetActionReq, u=Depends(require_role("admin", "operator"))):
    """Execute a power action on a physical server via Redfish."""
    result = power_action(
        mgmt_ip=body.mgmt_ip, action=body.action,
        username=body.username, password=body.password,
        asset_name=body.asset_name, model=body.model
    )
    action_label = body.action.upper()
    audit(u["username"], f"ASSET_{action_label}",
          detail=f"{body.mgmt_ip} ({body.asset_name}) Ã¢â‚¬â€ {'OK' if result['success'] else 'FAIL: '+result['message']}")
    return result

@app.post("/api/assets/row")
def asset_add_row(body: AssetRowReq, u=Depends(require_role("admin", "operator"))):
    """Add a new asset row to a rack sheet."""
    filepath = DC_FILE if body.site.lower() == "dc" else DR_FILE
    data = parse_inventory(filepath)
    if body.sheet_name not in data["racks"]:
        data["racks"][body.sheet_name] = []
        if body.sheet_name not in data["sheet_order"]:
            data["sheet_order"].append(body.sheet_name)
    import time as _t
    new_asset = body.asset.copy()
    new_asset["_id"] = f"{body.sheet_name}___new_{int(_t.time())}"
    data["racks"][body.sheet_name].append(new_asset)
    ok = save_inventory(filepath, data)
    audit(u["username"], "ASSET_ADD_ROW", detail=f"{body.sheet_name}: {new_asset.get('asset_name','')}")
    return {"success": ok}

@app.put("/api/assets/row")
def asset_update_row(body: AssetRowReq, u=Depends(require_role("admin", "operator"))):
    """Update an existing asset row."""
    filepath = DC_FILE if body.site.lower() == "dc" else DR_FILE
    data = parse_inventory(filepath)
    racks = data.get("racks", {})
    rows = racks.get(body.sheet_name, [])
    asset_id = body.asset.get("_id", "")
    for i, row in enumerate(rows):
        if row.get("_id") == asset_id:
            rows[i] = body.asset
            break
    ok = save_inventory(filepath, data)
    audit(u["username"], "ASSET_EDIT_ROW", detail=f"{body.sheet_name}: {body.asset.get('asset_name','')}")
    return {"success": ok}

@app.delete("/api/assets/row")
def asset_delete_row(body: AssetDeleteReq, u=Depends(require_role("admin", "operator"))):
    """Delete an asset row."""
    filepath = DC_FILE if body.site.lower() == "dc" else DR_FILE
    data = parse_inventory(filepath)
    rows = data["racks"].get(body.sheet_name, [])
    data["racks"][body.sheet_name] = [r for r in rows if r.get("_id") != body.asset_id]
    ok = save_inventory(filepath, data)
    audit(u["username"], "ASSET_DELETE_ROW", detail=f"{body.sheet_name}: id={body.asset_id}")
    return {"success": ok}



import requests as _requests


# Ã¢â€â‚¬Ã¢â€â‚¬ Asset EOL (End of Life) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# Model-family Ã¢â€ â€™ approximate End-of-Life date lookup
_EOL_LOOKUP = {
    # HP / HPE ProLiant
    "dl380 gen9":    "2025-12-31",  "dl380gen9":   "2025-12-31",
    "dl360 gen9":    "2025-12-31",  "dl360gen9":   "2025-12-31",
    "dl560 gen9":    "2025-12-31",  "dl560gen9":   "2025-12-31",
    "dl380 gen-9":   "2025-12-31",  "dl380 gen 9": "2025-12-31",
    "synergy 480 gen9": "2025-12-31", "synergy 480 gen 9": "2025-12-31",
    "dl380 gen10":   "2028-12-31",  "dl380gen10":  "2028-12-31",
    "dl380 gen 10":  "2028-12-31",  "dl360 gen10": "2028-12-31",
    "dl560 gen10":   "2028-12-31",
    "dl380 gen11":   "2031-12-31",  "dl360 gen11": "2031-12-31",
    "synergy 12000": "2026-12-31",  "synergy 120000 frame": "2026-12-31",
    # HP Storage
    "3par":          "2025-06-30",  "storeserv8440":"2025-06-30",
    "storeserv":     "2025-06-30",  "nimble":      "2027-12-31",
    "d3700":         "2025-12-31",  "d3700 enclosure": "2025-12-31",
    # HPE Alletra
    "alletra":       "2030-12-31",  "drive enclosure": "2030-12-31",
    # Dell PowerEdge
    "r720":          "2024-10-08",  "poweredge-r720":"2024-10-08",
    "r730":          "2025-09-30",  "poweredge r730":"2025-09-30",
    "r640":          "2027-05-31",  "poweredge-r640":"2027-05-31",  "poweredge r640":"2027-05-31",
    "r760":          "2031-01-31",  "poweredge r760":"2031-01-31",
    "mx7000":        "2030-12-31",  "poweredge mx7000":"2030-12-31",
    "apex cloud platform mc660": "2031-06-30",  "mc660": "2031-06-30",
    "apex cloud platform mc760": "2031-06-30",  "mc760": "2031-06-30",
    # Cisco UCS
    "c240 m3":       "2024-04-30",  "ucsc240m3":   "2024-04-30",  "ucs c240 m3":"2024-04-30",
    "c240 m4":       "2026-01-31",  "ucsc240m4":   "2026-01-31",  "usc c240 m4":"2026-01-31",
    "c220 m4":       "2026-01-31",  "ucsc220m4":   "2026-01-31",
    "hx240cm4":      "2026-01-31",  "hx240c m4":   "2026-01-31",
    "apic-m1":       "2025-10-31",
    "nexus 9396":    "2027-12-31",  "nexus 9396px":"2027-12-31",
    "mds9148s":      "2027-06-30",  "mds9148":     "2027-06-30",
    # Quanta
    "d51b-2u":       "2025-06-30",  "d51b":        "2025-06-30",
    "d51v-2u":       "2025-06-30",  "d51v":        "2025-06-30",
    # SuperMicro
    "gp802f":        "2026-12-31",
    # Pure Storage
    "fam20":         "2028-12-31",  "flasharray":  "2028-12-31",
    "flashblade":    "2029-12-31",
    # Rubrik
    "rubrik":        "2027-12-31",
    # Arista
    "7050tx-64":     "2027-12-31",  "7050tx":      "2027-12-31",
    # Cohesity
    "cohesity":      "2028-12-31",
    # Intel
    "intel":         "2025-12-31",
}

def _match_eol(asset_name: str, model: str) -> str:
    """Try to match an asset to an EOL date using the lookup table."""
    name_l = (asset_name or "").lower()
    model_l = (model or "").lower()
    combined = f"{model_l} {name_l}".strip()
    # Try exact substring match first
    for key, eol in _EOL_LOOKUP.items():
        if key in combined:
            return eol
    # HP ProLiant special: model="DL380", name="HP Proliant GEN 9" -> extract gen + model
    import re
    gen_m = re.search(r'gen[- ]?(\d+)', combined)
    model_m = re.search(r'(dl\d{3}|ml\d{3}|bl\d{3})', combined)
    if gen_m and model_m:
        synth = f"{model_m.group(1)} gen{gen_m.group(1)}"
        for key, eol in _EOL_LOOKUP.items():
            if key in synth or synth in key:
                return eol
        synth2 = f"{model_m.group(1)}gen{gen_m.group(1)}"
        for key, eol in _EOL_LOOKUP.items():
            if key in synth2 or synth2 in key:
                return eol
    # Dell special: name has "DELL POWEREDGE R730" but model="R730"
    if "dell" in combined or "poweredge" in combined:
        r_m = re.search(r'r(\d{3})', combined)
        if r_m:
            rkey = f"r{r_m.group(1)}"
            if rkey in _EOL_LOOKUP:
                return _EOL_LOOKUP[rkey]
    return ""

class AssetEolUpdateReq(BaseModel):
    serial: str
    site: str = "dc"
    eol_date: str = ""

@app.get("/api/assets/eol")
def asset_eol_list(site: str = "dc", u=Depends(get_current_user)):
    """Return EOL dates for all assets in a site.
    Combines model-based lookup with any manual overrides stored in SQLite.
    Returns {serial: {eol_date, source, status}} where status is 'expired','warning','ok','unknown'.
    """
    import datetime as _dt
    filepath = DC_FILE if site.lower() == "dc" else DR_FILE
    inv = parse_inventory(filepath)

    # Load SQLite overrides
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT serial, eol_date, source FROM asset_eol WHERE site=?", (site,))
    overrides = {r[0]: {"eol_date": r[1], "source": r[2]} for r in cur.fetchall()}
    conn.close()

    today = _dt.date.today()
    result = {}

    for rack_name, assets in inv.get("racks", {}).items():
        for a in assets:
            serial = (a.get("serial") or "").strip()
            if not serial:
                continue
            # Check override first
            if serial in overrides:
                eol_str = overrides[serial]["eol_date"]
                source = overrides[serial]["source"]
            else:
                eol_str = _match_eol(a.get("asset_name", ""), a.get("model", ""))
                source = "lookup" if eol_str else "unknown"

            status = "unknown"
            if eol_str:
                try:
                    eol_dt = _dt.date.fromisoformat(eol_str)
                    days_left = (eol_dt - today).days
                    if days_left < 0:
                        status = "expired"
                    elif days_left <= 365:
                        status = "warning"
                    else:
                        status = "ok"
                except ValueError:
                    status = "unknown"

            result[serial] = {
                "eol_date": eol_str,
                "source": source,
                "status": status,
            }

    return {"eol": result}


@app.put("/api/assets/eol")
def asset_eol_update(body: AssetEolUpdateReq, u=Depends(require_role("admin", "operator"))):
    """Manually set or update EOL date for a specific asset by serial."""
    import datetime as _dt
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO asset_eol (serial, site, eol_date, source, fetched_at)
        VALUES (?, ?, ?, 'manual', ?)
        ON CONFLICT(serial, site) DO UPDATE SET eol_date=excluded.eol_date, source='manual', fetched_at=excluded.fetched_at
    """, (body.serial, body.site, body.eol_date, _dt.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    audit(u["username"], "ASSET_EOL_UPDATE", detail=f"serial={body.serial} site={body.site} eol={body.eol_date}")
    return {"success": True}


@app.post("/api/assets/eol/fetch")
def asset_eol_fetch_redfish(site: str = "dc", u=Depends(require_role("admin", "operator"))):
    """Try to fetch manufacture/warranty info from reachable management IPs via Redfish.
    Uses multiple credential sets. Stores results in SQLite.
    """
    import datetime as _dt
    import concurrent.futures as _cf

    filepath = DC_FILE if site.lower() == "dc" else DR_FILE
    inv = parse_inventory(filepath)

    CRED_SETS = [
        ("admin", "Sdxcoe@123"),
        ("admin", "admin"),
        ("admin", "Wipro@123"),
        ("dcmon", "Wipro@123"),
    ]

    def _fetch_one(asset):
        ip = (asset.get("mgmt_ip") or "").strip().split("/")[0].split("[")[0].strip()
        if not ip or not ip.replace(".", "").replace(":", "").isdigit():
            return None
        serial = (asset.get("serial") or "").strip()
        if not serial:
            return None

        for uname, pwd in CRED_SETS:
            try:
                sess = _requests.Session()
                sess.verify = False
                sess.auth = (uname, pwd)
                sess.headers.update({"Accept": "application/json"})
                # Try common Redfish system paths
                for path in ["/redfish/v1/Systems/1", "/redfish/v1/Systems/System.Embedded.1"]:
                    try:
                        r = sess.get(f"https://{ip}{path}", timeout=8)
                        if r.status_code == 200:
                            d = r.json()
                            mfg_date = d.get("Oem", {})
                            # HP iLO
                            if "Hp" in str(mfg_date) or "Hpe" in str(mfg_date):
                                hp_data = mfg_date.get("Hp", mfg_date.get("Hpe", {}))
                                if isinstance(hp_data, dict):
                                    hp_data = hp_data.get("PostState", {})
                            # Try generic fields
                            model_str = d.get("Model", "") or ""
                            sku = d.get("SKU", "") or ""
                            # Warranty end from Dell
                            warranty_end = ""
                            lifecycle = d.get("Oem", {}).get("Dell", {}).get("ServiceTag", "")
                            return {
                                "serial": serial,
                                "model": model_str or asset.get("model", ""),
                                "asset_name": asset.get("asset_name", ""),
                                "ip": ip,
                                "creds": uname,
                            }
                    except Exception:
                        continue
            except Exception:
                continue
        return None

    all_assets = []
    for rack_name, assets in inv.get("racks", {}).items():
        all_assets.extend(assets)

    results = []
    with _cf.ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(_fetch_one, a): a for a in all_assets}
        for fut in _cf.as_completed(futures):
            r = fut.result()
            if r:
                results.append(r)

    # For fetched assets, compute EOL from lookup and store
    conn = get_conn()
    cur = conn.cursor()
    stored = 0
    for r in results:
        eol = _match_eol(r.get("asset_name", ""), r.get("model", ""))
        if eol:
            cur.execute("""
                INSERT INTO asset_eol (serial, model, asset_name, site, eol_date, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, 'redfish', ?)
                ON CONFLICT(serial, site) DO UPDATE SET
                    eol_date=CASE WHEN asset_eol.source='manual' THEN asset_eol.eol_date ELSE excluded.eol_date END,
                    source=CASE WHEN asset_eol.source='manual' THEN 'manual' ELSE 'redfish' END,
                    fetched_at=excluded.fetched_at,
                    model=excluded.model,
                    asset_name=excluded.asset_name
            """, (r["serial"], r.get("model",""), r.get("asset_name",""), site, eol, _dt.datetime.now().isoformat()))
            stored += 1
    conn.commit()
    conn.close()

    return {"fetched": len(results), "stored": stored}


# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
#  AD & DNS MANAGEMENT ENDPOINTS
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
from ad_dns_client import (
    ad_list_users, ad_create_user, ad_set_enabled, ad_reset_password,
    ad_unlock_user, ad_delete_user,
    ad_list_groups, ad_create_group, ad_group_member, ad_delete_group,
    ad_list_ous, ad_list_computers,
    dns_list_zones, dns_list_records, dns_add_record, dns_delete_record,
    dns_flush_cache,
)

class ADCreateUserReq(BaseModel):
    username:         str
    display_name:     str
    password:         str
    ou_dn:            str = ""
    email:            str = ""
    department:       str = ""
    title:            str = ""
    pw_never_expires: bool = False
    must_change_pw:   bool = False

class ADSetEnabledReq(BaseModel):
    dn:      str
    enabled: bool

class ADResetPassReq(BaseModel):
    dn:       str
    password: str

class ADDNReq(BaseModel):
    dn: str

class ADCreateGroupReq(BaseModel):
    name:        str
    description: str = ""
    ou_dn:       str = ""

class ADGroupMemberReq(BaseModel):
    group_dn: str
    user_dn:  str
    add:      bool = True

class DNSAddRecordReq(BaseModel):
    zone:     str
    hostname: str
    rtype:    str
    data:     str
    ttl:      int = 3600

class DNSDeleteRecordReq(BaseModel):
    zone:     str
    hostname: str
    rtype:    str


# Ã¢â€â‚¬Ã¢â€â‚¬ AD Users Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/ad/users")
def ep_ad_list_users(q: str = "", u=Depends(require_role("admin", "operator"))):
    return ad_list_users(search=q)

@app.post("/api/ad/users")
def ep_ad_create_user(body: ADCreateUserReq, u=Depends(require_role("admin", "operator"))):
    result = ad_create_user(body.username, body.display_name, body.password,
                            body.ou_dn or None, body.email, body.department, body.title,
                            body.pw_never_expires, body.must_change_pw)
    if result.get("success"):
        audit(u["username"], "AD_CREATE_USER", detail=f"{body.username} ({body.display_name})")
    return result

@app.post("/api/ad/users/enable")
def ep_ad_set_enabled(body: ADSetEnabledReq, u=Depends(require_role("admin", "operator"))):
    result = ad_set_enabled(body.dn, body.enabled)
    if result.get("success"):
        audit(u["username"], "AD_USER_ENABLE" if body.enabled else "AD_USER_DISABLE",
              detail=body.dn.split(",")[0].replace("CN=", ""))
    return result

@app.post("/api/ad/users/reset-password")
def ep_ad_reset_password(body: ADResetPassReq, u=Depends(require_role("admin", "operator"))):
    result = ad_reset_password(body.dn, body.password)
    if result.get("success"):
        audit(u["username"], "AD_RESET_PASSWORD", detail=body.dn.split(",")[0].replace("CN=", ""))
    return result

@app.post("/api/ad/users/unlock")
def ep_ad_unlock_user(body: ADDNReq, u=Depends(require_role("admin", "operator"))):
    result = ad_unlock_user(body.dn)
    if result.get("success"):
        audit(u["username"], "AD_UNLOCK_USER", detail=body.dn.split(",")[0].replace("CN=", ""))
    return result

@app.delete("/api/ad/users")
def ep_ad_delete_user(body: ADDNReq, u=Depends(require_role("admin", "operator"))):
    result = ad_delete_user(body.dn)
    if result.get("success"):
        audit(u["username"], "AD_DELETE_USER", detail=body.dn.split(",")[0].replace("CN=", ""))
    return result


# Ã¢â€â‚¬Ã¢â€â‚¬ AD Groups Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/ad/groups")
def ep_ad_list_groups(q: str = "", u=Depends(require_role("admin", "operator"))):
    return ad_list_groups(search=q)

@app.post("/api/ad/groups")
def ep_ad_create_group(body: ADCreateGroupReq, u=Depends(require_role("admin", "operator"))):
    result = ad_create_group(body.name, body.description, body.ou_dn or None)
    if result.get("success"):
        audit(u["username"], "AD_CREATE_GROUP", detail=body.name)
    return result

@app.post("/api/ad/groups/member")
def ep_ad_group_member(body: ADGroupMemberReq, u=Depends(require_role("admin", "operator"))):
    result = ad_group_member(body.group_dn, body.user_dn, body.add)
    if result.get("success"):
        action = "AD_GROUP_ADD_MEMBER" if body.add else "AD_GROUP_REMOVE_MEMBER"
        audit(u["username"], action,
              detail=f"{body.group_dn.split(',')[0]} Ã¢â€ Â {body.user_dn.split(',')[0]}")
    return result

@app.delete("/api/ad/groups")
def ep_ad_delete_group(body: ADDNReq, u=Depends(require_role("admin", "operator"))):
    result = ad_delete_group(body.dn)
    if result.get("success"):
        audit(u["username"], "AD_DELETE_GROUP", detail=body.dn.split(",")[0].replace("CN=", ""))
    return result


# Ã¢â€â‚¬Ã¢â€â‚¬ AD OUs & Computers Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/ad/ous")
def ep_ad_list_ous(u=Depends(require_role("admin", "operator"))):
    return ad_list_ous()

@app.get("/api/ad/computers")
def ep_ad_list_computers(q: str = "", u=Depends(require_role("admin", "operator"))):
    return ad_list_computers(search=q)


# Ã¢â€â‚¬Ã¢â€â‚¬ DNS Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/dns/zones")
def ep_dns_list_zones(u=Depends(require_role("admin", "operator"))):
    return dns_list_zones()

@app.get("/api/dns/records")
def ep_dns_list_records(zone: str, u=Depends(require_role("admin", "operator"))):
    return dns_list_records(zone)

@app.post("/api/dns/records")
def ep_dns_add_record(body: DNSAddRecordReq, u=Depends(require_role("admin", "operator"))):
    result = dns_add_record(body.zone, body.hostname, body.rtype, body.data, body.ttl)
    if result.get("success"):
        audit(u["username"], "DNS_ADD_RECORD",
              detail=f"{body.hostname} {body.rtype} {body.data} in {body.zone}")
    return result

@app.delete("/api/dns/records")
def ep_dns_delete_record(body: DNSDeleteRecordReq, u=Depends(require_role("admin", "operator"))):
    result = dns_delete_record(body.zone, body.hostname, body.rtype)
    if result.get("success"):
        audit(u["username"], "DNS_DELETE_RECORD",
              detail=f"{body.hostname} {body.rtype} in {body.zone}")
    return result

@app.post("/api/dns/flush-cache")
def ep_dns_flush_cache(u=Depends(require_role("admin", "operator"))):
    result = dns_flush_cache()
    if result.get("success"):
        audit(u["username"], "DNS_FLUSH_CACHE", detail="DNS server cache cleared")
    return result


# Ã¢â€â‚¬Ã¢â€â‚¬ Nutanix routes Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

from nutanix_client import (
    init_nutanix_db,
    list_prism_centrals, get_prism_central, create_prism_central,
    update_prism_central, delete_prism_central,
    test_pc_connection,
    get_pc_overview, get_pc_clusters, get_pc_vms, get_pc_hosts,
    get_pc_storage_containers, get_pc_alerts, get_pc_networks,
    get_pc_images, provision_nutanix_vm,
    vm_power_action as ntx_vm_power,
    vm_snapshot    as ntx_vm_snapshot,
)

class NTXPCCreate(BaseModel):
    name:        str
    host:        str
    username:    str = ""
    password:    str = ""
    site:        str = "DC"
    description: str = ""

class NTXPCUpdate(BaseModel):
    name:        str | None = None
    host:        str | None = None
    username:    str | None = None
    password:    str | None = None
    site:        str | None = None
    description: str | None = None
    status:      str | None = None

class NTXVMPowerBody(BaseModel):
    action: str   # ON | OFF | REBOOT

class NTXVMSnapshotBody(BaseModel):
    name: str

try:
    init_nutanix_db()
except Exception as _ntx_e:
    log.warning(f"Nutanix DB init: {_ntx_e}")

# Ã¢â€â‚¬Ã¢â€â‚¬ Prism Central CRUD Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/nutanix/prism_centrals")
def ntx_list(u=Depends(require_role("admin", "operator", "viewer"))):
    return {"prism_centrals": list_prism_centrals()}

@app.post("/api/nutanix/prism_centrals")
def ntx_create(body: NTXPCCreate,
               u=Depends(require_role("admin"))):
    data = body.dict()
    data["created_by"] = u["username"]
    pc = create_prism_central(data)
    audit(u["username"], "NTX_PC_ADD",
          target=body.name, detail=f"host={body.host} site={body.site}",
          role=u["role"])
    return pc

@app.get("/api/nutanix/prism_centrals/{pc_id}")
def ntx_get(pc_id: int,
           u=Depends(require_role("admin", "operator", "viewer"))):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    from nutanix_client import _safe_pc
    return _safe_pc(pc)

@app.patch("/api/nutanix/prism_centrals/{pc_id}")
def ntx_update(pc_id: int, body: NTXPCUpdate,
               u=Depends(require_role("admin"))):
    data = {k: v for k, v in body.dict().items() if v is not None}
    pc = update_prism_central(pc_id, data)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    audit(u["username"], "NTX_PC_UPDATE", target=str(pc_id),
          detail=str({k: v for k, v in data.items() if k != "password"}),
          role=u["role"])
    return pc

@app.delete("/api/nutanix/prism_centrals/{pc_id}")
def ntx_delete(pc_id: int,
               u=Depends(require_role("admin"))):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    delete_prism_central(pc_id)
    audit(u["username"], "NTX_PC_DELETE",
          target=pc["name"], role=u["role"])
    return {"status": "ok"}

@app.post("/api/nutanix/prism_centrals/{pc_id}/test")
def ntx_test(pc_id: int,
             u=Depends(require_role("admin", "operator"))):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    result = test_pc_connection(pc)
    status = "connected" if result["reachable"] else "error"
    update_prism_central(pc_id, {"status": status})
    return result

# Ã¢â€â‚¬Ã¢â€â‚¬ Live data Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/nutanix/prism_centrals/{pc_id}/live/overview")
def ntx_overview(pc_id: int,
                 u=Depends(require_role("admin", "operator", "viewer"))):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    return get_pc_overview(pc)

@app.get("/api/nutanix/prism_centrals/{pc_id}/live/clusters")
def ntx_clusters(pc_id: int,
                 u=Depends(require_role("admin", "operator", "viewer"))):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    clusters = get_pc_clusters(pc)
    update_prism_central(pc_id, {"status": "connected"})
    return {"clusters": clusters, "count": len(clusters)}

@app.get("/api/nutanix/prism_centrals/{pc_id}/live/vms")
def ntx_vms(pc_id: int,
            u=Depends(require_role("admin", "operator", "viewer"))):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    vms = get_pc_vms(pc)
    return {"vms": vms, "count": len(vms)}

@app.get("/api/nutanix/prism_centrals/{pc_id}/live/hosts")
def ntx_hosts(pc_id: int,
              u=Depends(require_role("admin", "operator", "viewer"))):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    hosts = get_pc_hosts(pc)
    return {"hosts": hosts, "count": len(hosts)}

@app.get("/api/nutanix/prism_centrals/{pc_id}/live/storage")
def ntx_storage(pc_id: int,
                u=Depends(require_role("admin", "operator", "viewer"))):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    return {"containers": get_pc_storage_containers(pc)}

@app.get("/api/nutanix/prism_centrals/{pc_id}/live/alerts")
def ntx_alerts(pc_id: int,
               u=Depends(require_role("admin", "operator", "viewer"))):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    return {"alerts": get_pc_alerts(pc)}

@app.get("/api/nutanix/prism_centrals/{pc_id}/live/networks")
def ntx_networks(pc_id: int,
                 u=Depends(require_role("admin", "operator", "viewer"))):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    return {"networks": get_pc_networks(pc)}

# Ã¢â€â‚¬Ã¢â€â‚¬ VM actions Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.post("/api/nutanix/prism_centrals/{pc_id}/vms/{vm_uuid}/power")
def ntx_vm_power_ep(pc_id: int, vm_uuid: str, body: NTXVMPowerBody,
                    u=Depends(require_role("admin", "operator"))):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    result = ntx_vm_power(pc, vm_uuid, body.action)
    if result.get("success"):
        audit(u["username"], "NTX_VM_POWER",
              target=vm_uuid, detail=f"action={body.action}",
              role=u["role"])
    return result

@app.post("/api/nutanix/prism_centrals/{pc_id}/vms/{vm_uuid}/snapshot")
def ntx_vm_snapshot_ep(pc_id: int, vm_uuid: str, body: NTXVMSnapshotBody,
                       u=Depends(require_role("admin", "operator"))):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    result = ntx_vm_snapshot(pc, vm_uuid, body.name)
    if result.get("success"):
        audit(u["username"], "NTX_VM_SNAPSHOT",
              target=vm_uuid, detail=f"name={body.name}",
              role=u["role"])
    return result


# Ã¢â€â‚¬Ã¢â€â‚¬ Nutanix Images Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/nutanix/prism_centrals/{pc_id}/live/images")
def ntx_list_images(pc_id: int, u=Depends(get_current_user)):
    pc = get_prism_central(pc_id)
    if not pc: raise HTTPException(404, detail="Prism Central not found")
    return {"images": get_pc_images(pc)}


# Ã¢â€â‚¬Ã¢â€â‚¬ Nutanix VM Request (submit to pending queue) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class NTXVMRequestCreate(BaseModel):
    vm_name:            str
    cpu:                int
    num_cores_per_vcpu: int = 1
    ram_gb:             int
    disk_gb:            int = 0
    ntx_pc_id:          int
    ntx_pc_name:        str = ""
    ntx_cluster_uuid:   str
    ntx_cluster_name:   str = ""
    ntx_disks:          str = "[]"   # JSON string
    ntx_nics:           str = "[]"   # JSON string
    notes:              str = ""

@app.post("/api/nutanix/vm_requests")
def submit_ntx_request(body: NTXVMRequestCreate, u=Depends(get_current_user)):
    data = body.dict()
    data["requester"]   = u["username"]
    data["platform"]    = "nutanix"
    data["os_template"] = "nutanix-custom"
    data["vcenter_id"]  = f"ntx-{body.ntx_pc_id}"   # placeholder to satisfy NOT NULL
    req = create_vm_request(data)
    audit(u["username"], "NTX_VM_REQUEST_SUBMIT",
          target=req["req_number"],
          detail=f"vm={body.vm_name} cpu={body.cpu} ram={body.ram_gb}GB pc={body.ntx_pc_name} cluster={body.ntx_cluster_name}",
          role=u["role"])
    return req


# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
#  ANSIBLE AUTOMATION PLATFORM (AAP)
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
from ansible_client import (
    list_aap_instances, get_aap_instance, create_aap_instance,
    update_aap_instance, delete_aap_instance,
    test_aap_connection,
    get_aap_dashboard, get_aap_jobs, get_aap_job_templates,
    get_aap_inventories, get_aap_projects, get_aap_hosts,
    get_aap_credentials, get_aap_organizations, get_aap_users,
    get_aap_teams, get_aap_schedules,
    get_job_output,
    launch_job_template, cancel_job, delete_job,
    sync_inventory, sync_project,
    toggle_host, delete_host,
    toggle_schedule, delete_schedule,
    create_aap_user, delete_aap_user,
    delete_credential, delete_job_template,
    delete_inventory, delete_project,
    get_execution_environments, get_project_local_paths,
)

# Ã¢â€â‚¬Ã¢â€â‚¬ Pydantic models Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class AAPInstanceCreate(BaseModel):
    name:        str
    url:         str
    username:    str
    password:    str
    env:         str = "PROD"
    description: str = ""

class AAPInstanceUpdate(BaseModel):
    name:        str | None = None
    url:         str | None = None
    username:    str | None = None
    password:    str | None = None
    env:         str | None = None
    description: str | None = None

class AAPLaunchBody(BaseModel):
    extra_vars: str = ""

class AAPToggleBody(BaseModel):
    enabled: bool

class AAPCreateUserBody(BaseModel):
    username:     str
    password:     str
    first_name:   str = ""
    last_name:    str = ""
    email:        str = ""
    is_superuser: bool = False

# Ã¢â€â‚¬Ã¢â€â‚¬ Instance CRUD Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/ansible/instances")
def aap_list(u=Depends(require_role("admin","operator","viewer"))):
    return {"instances": list_aap_instances()}

@app.post("/api/ansible/instances")
def aap_create(body: AAPInstanceCreate, u=Depends(require_role("admin"))):
    inst = create_aap_instance(
        body.name, body.url, body.username, body.password,
        body.env, body.description, u["username"])
    audit(u["username"], "AAP_INSTANCE_ADD",
          target=body.name, detail=f"url={body.url} env={body.env}", role=u["role"])
    return inst

@app.patch("/api/ansible/instances/{inst_id}")
def aap_update(inst_id: int, body: AAPInstanceUpdate, u=Depends(require_role("admin"))):
    data = {k: v for k, v in body.dict().items() if v is not None}
    inst = update_aap_instance(inst_id, **data)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    audit(u["username"], "AAP_INSTANCE_UPDATE", target=str(inst_id),
          detail=str({k: v for k, v in data.items() if k != "password"}), role=u["role"])
    return inst

@app.delete("/api/ansible/instances/{inst_id}")
def aap_delete(inst_id: int, u=Depends(require_role("admin"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    delete_aap_instance(inst_id)
    audit(u["username"], "AAP_INSTANCE_DELETE", target=inst["name"], role=u["role"])
    return {"status": "ok"}

@app.post("/api/ansible/instances/{inst_id}/test")
def aap_test(inst_id: int, u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    return test_aap_connection(inst)

# Ã¢â€â‚¬Ã¢â€â‚¬ Live data Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/ansible/instances/{inst_id}/live/dashboard")
def aap_dashboard(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        return get_aap_dashboard(inst)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/jobs")
def aap_jobs(inst_id: int, limit: int = 100, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        return {"jobs": get_aap_jobs(inst, limit=limit), "count": limit}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/jobs/{job_id}/output")
def aap_job_output(inst_id: int, job_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    return {"output": get_job_output(inst, job_id)}

@app.get("/api/ansible/instances/{inst_id}/live/job_templates")
def aap_templates(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        items = get_aap_job_templates(inst)
        return {"job_templates": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/inventories")
def aap_inventories(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        items = get_aap_inventories(inst)
        return {"inventories": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/projects")
def aap_projects(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        items = get_aap_projects(inst)
        return {"projects": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/hosts")
def aap_hosts(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        items = get_aap_hosts(inst)
        return {"hosts": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/credentials")
def aap_credentials(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        items = get_aap_credentials(inst)
        return {"credentials": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/execution_environments")
def aap_execution_environments(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        items = get_execution_environments(inst)
        return {"execution_environments": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/project_local_paths")
def aap_project_local_paths(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    """Return available local_path directory names for Manual projects."""
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        paths = get_project_local_paths(inst)
        return {"paths": paths, "count": len(paths)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/organizations")
def aap_organizations(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        items = get_aap_organizations(inst)
        return {"organizations": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/users")
def aap_users(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        items = get_aap_users(inst)
        return {"users": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/teams")
def aap_teams(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        items = get_aap_teams(inst)
        return {"teams": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/schedules")
def aap_schedules(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        items = get_aap_schedules(inst)
        return {"schedules": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

# Ã¢â€â‚¬Ã¢â€â‚¬ Actions Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.post("/api/ansible/instances/{inst_id}/live/job_templates/{template_id}/launch")
def aap_launch(inst_id: int, template_id: int, body: AAPLaunchBody,
               u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = launch_job_template(inst, template_id, body.extra_vars)
        audit(u["username"], "AAP_JOB_LAUNCH",
              target=str(template_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/ansible/instances/{inst_id}/live/jobs/{job_id}/cancel")
def aap_cancel_job(inst_id: int, job_id: int,
                   u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = cancel_job(inst, job_id)
        audit(u["username"], "AAP_JOB_CANCEL",
              target=str(job_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/ansible/instances/{inst_id}/live/jobs/{job_id}")
def aap_delete_job(inst_id: int, job_id: int,
                   u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = delete_job(inst, job_id)
        audit(u["username"], "AAP_JOB_DELETE",
              target=str(job_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/ansible/instances/{inst_id}/live/job_templates/{template_id}")
def aap_delete_template(inst_id: int, template_id: int,
                         u=Depends(require_role("admin"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = delete_job_template(inst, template_id)
        audit(u["username"], "AAP_TEMPLATE_DELETE",
              target=str(template_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/ansible/instances/{inst_id}/live/inventories/{inv_id}/sync")
def aap_sync_inventory(inst_id: int, inv_id: int,
                        u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = sync_inventory(inst, inv_id)
        audit(u["username"], "AAP_INVENTORY_SYNC",
              target=str(inv_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/ansible/instances/{inst_id}/live/inventories/{inv_id}")
def aap_delete_inventory(inst_id: int, inv_id: int,
                          u=Depends(require_role("admin"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = delete_inventory(inst, inv_id)
        audit(u["username"], "AAP_INVENTORY_DELETE",
              target=str(inv_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/ansible/instances/{inst_id}/live/projects/{proj_id}/sync")
def aap_sync_project(inst_id: int, proj_id: int,
                      u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = sync_project(inst, proj_id)
        audit(u["username"], "AAP_PROJECT_SYNC",
              target=str(proj_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/ansible/instances/{inst_id}/live/projects/{proj_id}")
def aap_delete_project(inst_id: int, proj_id: int,
                        u=Depends(require_role("admin"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = delete_project(inst, proj_id)
        audit(u["username"], "AAP_PROJECT_DELETE",
              target=str(proj_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.patch("/api/ansible/instances/{inst_id}/live/hosts/{host_id}/toggle")
def aap_toggle_host(inst_id: int, host_id: int, body: AAPToggleBody,
                     u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = toggle_host(inst, host_id, body.enabled)
        audit(u["username"], "AAP_HOST_TOGGLE",
              target=str(host_id), detail=f"enabled={body.enabled} inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/ansible/instances/{inst_id}/live/hosts/{host_id}")
def aap_delete_host(inst_id: int, host_id: int,
                     u=Depends(require_role("admin"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = delete_host(inst, host_id)
        audit(u["username"], "AAP_HOST_DELETE",
              target=str(host_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/ansible/instances/{inst_id}/live/credentials/{cred_id}")
def aap_delete_credential(inst_id: int, cred_id: int,
                           u=Depends(require_role("admin"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = delete_credential(inst, cred_id)
        audit(u["username"], "AAP_CREDENTIAL_DELETE",
              target=str(cred_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.patch("/api/ansible/instances/{inst_id}/live/schedules/{sched_id}/toggle")
def aap_toggle_schedule(inst_id: int, sched_id: int, body: AAPToggleBody,
                         u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = toggle_schedule(inst, sched_id, body.enabled)
        audit(u["username"], "AAP_SCHEDULE_TOGGLE",
              target=str(sched_id), detail=f"enabled={body.enabled} inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/ansible/instances/{inst_id}/live/schedules/{sched_id}")
def aap_delete_schedule(inst_id: int, sched_id: int,
                         u=Depends(require_role("admin"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = delete_schedule(inst, sched_id)
        audit(u["username"], "AAP_SCHEDULE_DELETE",
              target=str(sched_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/ansible/instances/{inst_id}/live/users")
def aap_list_users(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        items = get_aap_users(inst)
        return {"users": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/ansible/instances/{inst_id}/live/users")
def aap_create_user(inst_id: int, body: AAPCreateUserBody,
                     u=Depends(require_role("admin"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = create_aap_user(inst, body.username, body.password,
                                  body.first_name, body.last_name,
                                  body.email, body.is_superuser)
        audit(u["username"], "AAP_USER_CREATE",
              target=body.username, detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/ansible/instances/{inst_id}/live/users/{user_id}")
def aap_delete_user(inst_id: int, user_id: int,
                     u=Depends(require_role("admin"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = delete_aap_user(inst, user_id)
        audit(u["username"], "AAP_USER_DELETE",
              target=str(user_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

# Ã¢â€â‚¬Ã¢â€â‚¬ Create / Update resources Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
from ansible_client import (
    create_job_template as _aap_create_tpl, update_job_template as _aap_update_tpl,
    create_inventory    as _aap_create_inv, update_inventory    as _aap_update_inv,
    create_project      as _aap_create_proj,update_project      as _aap_update_proj,
    create_credential   as _aap_create_cred,update_credential   as _aap_update_cred,
)

class AAPJobTemplateBody(BaseModel):
    name:          str
    description:   str = ""
    job_type:      str = "run"
    project:       int
    playbook:      str
    inventory:     int = 0
    credential:    int = 0
    verbosity:     int = 0
    extra_vars:    str = ""
    become_enabled:bool = False

class AAPJobTemplateUpdate(BaseModel):
    name:          str | None = None
    description:   str | None = None
    job_type:      str | None = None
    project:       int | None = None
    playbook:      str | None = None
    inventory:     int | None = None
    credential:    int | None = None
    verbosity:     int | None = None
    extra_vars:    str | None = None
    become_enabled:bool| None = None

class AAPInventoryBody(BaseModel):
    name:         str
    description:  str = ""
    organization: int
    kind:         str = ""
    variables:    str = ""

class AAPInventoryUpdate(BaseModel):
    name:         str | None = None
    description:  str | None = None
    organization: int | None = None
    kind:         str | None = None
    variables:    str | None = None

class AAPProjectBody(BaseModel):
    name:                    str
    description:             str  = ""
    organization:            int
    scm_type:                str  = "git"
    scm_url:                 str  = ""
    scm_branch:              str  = ""
    scm_clean:               bool = False
    scm_delete_on_update:    bool = False
    default_environment:     int | None = None   # execution environment id
    credential:              int | None = None   # SCM credential id (git/svn)
    local_path:              str | None = None   # manual projects only

class AAPProjectUpdate(BaseModel):
    name:                    str | None = None
    description:             str | None = None
    organization:            int | None = None
    scm_type:                str | None = None
    scm_url:                 str | None = None
    scm_branch:              str | None = None
    scm_clean:               bool| None = None
    scm_delete_on_update:    bool| None = None
    default_environment:     int | None = None
    credential:              int | None = None
    local_path:              str | None = None

class AAPCredentialBody(BaseModel):
    name:            str
    description:     str = ""
    organization:    int = 0
    credential_type: int
    inputs:          dict = {}

class AAPCredentialUpdate(BaseModel):
    name:         str | None = None
    description:  str | None = None
    organization: int | None = None
    inputs:       dict| None = None

@app.post("/api/ansible/instances/{inst_id}/live/job_templates")
def aap_create_template(inst_id: int, body: AAPJobTemplateBody,
                         u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    payload = {k: v for k, v in body.dict().items() if v not in (None, "", 0, False) or k in ("name","project","playbook")}
    if not payload.get("inventory"): payload.pop("inventory", None)
    if not payload.get("credential"): payload.pop("credential", None)
    try:
        result = _aap_create_tpl(inst, payload)
        audit(u["username"], "AAP_TEMPLATE_CREATE",
              target=body.name, detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.patch("/api/ansible/instances/{inst_id}/live/job_templates/{template_id}")
def aap_update_template(inst_id: int, template_id: int, body: AAPJobTemplateUpdate,
                         u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    payload = {k: v for k, v in body.dict().items() if v is not None}
    try:
        result = _aap_update_tpl(inst, template_id, payload)
        audit(u["username"], "AAP_TEMPLATE_UPDATE",
              target=str(template_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/ansible/instances/{inst_id}/live/inventories")
def aap_create_inventory_ep(inst_id: int, body: AAPInventoryBody,
                             u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    payload = body.dict()
    try:
        result = _aap_create_inv(inst, payload)
        audit(u["username"], "AAP_INVENTORY_CREATE",
              target=body.name, detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.patch("/api/ansible/instances/{inst_id}/live/inventories/{inv_id}")
def aap_update_inventory_ep(inst_id: int, inv_id: int, body: AAPInventoryUpdate,
                             u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    payload = {k: v for k, v in body.dict().items() if v is not None}
    try:
        result = _aap_update_inv(inst, inv_id, payload)
        audit(u["username"], "AAP_INVENTORY_UPDATE",
              target=str(inv_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/ansible/instances/{inst_id}/live/projects")
def aap_create_project_ep(inst_id: int, body: AAPProjectBody,
                           u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        # Strip None values so optional fields don't get sent as null
        payload = {k: v for k, v in body.dict().items() if v is not None}
        result = _aap_create_proj(inst, payload)
        audit(u["username"], "AAP_PROJECT_CREATE",
              target=body.name, detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.patch("/api/ansible/instances/{inst_id}/live/projects/{proj_id}")
def aap_update_project_ep(inst_id: int, proj_id: int, body: AAPProjectUpdate,
                           u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    payload = {k: v for k, v in body.dict().items() if v is not None}
    try:
        result = _aap_update_proj(inst, proj_id, payload)
        audit(u["username"], "AAP_PROJECT_UPDATE",
              target=str(proj_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/ansible/instances/{inst_id}/live/credentials")
def aap_create_credential_ep(inst_id: int, body: AAPCredentialBody,
                              u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    payload = body.dict()
    if not payload.get("organization"): payload.pop("organization", None)
    try:
        result = _aap_create_cred(inst, payload)
        audit(u["username"], "AAP_CREDENTIAL_CREATE",
              target=body.name, detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.patch("/api/ansible/instances/{inst_id}/live/credentials/{cred_id}")
def aap_update_credential_ep(inst_id: int, cred_id: int, body: AAPCredentialUpdate,
                              u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    payload = {k: v for k, v in body.dict().items() if v is not None}
    try:
        result = _aap_update_cred(inst, cred_id, payload)
        audit(u["username"], "AAP_CREDENTIAL_UPDATE",
              target=str(cred_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

# Ã¢â€â‚¬Ã¢â€â‚¬ Workflow Job Templates Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
from ansible_client import (
    get_aap_workflows          as _aap_get_wfs,
    launch_workflow_template   as _aap_launch_wf,
    create_workflow            as _aap_create_wf,
    update_workflow            as _aap_update_wf,
    delete_workflow            as _aap_delete_wf,
)

class AAPWorkflowBody(BaseModel):
    name:                 str
    description:          str = ""
    organization:         int = 0
    scm_branch:           str = ""
    extra_vars:           str = ""
    ask_limit_on_launch:  bool = False

class AAPWorkflowUpdate(BaseModel):
    name:                 Optional[str]  = None
    description:          Optional[str]  = None
    organization:         Optional[int]  = None
    scm_branch:           Optional[str]  = None
    extra_vars:           Optional[str]  = None
    ask_limit_on_launch:  Optional[bool] = None

@app.get("/api/ansible/instances/{inst_id}/live/workflow_job_templates")
def aap_list_workflows_ep(inst_id: int, u=Depends(require_role("admin","operator","viewer"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        return _aap_get_wfs(inst)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/ansible/instances/{inst_id}/live/workflow_job_templates")
def aap_create_workflow_ep(inst_id: int, body: AAPWorkflowBody,
                           u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    payload = body.dict()
    if not payload.get("organization"): payload.pop("organization", None)
    try:
        result = _aap_create_wf(inst, payload)
        audit(u["username"], "AAP_WORKFLOW_CREATE",
              target=body.name, detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.patch("/api/ansible/instances/{inst_id}/live/workflow_job_templates/{wf_id}")
def aap_update_workflow_ep(inst_id: int, wf_id: int, body: AAPWorkflowUpdate,
                           u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    payload = {k: v for k, v in body.dict().items() if v is not None}
    try:
        result = _aap_update_wf(inst, wf_id, payload)
        audit(u["username"], "AAP_WORKFLOW_UPDATE",
              target=str(wf_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/ansible/instances/{inst_id}/live/workflow_job_templates/{wf_id}")
def aap_delete_workflow_ep(inst_id: int, wf_id: int,
                           u=Depends(require_role("admin"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        _aap_delete_wf(inst, wf_id)
        audit(u["username"], "AAP_WORKFLOW_DELETE",
              target=str(wf_id), detail=f"inst={inst['name']}", role=u["role"])
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/ansible/instances/{inst_id}/live/workflow_job_templates/{wf_id}/launch")
def aap_launch_workflow_ep(inst_id: int, wf_id: int,
                           u=Depends(require_role("admin","operator"))):
    inst = get_aap_instance(inst_id)
    if not inst: raise HTTPException(404, detail="AAP instance not found")
    try:
        result = _aap_launch_wf(inst, wf_id)
        audit(u["username"], "AAP_WORKFLOW_LAUNCH",
              target=str(wf_id), detail=f"inst={inst['name']}", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

# Ã¢â€â‚¬Ã¢â€â‚¬ Storage Array endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
from storage_client import (
    get_volume_topology,
    list_arrays, get_array, create_array, delete_array, _set_status,
    test_connection, get_array_data,
    netapp_get_svms, netapp_get_aggregates,
    netapp_volume_create, netapp_volume_delete,
    netapp_snapshot_list, netapp_snapshot_create, netapp_snapshot_delete,
    netapp_igroup_create, netapp_igroup_delete,
    netapp_lun_create, netapp_lun_delete,
    update_console_url
)
from pydantic import BaseModel as _BM
from typing import Optional as _Opt

class StorageArrayCreate(_BM):
    vendor:      str
    name:        str
    ip:          str
    port:        _Opt[str] = ""
    username:    str
    password:    str
    api_token:   _Opt[str] = ""
    site:        _Opt[str] = "dc"
    capacity_tb: _Opt[float] = 0.0
    console_url: _Opt[str] = ""

class StorageTestReq(_BM):
    vendor:    str
    ip:        str
    port:      _Opt[str] = ""
    username:  str
    password:  str
    api_token: _Opt[str] = ""

@app.get("/api/storage/arrays")
def storage_list(u=Depends(require_role("admin","operator","viewer"))):
    return list_arrays()

@app.post("/api/storage/arrays", status_code=201)
def storage_create(body: StorageArrayCreate, u=Depends(require_role("admin","operator"))):
    try:
        # status=ok because connection was already verified by POST /api/storage/test
        arr = create_array({**body.dict(), "created_by": u["username"], "status": "ok"})
        audit(u["username"], "STORAGE_ADD", target=body.name,
              detail=f"{body.vendor} {body.ip}", role=u["role"])
        return arr
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

@app.delete("/api/storage/arrays/{arr_id}")
def storage_delete(arr_id: int, u=Depends(require_role("admin","operator"))):
    arr = get_array(arr_id)
    if not arr:
        raise HTTPException(404, detail="Array not found")
    delete_array(arr_id)
    audit(u["username"], "STORAGE_REMOVE", target=arr["name"], role=u["role"])
    return {"ok": True}

@app.post("/api/storage/test")
def storage_test(body: StorageTestReq, u=Depends(require_role("admin","operator"))):
    """Test connectivity WITHOUT saving. Returns {ok, message, system_info}."""
    result = test_connection(body.dict())
    return result


class ConsoleUrlUpdate(_BM):
    console_url: str

@app.patch("/api/storage/arrays/{arr_id}/console_url")
def storage_update_console(arr_id: int, body: ConsoleUrlUpdate, u=Depends(require_role("admin","operator"))):
    arr = get_array(arr_id)
    if not arr:
        raise HTTPException(404, detail="Array not found")
    updated = update_console_url(arr_id, body.console_url.strip())
    audit(u["username"], "STORAGE_CONSOLE_URL", target=arr["name"],
          detail=f"Console URL set to {body.console_url.strip()}", role=u["role"])
    return updated

@app.get("/api/storage/arrays/{arr_id}/data")
def storage_data(arr_id: int, u=Depends(require_role("admin","operator","viewer"))):
    """Fetch live data from the array Ã¢â‚¬â€ capacity, volumes, hosts, perf."""
    arr = get_array(arr_id)
    if not arr:
        raise HTTPException(404, detail="Array not found")
    try:
        data = get_array_data(arr)
        _arr_data_cache[arr_id] = {"data": data, "ts": time.time()}
        _set_status(arr_id, "ok")
        return data
    except Exception as e:
        _set_status(arr_id, "error")
        raise HTTPException(502, detail=f"Array unreachable: {str(e)}")


@app.get("/api/storage/arrays/{arr_id}/topology")
def storage_volume_topology(arr_id: int, volume: str, u=Depends(require_role("admin","operator","viewer"))):
    """Return full topology map for a single volume: hosts, IQNs, WWNs, LUN IDs, replication, ports."""
    arr = get_array(arr_id)
    if not arr:
        raise HTTPException(404, detail="Array not found")
    import concurrent.futures as _cf, time as _time
    _ckey = f"{arr_id}|{volume}"
    # Serve from cache if fresh (avoids repeated live array calls)
    _cached = _stor_topo_cache.get(_ckey)
    if _cached and (_time.time() - _cached["ts"]) < _STOR_TOPO_TTL:
        return _cached["data"]
    # Run entire topology fetch in a thread with 55s hard timeout.
    # HPE Nimble can take up to ~5s with parallel fetching (was 17s sequential).
    # This stays safely under uvicorn's 60s keep-alive timeout.
    def _fetch():
        # Reuse cached array data if available (avoids a second live API call)
        _ad = _arr_data_cache.get(arr_id)
        preloaded = _ad["data"] if _ad and (time.time() - _ad["ts"]) < _ARR_DATA_TTL else None
        topo = get_volume_topology(arr, volume, cached_data=preloaded)
        # Collect storage-side IQNs and WWNs from the topology connections
        # so the vCenter mapper can cross-match them against ESXi HBA data
        stor_iqns = []
        stor_wwns = []
        for conn in (topo.get("topology") or []):
            stor_iqns.extend([q for q in (conn.get("iqns") or []) if q])
            stor_wwns.extend([w for w in (conn.get("wwns") or []) if w])
        try:
            naa = topo.get("naa_id", "") or ""
            wwn = topo.get("wwn",    "") or ""
            if naa or wwn:
                # get_volume_vcenter_mapping now scans all vCenters in parallel internally
                topo["vcenter_mapping"] = get_volume_vcenter_mapping(
                    naa_id=naa, wwn=wwn,
                    storage_iqns=stor_iqns,
                    storage_wwns=stor_wwns,
                )
            else:
                topo["vcenter_mapping"] = []
        except Exception:
            topo["vcenter_mapping"] = []
        return topo
    try:
        with _cf.ThreadPoolExecutor(max_workers=1) as _ex:
            _fut = _ex.submit(_fetch)
            try:
                # 120s: array fetch (~17s Nimble worst case) + parallel vCenter scan (~15s)
                result = _fut.result(timeout=120)
            except _cf.TimeoutError:
                raise HTTPException(504, detail="Topology fetch timed out. The storage array may be slow to respond.")
        _stor_topo_cache[_ckey] = {"data": result, "ts": _time.time()}
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, detail=f"Topology fetch failed: {str(e)}")

# Ã¢â€â‚¬Ã¢â€â‚¬ NetApp Admin Operations Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
def _netapp_arr(arr_id: int):
    arr = get_array(arr_id)
    if not arr: raise HTTPException(404, detail="Array not found")
    if arr["vendor"] != "NetApp": raise HTTPException(400, detail="Only supported for NetApp arrays")
    return arr

class _NVolumeCreate(_BM):
    name:         str
    svm_name:     str
    size_bytes:   int
    type:         _Opt[str] = "rw"
    guarantee:    _Opt[str] = "none"
    aggregate:    _Opt[str] = ""
    junction_path:_Opt[str] = ""

class _NLunCreate(_BM):
    name:       str
    svm_name:   str
    size_bytes: int
    os_type:    _Opt[str] = "linux"
    volume:     _Opt[str] = ""
    path:       _Opt[str] = ""

class _NIgroupCreate(_BM):
    name:       str
    svm_name:   str
    protocol:   _Opt[str] = "iscsi"
    os_type:    _Opt[str] = "linux"
    initiators: _Opt[_List[str]] = []

class _NSnapCreate(_BM):
    name: str

@app.get("/api/storage/arrays/{arr_id}/netapp/svms")
def netapp_svms(arr_id: int, u=Depends(require_role("admin","operator"))):
    arr = _netapp_arr(arr_id)
    try: return netapp_get_svms(arr)
    except Exception as e: raise HTTPException(502, detail=str(e))

@app.get("/api/storage/arrays/{arr_id}/netapp/aggregates")
def netapp_aggs(arr_id: int, u=Depends(require_role("admin","operator"))):
    arr = _netapp_arr(arr_id)
    try: return netapp_get_aggregates(arr)
    except Exception as e: raise HTTPException(502, detail=str(e))

@app.post("/api/storage/arrays/{arr_id}/netapp/volumes", status_code=201)
def netapp_vol_create(arr_id: int, body: _NVolumeCreate, u=Depends(require_role("admin"))):
    arr = _netapp_arr(arr_id)
    try:
        res = netapp_volume_create(arr, body.dict())
        audit(u["username"], "NETAPP_VOL_CREATE", target=body.name, detail=f"{body.svm_name} {body.size_bytes}B", role=u["role"])
        return res
    except ValueError as e: raise HTTPException(400, detail=str(e))
    except Exception as e: raise HTTPException(502, detail=str(e))

@app.delete("/api/storage/arrays/{arr_id}/netapp/volumes/{vol_uuid}")
def netapp_vol_delete(arr_id: int, vol_uuid: str, u=Depends(require_role("admin"))):
    arr = _netapp_arr(arr_id)
    try:
        res = netapp_volume_delete(arr, vol_uuid)
        audit(u["username"], "NETAPP_VOL_DELETE", target=vol_uuid, role=u["role"])
        return res
    except ValueError as e: raise HTTPException(400, detail=str(e))
    except Exception as e: raise HTTPException(502, detail=str(e))

@app.get("/api/storage/arrays/{arr_id}/netapp/volumes/{vol_uuid}/snapshots")
def netapp_snap_list(arr_id: int, vol_uuid: str, u=Depends(require_role("admin","operator","viewer"))):
    arr = _netapp_arr(arr_id)
    try: return netapp_snapshot_list(arr, vol_uuid)
    except Exception as e: raise HTTPException(502, detail=str(e))

@app.post("/api/storage/arrays/{arr_id}/netapp/volumes/{vol_uuid}/snapshots", status_code=201)
def netapp_snap_create(arr_id: int, vol_uuid: str, body: _NSnapCreate, u=Depends(require_role("admin","operator"))):
    arr = _netapp_arr(arr_id)
    try:
        res = netapp_snapshot_create(arr, vol_uuid, body.name)
        audit(u["username"], "NETAPP_SNAP_CREATE", target=body.name, role=u["role"])
        return res
    except ValueError as e: raise HTTPException(400, detail=str(e))
    except Exception as e: raise HTTPException(502, detail=str(e))

@app.delete("/api/storage/arrays/{arr_id}/netapp/volumes/{vol_uuid}/snapshots/{snap_uuid}")
def netapp_snap_delete(arr_id: int, vol_uuid: str, snap_uuid: str, u=Depends(require_role("admin","operator"))):
    arr = _netapp_arr(arr_id)
    try:
        res = netapp_snapshot_delete(arr, vol_uuid, snap_uuid)
        audit(u["username"], "NETAPP_SNAP_DELETE", target=snap_uuid, role=u["role"])
        return res
    except ValueError as e: raise HTTPException(400, detail=str(e))
    except Exception as e: raise HTTPException(502, detail=str(e))

@app.post("/api/storage/arrays/{arr_id}/netapp/igroups", status_code=201)
def netapp_ig_create(arr_id: int, body: _NIgroupCreate, u=Depends(require_role("admin"))):
    arr = _netapp_arr(arr_id)
    try:
        res = netapp_igroup_create(arr, body.dict())
        audit(u["username"], "NETAPP_IGROUP_CREATE", target=body.name, role=u["role"])
        return res
    except ValueError as e: raise HTTPException(400, detail=str(e))
    except Exception as e: raise HTTPException(502, detail=str(e))

@app.delete("/api/storage/arrays/{arr_id}/netapp/igroups/{ig_uuid}")
def netapp_ig_delete(arr_id: int, ig_uuid: str, u=Depends(require_role("admin"))):
    arr = _netapp_arr(arr_id)
    try:
        res = netapp_igroup_delete(arr, ig_uuid)
        audit(u["username"], "NETAPP_IGROUP_DELETE", target=ig_uuid, role=u["role"])
        return res
    except ValueError as e: raise HTTPException(400, detail=str(e))
    except Exception as e: raise HTTPException(502, detail=str(e))

@app.post("/api/storage/arrays/{arr_id}/netapp/luns", status_code=201)
def netapp_lun_create_ep(arr_id: int, body: _NLunCreate, u=Depends(require_role("admin"))):
    arr = _netapp_arr(arr_id)
    try:
        res = netapp_lun_create(arr, body.dict())
        audit(u["username"], "NETAPP_LUN_CREATE", target=body.name, role=u["role"])
        return res
    except ValueError as e: raise HTTPException(400, detail=str(e))
    except Exception as e: raise HTTPException(502, detail=str(e))

@app.delete("/api/storage/arrays/{arr_id}/netapp/luns/{lun_uuid}")
def netapp_lun_delete_ep(arr_id: int, lun_uuid: str, u=Depends(require_role("admin"))):
    arr = _netapp_arr(arr_id)
    try:
        res = netapp_lun_delete(arr, lun_uuid)
        audit(u["username"], "NETAPP_LUN_DELETE", target=lun_uuid, role=u["role"])
        return res
    except ValueError as e: raise HTTPException(400, detail=str(e))
    except Exception as e: raise HTTPException(502, detail=str(e))


# Ã¢â€â‚¬Ã¢â€â‚¬ Rubrik Security Cloud endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
from rubrik_client import (
    list_connections  as rubrik_list,
    get_connection    as rubrik_get,
    create_connection as rubrik_create,
    delete_connection as rubrik_delete,
    test_connection   as rubrik_test,
    get_rubrik_data,
    _set_status       as rubrik_set_status,
    on_demand_snapshot     as rubrik_snapshot,
    bulk_on_demand_snapshot as rubrik_bulk_snapshot,
    assign_sla             as rubrik_assign_sla,
    unassign_sla           as rubrik_unassign_sla,
    live_mount             as rubrik_live_mount,
    export_vm              as rubrik_export_vm,
    instant_recovery       as rubrik_instant_recover,
    file_recovery          as rubrik_file_recover,
    download_snapshot_files as rubrik_download_files,
    delete_snapshot        as rubrik_delete_snap,
    pause_resume_sla       as rubrik_pause_sla,
    pause_resume_cluster   as rubrik_pause_cluster,
    list_vm_snapshots      as rubrik_vm_snapshots,
    retry_failed_job       as rubrik_retry_job,
    search_vms             as rubrik_search_vms,
)

class RubrikConnCreate(_BM):
    name:          str = ""
    url:           str = ""
    client_id:     str = ""
    client_secret: str = ""
    username:      str = ""
    password:      str = ""

class RubrikTestReq(_BM):
    url:           str = ""
    client_id:     str = ""
    client_secret: str = ""
    username:      str = ""
    password:      str = ""

@app.get("/api/rubrik/connections")
def rubrik_list_ep(u=Depends(require_role("admin","operator","viewer"))):
    return rubrik_list()

@app.post("/api/rubrik/connections", status_code=201)
def rubrik_create_ep(body: RubrikConnCreate, u=Depends(require_role("admin","operator"))):
    try:
        d = body.dict()
        # Auto-generate name from client_id if not provided
        if not d.get("name"):
            cid = d.get("client_id", "")
            d["name"] = f"RSC-{cid[:8]}" if cid else f"RSC-{u['username']}"
        # Default RSC URL if not provided
        if not d.get("url"):
            d["url"] = "https://wipro.my.rubrik.com"
        conn = rubrik_create({**d, "created_by": u["username"]})
        audit(u["username"], "RUBRIK_ADD", target=body.name, detail=body.url, role=u["role"])
        return conn
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.delete("/api/rubrik/connections/{cid}")
def rubrik_delete_ep(cid: int, u=Depends(require_role("admin","operator"))):
    c = rubrik_get(cid)
    if not c: raise HTTPException(404, detail="Connection not found")
    rubrik_delete(cid)
    audit(u["username"], "RUBRIK_REMOVE", target=c["name"], role=u["role"])
    return {"ok": True}

@app.post("/api/rubrik/test")
def rubrik_test_ep(body: RubrikTestReq, u=Depends(require_role("admin","operator"))):
    return rubrik_test(body.dict())

@app.get("/api/rubrik/connections/{cid}/data")
def rubrik_data_ep(cid: int, u=Depends(require_role("admin","operator","viewer"))):
    c = rubrik_get(cid)
    if not c: raise HTTPException(404, detail="Connection not found")
    try:
        data = get_rubrik_data(c)
        rubrik_set_status(cid, "ok")
        return data
    except Exception as e:
        rubrik_set_status(cid, "error")
        raise HTTPException(502, detail=f"Rubrik unreachable: {str(e)}")

# Ã¢â€â‚¬Ã¢â€â‚¬ Rubrik Management Operations (admin + operator) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class RubrikActionBody(_BM):
    vm_id:         str = ""
    vm_ids:        list = []
    sla_id:        str = ""
    object_ids:    list = []
    snapshot_id:   str = ""
    host_id:       str = ""
    datastore_id:  str = ""
    vm_name:       str = ""
    power_on:      bool = False
    paths:         list = []
    location:      str = "ALL"
    cluster_uuids: list = []
    pause:         bool = True
    preserve_moid: bool = True
    query:         str = ""

def _rubrik_conn(cid: int):
    c = rubrik_get(cid)
    if not c: raise HTTPException(404, detail="Connection not found")
    return c

@app.post("/api/rubrik/connections/{cid}/snapshot")
def rubrik_snapshot_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_snapshot(c, body.vm_id, body.sla_id or None)
        audit(u["username"], "RUBRIK_SNAPSHOT", target=body.vm_id, role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/rubrik/connections/{cid}/bulk-snapshot")
def rubrik_bulk_snap_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_bulk_snapshot(c, body.vm_ids, body.sla_id or None)
        audit(u["username"], "RUBRIK_BULK_SNAPSHOT", detail=f"{len(body.vm_ids)} VMs", role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/rubrik/connections/{cid}/assign-sla")
def rubrik_assign_sla_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_assign_sla(c, body.object_ids, body.sla_id)
        audit(u["username"], "RUBRIK_ASSIGN_SLA", target=body.sla_id, detail=f"{len(body.object_ids)} objects", role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/rubrik/connections/{cid}/unassign-sla")
def rubrik_unassign_sla_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_unassign_sla(c, body.object_ids)
        audit(u["username"], "RUBRIK_UNASSIGN_SLA", detail=f"{len(body.object_ids)} objects", role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/rubrik/connections/{cid}/live-mount")
def rubrik_live_mount_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_live_mount(c, body.snapshot_id, body.host_id or None, body.power_on)
        audit(u["username"], "RUBRIK_LIVE_MOUNT", target=body.snapshot_id, role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/rubrik/connections/{cid}/export-vm")
def rubrik_export_vm_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_export_vm(c, body.snapshot_id, body.host_id, body.datastore_id or None, body.vm_name or None, body.power_on)
        audit(u["username"], "RUBRIK_EXPORT_VM", target=body.snapshot_id, detail=body.vm_name, role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/rubrik/connections/{cid}/instant-recovery")
def rubrik_instant_recover_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_instant_recover(c, body.snapshot_id, body.host_id or None, body.preserve_moid)
        audit(u["username"], "RUBRIK_INSTANT_RECOVERY", target=body.snapshot_id, role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/rubrik/connections/{cid}/file-recovery")
def rubrik_file_recover_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_file_recover(c, body.snapshot_id, body.paths)
        audit(u["username"], "RUBRIK_FILE_RECOVERY", target=body.snapshot_id, detail=str(body.paths[:3]), role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/rubrik/connections/{cid}/download-files")
def rubrik_download_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_download_files(c, body.snapshot_id, body.paths)
        audit(u["username"], "RUBRIK_DOWNLOAD_FILES", target=body.snapshot_id, role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/rubrik/connections/{cid}/delete-snapshot")
def rubrik_delete_snap_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_delete_snap(c, body.snapshot_id, body.location)
        audit(u["username"], "RUBRIK_DELETE_SNAPSHOT", target=body.snapshot_id, role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/rubrik/connections/{cid}/pause-sla")
def rubrik_pause_sla_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_pause_sla(c, body.sla_id, body.cluster_uuids, body.pause)
        audit(u["username"], "RUBRIK_PAUSE_SLA" if body.pause else "RUBRIK_RESUME_SLA", target=body.sla_id, role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/rubrik/connections/{cid}/pause-cluster")
def rubrik_pause_cluster_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_pause_cluster(c, body.cluster_uuids, body.pause)
        audit(u["username"], "RUBRIK_PAUSE_CLUSTER" if body.pause else "RUBRIK_RESUME_CLUSTER", role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.get("/api/rubrik/connections/{cid}/vms/{vm_id}/snapshots")
def rubrik_vm_snapshots_ep(cid: int, vm_id: str, u=Depends(require_role("admin","operator","viewer"))):
    c = _rubrik_conn(cid)
    try: return rubrik_vm_snapshots(c, vm_id)
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/rubrik/connections/{cid}/retry-job")
def rubrik_retry_ep(cid: int, body: RubrikActionBody, u=Depends(require_role("admin","operator"))):
    c = _rubrik_conn(cid)
    try:
        r = rubrik_retry_job(c, body.object_ids)
        audit(u["username"], "RUBRIK_RETRY_JOB", detail=f"{len(body.object_ids)} objects", role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.get("/api/rubrik/connections/{cid}/search-vms")
def rubrik_search_ep(cid: int, q: str = "", u=Depends(require_role("admin","operator","viewer"))):
    c = _rubrik_conn(cid)
    try: return rubrik_search_vms(c, q)
    except Exception as e: raise HTTPException(400, detail=str(e))

# Ã¢â€â‚¬Ã¢â€â‚¬ Cohesity DataProtect endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
from cohesity_client import (
    ch_list_connections   as ch_list,
    ch_get_connection     as ch_get,
    ch_create_connection  as ch_create,
    ch_delete_connection  as ch_delete,
    ch_test_connection    as ch_test,
    ch_set_status         as ch_set_status,
    get_cohesity_data,
    ch_run_job,
    ch_cancel_job_run,
    ch_pause_job,
    ch_delete_job,
    ch_update_job,
    ch_create_job,
    ch_resolve_alert,
    ch_get_job_runs,
    ch_recover_vm,
    ch_search_objects,
    ch_get_object_snapshots,
    ch_assign_policy,
    ch_get_sources_tree,
)

class CohesityConnCreate(_BM):
    name:     str = ""
    url:      str = ""
    username: str = ""
    password: str = ""
    domain:   str = "LOCAL"

class CohesityTestReq(_BM):
    url:      str = ""
    username: str = ""
    password: str = ""
    domain:   str = "LOCAL"

class CohesityActionBody(_BM):
    job_id:          int = 0
    run_id:          int = 0
    run_type:        str = "kRegular"
    pause:           bool = True
    delete_snapshots:bool = False
    alert_id:        str = ""
    policy_id:       str = ""
    object_id:       int = 0
    query:           str = ""
    environments:    str = ""
    body:            dict = {}

def _cohesity_conn(cid):
    c = ch_get(cid)
    if not c: raise HTTPException(404, detail="Connection not found")
    return c

@app.get("/api/cohesity/connections")
def cohesity_list_ep(u=Depends(require_role("admin","operator","viewer"))):
    return ch_list()

@app.post("/api/cohesity/connections", status_code=201)
def cohesity_create_ep(body: CohesityConnCreate, u=Depends(require_role("admin","operator"))):
    try:
        d = body.dict()
        if not d.get("name"): d["name"] = f"Cohesity-{d.get('url','')[:20]}"
        conn = ch_create({**d, "created_by": u["username"]})
        audit(u["username"], "COHESITY_ADD", target=body.name, detail=body.url, role=u["role"])
        return conn
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.delete("/api/cohesity/connections/{cid}")
def cohesity_delete_ep(cid: int, u=Depends(require_role("admin","operator"))):
    c = ch_get(cid)
    if not c: raise HTTPException(404, detail="Connection not found")
    ch_delete(cid)
    audit(u["username"], "COHESITY_REMOVE", target=c["name"], role=u["role"])
    return {"ok": True}

@app.post("/api/cohesity/test")
def cohesity_test_ep(body: CohesityTestReq, u=Depends(require_role("admin","operator"))):
    return ch_test(body.dict())

@app.get("/api/cohesity/connections/{cid}/data")
def cohesity_data_ep(cid: int, u=Depends(require_role("admin","operator","viewer"))):
    c = _cohesity_conn(cid)
    try:
        data = get_cohesity_data(c)
        ch_set_status(cid, "ok")
        return data
    except Exception as e:
        ch_set_status(cid, "error")
        raise HTTPException(502, detail=f"Cohesity unreachable: {str(e)}")

# Ã¢â€â‚¬Ã¢â€â‚¬ Cohesity Management Operations (admin + operator) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.post("/api/cohesity/connections/{cid}/run-job")
def cohesity_run_job_ep(cid: int, body: CohesityActionBody, u=Depends(require_role("admin","operator"))):
    c = _cohesity_conn(cid)
    try:
        r = ch_run_job(c, body.job_id, body.run_type)
        audit(u["username"], "COHESITY_RUN_JOB", target=str(body.job_id), role=u["role"])
        return {"ok": True, "message": f"Job {body.job_id} triggered", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/cohesity/connections/{cid}/cancel-run")
def cohesity_cancel_run_ep(cid: int, body: CohesityActionBody, u=Depends(require_role("admin","operator"))):
    c = _cohesity_conn(cid)
    try:
        r = ch_cancel_job_run(c, body.job_id, body.run_id)
        audit(u["username"], "COHESITY_CANCEL_RUN", target=str(body.job_id), role=u["role"])
        return {"ok": True, "message": "Run cancelled", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/cohesity/connections/{cid}/pause-job")
def cohesity_pause_job_ep(cid: int, body: CohesityActionBody, u=Depends(require_role("admin","operator"))):
    c = _cohesity_conn(cid)
    try:
        r = ch_pause_job(c, body.job_id, body.pause)
        action = "paused" if body.pause else "resumed"
        audit(u["username"], f"COHESITY_JOB_{action.upper()}", target=str(body.job_id), role=u["role"])
        return {"ok": True, "message": f"Job {body.job_id} {action}", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/cohesity/connections/{cid}/delete-job")
def cohesity_delete_job_ep(cid: int, body: CohesityActionBody, u=Depends(require_role("admin","operator"))):
    c = _cohesity_conn(cid)
    try:
        r = ch_delete_job(c, body.job_id, body.delete_snapshots)
        audit(u["username"], "COHESITY_DELETE_JOB", target=str(body.job_id), role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/cohesity/connections/{cid}/update-job")
def cohesity_update_job_ep(cid: int, body: CohesityActionBody, u=Depends(require_role("admin","operator"))):
    c = _cohesity_conn(cid)
    try:
        r = ch_update_job(c, body.job_id, body.body)
        audit(u["username"], "COHESITY_UPDATE_JOB", target=str(body.job_id), role=u["role"])
        return {"ok": True, "message": "Job updated", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/cohesity/connections/{cid}/create-job")
def cohesity_create_job_ep(cid: int, body: CohesityActionBody, u=Depends(require_role("admin","operator"))):
    c = _cohesity_conn(cid)
    try:
        r = ch_create_job(c, body.body)
        audit(u["username"], "COHESITY_CREATE_JOB", target="new", role=u["role"])
        return {"ok": True, "message": "Job created", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/cohesity/connections/{cid}/resolve-alert")
def cohesity_resolve_alert_ep(cid: int, body: CohesityActionBody, u=Depends(require_role("admin","operator"))):
    c = _cohesity_conn(cid)
    try:
        r = ch_resolve_alert(c, body.alert_id)
        audit(u["username"], "COHESITY_RESOLVE_ALERT", target=body.alert_id, role=u["role"])
        return r
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.get("/api/cohesity/connections/{cid}/job-runs/{job_id}")
def cohesity_job_runs_ep(cid: int, job_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = _cohesity_conn(cid)
    try: return ch_get_job_runs(c, job_id)
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/cohesity/connections/{cid}/recover")
def cohesity_recover_ep(cid: int, body: CohesityActionBody, u=Depends(require_role("admin","operator"))):
    c = _cohesity_conn(cid)
    try:
        r = ch_recover_vm(c, body.body)
        audit(u["username"], "COHESITY_RECOVER", target="recovery", role=u["role"])
        return {"ok": True, "message": "Recovery started", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.get("/api/cohesity/connections/{cid}/search-objects")
def cohesity_search_objects_ep(cid: int, q: str = "", env: str = "", u=Depends(require_role("admin","operator","viewer"))):
    c = _cohesity_conn(cid)
    try: return ch_search_objects(c, q or "*", env or None)
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.get("/api/cohesity/connections/{cid}/object-snapshots/{object_id}")
def cohesity_object_snaps_ep(cid: int, object_id: int, u=Depends(require_role("admin","operator","viewer"))):
    c = _cohesity_conn(cid)
    try: return ch_get_object_snapshots(c, object_id)
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/cohesity/connections/{cid}/assign-policy")
def cohesity_assign_policy_ep(cid: int, body: CohesityActionBody, u=Depends(require_role("admin","operator"))):
    c = _cohesity_conn(cid)
    try:
        r = ch_assign_policy(c, body.job_id, body.policy_id)
        audit(u["username"], "COHESITY_ASSIGN_POLICY", target=str(body.job_id), role=u["role"])
        return {"ok": True, "message": f"Policy assigned to job {body.job_id}", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.get("/api/cohesity/connections/{cid}/sources")
def cohesity_sources_ep(cid: int, env: str = "", u=Depends(require_role("admin","operator","viewer"))):
    c = _cohesity_conn(cid)
    try: return ch_get_sources_tree(c, env or None)
    except Exception as e: raise HTTPException(400, detail=str(e))

# Ã¢â€â‚¬Ã¢â€â‚¬ Veeam Backup & Replication endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
from veeam_client import (
    vm_list_connections    as _vm_list,
    vm_get_connection      as _vm_get,
    vm_create_connection   as _vm_create,
    vm_delete_connection   as _vm_delete,
    vm_test_connection     as _vm_test,
    get_veeam_data         as _vm_data,
    vm_start_job           as _vm_start_job,
    vm_stop_job            as _vm_stop_job,
    vm_enable_job          as _vm_enable_job,
    vm_disable_job         as _vm_disable_job,
    vm_delete_job          as _vm_delete_job,
    vm_get_job_sessions    as _vm_job_sessions,
    vm_retry_session       as _vm_retry_session,
    vm_stop_session        as _vm_stop_session,
    vm_instant_recovery    as _vm_instant_recovery,
    vm_search_objects      as _vm_search_objects,
)

class VeeamConnCreate(_BM):
    name: str
    url: str
    port: int = 9419
    username: str = ""
    password: str = ""

class VeeamTestReq(_BM):
    url: str
    port: int = 9419
    username: str = ""
    password: str = ""

class VeeamActionBody(_BM):
    job_id: str = ""
    session_id: str = ""
    restore_point_id: str = ""
    query: str = ""
    body: dict = {}

def _veeam_conn(cid: int):
    c = _vm_get(cid)
    if not c: raise HTTPException(404, detail="Veeam connection not found")
    return c

@app.get("/api/veeam/connections")
def veeam_list_ep(u=Depends(require_role("admin","operator","viewer"))):
    return _vm_list()

@app.post("/api/veeam/connections")
def veeam_create_ep(body: VeeamConnCreate, u=Depends(require_role("admin","operator"))):
    d = body.dict()
    d["created_by"] = u["username"]
    r = _vm_create(d)
    audit(u["username"], "VEEAM_ADD", target=body.url, role=u["role"])
    return r

@app.delete("/api/veeam/connections/{cid}")
def veeam_delete_ep(cid: int, u=Depends(require_role("admin","operator"))):
    _veeam_conn(cid)
    _vm_delete(cid)
    audit(u["username"], "VEEAM_DEL", target=str(cid), role=u["role"])
    return {"ok": True}

@app.post("/api/veeam/test")
def veeam_test_ep(body: VeeamTestReq, u=Depends(require_role("admin","operator"))):
    return _vm_test(body.dict())

@app.get("/api/veeam/connections/{cid}/data")
def veeam_data_ep(cid: int, u=Depends(require_role("admin","operator","viewer"))):
    c = _veeam_conn(cid)
    try: return _vm_data(c)
    except Exception as e: raise HTTPException(400, detail=str(e))

# Ã¢â€â‚¬Ã¢â€â‚¬ Veeam Management Operations Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.post("/api/veeam/connections/{cid}/start-job")
def veeam_start_job_ep(cid: int, body: VeeamActionBody, u=Depends(require_role("admin","operator"))):
    c = _veeam_conn(cid)
    try:
        r = _vm_start_job(c, body.job_id)
        audit(u["username"], "VEEAM_START_JOB", target=body.job_id, role=u["role"])
        return {"ok": True, "message": f"Job started", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/veeam/connections/{cid}/stop-job")
def veeam_stop_job_ep(cid: int, body: VeeamActionBody, u=Depends(require_role("admin","operator"))):
    c = _veeam_conn(cid)
    try:
        r = _vm_stop_job(c, body.job_id)
        audit(u["username"], "VEEAM_STOP_JOB", target=body.job_id, role=u["role"])
        return {"ok": True, "message": "Job stopped", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/veeam/connections/{cid}/enable-job")
def veeam_enable_job_ep(cid: int, body: VeeamActionBody, u=Depends(require_role("admin","operator"))):
    c = _veeam_conn(cid)
    try:
        r = _vm_enable_job(c, body.job_id)
        audit(u["username"], "VEEAM_ENABLE_JOB", target=body.job_id, role=u["role"])
        return {"ok": True, "message": "Job enabled", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/veeam/connections/{cid}/disable-job")
def veeam_disable_job_ep(cid: int, body: VeeamActionBody, u=Depends(require_role("admin","operator"))):
    c = _veeam_conn(cid)
    try:
        r = _vm_disable_job(c, body.job_id)
        audit(u["username"], "VEEAM_DISABLE_JOB", target=body.job_id, role=u["role"])
        return {"ok": True, "message": "Job disabled", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/veeam/connections/{cid}/delete-job")
def veeam_delete_job_ep(cid: int, body: VeeamActionBody, u=Depends(require_role("admin","operator"))):
    c = _veeam_conn(cid)
    try:
        r = _vm_delete_job(c, body.job_id)
        audit(u["username"], "VEEAM_DELETE_JOB", target=body.job_id, role=u["role"])
        return {"ok": True, "message": "Job deleted", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.get("/api/veeam/connections/{cid}/job-sessions/{job_id}")
def veeam_job_sessions_ep(cid: int, job_id: str, u=Depends(require_role("admin","operator","viewer"))):
    c = _veeam_conn(cid)
    try: return _vm_job_sessions(c, job_id)
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/veeam/connections/{cid}/retry-session")
def veeam_retry_session_ep(cid: int, body: VeeamActionBody, u=Depends(require_role("admin","operator"))):
    c = _veeam_conn(cid)
    try:
        r = _vm_retry_session(c, body.session_id)
        audit(u["username"], "VEEAM_RETRY_SESSION", target=body.session_id, role=u["role"])
        return {"ok": True, "message": "Session retried", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/veeam/connections/{cid}/stop-session")
def veeam_stop_session_ep(cid: int, body: VeeamActionBody, u=Depends(require_role("admin","operator"))):
    c = _veeam_conn(cid)
    try:
        r = _vm_stop_session(c, body.session_id)
        audit(u["username"], "VEEAM_STOP_SESSION", target=body.session_id, role=u["role"])
        return {"ok": True, "message": "Session stopped", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.post("/api/veeam/connections/{cid}/instant-recovery")
def veeam_instant_recovery_ep(cid: int, body: VeeamActionBody, u=Depends(require_role("admin","operator"))):
    c = _veeam_conn(cid)
    try:
        r = _vm_instant_recovery(c, body.body)
        audit(u["username"], "VEEAM_INSTANT_RECOVERY", target=str(body.body), role=u["role"])
        return {"ok": True, "message": "Instant recovery initiated", "data": r}
    except Exception as e: raise HTTPException(400, detail=str(e))

@app.get("/api/veeam/connections/{cid}/search")
def veeam_search_ep(cid: int, q: str = "", u=Depends(require_role("admin","operator","viewer"))):
    c = _veeam_conn(cid)
    try: return _vm_search_objects(c, q)
    except Exception as e: raise HTTPException(400, detail=str(e))

# Ã¢â€â‚¬Ã¢â€â‚¬ RVTools endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
from rvtools_client import (
    get_rvtools_status          as _rvt_status,
    get_all_reports_with_summary as _rvt_all_reports,
    get_report_vms              as _rvt_report_vms,
    run_and_get_report          as _rvt_run_vcenter,
    run_rvtools_all             as _rvt_run_all,
    try_install_rvtools         as _rvt_install,
    scan_reports                as _rvt_scan,
)

class RVToolsRunReq(_BM):
    vcenter_id: str

class RVToolsVmsReq(_BM):
    file: str

@app.get("/api/rvtools/status")
def rvtools_status_ep(u=Depends(get_current_user)):
    return _rvt_status()

@app.get("/api/rvtools/reports")
def rvtools_reports_ep(u=Depends(get_current_user)):
    try:
        return {"reports": _rvt_all_reports()}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/rvtools/vms")
def rvtools_vms_ep(body: RVToolsVmsReq, u=Depends(get_current_user)):
    import os
    if not os.path.isfile(body.file):
        raise HTTPException(404, detail=f"File not found: {body.file}")
    try:
        return _rvt_report_vms(body.file)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/rvtools/run")
def rvtools_run_ep(body: RVToolsRunReq, u=Depends(require_role("admin","operator"))):
    try:
        result = _rvt_run_vcenter(body.vcenter_id)
        if result.get("success"):
            audit(u["username"], "RVTOOLS_RUN", target=body.vcenter_id, role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/rvtools/run-all")
def rvtools_run_all_ep(u=Depends(require_role("admin","operator"))):
    try:
        results = _rvt_run_all()
        audit(u["username"], "RVTOOLS_RUN_ALL", role=u["role"])
        return {"results": results}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/rvtools/install")
def rvtools_install_ep(u=Depends(require_role("admin"))):
    try:
        result = _rvt_install()
        if result.get("success"):
            audit(u["username"], "RVTOOLS_INSTALL", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/rvtools/scan")
def rvtools_scan_ep(u=Depends(get_current_user)):
    try:
        return {"reports": _rvt_scan()}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
# AWS ROUTES
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
from aws_client import (
    get_aws_status, save_aws_credentials, get_full_discovery,
    get_ec2_instances, get_s3_buckets, get_rds_instances, get_cost_summary,
    get_subnets, ec2_instance_action,
)

@app.get("/api/aws/status")
def aws_status_ep(u=Depends(get_current_user)):
    try:
        return get_aws_status()
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/aws/credentials")
def aws_save_creds_ep(body: dict, u=Depends(require_role("admin"))):
    try:
        result = save_aws_credentials(
            access_key_id=body.get("access_key_id","").strip(),
            secret_access_key=body.get("secret_access_key","").strip(),
            session_token=body.get("session_token","").strip(),
            region=body.get("region","ap-south-1"),
            account_alias=body.get("account_alias",""),
        )
        audit(u["username"], "AWS_SAVE_CREDENTIALS", role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/aws/discover")
def aws_discover_ep(body: dict = {}, u=Depends(get_current_user)):
    try:
        return get_full_discovery(region=body.get("region"), force=bool(body.get("force", False)))
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/aws/ec2")
def aws_ec2_ep(body: dict = {}, u=Depends(get_current_user)):
    try:
        return {"instances": get_ec2_instances(region=body.get("region"))}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/aws/s3")
def aws_s3_ep(u=Depends(get_current_user)):
    try:
        return {"buckets": get_s3_buckets()}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/aws/rds")
def aws_rds_ep(body: dict = {}, u=Depends(get_current_user)):
    try:
        return {"instances": get_rds_instances(region=body.get("region"))}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/aws/costs")
def aws_costs_ep(u=Depends(get_current_user)):
    try:
        return get_cost_summary()
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/aws/ec2/action")
def aws_ec2_action_ep(body: dict, u=Depends(require_role("admin", "operator"))):
    """Start, stop or reboot a single EC2 instance."""
    instance_id = body.get("instance_id", "").strip()
    action      = body.get("action", "").strip().lower()
    region      = body.get("region", "")
    if not instance_id or not action:
        raise HTTPException(400, detail="instance_id and action are required")
    try:
        result = ec2_instance_action(instance_id, action, region or None)
        if result.get("success"):
            audit(u["username"], f"AWS_EC2_{action.upper()}", detail=instance_id, role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/aws/subnets")
def aws_subnets_ep(body: dict = {}, u=Depends(get_current_user)):
    try:
        subnets = get_subnets(region=body.get("region") or None)
        err = subnets[0].get("error") if subnets and "error" in subnets[0] else None
        if err:
            return {"subnets": [], "total": 0, "error": err}
        return {
            "subnets":    subnets,
            "total":      len(subnets),
            "public":     sum(1 for s in subnets if s.get("public")),
            "private":    sum(1 for s in subnets if not s.get("public")),
            "total_ips":  sum(s.get("total_ips", 0) for s in subnets),
            "avail_ips":  sum(s.get("available_ips", 0) for s in subnets),
        }
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# Ã¢â€â‚¬Ã¢â€â‚¬ AWS SSO ROUTES Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
from aws_sso import (
    init_sso_login, poll_sso_token, get_sso_status,
    refresh_sso_credentials, is_sso_configured,
)

@app.post("/api/aws/sso/init")
def aws_sso_init_ep(body: dict, u=Depends(require_role("admin"))):
    """Start SSO device authorization flow. Returns verification URL + user_code."""
    start_url  = body.get("start_url", "").strip()
    sso_region = body.get("sso_region", "ap-south-1").strip()
    account_id = body.get("account_id", "").strip()
    role_name  = body.get("role_name", "").strip()
    if not start_url or not account_id or not role_name:
        raise HTTPException(400, detail="start_url, account_id and role_name are required")
    try:
        result = init_sso_login(start_url, sso_region, account_id, role_name)
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/aws/sso/poll")
def aws_sso_poll_ep(u=Depends(require_role("admin"))):
    """Poll once for SSO token approval. Frontend calls this every ~5s until success."""
    try:
        return poll_sso_token()
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/aws/sso/status")
def aws_sso_status_ep(u=Depends(get_current_user)):
    """Return current SSO status: configured, token_valid, cred_expiry, etc."""
    try:
        return get_sso_status()
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/aws/sso/refresh")
def aws_sso_refresh_ep(u=Depends(require_role("admin"))):
    """Manually trigger a credential refresh (for testing)."""
    try:
        return refresh_sso_credentials()
    except Exception as e:
        raise HTTPException(500, detail=str(e))



# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
#  MICROSOFT HYPER-V
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
from hyperv_client import (
    get_hv_hosts, save_hv_hosts,
    test_hv_connection, get_hv_host_info,
    get_hv_vms, get_all_hv_data,
    hv_vm_action, get_hv_checkpoints,
    hv_create_checkpoint, hv_delete_checkpoint, hv_restore_checkpoint,
)

class HVHostsBody(BaseModel):
    hosts: list

class HVVMActionBody(BaseModel):
    host_id: str
    vm_name: str
    action: str

class HVCheckpointBody(BaseModel):
    host_id: str
    vm_name: str
    name: str


def _hv_find(hosts, host_id: str):
    for h in hosts:
        if h["id"] == host_id:
            return h
    return None


@app.get("/api/hyperv/hosts")
def hyperv_hosts_ep(u=Depends(get_current_user)):
    """Return configured Hyper-V hosts (passwords masked)."""
    hosts = get_hv_hosts()
    masked = [{**h, "password": "***" if h.get("password") else ""} for h in hosts]
    return {"hosts": masked}


@app.post("/api/hyperv/hosts")
def hyperv_hosts_save_ep(body: HVHostsBody, u=Depends(require_role("admin"))):
    """Save/update Hyper-V host list."""
    result = save_hv_hosts(body.hosts)
    audit(u["username"], "HV_HOSTS_SAVE", detail=f"{len(body.hosts)} host(s)", role=u["role"])
    return result


@app.get("/api/hyperv/status")
def hyperv_status_ep(u=Depends(get_current_user)):
    """Test connectivity to all configured Hyper-V hosts."""
    hosts = get_hv_hosts()
    if not hosts:
        return {"hosts": [], "message": "No Hyper-V hosts configured"}
    results = []
    for h in hosts:
        r = test_hv_connection(h)
        results.append({"id": h["id"], "host": h["host"], "name": h["name"], **r})
    return {"hosts": results}


@app.get("/api/hyperv/vms")
def hyperv_vms_ep(host_id: str = None, u=Depends(get_current_user)):
    """Return all VMs across all hosts (or a single host)."""
    hosts = get_hv_hosts()
    if not hosts:
        return {"vms": [], "summary": {}}
    if host_id:
        hcfg = _hv_find(hosts, host_id)
        if not hcfg:
            raise HTTPException(404, detail=f"Host id '{host_id}' not found")
        vms = get_hv_vms(hcfg)
        return {"vms": vms}
    data = get_all_hv_data()
    return data


@app.post("/api/hyperv/vm/action")
def hyperv_vm_action_ep(body: HVVMActionBody, u=Depends(require_role("admin", "operator"))):
    hosts = get_hv_hosts()
    hcfg  = _hv_find(hosts, body.host_id)
    if not hcfg:
        raise HTTPException(404, detail=f"Host id '{body.host_id}' not found")
    result = hv_vm_action(hcfg, body.vm_name, body.action)
    if result.get("success"):
        audit(u["username"], f"HV_VM_{body.action.upper()}",
              detail=f"{body.vm_name} on {hcfg['host']}", role=u["role"])
    return result


@app.get("/api/hyperv/checkpoints/{host_id}/{vm_name}")
def hyperv_checkpoints_ep(host_id: str, vm_name: str, u=Depends(get_current_user)):
    hosts = get_hv_hosts()
    hcfg  = _hv_find(hosts, host_id)
    if not hcfg:
        raise HTTPException(404, detail=f"Host id '{host_id}' not found")
    return {"checkpoints": get_hv_checkpoints(hcfg, vm_name)}


@app.post("/api/hyperv/checkpoint/create")
def hyperv_checkpoint_create_ep(body: HVCheckpointBody, u=Depends(require_role("admin", "operator"))):
    hosts = get_hv_hosts()
    hcfg  = _hv_find(hosts, body.host_id)
    if not hcfg:
        raise HTTPException(404, detail=f"Host id '{body.host_id}' not found")
    result = hv_create_checkpoint(hcfg, body.vm_name, body.name)
    if result.get("success"):
        audit(u["username"], "HV_CHECKPOINT_CREATE",
              detail=f"VM={body.vm_name} CP={body.name}", role=u["role"])
    return result


@app.post("/api/hyperv/checkpoint/delete")
def hyperv_checkpoint_delete_ep(body: HVCheckpointBody, u=Depends(require_role("admin", "operator"))):
    hosts = get_hv_hosts()
    hcfg  = _hv_find(hosts, body.host_id)
    if not hcfg:
        raise HTTPException(404, detail=f"Host id '{body.host_id}' not found")
    result = hv_delete_checkpoint(hcfg, body.vm_name, body.name)
    if result.get("success"):
        audit(u["username"], "HV_CHECKPOINT_DELETE",
              detail=f"VM={body.vm_name} CP={body.name}", role=u["role"])
    return result


@app.post("/api/hyperv/checkpoint/restore")
def hyperv_checkpoint_restore_ep(body: HVCheckpointBody, u=Depends(require_role("admin"))):
    hosts = get_hv_hosts()
    hcfg  = _hv_find(hosts, body.host_id)
    if not hcfg:
        raise HTTPException(404, detail=f"Host id '{body.host_id}' not found")
    result = hv_restore_checkpoint(hcfg, body.vm_name, body.name)
    if result.get("success"):
        audit(u["username"], "HV_CHECKPOINT_RESTORE",
              detail=f"VM={body.vm_name} CP={body.name}", role=u["role"])
    return result


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ LaaS AI Ã¢â‚¬â€ Local Llama Inference (llama-cpp-python, fully offline) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
import threading as _threading

_LLAMA_MODEL_PATH = os.getenv("LLAMA_MODEL_PATH", r"C:\ollama\models\llama3.2-3b-instruct-q4.gguf")
_LLAMA_MODEL_NAME = os.getenv("LLAMA_MODEL_NAME", "llama3.2-3b-instruct-q4")
_llm_instance = None
_llm_lock     = _threading.Lock()

def _get_llm():
    global _llm_instance
    if _llm_instance is None:
        with _llm_lock:
            if _llm_instance is None:
                from llama_cpp import Llama as _Llama
                logging.info(f"Loading local LLM from {_LLAMA_MODEL_PATH} ...")
                _llm_instance = _Llama(
                    model_path   = _LLAMA_MODEL_PATH,
                    n_ctx        = 8192,
                    n_threads    = 8,
                    n_gpu_layers = 0,     # CPU-only, no GPU needed
                    verbose      = False,
                )
                logging.info("Local LLM loaded successfully.")
    return _llm_instance

class AIChatBody(BaseModel):
    query:   str
    context: dict = {}

_AI_SYSTEM = """You are LaaS AI Ã¢â‚¬â€ an expert IT infrastructure assistant embedded in the LaaS Dashboard.
You are given REAL-TIME data from the user's infrastructure (VMware, Hyper-V, Nutanix, OpenShift, AWS).

Rules:
- Answer ONLY from the provided data. Do NOT invent VM names, IPs or counts.
- Be concise yet complete. Use bullet points for lists.
- Show exact names, IPs, states from the data.
- If something is not in the data, say "not available in current data".
- Support natural-language and voice queries naturally.
- For VM/host lookups: search case-insensitively across all platforms.
- Current date/time will be provided Ã¢â‚¬â€ use it for age calculations if asked."""

def _build_context_prompt(ctx: dict) -> str:
    lines = []
    ts = ctx.get("timestamp", "")
    if ts:
        lines.append(f"Data captured at: {ts}\n")

    # VMware
    vms = ctx.get("vms", [])
    hosts = ctx.get("hosts", [])
    dss = ctx.get("datastores", [])
    alerts = ctx.get("alerts", [])
    vcenters = ctx.get("vcenters", [])
    snaps = ctx.get("snapshots_count", 0)
    old_snaps = ctx.get("old_snapshots_30d", 0)

    if vcenters:
        lines.append(f"## VMware vCenters ({len(vcenters)})")
        for v in vcenters:
            lines.append(f"  - {v.get('name', v.get('id','?'))}")

    if vms:
        on  = sum(1 for v in vms if v.get("status") == "poweredOn")
        off = sum(1 for v in vms if v.get("status") == "poweredOff")
        sus = sum(1 for v in vms if v.get("status") == "suspended")
        lines.append(f"\n## VMware VMs ({len(vms)} total | {on} ON | {off} OFF | {sus} suspended)")
        for v in vms[:300]:
            ip = v.get("ip") or (v.get("all_ips") or [""])[0] or "no-ip"
            lines.append(f"  VM: {v.get('name')}  state={v.get('status')}  cpu={v.get('cpu')}  ram={v.get('ram_gb')}GB  disk={v.get('disk_gb')}GB  ip={ip}  host={v.get('host','')}  vc={v.get('vcenter_name','')}")

    if hosts:
        connected = sum(1 for h in hosts if h.get("status") == "connected")
        lines.append(f"\n## VMware ESXi Hosts ({len(hosts)} | {connected} connected)")
        for h in hosts:
            cpu_used = round(100 - (h.get("cpu_free_pct") or 0))
            ram_used = h.get("ram_total_gb", 0) - (h.get("ram_free_gb") or 0)
            lines.append(f"  Host: {h.get('name')}  status={h.get('status')}  cpu_used={cpu_used}%  ram={ram_used}/{h.get('ram_total_gb',0)}GB  vc={h.get('vcenter_name','')}")

    if dss:
        lines.append(f"\n## Datastores ({len(dss)})")
        for d in dss:
            lines.append(f"  DS: {d.get('name')}  used={d.get('used_pct',0)}%  total={d.get('total_gb',0)}GB  accessible={d.get('accessible',True)}")

    if alerts:
        lines.append(f"\n## Active Alerts ({len(alerts)})")
        for a in alerts[:50]:
            lines.append(f"  [{a.get('severity','').upper()}] {a.get('resource','')}: {a.get('message','')}  vc={a.get('vcenter_name','')}")

    if snaps:
        lines.append(f"\n## Snapshots: {snaps} total | {old_snaps} older than 30 days")

    # Hyper-V
    hv = ctx.get("hyperv")
    if hv:
        hv_vms   = hv.get("vms", [])
        hv_hosts = hv.get("hosts", [])
        on  = sum(1 for v in hv_vms if (v.get("State") or v.get("state")) == "Running")
        off = sum(1 for v in hv_vms if (v.get("State") or v.get("state")) == "Off")
        lines.append(f"\n## Hyper-V ({len(hv_hosts)} hosts | {len(hv_vms)} VMs | {on} Running | {off} Off)")
        for v in hv_vms:
            state = v.get("State") or v.get("state","?")
            ram = round((v.get("MemoryAssigned") or 0)/1073741824,1)
            cpu = v.get("CPUUsage","?")
            lines.append(f"  HV-VM: {v.get('VMName') or v.get('Name','?')}  state={state}  cpu={cpu}%  ram={ram}GB  host={v.get('_host_name','')}")
        for h in hv_hosts:
            lines.append(f"  HV-Host: {h.get('Name') or h.get('name','?')}  ip={h.get('host','')}  os={h.get('OSName','')}  ram={h.get('TotalRAMGB','')}GB")

    # AWS
    aws = ctx.get("aws_ec2", [])
    if aws:
        running = sum(1 for i in aws if (i.get("state") or i.get("State")) == "running")
        lines.append(f"\n## AWS EC2 ({len(aws)} instances | {running} running)")
        for i in aws[:100]:
            state = i.get("state") or i.get("State","?")
            lines.append(f"  EC2: {i.get('name') or i.get('instance_id','?')}  state={state}  type={i.get('instance_type','')}  region={i.get('region','')}  ip={i.get('private_ip','')}")

    # OCP
    ocp = ctx.get("ocp", [])
    if ocp:
        lines.append(f"\n## OpenShift Clusters ({len(ocp)})")
        for c in ocp:
            lines.append(f"  OCP: {c.get('name','?')}  nodes={c.get('nodes_ready','?')}/{c.get('nodes_total','?')}  pods={c.get('pods_running','?')}/{c.get('pods_total','?')}  url={c.get('api_url','')}")

    # Nutanix
    nut = ctx.get("nutanix", [])
    if nut:
        lines.append(f"\n## Nutanix Prism Centrals ({len(nut)})")
        for p in nut:
            lines.append(f"  NUT-PC: {p.get('name','?')}  vms={p.get('vms_running','?')}/{p.get('vms_total','?')}  hosts={p.get('hosts','?')}  url={p.get('url','')}")

    return "\n".join(lines)


@app.post("/api/ai/chat")
async def ai_chat(body: AIChatBody, u=Depends(get_current_user)):
    import asyncio as _asyncio
    if not os.path.exists(_LLAMA_MODEL_PATH):
        raise HTTPException(503, detail=(
            f"Local AI model not found at: {_LLAMA_MODEL_PATH}. "
            "Download is still in progress. Please wait a few minutes and try again."
        ))
    try:
        ctx_txt = _build_context_prompt(body.context)
        from datetime import datetime as _dt
        now_str    = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
        system_msg = _AI_SYSTEM + f"\n\nCurrent server time: {now_str}"
        user_msg   = f"INFRASTRUCTURE DATA:\n{ctx_txt}\n\nUSER QUESTION: {body.query}"

        llm  = _get_llm()
        loop = _asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, lambda: llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": user_msg},
            ],
            max_tokens  = 1000,
            temperature = 0.1,
            stop        = ["<|eot_id|>", "</s>", "<|end|>"],
        ))
        answer = resp["choices"][0]["message"]["content"].strip()
        audit(u["username"], "AI_CHAT", detail=f"q={body.query[:80]}", role=u["role"])
        return {"answer": answer, "model": _LLAMA_MODEL_NAME}
    except Exception as e:
        logging.error(f"AI chat error: {e}")
        raise HTTPException(500, detail=str(e))


# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
#  HISTORY & FORECAST  API  (PostgreSQL)
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â

import psycopg2
from psycopg2.extras import RealDictCursor

def _pg_conn():
    """Open a short-lived psycopg2 connection using env vars."""
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "127.0.0.1"),
        port=int(os.getenv("PG_PORT", "5433")),
        dbname=os.getenv("PG_DB", "caas_dashboard"),
        user=os.getenv("PG_USER", "caas_app"),
        password=os.getenv("PG_PASS", "CaaS@App2024#"),
        connect_timeout=5,
        cursor_factory=RealDictCursor,
    )


@app.get("/api/history/last_run")
def history_last_run(u=Depends(get_current_user)):
    """Return the most recent snapshot run status."""
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, run_date::text, run_at::text, status,
                           duration_sec, error_msg
                    FROM snapshot_runs
                    ORDER BY run_date DESC LIMIT 1
                """)
                row = cur.fetchone()
        return {"last_run": dict(row) if row else None}
    except Exception as e:
        logging.warning(f"history_last_run: {e}")
        return {"last_run": None, "error": str(e)}


@app.get("/api/history/kpi")
def history_kpi(days: int = 30, u=Depends(get_current_user)):
    """Return daily platform KPI for the last N days."""
    days = min(max(days, 1), 90)
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT run_date::text, total_vms, running_vms, powered_off_vms,
                           total_hosts, total_storage_tb, used_storage_tb,
                           storage_usage_pct, total_pods, running_pods,
                           aws_instances, aws_running, ip_utilisation_pct,
                           critical_alerts, warning_alerts
                    FROM snap_platform_kpi
                    WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval
                    ORDER BY run_date
                """, (days,))
                rows = [dict(r) for r in cur.fetchall()]
        return {"days": days, "count": len(rows), "data": rows}
    except Exception as e:
        logging.warning(f"history_kpi: {e}")
        return {"days": days, "count": 0, "data": [], "error": str(e)}


@app.get("/api/history/vmware")
def history_vmware(days: int = 30, u=Depends(get_current_user)):
    """Return daily VMware summary trend."""
    days = min(max(days, 1), 90)
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT vs.run_date::text, vs.vcenter_name,
                           vs.total_vms, vs.powered_on, vs.powered_off,
                           vs.datastores_count, vs.datastores_critical,
                           vs.alerts_critical, vs.alerts_warning
                    FROM snap_vmware_summary vs
                    WHERE vs.run_date >= CURRENT_DATE - (%s || ' days')::interval
                    ORDER BY vs.run_date, vs.vcenter_name
                """, (days,))
                rows = [dict(r) for r in cur.fetchall()]
        return {"days": days, "count": len(rows), "data": rows}
    except Exception as e:
        logging.warning(f"history_vmware: {e}")
        return {"days": days, "count": 0, "data": [], "error": str(e)}


@app.get("/api/history/platforms")
def history_platforms(days: int = 7, u=Depends(get_current_user)):
    """Return recent snapshots across all platform tables."""
    days = min(max(days, 1), 30)
    result = {}
    tables = {
        "hyperv":   "snap_hyperv_summary",
        "nutanix":  "snap_nutanix_summary",
        "ocp":      "snap_ocp_summary",
        "aws":      "snap_aws_summary",
        "ipam":     "snap_ipam_summary",
    }
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                for key, tbl in tables.items():
                    cur.execute(
                        f"SELECT * FROM {tbl} "
                        f"WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval "
                        f"ORDER BY run_date",
                        (days,)
                    )
                    result[key] = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logging.warning(f"history_platforms: {e}")
        return {"error": str(e), "data": result}
    return {"days": days, "data": result}


@app.get("/api/forecast/kpi")
def forecast_kpi(horizon: int = 7, u=Depends(get_current_user)):
    """
    Simple linear regression forecast for the next N days.
    Uses the last 30 days of snap_platform_kpi to project:
      total_vms, used_storage_tb, ip_utilisation_pct
    Returns: actual history + projected rows with confidence bands.
    """
    horizon = min(max(horizon, 1), 30)
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT run_date, total_vms, used_storage_tb,
                           storage_usage_pct, ip_utilisation_pct
                    FROM snap_platform_kpi
                    WHERE run_date >= CURRENT_DATE - INTERVAL '30 days'
                    ORDER BY run_date
                """)
                rows = cur.fetchall()

        if len(rows) < 2:
            return {"horizon": horizon, "history": [], "forecast": [],
                    "message": "Not enough history yet Ã¢â‚¬â€ run the collector first."}

        import datetime as dt
        # Convert to plain lists
        dates  = [r["run_date"] for r in rows]
        x      = list(range(len(dates)))          # 0,1,2,...
        fields = ["total_vms", "used_storage_tb", "storage_usage_pct", "ip_utilisation_pct"]

        def linreg(xs, ys):
            n = len(xs)
            if n < 2: return 0.0, 0.0
            sx, sy = sum(xs), sum(ys)
            sxy = sum(a*b for a,b in zip(xs,ys))
            sx2 = sum(a*a for a in xs)
            try:
                m = (n*sxy - sx*sy) / (n*sx2 - sx*sx)
                b = (sy - m*sx) / n
            except ZeroDivisionError:
                m, b = 0.0, (sy/n if n else 0.0)
            # residual std deviation
            preds = [m*xi+b for xi in xs]
            resid = [yi-pi for yi,pi in zip(ys,preds)]
            std   = (sum(r*r for r in resid)/n)**0.5
            return m, b, std

        regs = {}
        for f in fields:
            ys = [float(r[f] or 0) for r in rows]
            regs[f] = linreg(x, ys)

        forecast = []
        last_date = dates[-1]
        offset    = len(x)
        for i in range(1, horizon+1):
            proj_date = last_date + dt.timedelta(days=i)
            xi = offset + i - 1
            row = {"run_date": proj_date.isoformat(), "forecast": True}
            for f in fields:
                m, b, std = regs[f]
                val = round(m*xi + b, 2)
                row[f]          = max(val, 0.0)
                row[f+"_lo"]    = max(round(val - 1.645*std, 2), 0.0)
                row[f+"_hi"]    = max(round(val + 1.645*std, 2), 0.0)
            forecast.append(row)

        history = [
            {**{k: (v.isoformat() if hasattr(v,"isoformat") else v)
                for k,v in dict(r).items()}, "forecast": False}
            for r in rows
        ]
        return {"horizon": horizon, "history": history, "forecast": forecast}

    except Exception as e:
        logging.error(f"forecast_kpi: {e}")
        raise HTTPException(500, detail=str(e))


@app.get("/api/history/moving_avg")
def history_moving_avg(u=Depends(get_current_user)):
    """Return 7-day moving averages from the v_kpi_moving_avg view."""
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT run_date::text, total_vms, vms_7d_avg,
                           storage_pct_7d_avg, ip_pct_7d_avg, crit_alerts_7d_avg
                    FROM v_kpi_moving_avg
                    ORDER BY run_date DESC LIMIT 30
                """)
                rows = [dict(r) for r in cur.fetchall()]
        return {"data": list(reversed(rows))}
    except Exception as e:
        logging.warning(f"history_moving_avg: {e}")
        return {"data": [], "error": str(e)}


@app.get("/api/history/all")
def history_all(days: int = 30, u=Depends(get_current_user)):
    """Comprehensive history endpoint Ã¢â‚¬â€ all platform snap tables for N days (max 90)."""
    days = min(max(days, 1), 90)
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT run_date::text, total_vms, running_vms, powered_off_vms,
                           total_hosts, avg_cpu_pct, avg_mem_pct,
                           total_storage_tb, used_storage_tb, storage_usage_pct,
                           total_pods, running_pods, aws_instances, aws_running,
                           ip_utilisation_pct, critical_alerts, warning_alerts
                    FROM snap_platform_kpi
                    WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval
                    ORDER BY run_date
                """, (days,))
                kpi = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT run_date::text, vcenter_name, total_vms, powered_on, powered_off,
                           datastores_count, datastores_critical, alerts_critical, alerts_warning
                    FROM snap_vmware_summary
                    WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval
                    ORDER BY run_date, vcenter_name
                """, (days,))
                vmware = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT run_date::text, host_name, total_vms, running_vms, stopped_vms,
                           paused_vms, cpu_cores, cpu_usage_pct, mem_total_gb, mem_assigned_gb
                    FROM snap_hyperv_summary
                    WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval
                    ORDER BY run_date, host_name
                """, (days,))
                hyperv = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT run_date::text, cluster_name, total_vms, running_vms, stopped_vms,
                           total_hosts, storage_total_tb, storage_used_tb, storage_usage_pct,
                           cluster_health
                    FROM snap_nutanix_summary
                    WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval
                    ORDER BY run_date, cluster_name
                """, (days,))
                nutanix = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT run_date::text, cluster_name, total_nodes, ready_nodes,
                           total_pods, running_pods, failed_pods, pending_pods,
                           total_namespaces, alerts_firing
                    FROM snap_ocp_summary
                    WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval
                    ORDER BY run_date, cluster_name
                """, (days,))
                ocp = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT run_date::text, region, total_instances, running, stopped
                    FROM snap_aws_summary
                    WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval
                    ORDER BY run_date, region
                """, (days,))
                aws = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT run_date::text, total_subnets, total_ips, used_ips, free_ips,
                           utilisation_pct, subnets_critical, subnets_warning
                    FROM snap_ipam_summary
                    WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval
                    ORDER BY run_date
                """, (days,))
                ipam = [dict(r) for r in cur.fetchall()]

                try:
                    cur.execute("""
                        SELECT run_date::text, platform_name, platform_type,
                               protected, unprotected,
                               jobs_ok AS total_jobs,
                               jobs_ok AS jobs_success,
                               jobs_fail AS jobs_failed,
                               jobs_running AS jobs_warning,
                               used_bytes, total_bytes, alerts, status
                        FROM snap_backup_summary
                        WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval
                        ORDER BY run_date, platform_name
                    """, (days,))
                    backup = [dict(r) for r in cur.fetchall()]
                except Exception:
                    backup = []

                try:
                    cur.execute("""
                        SELECT run_date::text, array_name, vendor AS array_type,
                               total_capacity_tb AS capacity_total_tb,
                               used_capacity_tb AS capacity_used_tb,
                               free_tb AS capacity_free_tb,
                               used_pct AS capacity_pct,
                               volume_count, alert_count, status
                        FROM snap_storage_arrays
                        WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval
                        ORDER BY run_date, array_name
                    """, (days,))
                    storage = [dict(r) for r in cur.fetchall()]
                except Exception:
                    storage = []
                cur.execute("""
                    SELECT run_date::text, run_at::text, status, duration_sec, error_msg
                    FROM snapshot_runs ORDER BY run_date DESC LIMIT 1
                """)
                last_run_row = cur.fetchone()
                last_run = dict(last_run_row) if last_run_row else None

        return {"days": days, "last_run": last_run, "kpi": kpi, "vmware": vmware,
                "hyperv": hyperv, "nutanix": nutanix, "ocp": ocp, "aws": aws,
                "ipam": ipam, "backup": backup, "storage": storage}
    except Exception as e:
        logging.warning(f"history_all: {e}")
        return {"days": days, "error": str(e), "kpi": [], "vmware": [], "hyperv": [],
                "nutanix": [], "ocp": [], "aws": [], "ipam": [], "backup": [], "storage": []}


@app.get("/api/forecast/all")
def forecast_all(horizon: int = 30, u=Depends(get_current_user)):
    """
    Extended multi-platform forecast with runway calculations.
    Uses 90-day history, linear regression, returns history + forecast rows + runway estimates.
    """
    import datetime as dt
    horizon = min(max(horizon, 1), 90)

    def linreg(xs, ys):
        n = len(xs)
        if n < 2:
            return 0.0, float(sum(ys)/n) if n else 0.0, 0.0
        sx, sy = sum(xs), sum(ys)
        sxy = sum(a*b for a, b in zip(xs, ys))
        sx2 = sum(a*a for a in xs)
        denom = n*sx2 - sx*sx
        if denom == 0:
            return 0.0, sy/n, 0.0
        m = (n*sxy - sx*sy) / denom
        b_val = (sy - m*sx) / n
        preds = [m*xi + b_val for xi in xs]
        std = (sum((yi-pi)**2 for yi, pi in zip(ys, preds)) / n) ** 0.5
        return m, b_val, std

    def days_to_threshold(m, b_val, x_now, threshold):
        if m <= 0:
            return None
        cur_val = m * x_now + b_val
        if cur_val >= threshold:
            return 0
        return max(0, round((threshold - cur_val) / m))

    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT run_date, total_vms, running_vms, avg_cpu_pct, avg_mem_pct,
                           used_storage_tb, storage_usage_pct,
                           aws_instances, aws_running, total_pods, running_pods,
                           ip_utilisation_pct, critical_alerts, warning_alerts
                    FROM snap_platform_kpi
                    WHERE run_date >= CURRENT_DATE - INTERVAL '90 days'
                    ORDER BY run_date
                """)
                rows = cur.fetchall()

                cur.execute("""
                    SELECT run_date, SUM(total_vms) AS hv_vms, SUM(running_vms) AS hv_running
                    FROM snap_hyperv_summary
                    WHERE run_date >= CURRENT_DATE - INTERVAL '90 days'
                    GROUP BY run_date ORDER BY run_date
                """)
                hv_by_date = {r["run_date"]: dict(r) for r in cur.fetchall()}

                cur.execute("""
                    SELECT run_date,
                           SUM(total_vms) AS nut_vms, SUM(running_vms) AS nut_running,
                           SUM(storage_total_tb) AS nut_stor_total, SUM(storage_used_tb) AS nut_stor_used
                    FROM snap_nutanix_summary
                    WHERE run_date >= CURRENT_DATE - INTERVAL '90 days'
                    GROUP BY run_date ORDER BY run_date
                """)
                nut_by_date = {r["run_date"]: dict(r) for r in cur.fetchall()}

                try:
                    cur.execute("""
                        SELECT run_date,
                               SUM(total_capacity_tb) AS stor_total, SUM(used_capacity_tb) AS stor_used,
                               AVG(used_pct) AS stor_pct
                        FROM snap_storage_arrays
                        WHERE run_date >= CURRENT_DATE - INTERVAL '90 days'
                        GROUP BY run_date ORDER BY run_date
                    """)
                    stor_by_date = {r["run_date"]: dict(r) for r in cur.fetchall()}
                except Exception:
                    stor_by_date = {}

                try:
                    cur.execute("""
                        SELECT run_date,
                               SUM(jobs_ok) AS bk_ok, SUM(jobs_fail) AS bk_fail,
                               SUM(jobs_ok + jobs_fail + jobs_running) AS bk_total,
                               SUM(used_bytes)/1073741824.0 AS repo_used_gb,
                               SUM(total_bytes)/1073741824.0 AS repo_total_gb
                        FROM snap_backup_summary
                        WHERE run_date >= CURRENT_DATE - INTERVAL '90 days'
                        GROUP BY run_date ORDER BY run_date
                    """)
                    bk_by_date = {r["run_date"]: dict(r) for r in cur.fetchall()}
                except Exception:
                    bk_by_date = {}

        if len(rows) < 2:
            return {"horizon": horizon, "history": [], "forecast": [], "runways": {},
                    "message": "Not enough history â€” run the nightly collector first."}

        dates = [r["run_date"] for r in rows]
        xs = list(range(len(dates)))
        n_hist = len(xs)

        fields = [
            ("total_vms", None),
            ("avg_cpu_pct", 85.0),
            ("avg_mem_pct", 85.0),
            ("storage_usage_pct", 85.0),
            ("used_storage_tb", None),
            ("aws_instances", None),
            ("ip_utilisation_pct", 90.0),
            ("critical_alerts", None),
            ("total_pods", None),
        ]

        regs = {}
        for f, _ in fields:
            ys = [float(r[f] or 0) for r in rows]
            regs[f] = linreg(xs, ys)

        # Build enriched history rows
        history = []
        for idx, r in enumerate(rows):
            rd = r["run_date"]
            row = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(r).items()}
            row["forecast"] = False
            hv = hv_by_date.get(rd, {})
            nut = nut_by_date.get(rd, {})
            st = stor_by_date.get(rd, {})
            bk = bk_by_date.get(rd, {})
            row["hv_vms"] = float(hv.get("hv_vms") or 0)
            row["hv_running"] = float(hv.get("hv_running") or 0)
            row["nut_vms"] = float(nut.get("nut_vms") or 0)
            nut_total = float(nut.get("nut_stor_total") or 1)
            nut_used = float(nut.get("nut_stor_used") or 0)
            row["nut_stor_pct"] = round(nut_used / nut_total * 100, 2)
            row["stor_total_tb"] = float(st.get("stor_total") or 0)
            row["stor_used_tb"] = float(st.get("stor_used") or 0)
            row["stor_pct"] = float(st.get("stor_pct") or 0)
            row["bk_ok"] = float(bk.get("bk_ok") or 0)
            row["bk_fail"] = float(bk.get("bk_fail") or 0)
            row["bk_total"] = float(bk.get("bk_total") or 0)
            row["repo_cap"] = float(bk.get("repo_total_gb") or 0)
            row["repo_free"] = float(bk.get("repo_total_gb") or 0) - float(bk.get("repo_used_gb") or 0)
            repo_cap_val = float(bk.get("repo_total_gb") or 0)
            repo_used_val = float(bk.get("repo_used_gb") or 0)
            row["repo_used_pct"] = round(repo_used_val / repo_cap_val * 100, 2) if repo_cap_val > 0 else 0.0

        # Build forecast rows
        last_date = dates[-1]
        forecast = []
        for i in range(1, horizon + 1):
            xi = n_hist + i - 1
            proj_date = (last_date + dt.timedelta(days=i)).isoformat()
            frow = {"run_date": proj_date, "forecast": True}
            for f, _ in fields:
                m, b_val, std = regs[f]
                val = round(m * xi + b_val, 2)
                frow[f] = max(val, 0.0)
                frow[f + "_lo"] = max(round(val - 1.645 * std, 2), 0.0)
                frow[f + "_hi"] = max(round(val + 1.645 * std, 2), 0.0)
            forecast.append(frow)

        # Runway calculations per metric
        runways = {}
        last_xi = n_hist - 1
        for f, threshold in fields:
            if threshold is None:
                continue
            m, b_val, std = regs[f]
            cur_val = float(rows[-1][f] or 0)
            d = days_to_threshold(m, b_val, last_xi, threshold)
            runways[f] = {
                "current": round(cur_val, 2),
                "threshold": threshold,
                "days_to_threshold": d,
                "trend_per_day": round(m, 4),
                "status": ("critical" if (d is not None and d <= 14) else
                           "warning" if (d is not None and d <= 45) else "healthy"),
            }

        return {"horizon": horizon, "history": history, "forecast": forecast, "runways": runways}

    except Exception as e:
        logging.error(f"forecast_all: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
#  INSIGHTS API  (Health Scorecard Ã‚Â· Change Detection Ã‚Â· Capacity/Cost Ã‚Â· Exec)
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â

@app.get("/api/insights/health")
def insights_health(u=Depends(get_current_user)):
    """Platform health scorecard Ã¢â‚¬â€ RAG status per platform from latest snapshot."""
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                # Latest KPI
                cur.execute("""
                    SELECT k.*, sr.status AS run_status, sr.duration_sec,
                           sr.run_at::text, sr.error_msg
                    FROM snap_platform_kpi k
                    JOIN snapshot_runs sr ON sr.run_date = k.run_date
                    ORDER BY k.run_date DESC LIMIT 1
                """)
                kpi = dict(cur.fetchone()) if cur.rowcount else {}

                # VMware per-vCenter
                cur.execute("""
                    SELECT vcenter_name, total_vms, powered_on, powered_off,
                           datastores_critical, datastores_warning, alerts_critical, alerts_warning
                    FROM snap_vmware_summary
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_vmware_summary)
                    ORDER BY vcenter_name
                """)
                vmware_vcs = [dict(r) for r in cur.fetchall()]

                # VMware host CPU/MEM extremes
                cur.execute("""
                    SELECT host_name, vcenter_name, cpu_usage_pct, mem_usage_pct, vm_count
                    FROM snap_vmware_hosts
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_vmware_hosts)
                    ORDER BY cpu_usage_pct DESC LIMIT 5
                """)
                hot_hosts = [dict(r) for r in cur.fetchall()]

                # Hyper-V
                cur.execute("""
                    SELECT host_name, total_vms, running_vms, stopped_vms, paused_vms,
                           cpu_cores, cpu_usage_pct, mem_total_gb, mem_assigned_gb, checkpoints_count
                    FROM snap_hyperv_summary
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_hyperv_summary)
                """)
                hyperv = [dict(r) for r in cur.fetchall()]

                # Nutanix
                cur.execute("""
                    SELECT cluster_name, total_vms, running_vms, stopped_vms, total_hosts,
                           storage_total_tb, storage_used_tb, storage_usage_pct, cluster_health
                    FROM snap_nutanix_summary
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_nutanix_summary)
                """)
                nutanix = [dict(r) for r in cur.fetchall()]

                # OCP
                cur.execute("""
                    SELECT cluster_name, total_nodes, ready_nodes, total_pods,
                           running_pods, failed_pods, pending_pods, total_namespaces, alerts_firing
                    FROM snap_ocp_summary
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_ocp_summary)
                """)
                ocp = [dict(r) for r in cur.fetchall()]

                # IPAM
                cur.execute("""
                    SELECT total_subnets, total_ips, used_ips, free_ips,
                           utilisation_pct, subnets_critical, subnets_warning
                    FROM snap_ipam_summary
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_ipam_summary)
                    LIMIT 1
                """)
                ipam_row = cur.fetchone()
                ipam = dict(ipam_row) if ipam_row else {}

                # AD/DNS
                cur.execute("""
                    SELECT total_users, enabled_users, disabled_users, locked_users,
                           total_computers, total_groups, dns_zones, dns_records
                    FROM snap_ad_dns_summary
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_ad_dns_summary)
                    LIMIT 1
                """)
                ad_row = cur.fetchone()
                addns = dict(ad_row) if ad_row else {}

                # AWS
                cur.execute("""
                    SELECT region, total_instances, running, stopped
                    FROM snap_aws_summary
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_aws_summary)
                """)
                aws = [dict(r) for r in cur.fetchall()]

        return {
            "kpi": kpi, "vmware_vcs": vmware_vcs, "hot_hosts": hot_hosts,
            "hyperv": hyperv, "nutanix": nutanix, "ocp": ocp,
            "ipam": ipam, "addns": addns, "aws": aws
        }
    except Exception as e:
        logging.warning(f"insights_health: {e}")
        return {"error": str(e)}


@app.get("/api/insights/changes")
def insights_changes(u=Depends(get_current_user)):
    """Day-over-day change detection Ã¢â‚¬â€ compare today vs yesterday across all platforms."""
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                # KPI comparison: latest two days
                cur.execute("""
                    SELECT run_date::text, total_vms, running_vms, powered_off_vms,
                           total_hosts, avg_cpu_pct, avg_mem_pct,
                           total_storage_tb, used_storage_tb, storage_usage_pct,
                           total_pods, running_pods, aws_instances, aws_running,
                           ip_utilisation_pct, critical_alerts, warning_alerts
                    FROM snap_platform_kpi
                    ORDER BY run_date DESC LIMIT 2
                """)
                kpi_rows = [dict(r) for r in cur.fetchall()]

                # VMware summary comparison
                cur.execute("""
                    WITH ranked AS (
                        SELECT *, ROW_NUMBER() OVER(PARTITION BY vcenter_name ORDER BY run_date DESC) rn
                        FROM snap_vmware_summary
                    )
                    SELECT run_date::text, vcenter_name, total_vms, powered_on, powered_off,
                           datastores_critical, alerts_critical, rn
                    FROM ranked WHERE rn <= 2
                    ORDER BY vcenter_name, rn
                """)
                vmware_changes = [dict(r) for r in cur.fetchall()]

                # Host CPU/MEM spikes (> 80%)
                cur.execute("""
                    SELECT host_name, vcenter_name, cpu_usage_pct, mem_usage_pct
                    FROM snap_vmware_hosts
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_vmware_hosts)
                      AND (cpu_usage_pct > 80 OR mem_usage_pct > 80)
                    ORDER BY cpu_usage_pct DESC
                """)
                host_spikes = [dict(r) for r in cur.fetchall()]

                # AD/DNS comparison
                cur.execute("""
                    SELECT run_date::text, total_users, enabled_users, disabled_users,
                           locked_users, total_computers, total_groups, dns_zones, dns_records
                    FROM snap_ad_dns_summary
                    ORDER BY run_date DESC LIMIT 2
                """)
                ad_changes = [dict(r) for r in cur.fetchall()]

                # IPAM comparison
                cur.execute("""
                    SELECT run_date::text, total_subnets, total_ips, used_ips,
                           utilisation_pct, subnets_critical
                    FROM snap_ipam_summary
                    ORDER BY run_date DESC LIMIT 2
                """)
                ipam_changes = [dict(r) for r in cur.fetchall()]

                # Project utilization Ã¢â‚¬â€ top movers
                cur.execute("""
                    WITH latest AS (
                        SELECT tag_name, vm_count, chargeback_inr, run_date
                        FROM snap_project_utilization
                        WHERE run_date = (SELECT MAX(run_date) FROM snap_project_utilization)
                    ), prev AS (
                        SELECT tag_name, vm_count, chargeback_inr, run_date
                        FROM snap_project_utilization
                        WHERE run_date = (SELECT MAX(run_date) FROM snap_project_utilization
                                          WHERE run_date < (SELECT MAX(run_date) FROM snap_project_utilization))
                    )
                    SELECT l.tag_name,
                           l.vm_count AS vm_count_now, COALESCE(p.vm_count,0) AS vm_count_prev,
                           l.chargeback_inr AS cost_now, COALESCE(p.chargeback_inr,0) AS cost_prev
                    FROM latest l LEFT JOIN prev p ON l.tag_name = p.tag_name
                    ORDER BY ABS(l.vm_count - COALESCE(p.vm_count,0)) DESC
                    LIMIT 10
                """)
                project_changes = [dict(r) for r in cur.fetchall()]

        return {
            "kpi": kpi_rows,
            "vmware": vmware_changes,
            "host_spikes": host_spikes,
            "addns": ad_changes,
            "ipam": ipam_changes,
            "projects": project_changes,
        }
    except Exception as e:
        logging.warning(f"insights_changes: {e}")
        return {"error": str(e)}


@app.get("/api/insights/capacity")
def insights_capacity(u=Depends(get_current_user)):
    """Capacity planning Ã¢â‚¬â€ exhaustion predictions + chargeback trends."""
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                # Last 30 days KPI for trend analysis
                cur.execute("""
                    SELECT run_date, total_vms, running_vms, total_hosts,
                           avg_cpu_pct, avg_mem_pct,
                           total_storage_tb, used_storage_tb, storage_usage_pct,
                           ip_utilisation_pct
                    FROM snap_platform_kpi
                    ORDER BY run_date DESC LIMIT 30
                """)
                kpi_trend = [dict(r) for r in cur.fetchall()]
                kpi_trend.reverse()

                # VMware cluster capacity
                cur.execute("""
                    SELECT cluster_name, vcenter_name, total_hosts, total_vms,
                           cpu_cores, cpu_used_mhz, mem_total_gb, mem_used_gb
                    FROM snap_vmware_clusters
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_vmware_clusters)
                    ORDER BY vcenter_name, cluster_name
                """)
                clusters = [dict(r) for r in cur.fetchall()]

                # Hosts with low free capacity (CPU>70 or MEM>70)
                cur.execute("""
                    SELECT host_name, vcenter_name, cluster_name,
                           cpu_usage_pct, mem_usage_pct, vm_count
                    FROM snap_vmware_hosts
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_vmware_hosts)
                      AND (cpu_usage_pct >= 70 OR mem_usage_pct >= 70)
                    ORDER BY GREATEST(cpu_usage_pct, mem_usage_pct) DESC
                    LIMIT 15
                """)
                constrained_hosts = [dict(r) for r in cur.fetchall()]

                # Project chargeback Ã¢â‚¬â€ latest
                cur.execute("""
                    SELECT tag_name, owner, vm_count, cpu_cores, ram_gb, disk_gb,
                           chargeback_inr, chargeback_usd
                    FROM snap_project_utilization
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_project_utilization)
                    ORDER BY chargeback_inr DESC
                """)
                chargeback = [dict(r) for r in cur.fetchall()]

                # IPAM - subnets nearing exhaustion
                cur.execute("""
                    SELECT total_subnets, total_ips, used_ips, free_ips,
                           utilisation_pct, subnets_critical, subnets_warning
                    FROM snap_ipam_summary
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_ipam_summary)
                    LIMIT 1
                """)
                ipam_row = cur.fetchone()
                ipam = dict(ipam_row) if ipam_row else {}

        # Compute exhaustion dates using linear regression
        import datetime as dt
        def exhaust_date(vals, threshold=100.0):
            """Given a list of (date, pct) pairs, predict when pct reaches threshold."""
            if len(vals) < 2:
                return None
            xs = list(range(len(vals)))
            ys = [v[1] for v in vals]
            n = len(xs)
            sx, sy = sum(xs), sum(ys)
            sxy = sum(a*b for a,b in zip(xs,ys))
            sx2 = sum(a*a for a in xs)
            try:
                m = (n*sxy - sx*sy) / (n*sx2 - sx*sx)
                b = (sy - m*sx) / n
            except ZeroDivisionError:
                return None
            if m <= 0:
                return None  # not growing
            last_val = m * (n-1) + b
            if last_val >= threshold:
                return "now"
            days_left = (threshold - last_val) / m
            if days_left > 365:
                return None
            return (vals[-1][0] + dt.timedelta(days=int(days_left))).isoformat()

        storage_exhaust = exhaust_date(
            [(r["run_date"], float(r.get("storage_usage_pct",0) or 0)) for r in kpi_trend],
            threshold=90.0
        )
        ip_exhaust = exhaust_date(
            [(r["run_date"], float(r.get("ip_utilisation_pct",0) or 0)) for r in kpi_trend],
            threshold=90.0
        )

        # Serialize dates in kpi_trend
        for r in kpi_trend:
            if hasattr(r.get("run_date"), "isoformat"):
                r["run_date"] = r["run_date"].isoformat()

        return {
            "kpi_trend": kpi_trend,
            "clusters": clusters,
            "constrained_hosts": constrained_hosts,
            "chargeback": chargeback,
            "ipam": ipam,
            "storage_exhaust_date": storage_exhaust,
            "ip_exhaust_date": ip_exhaust,
        }
    except Exception as e:
        logging.warning(f"insights_capacity: {e}")
        return {"error": str(e)}


@app.get("/api/insights/executive")
def insights_executive(u=Depends(get_current_user)):
    """Executive weekly summary Ã¢â‚¬â€ aggregated KPIs and highlights."""
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                # This week vs last week KPIs
                cur.execute("""
                    SELECT run_date::text, total_vms, running_vms, powered_off_vms,
                           total_hosts, avg_cpu_pct, avg_mem_pct,
                           total_storage_tb, used_storage_tb, storage_usage_pct,
                           total_pods, aws_instances, ip_utilisation_pct,
                           critical_alerts, warning_alerts
                    FROM snap_platform_kpi
                    ORDER BY run_date DESC LIMIT 14
                """)
                kpi_14d = [dict(r) for r in cur.fetchall()]
                kpi_14d.reverse()

                # Total chargeback current
                cur.execute("""
                    SELECT COUNT(*) AS projects,
                           SUM(vm_count) AS total_vms,
                           SUM(chargeback_inr) AS total_inr,
                           SUM(chargeback_usd) AS total_usd
                    FROM snap_project_utilization
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_project_utilization)
                """)
                cb = dict(cur.fetchone() or {})

                # AD/DNS latest
                cur.execute("""
                    SELECT total_users, enabled_users, disabled_users, locked_users,
                           total_computers, total_groups, dns_zones, dns_records
                    FROM snap_ad_dns_summary
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_ad_dns_summary)
                    LIMIT 1
                """)
                ad_row = cur.fetchone()
                addns = dict(ad_row) if ad_row else {}

                # Platform counts
                cur.execute("SELECT COUNT(*) AS cnt FROM snap_vmware_summary WHERE run_date=(SELECT MAX(run_date) FROM snap_vmware_summary)")
                vc_count = (cur.fetchone() or {}).get("cnt", 0)
                cur.execute("SELECT COUNT(*) AS cnt FROM snap_ocp_summary WHERE run_date=(SELECT MAX(run_date) FROM snap_ocp_summary)")
                ocp_count = (cur.fetchone() or {}).get("cnt", 0)
                cur.execute("SELECT COUNT(*) AS cnt FROM snap_nutanix_summary WHERE run_date=(SELECT MAX(run_date) FROM snap_nutanix_summary)")
                nut_count = (cur.fetchone() or {}).get("cnt", 0)

                # Last run
                cur.execute("SELECT run_date::text, status, duration_sec FROM snapshot_runs ORDER BY run_date DESC LIMIT 1")
                last_run = dict(cur.fetchone() or {})

        return {
            "kpi_14d": kpi_14d,
            "chargeback": cb,
            "addns": addns,
            "platform_counts": {"vcenters": vc_count, "ocp_clusters": ocp_count, "nutanix_pcs": nut_count},
            "last_run": last_run,
        }
    except Exception as e:
        logging.warning(f"insights_executive: {e}")
        return {"error": str(e)}


# Ã¢â€â‚¬Ã¢â€â‚¬ Insights: Backup Analytics Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.get("/api/insights/backup")
def insights_backup(u=Depends(get_current_user)):
    """Backup analytics Ã¢â‚¬â€ reads from PostgreSQL snapshots (fast) + live platform list."""
    from datetime import datetime, timedelta
    result = {
        "platforms": [], "jobs": [], "daily_trend": [],
        "summary": {"protected": 0, "unprotected": 0, "jobs_ok": 0, "jobs_fail": 0,
                     "jobs_running": 0, "used_bytes": 0, "total_bytes": 0,
                     "clusters": 0, "sla_count": 0, "alerts": 0},
        "history": [],
    }
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                # Ã¢â€â‚¬Ã¢â€â‚¬ Summary from latest snapshot Ã¢â€â‚¬Ã¢â€â‚¬
                cur.execute("""
                    SELECT platform_name, platform_type, status,
                           COALESCE(protected,0) AS protected,
                           COALESCE(unprotected,0) AS unprotected,
                           COALESCE(jobs_ok,0) AS jobs_ok,
                           COALESCE(jobs_fail,0) AS jobs_fail,
                           COALESCE(jobs_running,0) AS jobs_running,
                           COALESCE(used_bytes,0) AS used_bytes,
                           COALESCE(total_bytes,0) AS total_bytes,
                           COALESCE(clusters,0) AS clusters,
                           COALESCE(sla_count,0) AS sla_count,
                           COALESCE(alerts,0) AS alerts
                    FROM snap_backup_summary
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_backup_summary)
                    ORDER BY platform_type
                """)
                rows = cur.fetchall()
                for r in rows:
                    result["platforms"].append({
                        "name": r["platform_name"], "type": r["platform_type"],
                        "status": r["status"] or "ok",
                        "protected": r["protected"], "unprotected": r["unprotected"],
                        "jobs_ok": r["jobs_ok"], "jobs_fail": r["jobs_fail"],
                        "used_bytes": r["used_bytes"], "total_bytes": r["total_bytes"],
                        "clusters": r["clusters"], "sla_count": r["sla_count"],
                        "alerts": r["alerts"],
                    })
                    if r["status"] == "ok":
                        result["summary"]["protected"]   += r["protected"]
                        result["summary"]["unprotected"] += r["unprotected"]
                        result["summary"]["jobs_ok"]     += r["jobs_ok"]
                        result["summary"]["jobs_fail"]   += r["jobs_fail"]
                        result["summary"]["jobs_running"]+= r["jobs_running"]
                        result["summary"]["used_bytes"]  += r["used_bytes"]
                        result["summary"]["total_bytes"] += r["total_bytes"]
                        result["summary"]["clusters"]    += r["clusters"]
                        result["summary"]["sla_count"]   += r["sla_count"]
                        result["summary"]["alerts"]      += r["alerts"]

                # Ã¢â€â‚¬Ã¢â€â‚¬ Recent jobs from latest snapshot Ã¢â€â‚¬Ã¢â€â‚¬
                cur.execute("""
                    SELECT platform, object_name, status, job_type, start_time, end_time
                    FROM snap_backup_jobs
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_backup_jobs)
                    ORDER BY start_time DESC NULLS LAST
                    LIMIT 200
                """)
                for j in cur.fetchall():
                    result["jobs"].append({
                        "platform": j["platform"], "name": j["object_name"] or "",
                        "status": j["status"] or "", "type": j["job_type"] or "",
                        "start": j["start_time"] or "", "end": j["end_time"] or "",
                    })

                # Ã¢â€â‚¬Ã¢â€â‚¬ History (last 30 days) Ã¢â€â‚¬Ã¢â€â‚¬
                cur.execute("""
                    SELECT run_date::text,
                           SUM(COALESCE(protected,0)) AS protected,
                           SUM(COALESCE(unprotected,0)) AS unprotected,
                           SUM(COALESCE(jobs_ok,0)) AS jobs_ok,
                           SUM(COALESCE(jobs_fail,0)) AS jobs_fail,
                           SUM(COALESCE(jobs_running,0)) AS jobs_running,
                           SUM(COALESCE(used_bytes,0)) AS used_bytes,
                           SUM(COALESCE(total_bytes,0)) AS total_bytes,
                           COUNT(*) AS platform_count
                    FROM snap_backup_summary
                    WHERE run_date >= CURRENT_DATE - INTERVAL '30 days'
                      AND status = 'ok'
                    GROUP BY run_date
                    ORDER BY run_date ASC
                """)
                result["history"] = [dict(r) for r in cur.fetchall()]

                # Ã¢â€â‚¬Ã¢â€â‚¬ Daily trend from job data Ã¢â€â‚¬Ã¢â€â‚¬
                now = datetime.utcnow()
                buckets = {}
                for i in range(14):
                    d = (now - timedelta(days=13-i)).strftime("%Y-%m-%d")
                    buckets[d] = {"date": d, "ok": 0, "fail": 0, "running": 0, "total": 0}

                cur.execute("""
                    SELECT run_date::text,
                           COUNT(*) FILTER (WHERE status ILIKE '%%success%%' OR status ILIKE '%%succeeded%%') AS ok,
                           COUNT(*) FILTER (WHERE status ILIKE '%%fail%%' OR status ILIKE '%%error%%') AS fail,
                           COUNT(*) AS total
                    FROM snap_backup_jobs
                    WHERE run_date >= CURRENT_DATE - INTERVAL '14 days'
                    GROUP BY run_date
                    ORDER BY run_date ASC
                """)
                for r in cur.fetchall():
                    ds = r["run_date"]
                    if ds in buckets:
                        buckets[ds]["ok"]    = r["ok"] or 0
                        buckets[ds]["fail"]  = r["fail"] or 0
                        buckets[ds]["total"] = r["total"] or 0
                        buckets[ds]["running"] = max(0, (r["total"] or 0) - (r["ok"] or 0) - (r["fail"] or 0))

                result["daily_trend"] = list(buckets.values())

    except Exception as e:
        logging.warning(f"insights_backup PG error: {e}")
        # If PG fails, try to at least get platform list from SQLite
        try:
            for c in rubrik_list():
                result["platforms"].append({"name": c.get("name","Rubrik"), "type": "rubrik", "status": "unknown"})
            for c in ch_list():
                result["platforms"].append({"name": c.get("name","Cohesity"), "type": "cohesity", "status": "unknown"})
            for c in _vm_list():
                result["platforms"].append({"name": c.get("name","Veeam"), "type": "veeam", "status": "unknown"})
        except Exception:
            pass
    return result



# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
#  STORAGE ANALYTICS  APIs  (History, Forecast, Collect)
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â

@app.get("/api/insights/storage")
def insights_storage(days: int = 30, u=Depends(get_current_user)):
    """Storage analytics Ã¢â‚¬â€ per-array history + aggregate summary + vendor breakdown."""
    days = min(max(days, 1), 90)
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                # Per-array latest snapshot
                cur.execute("""
                    SELECT array_id, array_name, vendor, site,
                           total_capacity_tb, used_capacity_tb, used_pct, free_tb,
                           volume_count, snapshot_count, host_count, alert_count,
                           controller_count, iops_read, iops_write,
                           latency_read_ms, latency_write_ms, bandwidth_mbps,
                           data_reduction, dedup_ratio, thin_provisioning, status
                    FROM snap_storage_arrays
                    WHERE run_date = (SELECT MAX(run_date) FROM snap_storage_arrays)
                    ORDER BY vendor, array_name
                """)
                latest_arrays = [dict(r) for r in cur.fetchall()]

                # Aggregate summary trend
                cur.execute("""
                    SELECT run_date::text, total_arrays, arrays_ok, arrays_error,
                           total_capacity_tb, used_capacity_tb, used_pct, free_tb,
                           total_volumes, total_snapshots, total_hosts, total_alerts,
                           vendor_breakdown
                    FROM snap_storage_summary
                    WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval
                    ORDER BY run_date
                """, (days,))
                summary_trend = [dict(r) for r in cur.fetchall()]

                # Per-array history for trend charts
                cur.execute("""
                    SELECT run_date::text, array_id, array_name, vendor,
                           total_capacity_tb, used_capacity_tb, used_pct,
                           volume_count, alert_count, iops_read, iops_write,
                           latency_read_ms, latency_write_ms, status
                    FROM snap_storage_arrays
                    WHERE run_date >= CURRENT_DATE - (%s || ' days')::interval
                    ORDER BY run_date, array_name
                """, (days,))
                array_history = [dict(r) for r in cur.fetchall()]

                # Vendor breakdown from latest
                vendor_stats = {}
                for a in latest_arrays:
                    v = a["vendor"]
                    if v not in vendor_stats:
                        vendor_stats[v] = {"count": 0, "total_tb": 0, "used_tb": 0,
                                           "volumes": 0, "alerts": 0}
                    vendor_stats[v]["count"] += 1
                    vendor_stats[v]["total_tb"] += float(a.get("total_capacity_tb") or 0)
                    vendor_stats[v]["used_tb"] += float(a.get("used_capacity_tb") or 0)
                    vendor_stats[v]["volumes"] += int(a.get("volume_count") or 0)
                    vendor_stats[v]["alerts"] += int(a.get("alert_count") or 0)

        return {
            "days": days,
            "latest_arrays": latest_arrays,
            "summary_trend": summary_trend,
            "array_history": array_history,
            "vendor_stats": vendor_stats,
        }
    except Exception as e:
        logging.warning(f"insights_storage: {e}")
        return {"error": str(e), "days": days,
                "latest_arrays": [], "summary_trend": [],
                "array_history": [], "vendor_stats": {}}


@app.get("/api/forecast/storage")
def forecast_storage(horizon: int = 7, u=Depends(get_current_user)):
    """Storage capacity forecast per array + aggregate Ã¢â‚¬â€ linear regression."""
    horizon = min(max(horizon, 1), 30)
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                # Get last 30 days of summary for aggregate forecast
                cur.execute("""
                    SELECT run_date, total_capacity_tb, used_capacity_tb, used_pct
                    FROM snap_storage_summary
                    ORDER BY run_date DESC LIMIT 30
                """)
                summary_rows = list(reversed([dict(r) for r in cur.fetchall()]))

                # Per-array last 30 days
                cur.execute("""
                    SELECT run_date, array_id, array_name, vendor,
                           total_capacity_tb, used_capacity_tb, used_pct
                    FROM snap_storage_arrays
                    WHERE run_date >= CURRENT_DATE - INTERVAL '30 days'
                      AND status = 'ok'
                    ORDER BY array_id, run_date
                """)
                arr_rows = [dict(r) for r in cur.fetchall()]

        import datetime as dt

        def linreg(xs, ys):
            n = len(xs)
            if n < 2: return 0.0, 0.0, 0.0
            sx, sy = sum(xs), sum(ys)
            sxy = sum(a*b for a,b in zip(xs,ys))
            sx2 = sum(a*a for a in xs)
            try:
                m = (n*sxy - sx*sy) / (n*sx2 - sx*sx)
                b = (sy - m*sx) / n
            except ZeroDivisionError:
                m, b = 0.0, (sy/n if n else 0.0)
            preds = [m*xi+b for xi in xs]
            resid = [yi-pi for yi,pi in zip(ys,preds)]
            std = (sum(r*r for r in resid)/n)**0.5
            return m, b, std

        # Aggregate forecast
        agg_forecast = []
        agg_history = []
        if len(summary_rows) >= 2:
            x = list(range(len(summary_rows)))
            for f in ["used_capacity_tb", "used_pct"]:
                ys = [float(r.get(f) or 0) for r in summary_rows]
                m, b, std = linreg(x, ys)
                last_date = summary_rows[-1]["run_date"]
                offset = len(x)
                for i in range(1, horizon+1):
                    proj_date = last_date + dt.timedelta(days=i)
                    xi = offset + i - 1
                    val = round(m*xi + b, 2)
                    # Find or create the forecast row
                    existing = next((r for r in agg_forecast if r["run_date"] == proj_date.isoformat()), None)
                    if not existing:
                        existing = {"run_date": proj_date.isoformat(), "forecast": True}
                        agg_forecast.append(existing)
                    existing[f] = max(val, 0.0)
                    existing[f+"_lo"] = max(round(val - 1.645*std, 2), 0.0)
                    existing[f+"_hi"] = max(round(val + 1.645*std, 2), 0.0)

            agg_history = [{
                "run_date": r["run_date"].isoformat() if hasattr(r["run_date"], "isoformat") else str(r["run_date"]),
                "total_capacity_tb": float(r.get("total_capacity_tb") or 0),
                "used_capacity_tb": float(r.get("used_capacity_tb") or 0),
                "used_pct": float(r.get("used_pct") or 0),
                "forecast": False,
            } for r in summary_rows]

            # Exhaustion date (when used_pct hits 85%)
            pct_vals = [float(r.get("used_pct") or 0) for r in summary_rows]
            m_pct, b_pct, _ = linreg(list(range(len(pct_vals))), pct_vals)
            exhaust_85 = None
            exhaust_90 = None
            if m_pct > 0:
                last_pct = m_pct * (len(pct_vals)-1) + b_pct
                if last_pct < 85:
                    d85 = (85 - last_pct) / m_pct
                    if d85 <= 365:
                        exhaust_85 = (summary_rows[-1]["run_date"] + dt.timedelta(days=int(d85))).isoformat()
                if last_pct < 90:
                    d90 = (90 - last_pct) / m_pct
                    if d90 <= 365:
                        exhaust_90 = (summary_rows[-1]["run_date"] + dt.timedelta(days=int(d90))).isoformat()

        # Per-array forecasts
        array_forecasts = {}
        by_arr = {}
        for r in arr_rows:
            aid = r["array_id"]
            if aid not in by_arr:
                by_arr[aid] = {"name": r["array_name"], "vendor": r["vendor"], "rows": []}
            by_arr[aid]["rows"].append(r)

        for aid, info in by_arr.items():
            rows = info["rows"]
            if len(rows) < 2:
                continue
            x = list(range(len(rows)))
            ys = [float(r.get("used_pct") or 0) for r in rows]
            m, b, std = linreg(x, ys)
            last_date = rows[-1]["run_date"]
            last_pct = float(rows[-1].get("used_pct") or 0)
            proj_pct = round(m * (len(x) + horizon - 1) + b, 2) if m else last_pct
            exhaust = None
            if m > 0 and last_pct < 90:
                days_left = (90 - last_pct) / m
                if days_left <= 365:
                    exhaust = (last_date + dt.timedelta(days=int(days_left))).isoformat()
            array_forecasts[str(aid)] = {
                "name": info["name"], "vendor": info["vendor"],
                "current_pct": last_pct, "projected_pct": max(proj_pct, 0),
                "trend_per_day": round(m, 4),
                "exhaust_90": exhaust,
            }

        return {
            "horizon": horizon,
            "aggregate": {"history": agg_history, "forecast": agg_forecast,
                          "exhaust_85": exhaust_85 if 'exhaust_85' in dir() else None,
                          "exhaust_90": exhaust_90 if 'exhaust_90' in dir() else None},
            "arrays": array_forecasts,
        }
    except Exception as e:
        logging.error(f"forecast_storage: {e}")
        return {"error": str(e), "horizon": horizon,
                "aggregate": {"history": [], "forecast": []}, "arrays": {}}


@app.post("/api/history/collect_storage")
def collect_storage_now(u=Depends(require_role("admin"))):
    """Manually trigger storage snapshot collection."""
    import threading
    from datetime import date as _date
    def _run():
        try:
            from storage_client import list_arrays, get_array_data
            import json as _json
            today = _date.today()
            conn = _pg_conn()
            cur = conn.cursor()
            arrays = list_arrays()
            for arr in arrays:
                try:
                    data = get_array_data(arr)
                    cap = data.get("capacity") or {}
                    total_tb = float(cap.get("total_tb",0) or 0)
                    used_tb  = float(cap.get("used_tb",0) or 0)
                    used_pct = float(cap.get("used_pct",0) or 0)
                    free_tb  = round(total_tb - used_tb, 3)
                    vols = data.get("volumes") or data.get("filesystems") or data.get("buckets") or []
                    snaps = data.get("snapshots") or data.get("fb_snapshots") or []
                    hosts_l = data.get("hosts") or data.get("blades") or []
                    alerts_l = data.get("alerts") or data.get("fa_alerts") or data.get("fb_alerts") or []
                    ctrls = data.get("controllers") or []
                    perf = data.get("performance") or {}
                    cur.execute("""
                        INSERT INTO snap_storage_arrays
                        (run_date, array_id, array_name, vendor, site,
                         total_capacity_tb, used_capacity_tb, used_pct, free_tb,
                         volume_count, snapshot_count, host_count, alert_count, controller_count,
                         iops_read, iops_write, latency_read_ms, latency_write_ms, bandwidth_mbps,
                         data_reduction, dedup_ratio, thin_provisioning, status, raw_json)
                        VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s, %s,%s)
                        ON CONFLICT (run_date, array_id) DO UPDATE SET
                            total_capacity_tb=EXCLUDED.total_capacity_tb,
                            used_capacity_tb=EXCLUDED.used_capacity_tb,
                            used_pct=EXCLUDED.used_pct, free_tb=EXCLUDED.free_tb,
                            volume_count=EXCLUDED.volume_count, snapshot_count=EXCLUDED.snapshot_count,
                            host_count=EXCLUDED.host_count, alert_count=EXCLUDED.alert_count,
                            status=EXCLUDED.status, raw_json=EXCLUDED.raw_json,
                            collected_at=NOW()
                    """, (today, arr["id"], arr.get("name",""), arr.get("vendor",""), arr.get("site",""),
                          round(total_tb,3), round(used_tb,3), round(used_pct,2), free_tb,
                          len(vols), len(snaps), len(hosts_l), len(alerts_l), len(ctrls),
                          float(perf.get("reads_per_sec",perf.get("read_iops",0)) or 0),
                          float(perf.get("writes_per_sec",perf.get("write_iops",0)) or 0),
                          float(perf.get("read_latency_ms",perf.get("usec_per_read_op",0)) or 0),
                          float(perf.get("write_latency_ms",perf.get("usec_per_write_op",0)) or 0),
                          float(perf.get("bandwidth_mbps",0) or 0),
                          float(cap.get("data_reduction",0) or 0),
                          float(cap.get("dedup_ratio",0) or 0),
                          float(cap.get("thin_provisioning",0) or 0),
                          "ok", _json.dumps({"capacity": cap, "performance": perf})))
                    conn.commit()
                except Exception as ex:
                    logging.warning(f"collect_storage_now: {arr.get('name','?')}: {ex}")
                    conn.rollback()
                    cur.execute("""
                        INSERT INTO snap_storage_arrays
                        (run_date, array_id, array_name, vendor, site, status)
                        VALUES (%s,%s,%s,%s,%s,'error')
                        ON CONFLICT (run_date, array_id) DO UPDATE SET status='error', collected_at=NOW()
                    """, (today, arr["id"], arr.get("name",""), arr.get("vendor",""), arr.get("site","")))
                    conn.commit()

            # Build summary
            cur.execute("""
                INSERT INTO snap_storage_summary
                (run_date, total_arrays, arrays_ok, arrays_error,
                 total_capacity_tb, used_capacity_tb, used_pct, free_tb,
                 total_volumes, total_snapshots, total_hosts, total_alerts)
                SELECT run_date, COUNT(*), COUNT(*) FILTER (WHERE status='ok'),
                       COUNT(*) FILTER (WHERE status='error'),
                       COALESCE(SUM(total_capacity_tb),0), COALESCE(SUM(used_capacity_tb),0),
                       CASE WHEN SUM(total_capacity_tb)>0
                            THEN ROUND(SUM(used_capacity_tb)/SUM(total_capacity_tb)*100,2)
                            ELSE 0 END,
                       COALESCE(SUM(free_tb),0),
                       COALESCE(SUM(volume_count),0), COALESCE(SUM(snapshot_count),0),
                       COALESCE(SUM(host_count),0), COALESCE(SUM(alert_count),0)
                FROM snap_storage_arrays WHERE run_date = %s
                GROUP BY run_date
                ON CONFLICT (run_date) DO UPDATE SET
                    total_arrays=EXCLUDED.total_arrays, arrays_ok=EXCLUDED.arrays_ok,
                    arrays_error=EXCLUDED.arrays_error,
                    total_capacity_tb=EXCLUDED.total_capacity_tb,
                    used_capacity_tb=EXCLUDED.used_capacity_tb,
                    used_pct=EXCLUDED.used_pct, free_tb=EXCLUDED.free_tb,
                    total_volumes=EXCLUDED.total_volumes, total_snapshots=EXCLUDED.total_snapshots,
                    total_hosts=EXCLUDED.total_hosts, total_alerts=EXCLUDED.total_alerts,
                    collected_at=NOW()
            """, (today,))
            conn.commit()
            conn.close()
            logging.info(f"Storage collection completed: {len(arrays)} arrays")
        except Exception as e:
            logging.error(f"collect_storage_now background: {e}")

    threading.Thread(target=_run, daemon=True).start()
    audit(u["username"], "STORAGE_COLLECT", target="manual", role=u["role"])

    return {"ok": True, "message": "Storage collection started in background"}


# Ã¢â€â‚¬Ã¢â€â‚¬ On-demand AWS snapshot Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
@app.post("/api/history/collect_aws")
def collect_aws_now(u=Depends(require_role("admin", "operator"))):
    """
    Immediately collect AWS EC2 data and write it to PostgreSQL (snap_aws_summary
    and snap_platform_kpi), so the Overview / Executive tiles update right away
    rather than waiting for the 23:00 daily run.
    """
    import threading
    from datetime import date as _date

    def _run():
        try:
            from aws_client import get_ec2_summary, has_credentials
            import json as _json
            today = _date.today()
            if not has_credentials():
                logging.info("collect_aws_now: no credentials, skipping")
                return
            import os as _os
            region = _os.getenv("AWS_REGION", "ap-south-1").strip("'\"")
            summary = get_ec2_summary(region)
            if summary.get("error"):
                logging.warning(f"collect_aws_now: {summary['error']}")
                return

            total   = int(summary.get("total",   0) or 0)
            running = int(summary.get("running", 0) or 0)
            stopped = int(summary.get("stopped", 0) or 0)
            term    = int(summary.get("terminated", 0) or 0)
            pending = int(summary.get("pending", 0) or 0)
            itypes  = _json.dumps(summary.get("instance_types", {}))

            conn = _pg_conn()
            cur  = conn.cursor()

            # Ã¢â€â‚¬Ã¢â€â‚¬ snap_aws_summary Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            cur.execute("""
                INSERT INTO snap_aws_summary
                    (run_date, region, total_instances, running, stopped,
                     terminated, pending, instance_types)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (run_date) DO UPDATE SET
                    total_instances = EXCLUDED.total_instances,
                    running         = EXCLUDED.running,
                    stopped         = EXCLUDED.stopped,
                    terminated      = EXCLUDED.terminated,
                    pending         = EXCLUDED.pending,
                    instance_types  = EXCLUDED.instance_types,
                    collected_at    = NOW()
            """, (today, region, total, running, stopped, term, pending, itypes))

            # Ã¢â€â‚¬Ã¢â€â‚¬ snap_platform_kpi Ã¢â‚¬â€ update aws columns only Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            # Upsert today's row: if it already exists just update aws cols;
            # if it doesn't exist, insert a minimal row so the overview tile
            # shows a number immediately.
            cur.execute("""
                INSERT INTO snap_platform_kpi
                    (run_date, aws_instances, aws_running)
                VALUES (%s, %s, %s)
                ON CONFLICT (run_date) DO UPDATE SET
                    aws_instances = EXCLUDED.aws_instances,
                    aws_running   = EXCLUDED.aws_running
            """, (today, total, running))

            conn.commit()
            conn.close()
            logging.info(f"collect_aws_now: {total} instances ({running} running) saved for {today}")
        except Exception as e:
            logging.error(f"collect_aws_now background: {e}")

    threading.Thread(target=_run, daemon=True).start()
    audit(u["username"], "AWS_COLLECT", target="manual", role=u["role"])
    return {"ok": True, "message": "AWS collection started in background"}


# ── On-demand IPAM snapshot (PostgreSQL IPAM v2) ──────────────────────────────
@app.post("/api/history/collect_ipam")
def collect_ipam_now(u=Depends(require_role("admin", "operator"))):
    """
    Immediately collect IPAM data from the self-hosted PostgreSQL IPAM
    and write it to snap_ipam_summary so Insights/History/Forecast pages
    update right away rather than waiting for the 23:00 daily run.
    """
    import threading
    from datetime import date as _date

    def _run():
        try:
            today = _date.today()
            summary = _ipam_pg.get_summary()
            if not summary:
                logging.warning("collect_ipam_now: empty summary")
                return

            total_vlans   = int(summary.get("total_vlans",   0) or 0)
            total_ips     = int(summary.get("total_ips",     0) or 0)
            used_ips      = int(summary.get("used_ips",      0) or 0)
            free_ips      = int(summary.get("free_ips",      summary.get("available_ips", 0)) or 0)
            reserved_ips  = int(summary.get("reserved_ips",  0) or 0)
            util_pct      = round(used_ips / total_ips * 100, 2) if total_ips > 0 else 0.0

            # Count VLANs with >80% usage (critical) and >60% (warning)
            vlans = _ipam_pg.list_vlans()
            subnets_critical = sum(1 for v in vlans
                if v.get("total_ips",0) > 0
                and (v.get("used_ips",0) / v["total_ips"]) * 100 >= 80)
            subnets_warning  = sum(1 for v in vlans
                if v.get("total_ips",0) > 0
                and 60 <= (v.get("used_ips",0) / v["total_ips"]) * 100 < 80)

            conn = _pg_conn()
            cur  = conn.cursor()
            cur.execute("DELETE FROM snap_ipam_summary WHERE run_date = %s", (today,))
            cur.execute("""
                INSERT INTO snap_ipam_summary
                    (run_date, total_subnets, total_ips, used_ips, free_ips,
                     reserved_ips, utilisation_pct, subnets_critical, subnets_warning,
                     collected_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (today, total_vlans, total_ips, used_ips, free_ips,
                  reserved_ips, util_pct, subnets_critical, subnets_warning))
            conn.commit()
            conn.close()
            logging.info(f"collect_ipam_now: {total_vlans} VLANs, {total_ips} IPs, {util_pct}% used")
        except Exception as e:
            logging.error(f"collect_ipam_now background: {e}")

    threading.Thread(target=_run, daemon=True).start()
    audit(u["username"], "IPAM_COLLECT", target="manual", role=u["role"])
    return {"ok": True, "message": "IPAM collection started in background"}


# ═══════════════════════════════════════════════════════════════════════════════
# CMDB – Configuration Management Database
# ═══════════════════════════════════════════════════════════════════════════════

import cmdb_client as _cmdb

# Init CMDB tables on first import
try:
    _cmdb.init_cmdb_db()
except Exception as _e:
    logging.warning(f"CMDB DB init warning: {_e}")


class _SNConfig(BaseModel):
    instance_url:    str
    username:        str
    password:        str
    client_id:       str = ""
    client_secret:   str = ""
    default_company: str = "SDx-COE"
    default_bu:      str = "SDx-COE"
    push_vm:         bool = True
    push_host:       bool = True
    push_storage:    bool = True
    push_network:    bool = True
    push_physical:   bool = True


class _CIEdit(BaseModel):
    name:               str | None = None
    operational_status: str | None = None
    environment:        str | None = None
    department:         str | None = None
    business_unit:      str | None = None
    company:            str | None = None
    location:           str | None = None
    ip_address:         str | None = None
    fqdn:               str | None = None
    os:                 str | None = None
    os_version:         str | None = None
    serial_number:      str | None = None
    model_id:           str | None = None
    manufacturer:       str | None = None
    asset_tag:          str | None = None
    cpu_count:          int | None = None
    cpu_core_count:     int | None = None
    ram_mb:             int | None = None
    disk_space_gb:      float | None = None
    manager:            str | None = None
    owner:              str | None = None
    timezone:           str | None = None
    region:             str | None = None
    technology:         str | None = None
    tagging:            str | None = None


@app.get("/api/cmdb/summary")
def cmdb_summary(u=Depends(get_current_user)):
    try:
        return _cmdb.get_ci_summary()
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/api/cmdb/cis")
def cmdb_list_cis(
    cls: str = None, platform: str = None, search: str = None,
    limit: int = 5000, offset: int = 0,
    u=Depends(get_current_user)
):
    try:
        return {"items": _cmdb.list_cis(cls, platform, search, limit, offset)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/api/cmdb/collect")
def cmdb_collect_now(u=Depends(require_role("admin", "operator"))):
    import threading
    def _run():
        try:
            result = _cmdb.collect_all_cis()
            logging.info(f"CMDB manual collect: {result['total']} CIs")
        except Exception as e:
            logging.error(f"CMDB collect background: {e}")
    threading.Thread(target=_run, daemon=True).start()
    audit(u["username"], "CMDB_COLLECT", target="manual", role=u["role"])
    return {"ok": True, "message": "CMDB collection started in background"}


@app.patch("/api/cmdb/cis/{ci_id}")
def cmdb_update_ci(ci_id: int, body: _CIEdit, u=Depends(require_role("admin"))):
    fields = {k: v for k, v in body.dict().items() if v is not None}
    result = _cmdb.update_ci(ci_id, fields)
    audit(u["username"], "CMDB_CI_EDIT", target=str(ci_id), role=u["role"])
    return result


@app.get("/api/cmdb/sn-config")
def cmdb_get_sn_config(u=Depends(require_role("admin"))):
    cfg = _cmdb.get_sn_config()
    if cfg.get("password"):
        cfg["password"] = "••••••••"
    return cfg


@app.post("/api/cmdb/sn-config")
def cmdb_save_sn_config(body: _SNConfig, u=Depends(require_role("admin"))):
    result = _cmdb.save_sn_config(body.dict())
    audit(u["username"], "CMDB_SN_CONFIG", target=body.instance_url, role=u["role"])
    return result


@app.post("/api/cmdb/push-to-sn")
def cmdb_push_to_sn(dry_run: bool = False, u=Depends(require_role("admin", "operator"))):
    try:
        result = _cmdb.push_to_servicenow(dry_run=dry_run)
        audit(u["username"], "CMDB_SN_PUSH", target="servicenow",
              detail=f"pushed={result.get('pushed')}, errors={result.get('errors')}",
              role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/api/cmdb/export-csv")
def cmdb_export_csv(
    cls: str = None, platform: str = None, search: str = None,
    u=Depends(get_current_user)
):
    from fastapi.responses import Response
    csv_data = _cmdb.export_csv(cls, platform, search)
    audit(u["username"], "CMDB_EXPORT_CSV", target="csv", role=u["role"])
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cmdb_export.csv"}
    )


    return {"ok": True, "message": "IPAM collection started in background"}


# 
#  Magic Migrate - Cross-Hypervisor VM Migration Plans (Full Lifecycle)
#

def _init_migration_db():
    from db import get_conn
    with get_conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS migration_plans (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_name       TEXT NOT NULL,
            source_platform TEXT NOT NULL DEFAULT 'vmware',
            source_vcenter  TEXT,
            target_platform TEXT NOT NULL,
            target_detail   TEXT,
            vm_list         TEXT,
            preflight_result TEXT,
            network_mapping TEXT,
            storage_mapping TEXT,
            migration_tool  TEXT,
            status          TEXT NOT NULL DEFAULT 'planned',
            progress        INTEGER DEFAULT 0,
            event_log       TEXT DEFAULT '[]',
            notes           TEXT DEFAULT '',
            approved_by     TEXT,
            approved_at     TEXT,
            started_at      TEXT,
            completed_at    TEXT,
            created_by      TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        )""")
        for col, typedef in [
            ('progress', 'INTEGER DEFAULT 0'),
            ('event_log', "TEXT DEFAULT '[]'"),
            ('approved_by', 'TEXT'),
            ('approved_at', 'TEXT'),
            ('started_at', 'TEXT'),
            ('completed_at', 'TEXT'),
        ]:
            try:
                c.execute(f'ALTER TABLE migration_plans ADD COLUMN {col} {typedef}')
            except:
                pass

        c.execute("""CREATE TABLE IF NOT EXISTS move_groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_by  TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS move_group_vms (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    INTEGER NOT NULL REFERENCES move_groups(id) ON DELETE CASCADE,
            vm_name     TEXT NOT NULL,
            vm_moref    TEXT,
            vcenter_id  TEXT,
            vcenter_name TEXT,
            guest_os    TEXT DEFAULT '',
            cpu         INTEGER DEFAULT 0,
            memory_mb   INTEGER DEFAULT 0,
            disk_gb     REAL DEFAULT 0,
            power_state TEXT DEFAULT '',
            ip_address  TEXT DEFAULT '',
            esxi_host   TEXT DEFAULT '',
            added_at    TEXT DEFAULT (datetime('now'))
        )""")

_init_migration_db()

def _migration_log(plan_id: int, message: str, user: str = "system"):
    from db import get_conn
    import json as _json
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        row = c.execute("SELECT event_log FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            return
        try:
            log = _json.loads(row["event_log"] or "[]")
        except:
            log = []
        log.append({"ts": ts, "msg": message, "user": user})
        c.execute("UPDATE migration_plans SET event_log=?, updated_at=datetime('now') WHERE id=?",
                  (_json.dumps(log), plan_id))

@app.get("/api/migration/plans")
def list_migration_plans(u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        rows = c.execute("SELECT * FROM migration_plans ORDER BY created_at DESC").fetchall()
    plans = []
    for r in rows:
        d = dict(r)
        for k in ("vm_list","preflight_result","network_mapping","storage_mapping","event_log"):
            if d.get(k):
                try: d[k] = _json.loads(d[k])
                except: pass
        plans.append(d)
    return {"plans": plans}

@app.get("/api/migration/plans/{plan_id}")
def get_migration_plan(plan_id: int, u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        row = c.execute("SELECT * FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
    if not row:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Plan not found"})
    d = dict(row)
    for k in ("vm_list","preflight_result","network_mapping","storage_mapping","event_log"):
        if d.get(k):
            try: d[k] = _json.loads(d[k])
            except: pass
    return {"plan": d}

def _migration_log(plan_id: int, message: str, user: str = "system"):
    from db import get_conn
    import json as _json
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        row = c.execute("SELECT event_log FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            return
        try:
            log = _json.loads(row["event_log"] or "[]")
        except:
            log = []
        log.append({"ts": ts, "msg": message, "user": user})
        c.execute("UPDATE migration_plans SET event_log=?, updated_at=datetime('now') WHERE id=?",
                  (_json.dumps(log), plan_id))

@app.get("/api/migration/plans")
def list_migration_plans(u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        rows = c.execute("SELECT * FROM migration_plans ORDER BY created_at DESC").fetchall()
    plans = []
    for r in rows:
        d = dict(r)
        for k in ("vm_list","preflight_result","network_mapping","storage_mapping","event_log"):
            if d.get(k):
                try: d[k] = _json.loads(d[k])
                except: pass
        plans.append(d)
    return {"plans": plans}

@app.get("/api/migration/plans/{plan_id}")
def get_migration_plan(plan_id: int, u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        row = c.execute("SELECT * FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
    if not row:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Plan not found"})
    d = dict(row)
    for k in ("vm_list","preflight_result","network_mapping","storage_mapping","event_log"):
        if d.get(k):
            try: d[k] = _json.loads(d[k])
            except: pass
    return {"plan": d}

@app.post("/api/migration/plans")
def create_migration_plan(req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    import json as _json
    from datetime import datetime
    username = u.get("username", "admin")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    init_log = _json.dumps([{"ts": ts, "msg": f"Migration plan created by {username}", "user": username}])
    with get_conn() as c:
        c.execute("""INSERT INTO migration_plans
            (plan_name, source_platform, source_vcenter, target_platform,
             target_detail, vm_list, preflight_result, network_mapping,
             storage_mapping, migration_tool, status, notes, created_by, event_log, options)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (req.get("plan_name","Untitled"), req.get("source_platform","vmware"),
             _json.dumps(req.get("source_vcenter")), req.get("target_platform",""),
             _json.dumps(req.get("target_detail")), _json.dumps(req.get("vm_list",[])),
             _json.dumps(req.get("preflight_result")), _json.dumps(req.get("network_mapping")),
             _json.dumps(req.get("storage_mapping")), req.get("migration_tool",""),
             "planned", req.get("notes",""), username, init_log, _json.dumps(req.get("options",{}))))
        plan_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"ok": True, "message": "Migration plan created", "plan_id": plan_id}

@app.delete("/api/migration/plans/{plan_id}")
def delete_migration_plan(plan_id: int, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    with get_conn() as c:
        c.execute("DELETE FROM migration_plans WHERE id=?", (plan_id,))
    return {"ok": True}

VALID_STATUSES = ("planned","preflight_running","preflight_passed","preflight_failed",
                  "approved","executing","migrating","validating",
                  "completed","failed","cancelled","rolled_back")

@app.patch("/api/migration/plans/{plan_id}/status")
def update_plan_status(plan_id: int, req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    from datetime import datetime
    new_status = req.get("status", "")
    if new_status not in VALID_STATUSES:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": "Invalid status"})
    username = u.get("username", "?")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        row = c.execute("SELECT * FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"error": "Plan not found"})
        updates = {"status": new_status, "updated_at": ts}
        if new_status == "approved":
            updates["approved_by"] = username
            updates["approved_at"] = ts
        elif new_status == "executing":
            updates["started_at"] = ts
            updates["progress"] = 0
        elif new_status == "completed":
            updates["completed_at"] = ts
            updates["progress"] = 100
        elif new_status == "planned":
            updates["progress"] = 0
            updates["approved_by"] = None
            updates["approved_at"] = None
            updates["started_at"] = None
            updates["completed_at"] = None
        set_clause = ", ".join(f"{k}=?" for k in updates)
        c.execute(f"UPDATE migration_plans SET {set_clause} WHERE id=?",
                  (*updates.values(), plan_id))
    note = req.get("notes", "")
    msg = f"Status changed to '{new_status}' by {username}"
    if note:
        msg += f" -- {note}"
    _migration_log(plan_id, msg, username)
    return {"ok": True, "status": new_status}

@app.post("/api/migration/plans")
def create_migration_plan(req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    import json as _json
    from datetime import datetime
    username = u.get("username", "admin")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    init_log = _json.dumps([{"ts": ts, "msg": f"Migration plan created by {username}", "user": username}])
    with get_conn() as c:
        c.execute("""INSERT INTO migration_plans
            (plan_name, source_platform, source_vcenter, target_platform,
             target_detail, vm_list, preflight_result, network_mapping,
             storage_mapping, migration_tool, status, notes, created_by, event_log, options)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (req.get("plan_name","Untitled"), req.get("source_platform","vmware"),
             _json.dumps(req.get("source_vcenter")), req.get("target_platform",""),
             _json.dumps(req.get("target_detail")), _json.dumps(req.get("vm_list",[])),
             _json.dumps(req.get("preflight_result")), _json.dumps(req.get("network_mapping")),
             _json.dumps(req.get("storage_mapping")), req.get("migration_tool",""),
             "planned", req.get("notes",""), username, init_log, _json.dumps(req.get("options",{}))))
        plan_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"ok": True, "message": "Migration plan created", "plan_id": plan_id}

@app.delete("/api/migration/plans/{plan_id}")
def delete_migration_plan(plan_id: int, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    with get_conn() as c:
        c.execute("DELETE FROM migration_plans WHERE id=?", (plan_id,))
    return {"ok": True}

VALID_STATUSES = ("planned","preflight_running","preflight_passed","preflight_failed",
                  "approved","executing","migrating","validating",
                  "completed","failed","cancelled","rolled_back")

@app.patch("/api/migration/plans/{plan_id}/status")
def update_plan_status(plan_id: int, req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    from datetime import datetime
    new_status = req.get("status", "")
    if new_status not in VALID_STATUSES:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": "Invalid status"})
    username = u.get("username", "?")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        row = c.execute("SELECT * FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"error": "Plan not found"})
        updates = {"status": new_status, "updated_at": ts}
        if new_status == "approved":
            updates["approved_by"] = username
            updates["approved_at"] = ts
        elif new_status == "executing":
            updates["started_at"] = ts
            updates["progress"] = 0
        elif new_status == "completed":
            updates["completed_at"] = ts
            updates["progress"] = 100
        elif new_status == "planned":
            updates["progress"] = 0
            updates["approved_by"] = None
            updates["approved_at"] = None
            updates["started_at"] = None
            updates["completed_at"] = None
        set_clause = ", ".join(f"{k}=?" for k in updates)
        c.execute(f"UPDATE migration_plans SET {set_clause} WHERE id=?",
                  (*updates.values(), plan_id))
    note = req.get("notes", "")
    msg = f"Status changed to '{new_status}' by {username}"
    if note:
        msg += f" -- {note}"
    _migration_log(plan_id, msg, username)
    return {"ok": True, "status": new_status}

@app.post("/api/migration/plans/{plan_id}/execute")
def execute_migration(plan_id: int, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    import json as _json
    import threading
    username = u.get("username", "?")
    with get_conn() as c:
        row = c.execute("SELECT * FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"error": "Plan not found"})
        plan = dict(row)
        if plan["status"] not in ("approved",):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=400, content={"error": "Plan must be approved to execute"})
    target = plan.get("target_platform", "")

    def _run_mtv():
        """Background thread: orchestrate real MTV migration + poll status."""
        from db import get_conn as _gc
        import time as _time
        with _gc() as c:
            c.execute("UPDATE migration_plans SET status='executing', progress=0, started_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (plan_id,))
        _migration_log(plan_id, f"Migration execution started by {username}", username)
        try:
            from mtv_client import orchestrate_migration, poll_mtv_status
            mtv_plan_name = orchestrate_migration(plan, log_fn=_migration_log)
            # Now poll MTV until done
            with _gc() as c:
                c.execute("UPDATE migration_plans SET status='migrating', progress=10, updated_at=datetime('now') WHERE id=?", (plan_id,))
            _migration_log(plan_id, "MTV migration in progress. Polling real status from OpenShift...", "system")
            while True:
                _time.sleep(15)
                try:
                    st = poll_mtv_status(plan)
                except Exception as pe:
                    _migration_log(plan_id, f"Poll error: {pe}", "system")
                    _time.sleep(15)
                    continue
                phase = st.get("phase", "unknown")
                progress = st.get("progress", 0)
                # Log VM-level progress
                for vm in st.get("vms", []):
                    vn = vm.get("name", "?")
                    vphase = vm.get("phase", "Pending")
                    for step in vm.get("pipeline", []):
                        if step.get("name") in ("DiskTransfer","DiskTransferV2v","DiskAllocation") and step.get("total", 0) > 0:
                            pct = int(step["completed"] / step["total"] * 100) if step["total"] else 0
                            _migration_log(plan_id, f"[{vn}] Disk transfer: {step['completed']} / {step['total']} MB ({pct}%) - {step['phase']}", "system")
                with _gc() as c:
                    c.execute("UPDATE migration_plans SET progress=?, updated_at=datetime('now') WHERE id=?", (min(progress, 99), plan_id))
                if phase == "completed":
                    with _gc() as c:
                        c.execute("UPDATE migration_plans SET status='completed', progress=100, completed_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (plan_id,))
                    # Log final VM results
                    for vm in st.get("vms", []):
                        _migration_log(plan_id, f"[OK] '{vm['name']}' migration {vm.get('phase','?')}", "system")
                    total_mb = st.get("total_disk_mb", 0)
                    _migration_log(plan_id, f"Migration completed! Total disk transferred: {total_mb} MB. Started: {st.get('started','?')}, Completed: {st.get('completed','?')}", "system")
                    break
                elif phase == "failed":
                    with _gc() as c:
                        c.execute("UPDATE migration_plans SET status='failed', updated_at=datetime('now') WHERE id=?", (plan_id,))
                    errs = [c.get("message","") for c in st.get("conditions",[]) if c.get("type") in ("Failed",)]
                    _migration_log(plan_id, f"Migration FAILED: {'; '.join(errs)}", "system")
                    break
        except Exception as ex:
            import traceback
            _migration_log(plan_id, f"MTV orchestration error: {ex}", "system")
            _migration_log(plan_id, traceback.format_exc()[:500], "system")
            with _gc() as c:
                c.execute("UPDATE migration_plans SET status='failed', updated_at=datetime('now') WHERE id=?", (plan_id,))

    if target == "openshift":
        threading.Thread(target=_run_mtv, daemon=True).start()
    elif target == "nutanix":
        # Real Nutanix Move integration (falls back to realistic simulation)
        def _run_nutanix():
            from db import get_conn as _gc
            from nutanix_move_client import orchestrate_nutanix_migration
            with _gc() as c:
                c.execute("UPDATE migration_plans SET status='executing', progress=0, started_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (plan_id,))
                row = c.execute("SELECT plan_name, source_vcenter, target_detail, vm_list, options FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
            plan_data = dict(row) if row else {}
            def _db_upd(pid, status, progress):
                with _gc() as c:
                    if status == "completed":
                        c.execute("UPDATE migration_plans SET status=?, progress=?, completed_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (status, progress, pid))
                    else:
                        c.execute("UPDATE migration_plans SET status=?, progress=?, updated_at=datetime('now') WHERE id=?", (status, progress, pid))
            orchestrate_nutanix_migration(plan_id, plan_data, _db_upd, _migration_log)
        threading.Thread(target=_run_nutanix, daemon=True).start()
    elif target == "hyperv":
        # Real VMware -> Hyper-V migration (VMDK export + convert + import)
        def _run_hyperv():
            from db import get_conn as _gc
            from hyperv_migrate import orchestrate_hyperv_migration
            import json as _json
            with _gc() as c:
                c.execute("UPDATE migration_plans SET status='executing', progress=0, started_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (plan_id,))
                row = c.execute("SELECT plan_name, source_vcenter, target_detail, vm_list, options FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
            plan_data = dict(row) if row else {}
            def _db_upd(pid, status, progress):
                with _gc() as c:
                    if status == "completed":
                        c.execute("UPDATE migration_plans SET status=?, progress=?, completed_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (status, progress, pid))
                    else:
                        c.execute("UPDATE migration_plans SET status=?, progress=?, updated_at=datetime('now') WHERE id=?", (status, progress, pid))
            orchestrate_hyperv_migration(plan_id, plan_data, _db_upd, _migration_log)
        threading.Thread(target=_run_hyperv, daemon=True).start()
    else:
        # Other targets: realistic phased simulation
        def _run_sim():
            from db import get_conn as _gc
            from nutanix_move_client import _run_realistic_simulation
            import json as _json
            with _gc() as c:
                c.execute("UPDATE migration_plans SET status='executing', progress=0, started_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (plan_id,))
                row = c.execute("SELECT vm_list, options FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
            vms = _json.loads((dict(row) if row else {}).get("vm_list") or "[]")
            options = _json.loads((dict(row) if row else {}).get("options") or "{}")
            def _db_upd(pid, status, progress):
                with _gc() as c:
                    if status == "completed":
                        c.execute("UPDATE migration_plans SET status=?, progress=?, completed_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (status, progress, pid))
                    else:
                        c.execute("UPDATE migration_plans SET status=?, progress=?, updated_at=datetime('now') WHERE id=?", (status, progress, pid))
            _migration_log(plan_id, f"Migration (simulated) for target={target}", username)
            _run_realistic_simulation(plan_id, vms, options, _db_upd, _migration_log)
        threading.Thread(target=_run_sim, daemon=True).start()

    _migration_log(plan_id, f"Execution triggered by {username} (target={target})", username)
    return {"ok": True, "message": f"Migration execution started (target={target})"}

@app.get("/api/migration/plans/{plan_id}/events")
def get_plan_events(plan_id: int, u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        row = c.execute("SELECT status, progress, event_log, updated_at, target_platform, target_detail, plan_name FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
    if not row:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Plan not found"})
    d = dict(row)
    try:
        d["event_log"] = _json.loads(d["event_log"] or "[]")
    except:
        d["event_log"] = []
    # If migration is active and target is openshift, include live MTV status
    if d["status"] in ("executing", "migrating", "validating") and d.get("target_platform") == "openshift":
        try:
            from mtv_client import poll_mtv_status
            mtv = poll_mtv_status(d)
            d["mtv_status"] = mtv
            # Use MTV progress if available
            if mtv.get("progress", 0) > d.get("progress", 0):
                d["progress"] = mtv["progress"]
        except Exception as e:
            d["mtv_error"] = str(e)
    return d


# ---- Move Groups ----
@app.get("/api/migration/move-groups")
def list_move_groups(u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        groups = [dict(r) for r in c.execute("SELECT * FROM move_groups ORDER BY created_at DESC").fetchall()]
        for g in groups:
            vms = [dict(v) for v in c.execute("SELECT * FROM move_group_vms WHERE group_id=? ORDER BY added_at", (g["id"],)).fetchall()]
            g["vms"] = vms
            g["vm_count"] = len(vms)
            g["vcenters"] = list(set(v["vcenter_name"] or v["vcenter_id"] or "" for v in vms))
    return groups


@app.post("/api/migration/move-groups")
def create_move_group(req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    name = req.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Group name is required")
    with get_conn() as c:
        c.execute("INSERT INTO move_groups (name, description, created_by) VALUES (?,?,?)",
                  (name, req.get("description",""), u.get("username","admin")))
        gid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"ok": True, "id": gid, "message": "Move group created"}

@app.delete("/api/migration/move-groups/{group_id}")
def delete_move_group(group_id: int, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    with get_conn() as c:
        c.execute("DELETE FROM move_group_vms WHERE group_id=?", (group_id,))
        c.execute("DELETE FROM move_groups WHERE id=?", (group_id,))
    return {"ok": True}

@app.post("/api/migration/move-groups/{group_id}/vms")
def add_vms_to_group(group_id: int, req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    vms = req.get("vms", [])
    vcenter_id = req.get("vcenter_id", "")
    vcenter_name = req.get("vcenter_name", "")
    added = 0
    with get_conn() as c:
        for vm in vms:
            exists = c.execute("SELECT id FROM move_group_vms WHERE group_id=? AND vm_name=? AND vcenter_id=?",
                               (group_id, vm.get("name",""), vcenter_id)).fetchone()
            if exists: continue
            c.execute('''INSERT INTO move_group_vms
                (group_id, vm_name, vm_moref, vcenter_id, vcenter_name, guest_os, cpu, memory_mb, disk_gb, power_state, ip_address, esxi_host)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (group_id, vm.get("name",""), vm.get("moref",""), vcenter_id, vcenter_name,
                 vm.get("guest_os",""), vm.get("cpu",0), vm.get("memory_mb",0), vm.get("disk_gb",0),
                 vm.get("power_state",""), vm.get("ip_address",""), vm.get("esxi_host","")))
            added += 1
        c.execute("UPDATE move_groups SET updated_at=datetime('now') WHERE id=?", (group_id,))
    return {"ok": True, "added": added}

@app.delete("/api/migration/move-groups/{group_id}/vms/{vm_id}")
def remove_vm_from_group(group_id: int, vm_id: int, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    with get_conn() as c:
        c.execute("DELETE FROM move_group_vms WHERE id=? AND group_id=?", (vm_id, group_id))
        c.execute("UPDATE move_groups SET updated_at=datetime('now') WHERE id=?", (group_id,))
    return {"ok": True}

@app.post("/api/migration/move-groups/{group_id}/migrate")
def migrate_move_group(group_id: int, req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    import json as _json
    from datetime import datetime
    username = u.get("username", "admin")
    target_platform = req.get("target_platform", "")
    target_detail = req.get("target_detail", {})
    options = req.get("options", {})
    if not target_platform: raise HTTPException(400, "target_platform is required")
    with get_conn() as c:
        group = c.execute("SELECT * FROM move_groups WHERE id=?", (group_id,)).fetchone()
        if not group: raise HTTPException(404, "Move group not found")
        vms = [dict(v) for v in c.execute("SELECT * FROM move_group_vms WHERE group_id=?", (group_id,)).fetchall()]
        if not vms: raise HTTPException(400, "No VMs in this group")
        by_vc = {}
        for vm in vms:
            vc = vm.get("vcenter_id") or "unknown"
            by_vc.setdefault(vc, []).append(vm)
        plan_ids = []
        for vc_id, vc_vms in by_vc.items():
            vc_name = vc_vms[0].get("vcenter_name") or vc_id
            suffix = f" ({vc_name})" if len(by_vc) > 1 else ""
            plan_name = f"{dict(group)['name']}{suffix}"
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            init_log = _json.dumps([{"ts": ts, "msg": f"Plan from move group by {username}", "user": username}])
            vm_list = [{"name": v["vm_name"], "moref": v.get("vm_moref",""), "guest_os": v.get("guest_os",""),
                        "cpu": v.get("cpu",0), "memory_mb": v.get("memory_mb",0), "disk_gb": v.get("disk_gb",0),
                        "power_state": v.get("power_state",""), "ip_address": v.get("ip_address",""),
                        "esxi_host": v.get("esxi_host","")} for v in vc_vms]
            source_vc = {"id": vc_id, "name": vc_name}
            c.execute('''INSERT INTO migration_plans
                (plan_name, source_platform, source_vcenter, target_platform,
                 target_detail, vm_list, status, notes, created_by, event_log, options)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (plan_name, "vmware", _json.dumps(source_vc), target_platform,
                 _json.dumps(target_detail), _json.dumps(vm_list),
                 "planned", f"From move group: {dict(group)['name']}", username, init_log, _json.dumps(options)))
            pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            plan_ids.append(pid)
    return {"ok": True, "plan_ids": plan_ids, "plans_created": len(plan_ids)}

@app.post("/api/migration/preflight")
def migration_preflight(req: dict, u=Depends(require_role("admin","operator"))):
    target = req.get("target_platform", "")
    vms = req.get("vms", [])
    target_detail = req.get("target_detail", {})
    results = []
    for vm in vms:
        r = {
            "vm_name": vm.get("name",""),
            "power_state": vm.get("power_state","unknown"),
            "cpu_compatible": True,
            "disk_format": "VMDK",
            "target_format": {"openshift":"PVC (KubeVirt)","nutanix":"qcow2 (AHV)","hyperv":"VHDX"}.get(target,"Unknown"),
            "snapshots_present": False,
            "vmware_tools": "installed",
            "network_mapped": True,
            "overall": "pass",
            "notes": []
        }
        snap_count = vm.get("snapshot_count", 0)
        if snap_count and int(snap_count) > 0:
            r["snapshots_present"] = True
            r["overall"] = "warning"
            r["notes"].append(f"Has {snap_count} snapshot(s) - consolidate before migration")
        if vm.get("power_state") == "poweredOn":
            r["notes"].append("VM is powered on - cold migration recommended")
        disk_gb = vm.get("storage_used_gb", 0) or 0
        if float(disk_gb) > 2000:
            r["notes"].append(f"Large disk ({disk_gb} GB) - extended time")
        if target == "openshift":
            r["notes"].append("VM will run as KubeVirt VirtualMachine resource")
            guest_os = (vm.get("guest_os","") or "").lower()
            if "windows" in guest_os:
                r["notes"].append("Windows guest: ensure virtio drivers available")
        elif target == "nutanix":
            r["notes"].append("Nutanix Move will handle VMDK to qcow2 conversion")
        elif target == "hyperv":
            r["notes"].append("VMDK to VHDX conversion via qemu-img or StarWind V2V")
            guest_os = (vm.get("guest_os","") or "").lower()
            if "linux" in guest_os:
                r["notes"].append("Linux guest: verify Hyper-V integration services")
        results.append(r)
    ocp_operator_found = None
    if target == "openshift" and target_detail.get("cluster_id"):
        try:
            from openshift_client import get_operators
            cluster_id = target_detail["cluster_id"]
            from db import get_conn
            with get_conn() as c:
                cl = c.execute("SELECT * FROM ocp_clusters WHERE id=?", (cluster_id,)).fetchone()
                if cl:
                    ops = get_operators(dict(cl))
                    ocp_operator_found = any(
                        "kubevirt" in (op.get("name","")).lower() or
                        "virtualization" in (op.get("name","")).lower()
                        for op in ops.get("operators",[]))
        except:
            ocp_operator_found = None
    return {
        "results": results,
        "ocp_operator_found": ocp_operator_found,
        "target_platform": target,
        "summary": {
            "total": len(results),
            "pass": sum(1 for r in results if r["overall"]=="pass"),
            "warning": sum(1 for r in results if r["overall"]=="warning"),
            "fail": sum(1 for r in results if r["overall"]=="fail"),
        }
    }

@app.get("/api/migration/plans/{plan_id}/events")
def get_plan_events(plan_id: int, u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        row = c.execute("SELECT status, progress, event_log, updated_at FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
    if not row:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Plan not found"})
    d = dict(row)
    try:
        d["event_log"] = _json.loads(d["event_log"] or "[]")
    except:
        d["event_log"] = []
    return d

@app.post("/api/migration/preflight")
def migration_preflight(req: dict, u=Depends(require_role("admin","operator"))):
    target = req.get("target_platform", "")
    vms = req.get("vms", [])
    target_detail = req.get("target_detail", {})
    results = []
    for vm in vms:
        r = {
            "vm_name": vm.get("name",""),
            "power_state": vm.get("power_state","unknown"),
            "cpu_compatible": True,
            "disk_format": "VMDK",
            "target_format": {"openshift":"PVC (KubeVirt)","nutanix":"qcow2 (AHV)","hyperv":"VHDX"}.get(target,"Unknown"),
            "snapshots_present": False,
            "vmware_tools": "installed",
            "network_mapped": True,
            "overall": "pass",
            "notes": []
        }
        snap_count = vm.get("snapshot_count", 0)
        if snap_count and int(snap_count) > 0:
            r["snapshots_present"] = True
            r["overall"] = "warning"
            r["notes"].append(f"Has {snap_count} snapshot(s) - consolidate before migration")
        if vm.get("power_state") == "poweredOn":
            r["notes"].append("VM is powered on - cold migration recommended")
        disk_gb = vm.get("storage_used_gb", 0) or 0
        if float(disk_gb) > 2000:
            r["notes"].append(f"Large disk ({disk_gb} GB) - extended time")
        if target == "openshift":
            r["notes"].append("VM will run as KubeVirt VirtualMachine resource")
            guest_os = (vm.get("guest_os","") or "").lower()
            if "windows" in guest_os:
                r["notes"].append("Windows guest: ensure virtio drivers available")
        elif target == "nutanix":
            r["notes"].append("Nutanix Move will handle VMDK to qcow2 conversion")
        elif target == "hyperv":
            r["notes"].append("VMDK to VHDX conversion via qemu-img or StarWind V2V")
            guest_os = (vm.get("guest_os","") or "").lower()
            if "linux" in guest_os:
                r["notes"].append("Linux guest: verify Hyper-V integration services")
        results.append(r)
    ocp_operator_found = None
    if target == "openshift" and target_detail.get("cluster_id"):
        try:
            from openshift_client import get_operators
            cluster_id = target_detail["cluster_id"]
            from db import get_conn
            with get_conn() as c:
                cl = c.execute("SELECT * FROM ocp_clusters WHERE id=?", (cluster_id,)).fetchone()
                if cl:
                    ops = get_operators(dict(cl))
                    ocp_operator_found = any(
                        "kubevirt" in (op.get("name","")).lower() or
                        "virtualization" in (op.get("name","")).lower()
                        for op in ops.get("operators",[]))
        except:
            ocp_operator_found = None
    return {
        "results": results,
        "ocp_operator_found": ocp_operator_found,
        "target_platform": target,
        "summary": {
            "total": len(results),
            "pass": sum(1 for r in results if r["overall"]=="pass"),
            "warning": sum(1 for r in results if r["overall"]=="warning"),
            "fail": sum(1 for r in results if r["overall"]=="fail"),
        }
    }

