path = r'C:\caas-dashboard\backend\vmware_client.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add a generic database pattern after the Elasticsearch line
old = '    {"pattern": r"elastic|elk|kibana|logstash",    "app": "Elasticsearch",    "icon": "elk",   "category": "database"},'
new = old + '\n    {"pattern": r"\\bdb\\b|database|\\bvdb\\b|\\bdbs\\b",  "app": "Database",         "icon": "db",    "category": "database"},'

content = content.replace(old, new, 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Added generic database pattern")
