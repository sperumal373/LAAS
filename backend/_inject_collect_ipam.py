"""Inject /api/history/collect_ipam endpoint at end of main.py"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

path = 'main.py'
content = open(path, encoding='utf-8').read()

if 'collect_ipam_now' in content:
    print("Already injected — skipping")
    exit(0)

BLOCK = '''

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
            cur.execute("""
                INSERT INTO snap_ipam_summary
                    (run_date, total_subnets, total_ips, used_ips, free_ips,
                     reserved_ips, utilisation_pct, subnets_critical, subnets_warning,
                     collected_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (run_date) DO UPDATE SET
                    total_subnets    = EXCLUDED.total_subnets,
                    total_ips        = EXCLUDED.total_ips,
                    used_ips         = EXCLUDED.used_ips,
                    free_ips         = EXCLUDED.free_ips,
                    reserved_ips     = EXCLUDED.reserved_ips,
                    utilisation_pct  = EXCLUDED.utilisation_pct,
                    subnets_critical = EXCLUDED.subnets_critical,
                    subnets_warning  = EXCLUDED.subnets_warning,
                    collected_at     = NOW()
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
'''

content += BLOCK
open(path, 'w', encoding='utf-8').write(content)
print(f"Injected collect_ipam_now — new length: {len(content.splitlines())} lines")
