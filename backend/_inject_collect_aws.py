"""Inject /api/history/collect_aws endpoint after collect_storage_now in main.py"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

path = 'main.py'
content = open(path, encoding='utf-8').read()

if 'collect_aws_now' in content:
    print("Already injected — skipping")
    exit(0)

INJECT_AFTER = '    return {"ok": True, "message": "Storage collection started in background"}'

AWS_COLLECT_BLOCK = '''
    return {"ok": True, "message": "Storage collection started in background"}


# ── On-demand AWS snapshot ──────────────────────────────────────────────────
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
            region = _os.getenv("AWS_REGION", "ap-south-1").strip("'\\"")
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

            # ── snap_aws_summary ──────────────────────────────────
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

            # ── snap_platform_kpi — update aws columns only ────────
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
    return {"ok": True, "message": "AWS collection started in background"}'''

if INJECT_AFTER not in content:
    print("ERROR: anchor not found")
    exit(1)

# Replace only the first occurrence (the return statement at end of collect_storage_now)
new_content = content.replace(INJECT_AFTER, AWS_COLLECT_BLOCK, 1)
open(path, 'w', encoding='utf-8').write(new_content)
print("Injected collect_aws_now endpoint")
print("Verify:", 'collect_aws_now' in open(path, encoding='utf-8').read())
