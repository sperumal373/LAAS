"""
aws_client.py — AWS discovery via boto3
=========================================
• Reads credentials from .env (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)
• Discovers EC2 instances, S3 buckets, RDS instances, VPCs, Security Groups, ELBs
• Returns structured summaries for dashboard display
"""

import os
import json
import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv, set_key

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

ENV_PATH = str(Path(__file__).parent / ".env")

# ── Credential helpers ────────────────────────────────────────────────────────
def _unquote(v: str) -> str:
    """Strip surrounding single/double quotes that python-dotenv set_key may add."""
    v = v.strip()
    if len(v) >= 2 and v[0] in ('"', "'") and v[-1] == v[0]:
        return v[1:-1]
    return v

def get_aws_credentials():
    return {
        "access_key_id":     _unquote(os.getenv("AWS_ACCESS_KEY_ID", "")),
        "secret_access_key": _unquote(os.getenv("AWS_SECRET_ACCESS_KEY", "")),
        "session_token":     _unquote(os.getenv("AWS_SESSION_TOKEN", "")),
        "region":            _unquote(os.getenv("AWS_REGION", "ap-south-1")) or "ap-south-1",
        "account_alias":     _unquote(os.getenv("AWS_ACCOUNT_ALIAS", "")),
    }

def save_aws_credentials(access_key_id: str, secret_access_key: str, region: str = "ap-south-1", account_alias: str = "", session_token: str = ""):
    # Use set_key for short values; write session token directly to avoid
    # python-dotenv truncation issues with long base64 strings
    set_key(ENV_PATH, "AWS_ACCESS_KEY_ID",     access_key_id.strip())
    set_key(ENV_PATH, "AWS_SECRET_ACCESS_KEY", secret_access_key.strip())
    set_key(ENV_PATH, "AWS_REGION",            (region or "ap-south-1").strip())
    set_key(ENV_PATH, "AWS_ACCOUNT_ALIAS",     account_alias.strip() if account_alias else "")

    # Write session token directly — avoids set_key quoting bugs on long values
    token_val = session_token.strip() if session_token else ""
    _write_env_key(ENV_PATH, "AWS_SESSION_TOKEN", token_val)

    # Reload env into current process
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    is_temp = bool(token_val)
    return {"success": True, "message": "Credentials saved.", "temporary": is_temp}


def _write_env_key(env_path: str, key: str, value: str):
    """Reliably write/update a single key in a .env file without quoting issues."""
    path = Path(env_path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    new_line = f'{key}={value}'
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f'{key}=') or line.startswith(f'{key} ='):
            lines[i] = new_line
            updated = True
            break
    if not updated:
        lines.append(new_line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def has_credentials() -> bool:
    return bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))

# ── boto3 session ───────────────────────────────────────────────────────────
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

def _client(service: str, region: str = None):
    return _session(region).client(service)

def _resource(service: str, region: str = None):
    return _session(region).resource(service)

# ── Status / connection test ──────────────────────────────────────────────────
def get_aws_status() -> dict:
    creds = get_aws_credentials()
    if not creds["access_key_id"] or not creds["secret_access_key"]:
        return {
            "configured": False,
            "connected":  False,
            "message":    "No credentials configured. Enter your AWS Access Key ID and Secret.",
            "account_id": None,
            "account_alias": None,
            "region":     creds["region"],
        }
    try:
        sts = _client("sts")
        identity = sts.get_caller_identity()
        # Try get account alias
        alias = creds.get("account_alias", "")
        try:
            iam = _client("iam")
            aliases = iam.list_account_aliases().get("AccountAliases", [])
            alias = aliases[0] if aliases else ""
        except Exception:
            pass
        return {
            "configured":    True,
            "connected":     True,
            "message":       "Connected successfully.",
            "account_id":    identity.get("Account"),
            "account_alias": alias,
            "user_arn":      identity.get("Arn"),
            "region":        creds["region"],
            "temporary":     bool(creds.get("session_token")),
        }
    except Exception as e:
        return {
            "configured":    True,
            "connected":     False,
            "message":       f"Connection failed: {str(e)[:200]}",
            "account_id":    None,
            "account_alias": None,
            "region":        creds["region"],
        }

