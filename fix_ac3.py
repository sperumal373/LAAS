path = r"C:\caas-dashboard\backend\ansible_client.py"
content = open(path, "r", encoding="utf-8").read()
old = '        items = _paginate(inst, "/api/v2/job_templates/", max_items=10000)'
new = '        params = {"search": search} if search else None\n        items = _paginate(inst, "/api/v2/job_templates/", params=params, max_items=10000)'
content = content.replace(old, new)
open(path, "w", encoding="utf-8").write(content)
print("Done - search param now passed to _paginate")
