"""Add unique constraint on run_date to snap_ipam_summary, then seed"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import ipam_pg, psycopg2, psycopg2.extras
from datetime import date

conn = psycopg2.connect(host='127.0.0.1',port=5433,dbname='caas_dashboard',
    user='caas_app',password='CaaS@App2024#',
    cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

# Add unique constraint if not present
try:
    cur.execute("ALTER TABLE snap_ipam_summary ADD CONSTRAINT snap_ipam_summary_run_date_key UNIQUE (run_date)")
    conn.commit()
    print("Added UNIQUE constraint on run_date")
except Exception as e:
    conn.rollback()
    print(f"Constraint already exists or error: {e}")

# Now seed
summary = ipam_pg.get_summary()
vlans   = ipam_pg.list_vlans()

total_vlans  = int(summary.get("total_vlans",  0) or 0)
total_ips    = int(summary.get("total_ips",    0) or 0)
used_ips     = int(summary.get("used_ips",     0) or 0)
free_ips     = int(summary.get("free_ips",     summary.get("available_ips",0)) or 0)
reserved_ips = int(summary.get("reserved_ips", 0) or 0)
util_pct     = round(used_ips / total_ips * 100, 2) if total_ips > 0 else 0.0
crit         = sum(1 for v in vlans if v.get("total_ips",0)>0 and (v.get("used_ips",0)/v["total_ips"])*100>=80)
warn         = sum(1 for v in vlans if v.get("total_ips",0)>0 and 60<=(v.get("used_ips",0)/v["total_ips"])*100<80)
today        = date.today()

cur.execute("""
    INSERT INTO snap_ipam_summary
        (run_date, total_subnets, total_ips, used_ips, free_ips,
         reserved_ips, utilisation_pct, subnets_critical, subnets_warning, collected_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
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
      reserved_ips, util_pct, crit, warn))
conn.commit()

cur.execute("SELECT run_date, total_subnets, total_ips, used_ips, free_ips, utilisation_pct FROM snap_ipam_summary ORDER BY run_date DESC LIMIT 5")
print("\nsnap_ipam_summary (latest 5):")
for r in cur.fetchall(): print(" ", dict(r))
conn.close()
print(f"\nSeeded: {total_vlans} VLANs, {total_ips} total, {used_ips} used ({util_pct}%), crit={crit}, warn={warn}")
