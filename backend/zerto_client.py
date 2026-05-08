import sqlite3, requests, time, warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

DB_PATH = Path(__file__).parent / "caas.db"
VERIFY_SSL = False
SESSION_CACHE = {}   # {site_id: {token, expires}}
SESSION_TTL   = 270  # Keycloak token is 5 min; refresh at 4.5 min

VPG_STATUS = {0:"Initializing",1:"MeetingSLA",2:"NotMeetingSLA",3:"HistoryNotMeetingSLA",
    4:"RpoNotMeetingSLA",5:"FailingOver",6:"Moving",7:"Deleting",8:"Recovered",9:"RollingBack"}
ALERT_LEVEL = {0:"Info",1:"Warning",2:"Error"}
TASK_STATUS  = {0:"FirstUnusedValue",1:"InProgress",2:"WaitingForUserInput",3:"Paused",
    4:"Failed",5:"Completed",6:"Cancelling",7:"Cancelled"}

def init_zerto_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS zerto_sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, host TEXT NOT NULL, port INTEGER DEFAULT 443,
            username TEXT DEFAULT 'admin', password TEXT DEFAULT '',
            site_type TEXT DEFAULT 'dc', management_url TEXT, api_base TEXT,
            enabled INTEGER DEFAULT 1, status TEXT DEFAULT 'unknown',
            last_check TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now'))
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS zerto_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER, site_name TEXT, action TEXT, vpg_id TEXT,
            vpg_name TEXT, detail TEXT, status TEXT, created_at TEXT DEFAULT (datetime('now'))
        )""")
        existing = db.execute("SELECT COUNT(*) FROM zerto_sites").fetchone()[0]
        if existing == 0:
            db.executemany(
                "INSERT INTO zerto_sites (name,host,port,username,password,site_type,notes) VALUES (?,?,?,?,?,?,?)",
                [("DC Site","172.17.73.176",443,"admin","Wipro@123","dc","Primary protected site"),
                 ("DR Site","172.17.90.216",443,"admin","Wipro@123","dr","Recovery site")]
            )
        db.commit()

def list_sites():
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute("SELECT * FROM zerto_sites WHERE enabled=1 ORDER BY site_type").fetchall()]

def get_site(site_id):
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        r = db.execute("SELECT * FROM zerto_sites WHERE id=?", (site_id,)).fetchone()
        return dict(r) if r else None

def create_site(data):
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute(
            "INSERT INTO zerto_sites (name,host,port,username,password,site_type,notes) VALUES (?,?,?,?,?,?,?)",
            (data.get("name"), data.get("host"), data.get("port",443),
             data.get("username","admin"), data.get("password",""),
             data.get("site_type","dc"), data.get("notes","")))
        db.commit()
        return {"id": cur.lastrowid, "ok": True}

def delete_site(site_id):
    with sqlite3.connect(DB_PATH) as db:
        db.execute("DELETE FROM zerto_sites WHERE id=?", (site_id,))
        db.commit()
        return {"ok": True}

def _get_token(site_id):
    """Get Keycloak bearer token for Zerto 10.x"""
    now = time.time()
    if site_id in SESSION_CACHE and SESSION_CACHE[site_id]["expires"] > now:
        return SESSION_CACHE[site_id]["token"]
    site = get_site(site_id)
    if not site:
        raise Exception("Site not found")
    host = site["host"]
    token_url = "https://%s/auth/realms/zerto/protocol/openid-connect/token" % host
    data = {
        "client_id": "zerto-client",
        "grant_type": "password",
        "username": site["username"],
        "password": site["password"],
    }
    r = requests.post(token_url, data=data, verify=VERIFY_SSL, timeout=15)
    if r.status_code != 200:
        # Update status
        with sqlite3.connect(DB_PATH) as db:
            db.execute("UPDATE zerto_sites SET status=?,last_check=? WHERE id=?",
                       ("unreachable", datetime.now().isoformat(), site_id))
            db.commit()
        raise Exception("Keycloak auth failed: HTTP %d %s" % (r.status_code, r.text[:200]))
    token = r.json()["access_token"]
    expires_in = r.json().get("expires_in", 300)
    SESSION_CACHE[site_id] = {"token": token, "expires": now + min(expires_in - 30, SESSION_TTL)}
    with sqlite3.connect(DB_PATH) as db:
        db.execute("UPDATE zerto_sites SET status=?,api_base=?,last_check=? WHERE id=?",
                   ("connected", "https://%s/v1" % host, datetime.now().isoformat(), site_id))
        db.commit()
    return token

def _zapi(site_id, path, method="GET", body=None):
    site = get_site(site_id)
    host = site["host"]
    token = _get_token(site_id)
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    url = "https://%s/v1/%s" % (host, path.lstrip("/"))
    r = requests.request(method, url, headers=headers, json=body, verify=VERIFY_SSL, timeout=30)
    if r.status_code == 401:
        if site_id in SESSION_CACHE:
            del SESSION_CACHE[site_id]
        token = _get_token(site_id)
        headers["Authorization"] = "Bearer " + token
        r = requests.request(method, url, headers=headers, json=body, verify=VERIFY_SSL, timeout=30)
    if r.status_code == 204:
        return {}
    if r.status_code >= 400:
        raise Exception("HTTP %d: %s" % (r.status_code, r.text[:300]))
    return r.json() if r.text.strip() else {}

def test_site_connection(site_id):
    try:
        token = _get_token(site_id)
        info = _zapi(site_id, "/localsite")
        return {"ok": True, "site_name": info.get("SiteName",""), "version": info.get("ZertoVersion",""),
                "location": info.get("Location",""), "site_id": info.get("SiteIdentifier","")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_dashboard(site_id):
    try:
        vpgs_raw   = _zapi(site_id, "/vpgs") or []
        vms_raw    = _zapi(site_id, "/vms")  or []
        alerts_raw = _zapi(site_id, "/alerts") or []
        tasks_raw  = _zapi(site_id, "/tasks")  or []
        vpg_list = []; total_rpo=0; rpo_count=0; total_iops=0.0; total_tp=0.0; meeting=0; not_meeting=0
        for v in vpgs_raw:
            s = VPG_STATUS.get(v.get("Status",0),"Unknown")
            rpo = v.get("ActualRPO",0) or 0
            iops = float(v.get("IOPs",0) or 0)
            tp   = float(v.get("ThroughputInMB",0) or 0)
            total_iops += iops; total_tp += tp
            if rpo: total_rpo += rpo; rpo_count += 1
            if s == "MeetingSLA": meeting += 1
            else: not_meeting += 1
            vpg_list.append({"id":v.get("VpgIdentifier",""),"name":v.get("VpgName",""),
                "status_text":s,"rpo_seconds":rpo,"iops":iops,"throughput_mb":tp})
        active_alerts = [a for a in alerts_raw if not a.get("IsDismissed")]
        running_tasks = [t for t in tasks_raw if (t.get("Status") or {}).get("State",0) not in (5,7)]
        prot_gb = round(sum(float(v.get("UsedStorageInMB",0) or 0) for v in vpgs_raw)/1024,1)
        return {
            "kpis": {"total_vpgs":len(vpgs_raw),"meeting_sla":meeting,"not_meeting_sla":not_meeting,
                "total_vms":len(vms_raw),"protected_gb":prot_gb,
                "avg_rpo_seconds":round(total_rpo/rpo_count) if rpo_count else 0,
                "total_iops":round(total_iops,2),"total_throughput_mb":round(total_tp,2),
                "active_alerts":len(active_alerts),"running_tasks":len(running_tasks)},
            "vpg_health": vpg_list,
            "active_alerts":[{"id":a.get("Link",{}).get("identifier",""),"level":a.get("Level","Info"),
                "description":a.get("Description",""),"entity":a.get("Entity",""),
                "type":str(a.get("HelpIdentifier","")),"turned_on":a.get("TurnedOn","")} for a in active_alerts[:10]],
            "running_tasks":[{"id":t.get("TaskIdentifier",""),"type":t.get("Type",""),
                "progress":(t.get("Status") or {}).get("Progress",0) or 0,"status":TASK_STATUS.get((t.get("Status") or {}).get("State",0),""),
                "started":t.get("Started","")} for t in running_tasks[:5]],
        }
    except Exception as e:
        return {"error":str(e),"kpis":{},"vpg_health":[],"active_alerts":[],"running_tasks":[]}

def list_vpgs(site_id):
    try:
        rows = _zapi(site_id, "/vpgs") or []
        result = []
        for v in rows:
            result.append({"id":v.get("VpgIdentifier",""),"name":v.get("VpgName",""),
                "status_text":VPG_STATUS.get(v.get("Status",0),"Unknown"),
                "substatus":str(v.get("SubStatus","")),"rpo_seconds":v.get("ActualRPO",0) or 0,
                "configured_rpo":v.get("ConfiguredRpoSeconds",300) or 300,
                "vms_count":v.get("VmsCount",0),"iops":float(v.get("IOPs",0) or 0),
                "throughput_mb":float(v.get("ThroughputInMB",0) or 0),
                "journal_mb":float(v.get("UsedStorageInMB",0) or 0),
                "source_site":v.get("SourceSite",""),"target_site":v.get("TargetSite",""),
                "last_test":v.get("LastTest","")})
        return result
    except Exception as e:
        return {"error":str(e)}

def get_vpg_detail(site_id, vpg_id):
    try: return _zapi(site_id, "/vpgs/%s" % vpg_id)
    except Exception as e: return {"error":str(e)}

def list_vms(site_id):
    try:
        rows = _zapi(site_id, "/vms") or []
        return [{"id":v.get("Link",{}).get("identifier",""),"name":v.get("VmName",""),
            "vpg_name":v.get("VpgName",""),"vpg_id":v.get("VpgIdentifier",""),
            "status_text":VPG_STATUS.get(v.get("Status",0),"Unknown"),
            "rpo_seconds":v.get("ActualRPO",0) or 0,"iops":float(v.get("IOPs",0) or 0),
            "journal_mb":float(v.get("JournalUsedStorageMb",0) or 0),
            "protected_site":v.get("ProtectedSite",{}).get("href","") if isinstance(v.get("ProtectedSite"),dict) else str(v.get("ProtectedSite","")),
            "recovery_site":v.get("RecoverySite",{}).get("href","") if isinstance(v.get("RecoverySite"),dict) else str(v.get("RecoverySite","")),
            "last_test":v.get("LastTest","")} for v in rows]
    except Exception as e:
        return {"error":str(e)}

def list_alerts(site_id):
    try:
        rows = _zapi(site_id, "/alerts") or []
        return [{"id":a.get("Link",{}).get("identifier",""),
            "level":a.get("Level","Info"),
            "description":a.get("Description",""),"entity":a.get("Entity",""),
            "type":str(a.get("HelpIdentifier","")),"turned_on":a.get("TurnedOn",""),
            "is_dismissed":a.get("IsDismissed",False),"site":a.get("Site","")} for a in rows]
    except Exception as e:
        return {"error":str(e)}

def dismiss_alert(site_id, alert_id):
    try:
        _zapi(site_id, "/alerts/%s/dismiss" % alert_id, method="POST")
        return {"ok":True}
    except Exception as e:
        return {"error":str(e)}

def list_tasks(site_id):
    try:
        rows = _zapi(site_id, "/tasks") or []
        return [{"id":t.get("TaskIdentifier",""),"type":t.get("Type",""),
            "progress":(t.get("Status") or {}).get("Progress",0) or 0,
            "status":TASK_STATUS.get((t.get("Status") or {}).get("State",0),""),
            "started":t.get("Started",""),"completed":t.get("Completed","")} for t in rows]
    except Exception as e:
        return {"error":str(e)}

def list_events(site_id):
    try:
        rows = _zapi(site_id, "/events?count=200") or []
        return [{"id":e.get("EventIdentifier",""),"timestamp":e.get("OccurredOn",""),
            "description":e.get("Description",""),"type":str(e.get("EventType","")),
            "category":"","user":e.get("UserName",""),
            "site":e.get("SiteName","")} for e in (rows if isinstance(rows,list) else [])]
    except Exception as e:
        return {"error":str(e)}

def get_reports(site_id):
    """Build DR operation history from tasks + events (Zerto 10.x has no /reports endpoint)."""
    try:
        tasks  = _zapi(site_id, "tasks?count=200") or []
        events = _zapi(site_id, "events?count=500") or []
        rows = []
        # Completed tasks as report rows
        for t in tasks:
            st = (t.get("Status") or {})
            state = st.get("State", 0)
            t_type = t.get("Type","")
            started   = t.get("Started","")
            completed = t.get("Completed","")
            vpg_name = ""
            for rel in (t.get("RelatedEntities") or []):
                if isinstance(rel, dict) and rel.get("type","").lower() in ("vpg","vpgapi"):
                    vpg_name = rel.get("identifier","") or rel.get("href","").split("/")[-1]
            try:
                from datetime import datetime
                s = datetime.fromisoformat(started.replace("Z","+00:00")) if started else None
                c = datetime.fromisoformat(completed.replace("Z","+00:00")) if completed else None
                dur = round((c - s).total_seconds() / 60, 1) if s and c else None
            except Exception:
                dur = None
            rows.append({
                "vpg_name": vpg_name or t.get("TaskIdentifier","")[:8],
                "test_type": t_type,
                "started": started,
                "completed": completed,
                "duration_min": dur,
                "rpo_achieved": 0,
                "result": "Success" if state == 5 else ("Failed" if state == 4 else TASK_STATUS.get(state,"")),
                "initiator": (t.get("InitiatedBy") or {}).get("UserName","") if isinstance(t.get("InitiatedBy"),dict) else str(t.get("InitiatedBy",""))
            })
        # DR-related events
        dr_types = {3,4,5,6,7,8,9,19,20,21,45,46,47,48,49,50,51,52,53,60}
        for e in events:
            et = e.get("EventType",0)
            try: et_int = int(et)
            except: et_int = 0
            if et_int not in dr_types:
                continue
            vpg_list = e.get("Vpgs") or []
            vpg_name = vpg_list[0].get("VpgName","") if vpg_list and isinstance(vpg_list[0],dict) else ""
            rows.append({
                "vpg_name": vpg_name,
                "test_type": "Event #"+str(et_int),
                "started": e.get("OccurredOn",""),
                "completed": "",
                "duration_min": None,
                "rpo_achieved": 0,
                "result": "Success" if e.get("EventCompletedSuccessfully") else "Info",
                "initiator": e.get("UserName","")
            })
        rows.sort(key=lambda x: x.get("started",""), reverse=True)
        return rows[:100]
    except Exception as ex:
        return []

def create_vpg(site_id, payload):
    """Create a new VPG via Zerto API. Payload: {name, rpo, target_site_id, ...}"""
    try:
        body = {
            "Vpg": {
                "Name": payload.get("name","New_VPG"),
                "RpoInSeconds": int(payload.get("rpo_seconds", 300)),
                "JournalHistoryInHours": int(payload.get("journal_hours", 24)),
                "Priority": payload.get("priority","Medium"),
            },
            "RecoverySite": {"Identifier": payload.get("target_site_id","")},
            "Networks": {},
            "Vms": [{"VmIdentifier": vid} for vid in payload.get("vm_ids", [])]
        }
        result = _zapi(site_id, "vpgsettings", method="POST", body=body)
        _audit(site_id, "CREATE_VPG", payload.get("name",""), "VPG creation initiated", "Success")
        return {"ok": True, "result": result}
    except Exception as e:
        _audit(site_id, "CREATE_VPG", payload.get("name",""), str(e), "Failed")
        return {"error": str(e)}

def delete_vpg(site_id, vpg_id):
    """Delete/remove a VPG via Zerto API."""
    try:
        result = _zapi(site_id, "vpgs/%s" % vpg_id, method="DELETE")
        _audit(site_id, "DELETE_VPG", vpg_id, "VPG deleted", "Success")
        return {"ok": True}
    except Exception as e:
        _audit(site_id, "DELETE_VPG", vpg_id, str(e), "Failed")
        return {"error": str(e)}

def create_vpg(site_id, payload):
    """Create a new VPG via Zerto API. Payload: {name, rpo, target_site_id, ...}"""
    try:
        body = {
            "Vpg": {
                "Name": payload.get("name","New_VPG"),
                "RpoInSeconds": int(payload.get("rpo_seconds", 300)),
                "JournalHistoryInHours": int(payload.get("journal_hours", 24)),
                "Priority": payload.get("priority","Medium"),
            },
            "RecoverySite": {"Identifier": payload.get("target_site_id","")},
            "Networks": {},
            "Vms": [{"VmIdentifier": vid} for vid in payload.get("vm_ids", [])]
        }
        result = _zapi(site_id, "vpgsettings", method="POST", body=body)
        _audit(site_id, "CREATE_VPG", payload.get("name",""), "VPG creation initiated", "Success")
        return {"ok": True, "result": result}
    except Exception as e:
        _audit(site_id, "CREATE_VPG", payload.get("name",""), str(e), "Failed")
        return {"error": str(e)}

def delete_vpg(site_id, vpg_id):
    """Delete/remove a VPG via Zerto API."""
    try:
        result = _zapi(site_id, "vpgs/%s" % vpg_id, method="DELETE")
        _audit(site_id, "DELETE_VPG", vpg_id, "VPG deleted", "Success")
        return {"ok": True}
    except Exception as e:
        _audit(site_id, "DELETE_VPG", vpg_id, str(e), "Failed")
        return {"error": str(e)}

def get_local_site(site_id):
    try: return _zapi(site_id, "/localsite")
    except Exception as e: return {"error":str(e)}

def get_peer_sites(site_id):
    try: return _zapi(site_id, "/peersites") or []
    except Exception as e: return {"error":str(e)}

def get_virt_site_vms(site_id, virt_site_id):
    """List all VMs visible to Zerto at a virtualization site (vCenter inventory)."""
    try:
        return _zapi(site_id, "/virtualizationsites/%s/vms" % virt_site_id) or []
    except Exception as e:
        return {"error": str(e)}

def get_virt_sites(site_id):
    """List all virtualization sites (vCenters) known to this ZVM."""
    try:
        return _zapi(site_id, "/virtualizationsites") or []
    except Exception as e:
        return {"error": str(e)}

def list_checkpoints(site_id, vpg_id):
    try: return _zapi(site_id, "/vpgs/%s/checkpoints" % vpg_id) or []
    except Exception as e: return {"error":str(e)}

def list_service_profiles(site_id):
    try: return _zapi(site_id, "/serviceprofiles") or []
    except Exception as e: return {"error":str(e)}

def _audit(site_id, action, vpg_id, vpg_name, detail, status):
    site = get_site(site_id)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("INSERT INTO zerto_audit_log (site_id,site_name,action,vpg_id,vpg_name,detail,status) VALUES (?,?,?,?,?,?,?)",
            (site_id, site.get("name","") if site else "", action, vpg_id, vpg_name, detail, status))
        db.commit()

def failover_test(site_id, vpg_id, vpg_name="", checkpoint_id=None):
    try:
        body = {}
        if checkpoint_id: body["CheckpointIdentifier"] = checkpoint_id
        r = _zapi(site_id, "/vpgs/%s/FailoverTest" % vpg_id, method="POST", body=body)
        _audit(site_id,"TestFailover",vpg_id,vpg_name,"DR Drill started","Success")
        return {"ok":True,"TaskIdentifier":r} if not isinstance(r,dict) else {"ok":True,**r}
    except Exception as e:
        _audit(site_id,"TestFailover",vpg_id,vpg_name,str(e),"Failed")
        return {"error":str(e)}

def failover_test_stop(site_id, vpg_id, vpg_name="", success=True, notes=""):
    try:
        _zapi(site_id, "/vpgs/%s/FailoverTestStop" % vpg_id, method="POST",
              body={"FailoverTestSuccess":success,"FailoverTestSummary":notes})
        _audit(site_id,"StopTestFailover",vpg_id,vpg_name,"Drill stopped success=%s"%success,"Success")
        return {"ok":True}
    except Exception as e:
        _audit(site_id,"StopTestFailover",vpg_id,vpg_name,str(e),"Failed")
        return {"error":str(e)}

def live_failover(site_id, vpg_id, vpg_name="", opts=None):
    try:
        r = _zapi(site_id, "/vpgs/%s/Failover" % vpg_id, method="POST", body=opts or {})
        _audit(site_id,"LiveFailover",vpg_id,vpg_name,"Live failover initiated","Success")
        return {"ok":True,"TaskIdentifier":r} if not isinstance(r,dict) else {"ok":True,**r}
    except Exception as e:
        _audit(site_id,"LiveFailover",vpg_id,vpg_name,str(e),"Failed")
        return {"error":str(e)}

def commit_failover(site_id, vpg_id, vpg_name="", reverse_protection=False):
    try:
        _zapi(site_id, "/vpgs/%s/FailoverCommit" % vpg_id, method="POST", body={"ReverseProtection":reverse_protection})
        _audit(site_id,"CommitFailover",vpg_id,vpg_name,"rev=%s"%reverse_protection,"Success")
        return {"ok":True}
    except Exception as e:
        _audit(site_id,"CommitFailover",vpg_id,vpg_name,str(e),"Failed")
        return {"error":str(e)}

def rollback_failover(site_id, vpg_id, vpg_name=""):
    try:
        _zapi(site_id, "/vpgs/%s/FailoverRollback" % vpg_id, method="POST")
        _audit(site_id,"RollbackFailover",vpg_id,vpg_name,"Rolled back","Success")
        return {"ok":True}
    except Exception as e:
        _audit(site_id,"RollbackFailover",vpg_id,vpg_name,str(e),"Failed")
        return {"error":str(e)}

def move_vpg(site_id, vpg_id, vpg_name="", opts=None):
    try:
        r = _zapi(site_id, "/vpgs/%s/Move" % vpg_id, method="POST", body=opts or {})
        _audit(site_id,"PlannedMove",vpg_id,vpg_name,"Planned move initiated","Success")
        return {"ok":True,"TaskIdentifier":r} if not isinstance(r,dict) else {"ok":True,**r}
    except Exception as e:
        _audit(site_id,"PlannedMove",vpg_id,vpg_name,str(e),"Failed")
        return {"error":str(e)}

def failback_vpg(site_id, vpg_id, vpg_name="", opts=None):
    try:
        _zapi(site_id, "/vpgs/%s/Failback" % vpg_id, method="POST", body=opts or {})
        _audit(site_id,"Failback",vpg_id,vpg_name,"Failback initiated","Success")
        return {"ok":True}
    except Exception as e:
        _audit(site_id,"Failback",vpg_id,vpg_name,str(e),"Failed")
        return {"error":str(e)}

def get_audit_log(site_id=None, limit=100):
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        if site_id:
            rows = db.execute("SELECT * FROM zerto_audit_log WHERE site_id=? ORDER BY created_at DESC LIMIT ?", (site_id, limit)).fetchall()
        else:
            rows = db.execute("SELECT * FROM zerto_audit_log ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]