# This script builds the complete migration backend section
import sys

P = r"C:\caas-dashboard\migration_backend_new.py"
DT = "date" + "time"  # avoid PS parsing

L = []
a = L.append

a('# ')
a('#  Magic Migrate - Cross-Hypervisor VM Migration Plans (Full Lifecycle)')
a('#')
a('')
a('def _init_migration_db():')
a('    from db import get_conn')
a('    with get_conn() as c:')
a('        c.execute("""CREATE TABLE IF NOT EXISTS migration_plans (')
a('            id              INTEGER PRIMARY KEY AUTOINCREMENT,')
a('            plan_name       TEXT NOT NULL,')
a("            source_platform TEXT NOT NULL DEFAULT 'vmware',")
a('            source_vcenter  TEXT,')
a('            target_platform TEXT NOT NULL,')
a('            target_detail   TEXT,')
a('            vm_list         TEXT,')
a('            preflight_result TEXT,')
a('            network_mapping TEXT,')
a('            storage_mapping TEXT,')
a('            migration_tool  TEXT,')
a("            status          TEXT NOT NULL DEFAULT 'planned',")
a('            progress        INTEGER DEFAULT 0,')
a("            event_log       TEXT DEFAULT '[]',")
a("            notes           TEXT DEFAULT '',")
a('            approved_by     TEXT,')
a('            approved_at     TEXT,')
a('            started_at      TEXT,')
a('            completed_at    TEXT,')
a('            created_by      TEXT,')
a(f"            created_at      TEXT DEFAULT ({DT}('now')),")
a(f"            updated_at      TEXT DEFAULT ({DT}('now'))")
a('        )""")')
a("        for col, typedef in [")
a("            ('progress', 'INTEGER DEFAULT 0'),")
a('            (\'event_log\', "TEXT DEFAULT \'[]\'"),')
a("            ('approved_by', 'TEXT'),")
a("            ('approved_at', 'TEXT'),")
a("            ('started_at', 'TEXT'),")
a("            ('completed_at', 'TEXT'),")
a("        ]:")
a("            try:")
a("                c.execute(f'ALTER TABLE migration_plans ADD COLUMN {col} {typedef}')")
a("            except:")
a("                pass")
a('')
a('_init_migration_db()')

with open(P, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
print(f"Wrote {len(L)} lines")