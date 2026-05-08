"""
cis_migrate_v2.py  -- DB migration for CIS Hardening v2
"""
import psycopg2, psycopg2.extras, logging

log = logging.getLogger("cis_migrate")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PG_CONFIG = dict(host="127.0.0.1",port=5433,dbname="caas_dashboard",user="caas_app",password="CaaS@App2024#",connect_timeout=10)

MIGRATIONS = [
    "ALTER TABLE cis_scan_jobs ADD COLUMN IF NOT EXISTS os_filter TEXT",
    "ALTER TABLE cis_scan_jobs ADD COLUMN IF NOT EXISTS duration_sec NUMERIC(10,2)",
    "ALTER TABLE cis_scan_jobs ADD COLUMN IF NOT EXISTS powered_on INT DEFAULT 0",
    "ALTER TABLE cis_scan_jobs ADD COLUMN IF NOT EXISTS powered_off INT DEFAULT 0",
    "ALTER TABLE cis_scan_jobs ADD COLUMN IF NOT EXISTS not_accessible INT DEFAULT 0",
    "ALTER TABLE cis_vm_scans ADD COLUMN IF NOT EXISTS power_state TEXT DEFAULT 'unknown'",
    "ALTER TABLE cis_vm_scans ADD COLUMN IF NOT EXISTS accessible BOOLEAN DEFAULT TRUE",
    "ALTER TABLE cis_vm_scans ADD COLUMN IF NOT EXISTS skip_reason TEXT",
    "ALTER TABLE cis_vm_scans ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ",
    "ALTER TABLE cis_vm_scans ADD COLUMN IF NOT EXISTS duration_sec NUMERIC(8,2)",
    "ALTER TABLE cis_remediation_log ADD COLUMN IF NOT EXISTS approved_by TEXT",
    "ALTER TABLE cis_remediation_log ADD COLUMN IF NOT EXISTS pre_status TEXT",
    "ALTER TABLE cis_remediation_log ADD COLUMN IF NOT EXISTS post_status TEXT",
    "ALTER TABLE cis_remediation_log ADD COLUMN IF NOT EXISTS dry_run BOOLEAN DEFAULT FALSE",
    "ALTER TABLE cis_remediation_log ADD COLUMN IF NOT EXISTS bulk_job_id TEXT",
    """CREATE TABLE IF NOT EXISTS cis_baselines (
        id SERIAL PRIMARY KEY, os_key TEXT NOT NULL, rule_id TEXT,
        cis_id TEXT NOT NULL, section TEXT, title TEXT, description TEXT,
        remediation TEXT, desired_value TEXT, enabled BOOLEAN DEFAULT TRUE,
        source_file TEXT, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_cis_baselines_os_cis ON cis_baselines(os_key, cis_id)",
    "ALTER TABLE compliance_assets ADD COLUMN IF NOT EXISTS power_state TEXT DEFAULT 'unknown'",
    "ALTER TABLE compliance_assets ADD COLUMN IF NOT EXISTS os_key TEXT",
]

def run_migrations():
    conn = psycopg2.connect(**PG_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    for sql in MIGRATIONS:
        try:
            with conn.cursor() as cur: cur.execute(sql)
            conn.commit()
            log.info(f"OK: {sql[:70]}...")
        except Exception as ex:
            conn.rollback()
            log.warning(f"SKIP/FAIL: {str(ex)[:80]}")
    conn.close()
    log.info("Migration complete.")

if __name__ == "__main__":
    run_migrations()
    print("CIS v2 DB migration done.")
