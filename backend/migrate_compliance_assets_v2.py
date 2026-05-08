"""
migrate_compliance_assets_v2.py
Adds: location, vm_tags, missing_patches columns to compliance_assets
Run once as postgres superuser.
"""
import psycopg2
conn = psycopg2.connect(host="127.0.0.1", port=5433, dbname="caas_dashboard",
                        user="postgres", password="CaaS@2024#DB")
cur = conn.cursor()
cur.execute("ALTER TABLE compliance_assets ADD COLUMN IF NOT EXISTS location TEXT DEFAULT 'Bangalore'")
cur.execute("ALTER TABLE compliance_assets ADD COLUMN IF NOT EXISTS vm_tags TEXT[] DEFAULT '{}'")
cur.execute("ALTER TABLE compliance_assets ADD COLUMN IF NOT EXISTS missing_patches INTEGER DEFAULT 0")
conn.commit()
print("OK — location, vm_tags, missing_patches columns added to compliance_assets")
conn.close()
