import ipam_pg, time
print("Running ping_and_save on VLAN 1263 (db_id=1)...")
start = time.time()
results = ipam_pg.ping_and_save(1)
elapsed = time.time() - start
up   = [ip for ip,v in results.items() if v["ping"]=="up"]
down = [ip for ip,v in results.items() if v["ping"]=="down"]
print(f"Done in {elapsed:.1f}s  total={len(results)}  up={len(up)}  down={len(down)}")
print("Sample UP IPs (should show status=used):")
for ip in up[:5]:
    print(f"  {ip}  ping={results[ip]['ping']}  status={results[ip]['status']}")
print("Sample DOWN IPs (should show status=available):")
for ip in down[:5]:
    print(f"  {ip}  ping={results[ip]['ping']}  status={results[ip]['status']}")
