import requests, json, urllib3
urllib3.disable_warnings()
BASE='https://172.17.70.15/irisservices/api/v1/public'
tok=requests.post(BASE+'/accessTokens', json={'domain':'LOCAL','username':'laasuser','password':'Wipro@123'}, verify=False, timeout=15).json()
hdr={'Authorization': tok['tokenType']+' '+tok['accessToken']}

# V2 API endpoints
BASE2='https://172.17.70.15/v2'

# 1. Stats - storage
r=requests.get(BASE2+'/stats/storage', headers=hdr, verify=False, timeout=15)
print(f'=== V2 stats/storage status={r.status_code} ===')
if r.ok: print(json.dumps(r.json(), indent=2, default=str)[:800])

# 2. Data protect - protection groups
r2=requests.get(BASE2+'/data-protect/protection-groups', headers=hdr, verify=False, timeout=15)
print(f'\n=== V2 protection-groups status={r2.status_code} ===')
if r2.ok:
    pg=r2.json()
    groups=pg.get('protectionGroups',[])
    print(f'Count: {len(groups)}')
    for g in groups[:5]: print(f"  {g.get('name')} env={g.get('environment')} active={not g.get('isPaused',False)} lastRun={g.get('lastRun',{}).get('localBackupInfo',{}).get('status','?')}")

# 3. Objects (protected)
r3=requests.get(BASE2+'/data-protect/objects', params={'onlyProtectedObjects':True}, headers=hdr, verify=False, timeout=15)
print(f'\n=== V2 protected objects status={r3.status_code} ===')
if r3.ok:
    obj=r3.json()
    objs=obj.get('objects',[])
    print(f'Protected objects: {len(objs)}')

# 3b. Objects (unprotected)
r3b=requests.get(BASE2+'/data-protect/objects', params={'onlyProtectedObjects':False}, headers=hdr, verify=False, timeout=15)
if r3b.ok:
    obj2=r3b.json()
    objs2=obj2.get('objects',[])
    print(f'All objects: {len(objs2)}')

# 4. Alerts
r4=requests.get(BASE2+'/alerts', params={'maxAlerts':5,'alertStateList':['kOpen']}, headers=hdr, verify=False, timeout=15)
print(f'\n=== V2 alerts status={r4.status_code} ===')
if r4.ok:
    al=r4.json()
    alerts=al if isinstance(al,list) else al.get('alerts',[])
    for a in alerts[:3]:
        print(f"  sev={a.get('severity')} cat={a.get('alertCategory')} desc={a.get('alertDocument',{}).get('alertName','?')}")

# 5. Recovery
r5=requests.get(BASE2+'/data-protect/recoveries', params={'count':5}, headers=hdr, verify=False, timeout=15)
print(f'\n=== V2 recoveries status={r5.status_code} ===')
if r5.ok:
    rec=r5.json()
    recs=rec.get('recoveries',[])
    print(f'Recoveries: {len(recs)}')
    for rc in recs[:3]: print(f"  {rc.get('name')} status={rc.get('status')} type={rc.get('snapshotEnvironment')}")

# 6. Search protected objects
r6=requests.get(BASE2+'/data-protect/search/objects', params={'searchString':'*','environments':'kVMware'}, headers=hdr, verify=False, timeout=15)
print(f'\n=== V2 search objects status={r6.status_code} ===')
if r6.ok:
    sr=r6.json()
    res=sr.get('objects',[])
    print(f'Search results: {len(res)}')
    for o in res[:5]: print(f"  {o.get('name')} env={o.get('environment')} id={o.get('id')}")
