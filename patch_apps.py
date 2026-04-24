import re

path = r'C:\caas-dashboard\backend\vmware_client.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add the _detect_applications function before get_all_data
app_detect_func = '''
#  Application Detection 
_APP_PATTERNS = [
    # Databases
    {"pattern": r"oracle|ora[0-9]|orcl",          "app": "Oracle DB",        "icon": "ora",   "category": "database"},
    {"pattern": r"mssql|sqlserver|sql.?srv",       "app": "MS SQL Server",    "icon": "mssql", "category": "database"},
    {"pattern": r"postgres|pgsql|pgdb",            "app": "PostgreSQL",       "icon": "pg",    "category": "database"},
    {"pattern": r"mysql|mariadb|maria",            "app": "MySQL/MariaDB",    "icon": "mysql", "category": "database"},
    {"pattern": r"mongo",                          "app": "MongoDB",          "icon": "mongo", "category": "database"},
    {"pattern": r"redis",                          "app": "Redis",            "icon": "redis", "category": "database"},
    {"pattern": r"cassandra",                      "app": "Cassandra",        "icon": "cass",  "category": "database"},
    {"pattern": r"elastic|elk|kibana|logstash",    "app": "Elasticsearch",    "icon": "elk",   "category": "database"},
    # Web / App Servers
    {"pattern": r"apache|httpd|websvr",            "app": "Apache HTTP",      "icon": "web",   "category": "web"},
    {"pattern": r"nginx",                          "app": "Nginx",            "icon": "web",   "category": "web"},
    {"pattern": r"tomcat|catalina",                "app": "Tomcat",           "icon": "java",  "category": "web"},
    {"pattern": r"iis|webserver",                  "app": "IIS Web Server",   "icon": "iis",   "category": "web"},
    {"pattern": r"jboss|wildfly",                  "app": "JBoss/WildFly",    "icon": "java",  "category": "web"},
    {"pattern": r"weblogic|wls",                   "app": "WebLogic",         "icon": "java",  "category": "web"},
    {"pattern": r"websphere",                      "app": "WebSphere",        "icon": "java",  "category": "web"},
    # DevOps / CI-CD
    {"pattern": r"jenkins",                        "app": "Jenkins",          "icon": "ci",    "category": "devops"},
    {"pattern": r"gitlab",                         "app": "GitLab",           "icon": "ci",    "category": "devops"},
    {"pattern": r"ansible|tower|aap",              "app": "Ansible/AAP",      "icon": "auto",  "category": "devops"},
    {"pattern": r"terraform",                      "app": "Terraform",        "icon": "auto",  "category": "devops"},
    {"pattern": r"cicd|pipeline|bamboo|argo",      "app": "CI/CD Pipeline",   "icon": "ci",    "category": "devops"},
    # Container / K8s
    {"pattern": r"k8s|kube|kubernetes|ocp|openshift", "app": "Kubernetes",    "icon": "k8s",   "category": "container"},
    {"pattern": r"docker|container|podman",        "app": "Container Host",   "icon": "k8s",   "category": "container"},
    {"pattern": r"rancher",                        "app": "Rancher",          "icon": "k8s",   "category": "container"},
    # Infrastructure
    {"pattern": r"\\\\bdc\\\\b|\\\\bad\\\\b|activedirectory|domain.?controller|ldap", "app": "Active Directory", "icon": "ad", "category": "infra"},
    {"pattern": r"\\\\bdns\\\\b|named|bind9",      "app": "DNS Server",       "icon": "dns",   "category": "infra"},
    {"pattern": r"\\\\bdhcp\\\\b",                  "app": "DHCP Server",      "icon": "net",   "category": "infra"},
    {"pattern": r"ntp|chrony|timeserver",          "app": "NTP Server",       "icon": "net",   "category": "infra"},
    {"pattern": r"vcsa|vcenter|vsphere",           "app": "vCenter/VCSA",     "icon": "vmw",   "category": "infra"},
    {"pattern": r"esxi|hypervisor",                "app": "ESXi Nested",      "icon": "vmw",   "category": "infra"},
    {"pattern": r"nfs|cifs|samba|fileserver|nas",  "app": "File Server",      "icon": "stor",  "category": "infra"},
    {"pattern": r"\\\\bvpn\\\\b|firewall|pfsense|fortigate", "app": "Network/Firewall", "icon": "net", "category": "infra"},
    # Monitoring
    {"pattern": r"nagios|zabbix|prometheus|grafana|splunk|solarwinds|prtg", "app": "Monitoring", "icon": "mon", "category": "monitoring"},
    # Mail
    {"pattern": r"exchange|smtp|postfix|sendmail|mail", "app": "Mail Server", "icon": "mail", "category": "mail"},
    # Backup
    {"pattern": r"veeam|cohesity|rubrik|networker|commvault|backup", "app": "Backup", "icon": "bak", "category": "backup"},
]

def _detect_applications(vm: dict) -> list[dict]:
    """Detect applications from VM name, guest OS, annotation, tags, and folder."""
    found = []
    seen = set()
    # Build search corpus from all available signals
    corpus = " ".join([
        (vm.get("name") or ""),
        (vm.get("guest_os") or ""),
        (vm.get("guest_id") or ""),
        (vm.get("annotation") or ""),
        (vm.get("folder") or ""),
        " ".join(vm.get("tags") or []),
    ]).lower()
    for rule in _APP_PATTERNS:
        if rule["app"] in seen:
            continue
        if re.search(rule["pattern"], corpus, re.IGNORECASE):
            found.append({"app": rule["app"], "icon": rule["icon"], "category": rule["category"]})
            seen.add(rule["app"])
    return found

'''

# Insert before get_all_data
marker = "def get_all_data():"
if "_detect_applications" not in content:
    idx = content.index(marker)
    content = content[:idx] + app_detect_func + "\n" + content[idx:]
    print("Inserted _detect_applications function")
else:
    print("_detect_applications already exists")

# Now add the applications field after tags are attached
# Find the line after tags attachment
old_tag_block = '''            except Exception:
                for v in vms:
                    v.setdefault("tags", [])'''

new_tag_block = '''            except Exception:
                for v in vms:
                    v.setdefault("tags", [])
            # Detect applications for each VM
            for v in vms:
                v["applications"] = _detect_applications(v)'''

if "v[\"applications\"] = _detect_applications" not in content:
    content = content.replace(old_tag_block, new_tag_block, 1)
    print("Added application detection to get_all_data")
else:
    print("Application detection already in get_all_data")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("vmware_client.py updated!")
