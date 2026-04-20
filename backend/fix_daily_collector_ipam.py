"""
Fix collect_ipam() in daily_collector.py to use ipam_pg instead of SolarWinds ipam_client.
Also adds DELETE before INSERT to avoid duplicate-key issues.
"""

with open(r'E:\postgresql\daily_collector.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_func = '''def collect_ipam(run_date, cur):
    log.info("Collecting IPAM data...")
    totals = dict(total=0, used=0, free=0)
    try:
        from ipam_client import get_ipam_subnets
        result  = get_ipam_subnets(force=True)
        if result.get("error"):
            log.warning(f"  IPAM error: {result['error']}"); return totals
        subnets = result.get("subnets",[]) or []
        summary = result.get("summary",{}) or {}
        if not subnets:
            log.info("  IPAM: no data"); return totals
        total_ips    = si(summary.get("total_ips",0))
        used_ips     = si(summary.get("used_ips",0))
        free_ips     = si(summary.get("available_ips",0))
        reserved_ips = si(summary.get("reserved_ips",0))
        pct_used     = round(sf(summary.get("percent_used",0)),2)
        crit = warn = 0
        for s in subnets:
            p = sf(s.get("percent_used",0))
            if p>=90: crit+=1
            elif p>=75: warn+=1
        cur.execute("""
            INSERT INTO snap_ipam_summary
            (run_date,total_subnets,total_ips,used_ips,free_ips,
             reserved_ips,utilisation_pct,subnets_critical,subnets_warning)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (run_date, len(subnets), total_ips, used_ips, free_ips,
              reserved_ips, pct_used, crit, warn))
        totals = dict(total=total_ips, used=used_ips, free=free_ips)
        log.info(f"  IPAM: {len(subnets)} subnets, {total_ips} IPs ({pct_used}% used)")
    except Exception as e:
        log.warning(f"  IPAM error: {e}")
    return totals'''

new_func = '''def collect_ipam(run_date, cur):
    log.info("Collecting IPAM data (PostgreSQL IPAM)...")
    totals = dict(total=0, used=0, free=0)
    try:
        from ipam_pg import get_summary as ipam_get_summary, list_vlans as ipam_list_vlans
        summary = ipam_get_summary()
        if not summary or summary.get("error"):
            log.warning(f"  IPAM error: {summary.get('error','no data') if summary else 'no data'}")
            return totals
        total_vlans  = int(summary.get("total_vlans",  0) or 0)
        total_ips    = int(summary.get("total_ips",    0) or 0)
        used_ips     = int(summary.get("used_ips",     0) or 0)
        free_ips     = int(summary.get("free_ips",     summary.get("available_ips", 0)) or 0)
        reserved_ips = int(summary.get("reserved_ips", 0) or 0)
        pct_used     = round(used_ips / total_ips * 100, 2) if total_ips > 0 else 0.0
        # Count VLANs at critical (>=80%) and warning (60-80%) utilisation
        vlans = ipam_list_vlans()
        crit = sum(1 for v in vlans if v.get("total_ips",0) > 0
                   and (v.get("used_ips",0) / v["total_ips"]) * 100 >= 80)
        warn = sum(1 for v in vlans if v.get("total_ips",0) > 0
                   and 60 <= (v.get("used_ips",0) / v["total_ips"]) * 100 < 80)
        # DELETE first (no unique constraint on run_date - caas_app is not table owner)
        cur.execute("DELETE FROM snap_ipam_summary WHERE run_date = %s", (run_date,))
        cur.execute("""
            INSERT INTO snap_ipam_summary
            (run_date,total_subnets,total_ips,used_ips,free_ips,
             reserved_ips,utilisation_pct,subnets_critical,subnets_warning)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (run_date, total_vlans, total_ips, used_ips, free_ips,
              reserved_ips, pct_used, crit, warn))
        totals = dict(total=total_ips, used=used_ips, free=free_ips)
        log.info(f"  IPAM: {total_vlans} VLANs, {total_ips} IPs ({pct_used}% used), crit={crit}, warn={warn}")
    except Exception as e:
        log.warning(f"  IPAM error: {e}")
    return totals'''

if old_func in content:
    content = content.replace(old_func, new_func, 1)
    with open(r'E:\postgresql\daily_collector.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: collect_ipam updated to use ipam_pg with DELETE+INSERT")
else:
    print("PATTERN NOT FOUND - checking for partial match...")
    if 'from ipam_client import get_ipam_subnets' in content:
        print("Found: from ipam_client import get_ipam_subnets")
    if 'def collect_ipam(run_date, cur):' in content:
        print("Found: def collect_ipam(run_date, cur):")
    # Show the actual function text
    idx = content.find('def collect_ipam')
    if idx >= 0:
        print("Actual function text:")
        print(repr(content[idx:idx+800]))
