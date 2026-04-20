import psycopg2, json
conn = psycopg2.connect(host='127.0.0.1', port=5433, dbname='caas_dashboard', user='caas_app', password='CaaS@App2024#')
cur = conn.cursor()

# Sample VM CIs with their extra JSON (which has tags)
cur.execute("""
    SELECT name, ip_address, os, os_version, operational_status, environment, department,
           source_platform, extra
    FROM cmdb_ci
    WHERE source_platform = 'vmware' AND sys_class_name = 'cmdb_ci_vm_instance'
    LIMIT 15
""")
print("=== VMware VM samples ===")
for r in cur.fetchall():
    extra = json.loads(r[8]) if r[8] else {}
    tags = extra.get("tags", [])
    print(f"  {r[0]:35s} IP={r[1]:16s} OS={r[2]:25s} Status={r[4]:16s} Env={r[5]:12s} Tags={tags}")

# Check what tags look like across all VMs
cur.execute("SELECT extra FROM cmdb_ci WHERE source_platform='vmware' AND sys_class_name='cmdb_ci_vm_instance'")
all_tags = set()
env_counts = {}
for row in cur.fetchall():
    extra = json.loads(row[0]) if row[0] else {}
    for t in (extra.get("tags") or []):
        all_tags.add(t)

print(f"\n=== All unique VMware tags ({len(all_tags)}) ===")
for t in sorted(all_tags):
    print(f"  {t}")

# Check environment distribution
cur.execute("SELECT environment, COUNT(*) FROM cmdb_ci GROUP BY environment ORDER BY COUNT(*) DESC")
print("\n=== Environment distribution ===")
for r in cur.fetchall():
    print(f"  {r[0] or '(empty)':20s} {r[1]}")

conn.close()