# ── EC2 ───────────────────────────────────────────────────────────────────────
def get_ec2_instances(region: str = None) -> list:
    creds = get_aws_credentials()
    region = region or creds["region"]
    try:
        ec2 = _client("ec2", region)
        paginator = ec2.get_paginator("describe_instances")
        instances = []
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                    instances.append({
                        "id":            inst.get("InstanceId"),
                        "name":          tags.get("Name", inst.get("InstanceId")),
                        "type":          inst.get("InstanceType"),
                        "state":         inst.get("State", {}).get("Name"),
                        "public_ip":     inst.get("PublicIpAddress"),
                        "private_ip":    inst.get("PrivateIpAddress"),
                        "az":            inst.get("Placement", {}).get("AvailabilityZone"),
                        "ami":           inst.get("ImageId"),
                        "platform":      inst.get("Platform", "linux"),
                        "key_name":      inst.get("KeyName"),
                        "vpc_id":        inst.get("VpcId"),
                        "subnet_id":     inst.get("SubnetId"),
                        "launch_time":   inst.get("LaunchTime", "").isoformat() if hasattr(inst.get("LaunchTime",""), "isoformat") else str(inst.get("LaunchTime","")),
                        "monitoring":    inst.get("Monitoring", {}).get("State"),
                        "tags":          tags,
                        "arch":          inst.get("Architecture"),
                        "root_device":   inst.get("RootDeviceType"),
                        "security_groups": [sg["GroupName"] for sg in inst.get("SecurityGroups", [])],
                    })
        return instances
    except Exception as e:
        return [{"error": str(e)}]

def get_ec2_summary(region: str = None) -> dict:
    instances = get_ec2_instances(region)
    if instances and "error" in instances[0]:
        return {"error": instances[0]["error"]}
    total      = len(instances)
    running    = sum(1 for i in instances if i["state"] == "running")
    stopped    = sum(1 for i in instances if i["state"] == "stopped")
    terminated = sum(1 for i in instances if i["state"] == "terminated")
    types      = {}
    for i in instances:
        t = i["type"] or "unknown"
        types[t] = types.get(t, 0) + 1
    azs = sorted(set(i["az"] for i in instances if i.get("az")))
    return {
        "total": total, "running": running, "stopped": stopped,
        "terminated": terminated, "instance_types": types, "azs": azs,
    }

# ── S3 ────────────────────────────────────────────────────────────────────────
def get_s3_buckets() -> list:
    try:
        s3 = _client("s3")
        response = s3.list_buckets()

        def _enrich(b):
            name    = b["Name"]
            created = b.get("CreationDate", "")
            region  = "unknown"
            public_access = True
            versioning    = "Unknown"
            try:
                loc = s3.get_bucket_location(Bucket=name)
                region = loc.get("LocationConstraint") or "us-east-1"
            except Exception:
                pass
            try:
                pa  = s3.get_public_access_block(Bucket=name)
                cfg = pa.get("PublicAccessBlockConfiguration", {})
                public_access = not (cfg.get("BlockPublicAcls") and cfg.get("BlockPublicPolicy"))
            except Exception:
                pass
            try:
                v = s3.get_bucket_versioning(Bucket=name)
                versioning = v.get("Status", "Disabled") or "Disabled"
            except Exception:
                pass
            return {
                "name":         name,
                "region":       region,
                "created":      created.isoformat() if hasattr(created, "isoformat") else str(created),
                "public_access": public_access,
                "versioning":   versioning,
            }

        raw_buckets = response.get("Buckets", [])
        with ThreadPoolExecutor(max_workers=min(20, len(raw_buckets) or 1)) as ex:
            buckets = list(ex.map(_enrich, raw_buckets))
        return buckets
    except Exception as e:
        return [{"error": str(e)}]

# ── RDS ───────────────────────────────────────────────────────────────────────
def get_rds_instances(region: str = None) -> list:
    creds = get_aws_credentials()
    region = region or creds["region"]
    try:
        rds = _client("rds", region)
        paginator = rds.get_paginator("describe_db_instances")
        dbs = []
        for page in paginator.paginate():
            for db in page.get("DBInstances", []):
                dbs.append({
                    "id":          db.get("DBInstanceIdentifier"),
                    "engine":      db.get("Engine"),
                    "version":     db.get("EngineVersion"),
                    "class":       db.get("DBInstanceClass"),
                    "status":      db.get("DBInstanceStatus"),
                    "storage_gb":  db.get("AllocatedStorage"),
                    "storage_type": db.get("StorageType"),
                    "multi_az":    db.get("MultiAZ"),
                    "endpoint":    db.get("Endpoint", {}).get("Address"),
                    "port":        db.get("Endpoint", {}).get("Port"),
                    "az":          db.get("AvailabilityZone"),
                    "vpc_id":      db.get("DBSubnetGroup", {}).get("VpcId"),
                    "encrypted":   db.get("StorageEncrypted"),
                    "backup_retention": db.get("BackupRetentionPeriod"),
                })
        return dbs
    except Exception as e:
        return [{"error": str(e)}]

