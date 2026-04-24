text = open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx","rb").read().decode("utf-8")

# Add a useEffect to preload AAP instances when groups tab is shown
old = 'useEffect(() => { if (tab === "groups") loadGroups(); }, [tab]);'
new = '''useEffect(() => { if (tab === "groups") loadGroups(); }, [tab]);
  useEffect(() => {
    fetch("/api/ansible/instances", { headers: { Authorization: "Bearer " + localStorage.getItem("token") } })
      .then(r => r.json())
      .then(data => { const ok = (data.instances || []).filter(i => i.status === "ok"); setPtAapInstances(ok); })
      .catch(() => {});
  }, []);'''

if 'fetch("/api/ansible/instances"' not in text.split("useEffect")[1][:200]:
    text = text.replace(old, new, 1)
    open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx","wb").write(text.encode("utf-8"))
    print("Added preload useEffect for AAP instances")
else:
    print("Already has preload")