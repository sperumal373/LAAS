import json, os

# Generate the migration backend code
path = r"C:\caas-dashboard\migration_backend_new.py"

code = []
code.append("# ")
code.append("#  Magic Migrate - Cross-Hypervisor VM Migration Plans (Full Lifecycle)")
code.append("#")
code.append("")
code.append("def _init_migration_db():")
code.append("    from db import get_conn")
code.append("    with get_conn() as c:")
code.append('        c.execute("""CREATE TABLE IF NOT EXISTS migration_plans (')
code.append("            id              INTEGER PRIMARY KEY AUTOINCREMENT,")
code.append("            plan_name       TEXT NOT NULL,")
code.append("            source_platform TEXT NOT NULL DEFAULT 'vmware',")
code.append("            source_vcenter  TEXT,")
code.append("            target_platform TEXT NOT NULL,")
code.append("            target_detail   TEXT,")
code.append("            vm_list         TEXT,")
code.append("            preflight_result TEXT,")
code.append("            network_mapping TEXT,")
code.append("            storage_mapping TEXT,")
code.append("            migration_tool  TEXT,")
code.append("            status          TEXT NOT NULL DEFAULT 'planned',")
code.append("            progress        INTEGER DEFAULT 0,")
code.append("            event_log       TEXT DEFAULT '[]',")
code.append("            notes           TEXT DEFAULT '',")
code.append("            approved_by     TEXT,")
code.append("            approved_at     TEXT,")
code.append("            started_at      TEXT,")
code.append("            completed_at    TEXT,")
code.append("            created_by      TEXT,")
code.append("            created_at      TEXT DEFAULT (datetime('now')),")
code.append("            updated_at      TEXT DEFAULT (datetime('now'))")
code.append('        )""")')

with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(code))
print(f"Wrote {len(code)} lines (part1)")