# ── VPCs ──────────────────────────────────────────────────────────────────────
def get_vpcs(region: str = None) -> list:
    creds = get_aws_credentials()
    region = region or creds["region"]
    try:
        ec2 = _client("ec2", region)
        vpcs = []
        for vpc in ec2.describe_vpcs().get("Vpcs", []):
            tags = {t["Key"]: t["Value"] for t in vpc.get("Tags", [])}
            vpcs.append({
                "id":        vpc.get("VpcId"),
                "name":      tags.get("Name", vpc.get("VpcId")),
                "cidr":      vpc.get("CidrBlock"),
                "default":   vpc.get("IsDefault"),
                "state":     vpc.get("State"),
                "tenancy":   vpc.get("InstanceTenancy"),
            })
        return vpcs
    except Exception as e:
        return [{"error": str(e)}]

# ── Subnets ──────────────────────────────────────────────────────────────────
def get_subnets(region: str = None) -> list:
    creds = get_aws_credentials()
    region = region or creds["region"]
    try:
        ec2 = _client("ec2", region)
        subnets = []
        for s in ec2.describe_subnets().get("Subnets", []):
            tags = {t["Key"]: t["Value"] for t in s.get("Tags", [])}
            prefix = int(s.get("CidrBlock", "0/32").split("/")[1])
            total_ips = max(0, (2 ** (32 - prefix)) - 5)
            subnets.append({
                "id":            s.get("SubnetId"),
                "name":          tags.get("Name", s.get("SubnetId")),
                "vpc_id":        s.get("VpcId"),
                "cidr":          s.get("CidrBlock"),
                "az":            s.get("AvailabilityZone"),
                "available_ips": s.get("AvailableIpAddressCount", 0),
                "total_ips":     total_ips,
                "used_ips":      max(0, total_ips - s.get("AvailableIpAddressCount", 0)),
                "state":         s.get("State"),
                "public":        s.get("MapPublicIpOnLaunch", False),
                "default":       s.get("DefaultForAz", False),
            })
        return sorted(subnets, key=lambda x: (x.get("az", ""), x.get("cidr", "")))
    except Exception as e:
        return [{"error": str(e)}]


# ── EC2 instance actions ──────────────────────────────────────────────────────
def ec2_instance_action(instance_id: str, action: str, region: str = None) -> dict:
    creds = get_aws_credentials()
    region = region or creds["region"]
    if action not in ("start", "stop", "reboot"):
        return {"success": False, "message": f"Unknown action: {action}"}
    try:
        ec2 = _client("ec2", region)
        if action == "start":
            resp = ec2.start_instances(InstanceIds=[instance_id])
            new_state = resp["StartingInstances"][0]["CurrentState"]["Name"]
        elif action == "stop":
            resp = ec2.stop_instances(InstanceIds=[instance_id])
            new_state = resp["StoppingInstances"][0]["CurrentState"]["Name"]
        else:  # reboot
            ec2.reboot_instances(InstanceIds=[instance_id])
            new_state = "rebooting"
        return {"success": True, "instance_id": instance_id, "action": action, "state": new_state}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ── Cost Explorer (last 30 days) ──────────────────────────────────────────────
def get_cost_summary() -> dict:
    try:
        ce = _client("ce", "us-east-1")   # Cost Explorer only in us-east-1
        end   = datetime.date.today()
        start = end - datetime.timedelta(days=30)
        resp  = ce.get_cost_and_usage(
            TimePeriod={"Start": start.strftime("%Y-%m-%d"), "End": end.strftime("%Y-%m-%d")},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        totals = {}
        grand  = 0.0
        for result in resp.get("ResultsByTime", []):
            for group in result.get("Groups", []):
                svc  = group["Keys"][0]
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                totals[svc] = totals.get(svc, 0.0) + cost
                grand += cost
        top10 = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:10]
        return {
            "total_usd":     round(grand, 2),
            "period_days":   30,
            "by_service":    {k: round(v, 2) for k, v in top10},
            "currency":      "USD",
        }
    except Exception as e:
        return {"error": str(e)}

