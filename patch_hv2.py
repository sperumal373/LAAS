p = r"C:\caas-dashboard\backend\hyperv_migrate.py"
t = open(p, "r", encoding="utf-8").read()
old = '''    source_vc = plan_data.get("source_vcenter", "172.17.168.212")'''
new = '''    source_vc_raw = plan_data.get("source_vcenter", "172.17.168.212")
    # source_vcenter may be a JSON string like '{"vcenter_id":"172.17.168.212",...}'
    if isinstance(source_vc_raw, str) and source_vc_raw.strip().startswith("{"):
        try:
            vc_obj = json.loads(source_vc_raw)
            source_vc = vc_obj.get("vcenter_id", vc_obj.get("host", source_vc_raw))
        except: source_vc = source_vc_raw
    elif isinstance(source_vc_raw, dict):
        source_vc = source_vc_raw.get("vcenter_id", source_vc_raw.get("host", "172.17.168.212"))
    else:
        source_vc = source_vc_raw'''
if old in t:
    t = t.replace(old, new)
    open(p, "w", encoding="utf-8").write(t)
    print("PATCHED OK")
else:
    print("NOT FOUND")
