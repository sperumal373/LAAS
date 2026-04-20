import requests, json, urllib3
urllib3.disable_warnings()
BASE='https://172.17.70.15/irisservices/api/v1/public'
tok=requests.post(BASE+'/accessTokens', json={'domain':'LOCAL','username':'laasuser','password':'Wipro@123'}, verify=False, timeout=15).json()
hdr={'Authorization': tok['tokenType']+' '+tok['accessToken']}

# Storage from viewBoxes with all stats
r=requests.get(BASE+'/viewBoxes', headers=hdr, verify=False, timeout=15)
vbs=r.json() if r.ok else []
print('=== VIEWBOXES FULL STATS ===')
total_used=0; total_cap=0
for v in vbs:
    print(f"\n--- {v['name']} ---")
    s=v.get('stats',{})
    up=s.get('usagePerfStats',{})
    dp=s.get('dataProtectStats',{})
    for k2 in sorted(up.keys()) if up else []: print(f'  usagePerfStats.{k2}: {up[k2]}')
    for k2 in sorted(dp.keys()) if dp else []: print(f'  dataProtectStats.{k2}: {dp[k2]}')
    if not up and not dp:
        for k2 in sorted(s.keys()): print(f'  stats.{k2}: {s[k2]}')

# Nodes info
r2=requests.get(BASE+'/nodes', headers=hdr, verify=False, timeout=15)
print(f'\n=== NODES status={r2.status_code} ===')
if r2.ok:
    nodes=r2.json()
    print(f'Nodes: {len(nodes)}')
    for n in nodes:
        cap=n.get('capacity',{}) or {}
        stats=n.get('stats',{}) or {}
        print(f"  id={n.get('id')} slotNum={n.get('slotNumber')} ip={n.get('ip')} capacity={cap}")

# V2 protection-groups with lastRun details
r3=requests.get('https://172.17.70.15/v2/data-protect/protection-groups', params={'includeLastRunInfo':True,'isDeleted':False,'isActive':True}, headers=hdr, verify=False, timeout=15)
pg=r3.json().get('protectionGroups',[]) if r3.ok else []
active_pg=[g for g in pg if not g.get('isDeleted') and not g.get('isPaused')]
paused_pg=[g for g in pg if g.get('isPaused')]
print(f'\n=== V2 ACTIVE GROUPS: {len(active_pg)}, PAUSED: {len(paused_pg)} ===')
for g in active_pg[:3]:
    lr=g.get('lastRun',{})
    print(f"  {g.get('name')} env={g.get('environment')} id={g.get('id')} policy={g.get('policyId','?')[:30]}")
    if lr: print(f"    lastRun: local={lr.get('localBackupInfo',{}).get('status','?')} arch={lr.get('archivalInfo',{})}")

# V2 policies
r4=requests.get('https://172.17.70.15/v2/data-protect/policies', headers=hdr, verify=False, timeout=15)
print(f'\n=== V2 POLICIES status={r4.status_code} ===')
if r4.ok:
    pol=r4.json().get('policies',[])
    print(f'Count: {len(pol)}')
    for p in pol[:5]:
        print(f"  {p.get('name')} id={p.get('id')}")
        inc=p.get('backupPolicy',{}).get('regular',{}).get('incremental',{}).get('schedule',{})
        full_=p.get('backupPolicy',{}).get('regular',{}).get('full',{}).get('schedule',{})
        if inc: print(f"    incremental: {inc.get('unit','?')} freq={inc.get('daySchedule',{}).get('frequency',inc.get('frequency','?'))}")