# ── Full discovery ─────────────────────────────────────────────────────────────
_discovery_cache: dict = {}
_DISCOVERY_TTL = 1200  # 20 minutes — matches SSO credential lifetime

def get_full_discovery(region: str = None, force: bool = False) -> dict:
    creds  = get_aws_credentials()
    region = region or creds["region"]
    status = get_aws_status()
    if not status["connected"]:
        return {"error": status["message"], "status": status}

    # Return cached result if fresh
    cache_key = region
    now = datetime.datetime.utcnow().timestamp()
    if not force and cache_key in _discovery_cache:
        cached_at, data = _discovery_cache[cache_key]
        if now - cached_at < _DISCOVERY_TTL:
            data["cached"] = True
            data["cache_age"] = int(now - cached_at)
            return data

    # Run all service calls in parallel to cut discovery time significantly
    tasks = {
        "ec2":     lambda: get_ec2_instances(region),
        "s3":      get_s3_buckets,
        "rds":     lambda: get_rds_instances(region),
        "vpcs":    lambda: get_vpcs(region),
        "subnets": lambda: get_subnets(region),
        "costs":   get_cost_summary,
    }
    raw = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fn): key for key, fn in tasks.items()}
        for f in as_completed(futs):
            key = futs[f]
            try:
                raw[key] = f.result()
            except Exception as e:
                raw[key] = [{"error": str(e)}]

    ec2_instances = raw.get("ec2",     [])
    s3_buckets    = raw.get("s3",      [])
    rds_instances = raw.get("rds",     [])
    vpcs          = raw.get("vpcs",    [])
    subnets       = raw.get("subnets", [])
    costs         = raw.get("costs",   {})

    ec2_err  = ec2_instances[0].get("error")  if ec2_instances  and "error" in ec2_instances[0]  else None
    s3_err   = s3_buckets[0].get("error")     if s3_buckets     and "error" in s3_buckets[0]     else None
    rds_err  = rds_instances[0].get("error")  if rds_instances  and "error" in rds_instances[0]  else None
    vpc_err  = vpcs[0].get("error")           if vpcs           and "error" in vpcs[0]           else None
    snet_err = subnets[0].get("error")        if subnets        and "error" in subnets[0]        else None

    if ec2_err:  ec2_instances = []
    if s3_err:   s3_buckets    = []
    if rds_err:  rds_instances = []
    if vpc_err:  vpcs          = []
    if snet_err: subnets       = []

    # Build EC2 summary
    ec2_running = sum(1 for i in ec2_instances if i.get("state") == "running")
    ec2_stopped = sum(1 for i in ec2_instances if i.get("state") == "stopped")

    return {
        "status":        status,
        "region":        region,
        "discovered_at": datetime.datetime.utcnow().isoformat() + "Z",
        "ec2": {
            "instances": ec2_instances,
            "total":     len(ec2_instances),
            "running":   ec2_running,
            "stopped":   ec2_stopped,
            "error":     ec2_err,
        },
        "s3": {
            "buckets": s3_buckets,
            "total":   len(s3_buckets),
            "public":  sum(1 for b in s3_buckets if b.get("public_access")),
            "error":   s3_err,
        },
        "rds": {
            "instances": rds_instances,
            "total":     len(rds_instances),
            "available": sum(1 for d in rds_instances if d.get("status") == "available"),
            "error":     rds_err,
        },
        "vpcs": {
            "list":  vpcs,
            "total": len(vpcs),
            "error": vpc_err,
        },
        "subnets": {
            "list":        subnets,
            "total":       len(subnets),
            "public":      sum(1 for s in subnets if s.get("public")),
            "private":     sum(1 for s in subnets if not s.get("public")),
            "total_ips":   sum(s.get("total_ips", 0) for s in subnets),
            "avail_ips":   sum(s.get("available_ips", 0) for s in subnets),
            "error":       snet_err,
        },
        "costs": costs,
        "errors": {k: v for k, v in {
            "ec2": ec2_err, "s3": s3_err, "rds": rds_err,
            "vpc": vpc_err, "subnets": snet_err,
        }.items() if v},
        "cached": False,
        "cache_age": 0,
    }
    _discovery_cache[cache_key] = (now, result)
    return result
