import requests, json, urllib3
urllib3.disable_warnings()
BASE='https://172.17.70.15/irisservices/api/v1/public'
tok=requests.post(BASE+'/accessTokens', json={'domain':'LOCAL','username':'laasuser','password':'Wipro@123'}, verify=False, timeout=15).json()
hdr={'Authorization': tok['tokenType']+' '+tok['accessToken']}
BASE2='https://172.17.70.15/v2'

# Run one job to see full detail
r=requests.get(BASE+'/protectionJobs', headers=hdr, verify=False, timeout=15)
pj=r.json()
# Find a non-deleted job 
active_jobs=[j for j in pj if not j.get('isDeleted')][:1]
if active_jobs:
    j=active_jobs[0]
    print('=== SAMPLE JOB ===')
    keys=['id','name','policyId','environment','parentSourceId','sourceIds','viewBoxId','isActive','isDeleted','isPaused','startTime','timezone','priority','qosType','lastRun']
    for k in keys:
        if k in j: print(f'  {k}: {j[k]}')

# Protection runs with tasks for one job
r2=requests.get(BASE+'/protectionRuns', params={'jobId':active_jobs[0]['id'],'numRuns':3,'excludeTasks':False}, headers=hdr, verify=False, timeout=15)
runs=r2.json() if r2.ok else []
print(f'\n=== RUNS for {active_jobs[0]["name"]} ({len(runs)}) ===')
for rn in runs[:2]:
    br=rn.get('backupRun',{})
    print(f"  status={br.get('status')} start={br.get('stats',{}).get('startTimeUsecs')} sources={len(br.get('sourceBackupStatus',[]))}")
    for sb in br.get('sourceBackupStatus',[])[:3]:
        src=sb.get('source',{})
        st=sb.get('status','?')
        print(f"    {src.get('name','')} status={st}")

# V2 protection-groups with last runs
r3=requests.get(BASE2+'/data-protect/protection-groups', params={'includeTenants':True,'includeLastRunInfo':True}, headers=hdr, verify=False, timeout=15)
pg=r3.json().get('protectionGroups',[]) if r3.ok else []
print(f'\n=== V2 GROUPS WITH LAST RUN ({len(pg)}) ===')
for g in pg[:5]:
    lr=g.get('lastRun',{})
    lb=lr.get('localBackupInfo',{})
    print(f"  {g.get('name')} paused={g.get('isPaused',False)} lastStatus={lb.get('status','?')} objects={g.get('numProtectedObjects','?')}")

# Storage - from v1 cluster with different fields
r4=requests.get(BASE+'/cluster', headers=hdr, verify=False, timeout=15)
cl=r4.json()
print(f'\n=== CLUSTER ALL KEYS ===')
for k in sorted(cl.keys()): 
    v=cl[k]
    if not isinstance(v,(dict,list)): print(f'  {k}: {v}')
    elif isinstance(v,dict) and len(v)<5: print(f'  {k}: {v}')
