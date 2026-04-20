"""fix_dr_vlans.py – Fix DR VLANs 1207-1209 to correct subnets"""
import sys; sys.path.insert(0, r'c:\caas-dashboard\backend')
import psycopg2, psycopg2.extras, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(r'c:\caas-dashboard\backend') / ".env")

conn = psycopg2.connect(
    host=os.getenv("PG_HOST"), port=int(os.getenv("PG_PORT", "5433")),
    dbname=os.getenv("PG_DB"), user=os.getenv("PG_USER"), password=os.getenv("PG_PASS"),
    cursor_factory=psycopg2.extras.RealDictCursor,
)
conn.autocommit = False
cur = conn.cursor()

for vid in [1207, 1208, 1209]:
    octet = vid - 1200  # 7, 8, 9
    new_sub = f"172.16.{octet}.0/24"
    new_gw  = f"172.16.{octet}.1"
    cur.execute("SELECT id, subnet FROM ipam_vlans WHERE vlan_id=%s AND site='DR'", (vid,))
    r = cur.fetchone()
    if r:
        old_sub = r["subnet"]
        if old_sub != new_sub:
            cur.execute("DELETE FROM ipam_ips WHERE vlan_id=%s", (r["id"],))
            cur.execute("UPDATE ipam_vlans SET subnet=%s, gateway=%s WHERE id=%s", (new_sub, new_gw, r["id"]))
            print(f"Fixed DR VLAN{vid}: {old_sub} -> {new_sub}")
        else:
            print(f"DR VLAN{vid} already correct: {old_sub}")

conn.commit()
conn.close()

# Reseed IPs for fixed VLANs
import ipam_pg
for vid in [1207, 1208, 1209]:
    octet = vid - 1200
    subnet = f"172.16.{octet}.0/24"
    gateway = f"172.16.{octet}.1"
    c2 = ipam_pg._get_pg()
    c2.autocommit = False
    cu = c2.cursor()
    cu.execute("SELECT id FROM ipam_vlans WHERE vlan_id=%s AND site='DR'", (vid,))
    r2 = cu.fetchone()
    if r2:
        cu.execute("SELECT COUNT(*) FROM ipam_ips WHERE vlan_id=%s", (r2["id"],))
        cnt = cu.fetchone()
        if (cnt.get("count") or 0) == 0:
            ipam_pg._seed_ips_for_vlan(cu, r2["id"], subnet, gateway)
            c2.commit()
            print(f"Reseeded DR VLAN{vid} {subnet}")
        else:
            print(f"DR VLAN{vid} IPs already present")
    c2.close()

# Final verify
vlans = ipam_pg.list_vlans()
dr_v = [(v["vlan_id"], v["subnet"]) for v in vlans if v["site"] == "DR"]
print(f"\nDR VLANs: {dr_v}")
