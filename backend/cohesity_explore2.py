import requests, json, urllib3
urllib3.disable_warnings()
BASE='https://172.17.70.15/irisservices/api/v1/public'
tok=requests.post(BASE+'/accessTokens', json={'domain':'LOCAL','username':'laasuser','password':'Wipro@123'}, verify=False, timeout=15).json()
hdr={'Authorization': tok['tokenType']+' '+tok['accessToken']}

# 1. Storage domains detail
r=requests.get(BASE+'/viewBoxes', headers=hdr, verify=False, timeout=15)
vbs=r.json() if r.ok else []
print(f'=== VIEW BOXES / STORAGE DOMAINS ({len(vbs)}) ===')
for v in vbs:
    stats=v.get('stats',{})
    print(json.dumps({'name':v['name'],'id':v['id'],'usageBytes':stats.get('usagePerfStats',{}).get('totalPhysicalUsageBytes',0),'capacity':stats.get('usagePerfStats',{}).get('physicalCapacityBytes',0)}, default=str))

# 2. Restore tasks
r2=requests.get(BASE+'/restoretasks', params={'taskTypes':['kRecoverVMs'],'count':10}, headers=hdr, verify=False, timeout=15)
print(f'\n=== RESTORE TASKS status={r2.status_code} ===')
if r2.ok:
    rt=r2.json()
    print(f'Count: {len(rt)}')
    for t in rt[:3]: print(json.dumps({'name':t.get('name'),'status':t.get('status'),'type':t.get('type')}, default=str))

# 3. Search VMs
r3=requests.get(BASE+'/searchvms', params={'vmName':'*','entityTypes':['kVMware']}, headers=hdr, verify=False, timeout=15)
print(f'\n=== SEARCH VMS status={r3.status_code} ===')
if r3.ok:
    sr=r3.json()
    vms=sr.get('vms',[])
    print(f'Total VMs: {len(vms)}')
    for vm in vms[:5]:
        s=vm.get('vmDocument',{})
        print(f"  {s.get('objectName','')} job={s.get('jobName','')} versions={len(s.get('versions',[]))}")

# 4. Registered sources
r4=requests.get(BASE+'/protectionSources/registrationInfo', headers=hdr, verify=False, timeout=15)
print(f'\n=== REGISTRATION INFO status={r4.status_code} ===')
if r4.ok:
    ri=r4.json()
    roots=ri.get('rootNodes',[])
    print(f'Registered roots: {len(roots)}')
    for rn in roots[:5]:
        src=rn.get('rootNode',{})
        stats=rn.get('stats',{})
        print(f"  {src.get('name','')} env={src.get('environment','')} protected={stats.get('protectedCount',0)} unprotected={stats.get('unprotectedCount',0)}")

# 5. Cluster stats via v2 API
r5=requests.get('https://172.17.70.15/v2/clusters', headers=hdr, verify=False, timeout=15)
print(f'\n=== V2 CLUSTER status={r5.status_code} ===')
if r5.ok:
    c2=r5.json()
    print(json.dumps({k:c2.get(k) for k in ['name','nodeCount','stats','usedCapacityBytes','totalCapacityBytes'] if c2.get(k) is not None}, indent=2, default=str)[:600])
