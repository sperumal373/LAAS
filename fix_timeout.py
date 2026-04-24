import re

path = r"C:\caas-dashboard\frontend\https_server.cjs"
content = open(path, "r").read()
old = "var timeoutMs = req.url.startsWith('/api/ai/chat') ? 180000 : 30000;"
new = "var timeoutMs = (req.url.startsWith('/api/ai/chat') ? 180000 : (req.url.indexOf('/post-tasks/playbooks') !== -1 ? 120000 : 30000));"
if old in content:
    content = content.replace(old, new)
    open(path, "w").write(content)
    print("Updated https_server.cjs timeout")
else:
    print("Timeout line not found or already changed")
