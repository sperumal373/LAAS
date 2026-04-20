import requests, json, urllib3
urllib3.disable_warnings()
BASE='https://172.17.70.15/irisservices/api/v1/public'
tok=requests.post(BASE+'/accessTokens', json={'domain':'LOCAL','username':'laasuser','password':'Wipro@123'}, verify=False, timeout=15).json()
hdr={'Authorization': tok['tokenType']+' '+tok['accessToken']}

# Protection sources summary
r=requests.get(BASE+'/protectionSources', headers=hdr, verify=False, timeout=15)
ps=r.json() if r.ok else []
print(f'=== ALL SOURCES ({len(ps)}) ===')
for s in ps[:15]:
    src=s.get('protectionSource',{})
    print(f"  {src.get('environment','?'):15s} {src.get('name','?'):35s} id={src.get('id')}")

# Protection jobs detail
r3=requests.get(BASE+'/protectionJobs', headers=hdr, verify=False, timeout=15)
pj=r3.json() if r3.ok else []
envs={}
for j in pj:
    e=j.get('environment','?')
    envs[e]=envs.get(e,0)+1
print(f'\n=== JOBS by ENV ({len(pj)} total) ===')
for e,c in sorted(envs.items(), key=lambda x:-x[1]): print(f'  {e}: {c}')

active=sum(1 for j in pj if not j.get('isDeleted') and not j.get('isPaused'))
paused=sum(1 for j in pj if j.get('isPaused'))
deleted=sum(1 for j in pj if j.get('isDeleted'))
print(f'\nActive={active} Paused={paused} Deleted={deleted}')

# Protection runs - get more
r4=requests.get(BASE+'/protectionRuns', params={'numRuns':50,'excludeTasks':True}, headers=hdr, verify=False, timeout=15)
runs=r4.json() if r4.ok else []
ok=sum(1 for rn in runs if rn.get('backupRun',{}).get('status')=='kSuccess')
fail=sum(1 for rn in runs if rn.get('backupRun',{}).get('status')=='kFailure')
running=sum(1 for rn in runs if rn.get('backupRun',{}).get('status') in ('kRunning','kAccepted'))
print(f'\n=== RECENT RUNS ({len(runs)}) OK={ok} Fail={fail} Running={running} ===')

# Alerts count
r5=requests.get(BASE+'/alerts', params={'maxAlerts':100,'alertStateList':['kOpen']}, headers=hdr, verify=False, timeout=15)
alerts=r5.json() if r5.ok else []
print(f'\n=== OPEN ALERTS ({len(alerts)}) ===')
sev={}
for a in alerts:
    s=a.get('severity','?')
    sev[s]=sev.get(s,0)+1
for s,c in sev.items(): print(f'  {s}: {c}')

# Storage info from cluster
r6=requests.get(BASE+'/cluster', headers=hdr, verify=False, timeout=15)
cl=r6.json()
print(f'\n=== CLUSTER STORAGE ===')
stats=cl.get('stats',{})
usage=cl.get('usageSummary',{}) or stats
print(json.dumps(stats, indent=2, default=str)[:800] if stats else 'No stats key')
print('\n--- usageSummary ---')
print(json.dumps(usage, indent=2, default=str)[:800] if usage else 'No usageSummary')

# Views (NAS)
r7=requests.get(BASE+'/views', headers=hdr, verify=False, timeout=15)
print(f'\nViews status: {r7.status_code}')
if r7.ok:
    vd=r7.json()
    views=vd.get('views',[]) if isinstance(vd,dict) else vd
    print(f'Views count: {len(views)}')
    for v in views[:3]: print(f"  {v.get('name')} bytes={v.get('logicalUsageBytes',0)}")
