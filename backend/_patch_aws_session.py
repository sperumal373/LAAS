"""Patch aws_client.py _session() to add SSO auto-refresh before building session."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

path = 'aws_client.py'
content = open(path, encoding='utf-8').read()

# Check not already patched
if '_maybe_refresh_sso' in content:
    print("Already patched — skipping")
    exit(0)

SSO_SESSION = '''# ── boto3 session ───────────────────────────────────────────────────────────
def _maybe_refresh_sso():
    """If SSO mode is active and credentials are near expiry, refresh them now."""
    try:
        from aws_sso import is_sso_configured, is_sso_token_valid, refresh_sso_credentials
        import datetime
        if not is_sso_configured():
            return
        exp_str = _unquote(os.getenv("AWS_SSO_CRED_EXPIRY", ""))
        if exp_str:
            try:
                exp_dt = datetime.datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                if (exp_dt - now_dt).total_seconds() < 180 and is_sso_token_valid():
                    load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)
                    refresh_sso_credentials()
                    load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)
            except Exception:
                pass
    except ImportError:
        pass

def _session(region: str = None):
    try:
        import boto3
    except ImportError:
        raise RuntimeError("boto3 is not installed. Run: pip install boto3")
    # If SSO is active, ensure creds are fresh
    _maybe_refresh_sso()
    # Re-read env so we pick up freshly refreshed SSO credentials
    load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)
    creds = get_aws_credentials()
    kwargs = dict(
        aws_access_key_id=creds["access_key_id"],
        aws_secret_access_key=creds["secret_access_key"],
        region_name=region or creds["region"] or "us-east-1",
    )
    if creds.get("session_token"):
        kwargs["aws_session_token"] = creds["session_token"]
    return boto3.Session(**kwargs)
'''

# Find the start of the old block and replace it
import re
old_block = re.compile(
    r'# ── boto3 session ─+\ndef _session\(region: str = None\):.*?return boto3\.Session\(\*\*kwargs\)\n',
    re.DOTALL
)
m = old_block.search(content)
if not m:
    print("ERROR: could not find _session block")
    exit(1)

new_content = content[:m.start()] + SSO_SESSION + content[m.end():]
open(path, 'w', encoding='utf-8').write(new_content)
print(f"Patched _session() in {path}")
# Verify
if '_maybe_refresh_sso' in open(path, encoding='utf-8').read():
    print("Verification: OK")
