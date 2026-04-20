"""
aws_sso.py — AWS IAM Identity Center (SSO) auto-refresh
=========================================================
Implements the Device Authorization / OIDC flow so that temporary
credentials are automatically refreshed every 20 minutes without any
manual copy-paste.

Flow
----
1. Admin calls init_sso_login()
   → registers an OIDC public client with AWS
   → starts device authorization
   → returns a verification_uri_complete + user_code for the admin
     to open in a browser (one-time consent on the SSO portal)

2. poll_sso_token(device_code, client_id, client_secret)
   → polls create_token until the admin has approved in the browser
   → saves the access_token + refresh_token to .env

3. refresh_sso_credentials()  ← called by background thread every 20 min
   → calls sso.get_role_credentials() with the stored access_token
   → writes the new AKID/Secret/SessionToken into .env
   → reloads env into current process so next boto3 call picks them up

Everything is stored as AWS_SSO_* keys in .env so it never clashes
with the existing AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY path.
"""

import os
import time
import threading
import datetime
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = str(Path(__file__).parent / ".env")

# ── .env helper (same as aws_client._write_env_key) ───────────────
def _write_env_key(key: str, value: str):
    path = Path(ENV_PATH)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    new_line = f"{key}={value}"
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
            lines[i] = new_line
            updated = True
            break
    if not updated:
        lines.append(new_line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def _read_env_key(key: str, default: str = "") -> str:
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    v = os.getenv(key, default) or default
    v = v.strip()
    if len(v) >= 2 and v[0] in ('"', "'") and v[-1] == v[0]:
        v = v[1:-1]
    return v

# ── Persistent state for the device-auth polling ──────────────────
_pending: dict = {}          # holds device_code, client_id, client_secret while polling
_last_error: str = ""        # last error message from refresh
_last_refresh: float = 0.0   # epoch seconds of last successful refresh
_token_expiry: float = 0.0   # epoch seconds when current STS creds expire
_sso_mode: bool = False      # True once SSO is fully configured

def get_sso_config() -> dict:
    """Return current SSO configuration from .env."""
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    return {
        "start_url":    _read_env_key("AWS_SSO_START_URL"),
        "sso_region":   _read_env_key("AWS_SSO_REGION", "ap-south-1"),
        "account_id":   _read_env_key("AWS_SSO_ACCOUNT_ID"),
        "role_name":    _read_env_key("AWS_SSO_ROLE_NAME"),
        "access_token": _read_env_key("AWS_SSO_ACCESS_TOKEN"),
        "token_expiry": _read_env_key("AWS_SSO_TOKEN_EXPIRY"),
        "client_id":    _read_env_key("AWS_SSO_CLIENT_ID"),
        "client_secret":_read_env_key("AWS_SSO_CLIENT_SECRET"),
    }

def is_sso_configured() -> bool:
    cfg = get_sso_config()
    return bool(cfg["start_url"] and cfg["account_id"] and cfg["role_name"])

def is_sso_token_valid() -> bool:
    """True if we have an access_token that hasn't expired yet."""
    cfg = get_sso_config()
    if not cfg["access_token"]:
        return False
    expiry = cfg.get("token_expiry", "")
    if not expiry:
        return True  # assume valid if no expiry stored
    try:
        exp_dt = datetime.datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        return exp_dt > now_dt + datetime.timedelta(minutes=5)
    except Exception:
        return True

def get_sso_status() -> dict:
    global _last_error, _last_refresh, _token_expiry
    cfg = get_sso_config()
    configured = is_sso_configured()
    token_valid = is_sso_token_valid() if configured else False

    # Work out credential expiry
    cred_expires_at = None
    cred_expires_in_sec = None
    try:
        exp_str = _read_env_key("AWS_SSO_CRED_EXPIRY")
        if exp_str:
            exp_dt = datetime.datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            delta = (exp_dt - now_dt).total_seconds()
            cred_expires_in_sec = int(delta)
            cred_expires_at = exp_str
    except Exception:
        pass

    return {
        "sso_configured":       configured,
        "token_valid":          token_valid,
        "start_url":            cfg["start_url"],
        "sso_region":           cfg["sso_region"],
        "account_id":           cfg["account_id"],
        "role_name":            cfg["role_name"],
        "last_refresh":         datetime.datetime.utcfromtimestamp(_last_refresh).isoformat() + "Z" if _last_refresh else None,
        "last_error":           _last_error or None,
        "cred_expires_at":      cred_expires_at,
        "cred_expires_in_sec":  cred_expires_in_sec,
        "pending_verification": bool(_pending),
        "needs_reauth": configured and not token_valid,
    }

# ── Phase 1 — initiate device authorization ───────────────────────
def init_sso_login(start_url: str, sso_region: str, account_id: str, role_name: str) -> dict:
    """
    Register OIDC client + start device authorization.
    Returns verification_uri_complete + user_code for the admin to open in browser.
    """
    global _pending
    try:
        import boto3
    except ImportError:
        return {"success": False, "error": "boto3 not installed"}

    # Persist the SSO config fields (not the token yet)
    _write_env_key("AWS_SSO_START_URL",  start_url.strip())
    _write_env_key("AWS_SSO_REGION",     (sso_region or "ap-south-1").strip())
    _write_env_key("AWS_SSO_ACCOUNT_ID", account_id.strip())
    _write_env_key("AWS_SSO_ROLE_NAME",  role_name.strip())
    load_dotenv(dotenv_path=ENV_PATH, override=True)

    try:
        oidc = boto3.client("sso-oidc", region_name=sso_region or "ap-south-1")

        # Register a public OIDC client (idempotent — can be called again)
        reg = oidc.register_client(
            clientName="caas-dashboard",
            clientType="public",
        )
        client_id     = reg["clientId"]
        client_secret = reg["clientSecret"]

        # Save client registration (expires in ~90 days so we can reuse)
        _write_env_key("AWS_SSO_CLIENT_ID",     client_id)
        _write_env_key("AWS_SSO_CLIENT_SECRET",  client_secret)

        # Start device authorization
        auth = oidc.start_device_authorization(
            clientId=client_id,
            clientSecret=client_secret,
            startUrl=start_url,
        )

        device_code  = auth["deviceCode"]
        interval     = auth.get("interval", 5)
        expires_in   = auth.get("expiresIn", 600)

        # Store for polling
        _pending = {
            "device_code":   device_code,
            "client_id":     client_id,
            "client_secret": client_secret,
            "interval":      interval,
            "oidc":          oidc,
            "sso_region":    sso_region or "ap-south-1",
        }

        return {
            "success":                  True,
            "verification_uri":         auth.get("verificationUri"),
            "verification_uri_complete":auth.get("verificationUriComplete"),
            "user_code":                auth.get("userCode"),
            "expires_in":               expires_in,
            "interval":                 interval,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Phase 2 — poll for token approval ─────────────────────────────
def poll_sso_token() -> dict:
    """
    Poll create_token once. Call this repeatedly (every `interval` seconds)
    until success=True or an error other than AuthorizationPendingException.
    """
    global _pending, _last_error
    if not _pending:
        return {"success": False, "error": "No pending authorization. Call init first."}

    try:
        import boto3
    except ImportError:
        return {"success": False, "error": "boto3 not installed"}

    p = _pending
    try:
        oidc = p.get("oidc") or boto3.client("sso-oidc", region_name=p["sso_region"])
        resp = oidc.create_token(
            clientId=p["client_id"],
            clientSecret=p["client_secret"],
            grantType="urn:ietf:params:oauth:grant-type:device_code",
            deviceCode=p["device_code"],
        )
        access_token   = resp["accessToken"]
        token_type     = resp.get("tokenType", "Bearer")
        expires_in     = resp.get("expiresIn", 28800)   # 8 hours default
        refresh_token  = resp.get("refreshToken", "")

        # Calculate expiry timestamp
        expiry_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expires_in)
        expiry_str = expiry_dt.isoformat()

        # Save to .env
        _write_env_key("AWS_SSO_ACCESS_TOKEN",  access_token)
        _write_env_key("AWS_SSO_TOKEN_EXPIRY",  expiry_str)
        if refresh_token:
            _write_env_key("AWS_SSO_REFRESH_TOKEN", refresh_token)
        load_dotenv(dotenv_path=ENV_PATH, override=True)

        _pending = {}  # clear pending
        _last_error = ""

        # Immediately fetch credentials
        cred_result = refresh_sso_credentials()

        # Start the background refresh thread
        _start_refresh_thread()

        return {
            "success":     True,
            "token_type":  token_type,
            "expires_in":  expires_in,
            "cred_result": cred_result,
        }

    except Exception as e:
        err_name = type(e).__name__
        if "AuthorizationPending" in err_name or "authorization_pending" in str(e).lower():
            return {"success": False, "pending": True, "error": "Waiting for browser approval…"}
        if "SlowDown" in err_name:
            return {"success": False, "pending": True, "error": "SlowDown — increase poll interval"}
        if "ExpiredToken" in err_name or "expired" in str(e).lower():
            _pending = {}
            return {"success": False, "error": "Device code expired. Please initiate login again."}
        _last_error = str(e)
        _pending = {}
        return {"success": False, "error": str(e)}


# ── Credential refresh ─────────────────────────────────────────────
def refresh_sso_credentials() -> dict:
    """
    Exchange SSO access_token → short-lived STS credentials.
    Writes the new AKID/Secret/SessionToken into .env and reloads.
    """
    global _last_error, _last_refresh, _token_expiry
    cfg = get_sso_config()

    if not cfg["access_token"]:
        return {"success": False, "error": "No SSO access token stored"}
    if not cfg["account_id"] or not cfg["role_name"]:
        return {"success": False, "error": "account_id or role_name not configured"}

    try:
        import boto3
        sso = boto3.client("sso", region_name=cfg["sso_region"] or "ap-south-1")
        resp = sso.get_role_credentials(
            accountId=cfg["account_id"],
            roleName=cfg["role_name"],
            accessToken=cfg["access_token"],
        )
        rc = resp["roleCredentials"]
        akid      = rc["accessKeyId"]
        secret    = rc["secretAccessKey"]
        token     = rc["sessionToken"]
        expiry_ms = rc.get("expiration")   # epoch milliseconds

        # Calculate expiry
        if expiry_ms:
            expiry_dt = datetime.datetime.utcfromtimestamp(expiry_ms / 1000).replace(
                tzinfo=datetime.timezone.utc
            )
            expiry_str = expiry_dt.isoformat()
            _token_expiry = expiry_ms / 1000
        else:
            expiry_str = ""
            _token_expiry = time.time() + 3600  # assume 1h

        # Write to .env — overwrites the old ASIA* keys
        _write_env_key("AWS_ACCESS_KEY_ID",     akid)
        _write_env_key("AWS_SECRET_ACCESS_KEY", secret)
        _write_env_key("AWS_SESSION_TOKEN",     token)
        _write_env_key("AWS_SSO_CRED_EXPIRY",   expiry_str)
        load_dotenv(dotenv_path=ENV_PATH, override=True)

        _last_refresh = time.time()
        _last_error   = ""

        return {
            "success":    True,
            "access_key": akid[:8] + "****",
            "expiry":     expiry_str,
        }
    except Exception as e:
        err_str = str(e)
        _last_error = err_str

        # If the SSO access token itself has expired, try refresh token
        if "UnauthorizedException" in type(e).__name__ or "unauthorized" in err_str.lower():
            refresh_result = _try_refresh_token()
            if refresh_result.get("success"):
                return refresh_sso_credentials()  # retry once with new token
        return {"success": False, "error": err_str}


def _try_refresh_token() -> dict:
    """Attempt to get a new access_token using the stored refresh_token."""
    cfg = get_sso_config()
    refresh_token = _read_env_key("AWS_SSO_REFRESH_TOKEN")
    if not refresh_token or not cfg["client_id"]:
        return {"success": False, "error": "No refresh token available"}
    try:
        import boto3
        oidc = boto3.client("sso-oidc", region_name=cfg["sso_region"] or "ap-south-1")
        resp = oidc.create_token(
            clientId=cfg["client_id"],
            clientSecret=cfg["client_secret"],
            grantType="refresh_token",
            refreshToken=refresh_token,
        )
        access_token = resp["accessToken"]
        expires_in   = resp.get("expiresIn", 28800)
        new_refresh  = resp.get("refreshToken", refresh_token)
        expiry_dt    = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expires_in)

        _write_env_key("AWS_SSO_ACCESS_TOKEN",  access_token)
        _write_env_key("AWS_SSO_TOKEN_EXPIRY",  expiry_dt.isoformat())
        _write_env_key("AWS_SSO_REFRESH_TOKEN", new_refresh)
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Background auto-refresh thread ────────────────────────────────
_refresh_thread: threading.Thread | None = None
_refresh_stop   = threading.Event()

