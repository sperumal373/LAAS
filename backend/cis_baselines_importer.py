import sys, logging
from pathlib import Path
import psycopg2, psycopg2.extras

try:
    import openpyxl
except ImportError:
    print("openpyxl not installed")
    sys.exit(1)

log = logging.getLogger("cis_importer")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PG_CONFIG = dict(host="127.0.0.1",port=5433,dbname="caas_dashboard",user="caas_app",password="CaaS@App2024#",connect_timeout=10)

OS_KEY_MAP = [
    ("rhel8",   ["rhel8","rhel 8"]),
    ("rhel9",   ["rhel9","rhel 9"]),
    ("win2016", ["windows2016","windows 2016","win2016","2016"]),
    ("win2019", ["windows2019","windows 2019","win2019","2019"]),
]

def get_os_key(filename):
    name = filename.lower().replace("_"," ").replace("-"," ")
    for os_key, patterns in OS_KEY_MAP:
        for pat in patterns:
            if pat in name:
                return os_key
    return None

def get_section(cis_id):
    if not cis_id: return ""
    parts = str(cis_id).split(".")
    return parts[0] if parts else ""

def read_excel_rules(filepath, os_key):
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows: return []
    header = None; header_row_idx = 0
    for i, row in enumerate(rows[:5]):
        row_strs = [str(c).lower().strip() if c else "" for c in row]
        if any("cis" in c or "rule" in c or "description" in c for c in row_strs):
            header = row_strs; header_row_idx = i; break
    if header is None: return []
    col_map = {}
    for idx, col in enumerate(header):
        if "rule" in col and "id" in col: col_map["rule_id"] = idx
        elif col in ("cis id","cis_id","cis"): col_map["cis_id"] = idx
        elif "description" in col: col_map["title"] = idx
        elif "remediation" in col: col_map["remediation"] = idx
        elif "desired" in col: col_map["desired_value"] = idx
        elif "state" in col: col_map["enabled"] = idx
    if "cis_id" not in col_map:
        log.warning(f"{filepath.name}: CIS Id column not found. Headers: {header}")
        return []
    rules = []
    for row in rows[header_row_idx + 1:]:
        if not row or all(c is None for c in row): continue
        def cell(key):
            idx = col_map.get(key)
            if idx is None or idx >= len(row): return None
            v = row[idx]
            return str(v).strip() if v is not None else None
        cis_id = cell("cis_id")
        if not cis_id or cis_id.lower() in ("none","cis id","cis_id",""): continue
        enabled_raw = cell("enabled") or ""
        enabled = enabled_raw.lower() not in ("disabled","false","0","no")
        rules.append({
            "os_key": os_key, "rule_id": cell("rule_id") or "",
            "cis_id": cis_id, "section": get_section(cis_id),
            "title": cell("title") or "", "description": cell("title") or "",
            "remediation": cell("remediation") or "",
            "desired_value": cell("desired_value") or "",
            "enabled": enabled, "source_file": filepath.name,
        })
    wb.close()
    log.info(f"  {filepath.name}: read {len(rules)} rules for os_key={os_key!r}")
    return rules

def upsert_rules(conn, rules):
    inserted = updated = 0
    with conn.cursor() as cur:
        for r in rules:
            cur.execute("""
                INSERT INTO cis_baselines
                    (os_key,rule_id,cis_id,section,title,description,remediation,desired_value,enabled,source_file,updated_at)
                VALUES (%(os_key)s,%(rule_id)s,%(cis_id)s,%(section)s,%(title)s,%(description)s,%(remediation)s,%(desired_value)s,%(enabled)s,%(source_file)s,NOW())
                ON CONFLICT (os_key,cis_id) DO UPDATE SET
                    rule_id=EXCLUDED.rule_id,section=EXCLUDED.section,title=EXCLUDED.title,
                    description=EXCLUDED.description,remediation=EXCLUDED.remediation,
                    desired_value=EXCLUDED.desired_value,source_file=EXCLUDED.source_file,updated_at=NOW()
                RETURNING (xmax=0) AS is_insert
            """, r)
            row = cur.fetchone()
            if row and row['is_insert']: inserted += 1
            else: updated += 1
    conn.commit()
    return inserted, updated

base = Path(r"E:\Compliance\ST CT")
xlsx_files = sorted(base.glob("*.xlsx"))
log.info(f"Found {len(xlsx_files)} Excel files")
conn = psycopg2.connect(**PG_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)
total_ins = total_upd = 0
for fpath in xlsx_files:
    os_key = get_os_key(fpath.stem)
    if not os_key:
        log.warning(f"Skipping {fpath.name}")
        continue
    log.info(f"Processing {fpath.name} -> {os_key}")
    rules = read_excel_rules(fpath, os_key)
    if rules:
        ins, upd = upsert_rules(conn, rules)
        log.info(f"  -> inserted={ins}, updated={upd}")
        total_ins += ins; total_upd += upd
conn.close()
print(f"\nDone: inserted={total_ins}, updated={total_upd}, total={total_ins+total_upd}")
conn2 = psycopg2.connect(**PG_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)
with conn2.cursor() as cur:
    cur.execute("SELECT os_key, COUNT(*) AS cnt FROM cis_baselines GROUP BY os_key ORDER BY os_key")
    for row in cur.fetchall(): print(f"  {row['os_key']:10s}: {row['cnt']} rules")
conn2.close()

