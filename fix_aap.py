text = open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", encoding="utf-8").read()

# Find AapDropdown component and replace it entirely with a version that logs
OLD_COMP = '''function AapDropdown({ value, onSelect, p }) {
  const [list, setList] = useState([]);
  const [ld, setLd] = useState(true);
  useEffect(() => {
    fetch("/api/ansible/instances", { headers: { Authorization: "Bearer " + localStorage.getItem("token") } })
      .then(r => r.json())
      .then(d => { setList((d.instances || []).filter(i => i.status === "ok")); setLd(false); })
      .catch(() => setLd(false));
  }, []);'''

NEW_COMP = '''function AapDropdown({ value, onSelect, p }) {
  const [list, setList] = useState([]);
  const [ld, setLd] = useState(true);
  const [err, setErr] = useState(null);
  useEffect(() => {
    const tok = localStorage.getItem("token");
    console.log("AapDropdown: fetching, token exists:", !!tok);
    fetch("/api/ansible/instances", { headers: { Authorization: "Bearer " + (tok || "") } })
      .then(r => { console.log("AapDropdown: status", r.status); if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(d => { console.log("AapDropdown: data", d); const ok = (d.instances || []).filter(i => i.status === "ok"); console.log("AapDropdown: ok instances", ok.length); setList(ok); setLd(false); })
      .catch(e => { console.error("AapDropdown: ERROR", e); setErr(String(e)); setLd(false); });
  }, []);'''

if OLD_COMP in text:
    text = text.replace(OLD_COMP, NEW_COMP, 1)
    print("Replaced AapDropdown with logging version")
    
    # Also add error display
    old_no_aap = 'list.length === 0 ? <div style={{ color: "#f59e0b", fontSize: 12, padding: 8 }}>No AAP instances configured.</div> :'
    new_no_aap = 'list.length === 0 ? <div style={{ color: "#f59e0b", fontSize: 12, padding: 8 }}>{err ? "Fetch error: " + err : "No AAP instances configured."}</div> :'
    text = text.replace(old_no_aap, new_no_aap, 1)
    print("Added error display")
else:
    print("OLD not found - checking...")
    idx = text.find("function AapDropdown")
    print("AapDropdown at:", idx)
    print(text[idx:idx+500])

open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", "w", encoding="utf-8").write(text)
print("SAVED")