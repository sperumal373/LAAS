"""
Add collect_cmdb call to daily_collector.py main() function.
Inserts after the existing collect_storage line.
"""

with open(r'E:\postgresql\daily_collector.py', 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. Add collect_cmdb function before main() ────────────────────────────────
CMDB_FUNCTION = '''
# ===================================================================
# CMDB – Configuration Items (ServiceNow-aligned)
# ===================================================================
def collect_cmdb():
    """Collect all CIs into cmdb_ci table via cmdb_client."""
    log.info("Collecting CMDB Configuration Items...")
    try:
        from cmdb_client import collect_all_cis, init_cmdb_db
        init_cmdb_db()
        result = collect_all_cis()
        log.info(f"  CMDB: {result['total']} CIs ({result['inserted']} new, {result['updated']} updated)")
        for plat, cnt in result.get("by_platform", {}).items():
            log.info(f"    {plat}: {cnt} CIs")
        return result
    except Exception as e:
        log.warning(f"  CMDB error: {e}")
        return {}


'''

# Insert before def main():
OLD_MAIN = 'def main():'
if CMDB_FUNCTION + OLD_MAIN in content:
    print("CMDB function already injected")
elif OLD_MAIN in content:
    content = content.replace(OLD_MAIN, CMDB_FUNCTION + OLD_MAIN, 1)
    print("OK: collect_cmdb() function added before main()")
else:
    print("ERROR: def main(): not found")

# ── 2. Add cmdb call inside main() after collect_storage ─────────────────────
OLD_CALL = '        st_data = collect_storage(today, cur);   conn.commit()'
NEW_CALL = '''        st_data = collect_storage(today, cur);   conn.commit()
        collect_cmdb()   # CMDB CIs – uses its own PG connection'''

if OLD_CALL in content:
    content = content.replace(OLD_CALL, NEW_CALL, 1)
    print("OK: collect_cmdb() call added in main()")
else:
    print("ERROR: collect_storage call not found")
    # Try to find it
    import re
    m = re.search(r'collect_storage\(today.*\)', content)
    if m:
        print(f"  Found at {m.start()}: {repr(content[m.start()-10:m.start()+80])}")

with open(r'E:\postgresql\daily_collector.py', 'w', encoding='utf-8') as f:
    f.write(content)

lines = content.count('\n') + 1
print(f"daily_collector.py: {lines} lines")
