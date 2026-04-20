"""Seed snap_ipam_summary with today's IPAM data from ipam_pg"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import ipam_pg, psycopg2, psycopg2.extras
from datetime import date

summary = ipam_pg.get_summary()
vlans   = ipam_pg.list_vlans()
print("Summary:", summary)

total_vlans   = int(summary.get("total_vlans",   0) or 0)
total_ips     = int(summary.get("total_ips",     0) or 0)
used_ips      = int(summary.get("used_ips",      0) or 0)
free_ips      = int(summary.get("free_ips",      summary.get("available_ips", 0)) or 0)
reserved_ips  = int(summary.get("reserved_ips",  0) or 0)
util_pct      = round(used_ips / total_ips * 100, 2) if total_ips > 0 else 0.0
subnets_crit  = sum(1 for v in vlans if v.get("total_ips",0)>0 and (v.get("used_ips",0)/v["total_ips"])*100>=80)
subnets_warn  = sum(1 for v in vlans if v.get("total_ips",0)>0 and 60<=(v.get("used_ips",0)/v["total_ips"])*100<80)
today         = date.today()

conn = psycopg2.connect(host='127.0.0.1',port=5433,dbname='caas_dashboard',
    user='caas_app',password='CaaS@App2024#',
    cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()
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
      reserved_ips, util_pct, subnets_crit, subnets_warn))
conn.commit()

cur.execute("SELECT * FROM snap_ipam_summary ORDER BY run_date DESC LIMIT 5")
print("\nsnap_ipam_summary (latest 5 rows):")
for r in cur.fetchall(): print(" ", dict(r))
conn.close()
print(f"\nDone: {total_vlans} VLANs, {total_ips} IPs, {util_pct}% used, critical={subnets_crit}, warning={subnets_warn}")
