with open("C:/caas-dashboard/backend/cis_scanner.py","rb") as f: raw=f.read()
t = raw.decode("utf-8-sig")
idx = t.find("OS-Version-Specific")
while idx > 0 and t[idx-1] not in ("\n","\r"): idx -= 1
insert_code = """
def bulk_remediate_vm(vm_scan_id, performed_by="system", dry_run=False):
    import uuid
    bulk_job = str(uuid.uuid4())[:8]
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(\"\"\"
                SELECT cr.cis_id, cr.title, cr.remediation_cmd,
                       vs.vm_name, vs.ip_address, vs.os_family
                FROM cis_check_results cr
                JOIN cis_vm_scans vs ON vs.id = cr.vm_scan_id
                WHERE cr.vm_scan_id = %s AND cr.status = 'fail'
                  AND cr.remediation_cmd IS NOT NULL AND cr.remediation_cmd != ''
                ORDER BY cr.cis_id
            \"\"\", (vm_scan_id,))
            checks = [dict(r) for r in cur.fetchall()]
        conn.close()
    except Exception as ex:
        return {"success": False, "error": str(ex)}
    if not checks:
        return {"success": True, "fixed": 0, "failed": 0, "message": "No failed checks to fix", "results": []}
    if dry_run:
        return {"success": True, "dry_run": True, "total_to_fix": len(checks),
                "checks": [{"cis_id": c["cis_id"], "title": c["title"]} for c in checks]}
    fixed = failed = 0
    results = []
    for chk in checks:
        res = remediate_check(vm_scan_id, chk["cis_id"], performed_by)
        results.append({"cis_id": chk["cis_id"], "title": chk["title"],
                        "success": res.get("success"), "output": res.get("output","")[:200]})
        if res.get("success"): fixed += 1
        else: failed += 1
    return {"success": True, "bulk_job_id": bulk_job, "fixed": fixed, "failed": failed,
            "total": len(checks), "results": results}


def bulk_remediate_rule(cis_id, os_key=None, performed_by="system", dry_run=False):
    import uuid
    bulk_job = str(uuid.uuid4())[:8]
    OS_KEY_FAM = {"rhel8": "linux", "rhel9": "linux", "win2016": "windows", "win2019": "windows"}
    try:
        conn = get_db()
        with conn.cursor() as cur:
            q = (\"\"\"SELECT DISTINCT ON (vs.vm_name) cr.vm_scan_id, cr.cis_id, cr.title,
                       cr.remediation_cmd, vs.vm_name, vs.ip_address, vs.os_family
                   FROM cis_check_results cr JOIN cis_vm_scans vs ON vs.id=cr.vm_scan_id
                   WHERE cr.cis_id=%s AND cr.status='fail'
                     AND cr.remediation_cmd IS NOT NULL AND cr.remediation_cmd!=''\"\"\"
            )
            params = [cis_id]
            if os_key and os_key in OS_KEY_FAM:
                q += " AND vs.os_family=%s"; params.append(OS_KEY_FAM[os_key])
            q += " ORDER BY vs.vm_name, vs.scanned_at DESC"
            cur.execute(q, params)
            checks = [dict(r) for r in cur.fetchall()]
        conn.close()
    except Exception as ex:
        return {"success": False, "error": str(ex)}
    if not checks:
        return {"success": True, "fixed": 0, "failed": 0, "total": 0, "results": []}
    if dry_run:
        return {"success": True, "dry_run": True, "cis_id": cis_id, "total_vms": len(checks),
                "vms": [{"vm_name": c["vm_name"]} for c in checks]}
    fixed = failed = 0
    results = []
    for chk in checks:
        res = remediate_check(chk["vm_scan_id"], cis_id, performed_by)
        results.append({"vm_name": chk["vm_name"], "success": res.get("success"),
                        "output": res.get("output","")[:200]})
        if res.get("success"): fixed += 1
        else: failed += 1
    return {"success": True, "bulk_job_id": bulk_job, "cis_id": cis_id,
            "fixed": fixed, "failed": failed, "total": len(checks), "results": results}


"""
new_t = t[:idx] + insert_code + t[idx:]
with open("C:/caas-dashboard/backend/cis_scanner.py","wb") as f: f.write(new_t.encode("utf-8"))
print("Done. File size:", len(new_t))
