"""Insert SSO routes into main.py right after the aws/subnets endpoint (line 4231)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

INSERT_AFTER = 4231   # the closing `raise HTTPException(500...)` of aws_subnets_ep

SSO_BLOCK = '''

# ── AWS SSO ROUTES ─────────────────────────────────────────────────────────
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

'''

lines = open('main.py', encoding='utf-8').readlines()
print(f"Total lines before: {len(lines)}")

# Verify the target line
print(f"Line {INSERT_AFTER}: {repr(lines[INSERT_AFTER-1])}")

# Check SSO block not already inserted
if 'aws_sso_init_ep' in open('main.py', encoding='utf-8').read():
    print("SSO routes already present — skipping")
else:
    new_lines = lines[:INSERT_AFTER] + [SSO_BLOCK] + lines[INSERT_AFTER:]
    open('main.py', 'w', encoding='utf-8').writelines(new_lines)
    print(f"Inserted SSO block after line {INSERT_AFTER}")
    print(f"Total lines after: {len(new_lines)}")