_REFRESH_INTERVAL = 20 * 60   # refresh every 20 minutes
_REFRESH_BEFORE   = 10 * 60   # also refresh if cred expires within 10 minutes

def _refresh_loop():
    global _last_error
    while not _refresh_stop.is_set():
        # Sleep in short chunks so we can respond to stop quickly
        for _ in range(_REFRESH_INTERVAL // 10):
            if _refresh_stop.is_set():
                return
            time.sleep(10)

        if not is_sso_configured():
            continue

        # Refresh if within 5 min of expiry OR 20 min have passed
        now = time.time()
        near_expiry = _token_expiry > 0 and (_token_expiry - now) < _REFRESH_BEFORE
        time_due    = (now - _last_refresh) >= _REFRESH_INTERVAL

        if near_expiry or time_due:
            try:
                result = refresh_sso_credentials()
                if not result.get("success") and "unauthorized" in result.get("error","").lower():
                    # SSO access token itself is expired — try refresh token first
                    rt = _try_refresh_token()
                    if rt.get("success"):
                        refresh_sso_credentials()
            except Exception as e:
                _last_error = str(e)


def _start_refresh_thread():
    global _refresh_thread, _refresh_stop
    if _refresh_thread and _refresh_thread.is_alive():
        return   # already running
    _refresh_stop.clear()
    _refresh_thread = threading.Thread(
        target=_refresh_loop,
        name="aws-sso-refresh",
        daemon=True,
    )
    _refresh_thread.start()


def stop_refresh_thread():
    _refresh_stop.set()


# ── Auto-start on import if SSO is already configured ─────────────
def _auto_start():
    """Called once at import time. If SSO is configured and token looks
    valid, kick off the background refresh thread immediately."""
    if is_sso_configured():
        # Do an immediate refresh if creds look stale / expired
        cred_expiry_str = _read_env_key("AWS_SSO_CRED_EXPIRY")
        needs_refresh = True
        if cred_expiry_str:
            try:
                exp_dt = datetime.datetime.fromisoformat(cred_expiry_str.replace("Z", "+00:00"))
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                if (exp_dt - now_dt).total_seconds() > _REFRESH_BEFORE:
                    needs_refresh = False
            except Exception:
                pass
        if needs_refresh and is_sso_token_valid():
            try:
                refresh_sso_credentials()
            except Exception:
                pass
        _start_refresh_thread()

_auto_start()
