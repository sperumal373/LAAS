path = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
data = open(path, "rb").read()
NL = b"\r\n"

# Fix duplicate getToken
data = data.replace(b'  getToken,\r\n  getToken,', b'  getToken,')

lines = data.split(NL)

# Find PlaybookDropdown start (not AapDropdown)
start = None
end = None
for i, line in enumerate(lines):
    if b"function PlaybookDropdown" in line:
        start = i
        break

# Find end: "export default function" 
for i in range(start + 1, len(lines)):
    if b"export default function" in lines[i]:
        end = i
        break

# Trim trailing blank lines
while end > start and lines[end - 1].strip() == b"":
    end -= 1

print(f"PlaybookDropdown: lines {start+1} to {end} (replacing {end-start} lines)")

new_lines = [
    b"function PlaybookDropdown({ aapId, groupId, value, onSelect, p }) {",
    b'  const [list, setList] = useState([]);',
    b'  const [ld, setLd] = useState(false);',
    b'  const [q, setQ] = useState("");',
    b'  const [debounceTimer, setDebounceTimer] = useState(null);',
    b'  const doSearch = (searchTerm) => {',
    b'    if (!aapId) return;',
    b'    setLd(true);',
    b'    const url = "/api/migration/move-groups/" + groupId + "/post-tasks/playbooks?aap_id=" + aapId + (searchTerm ? "&search=" + encodeURIComponent(searchTerm) : "");',
    b'    fetch(url, { headers: { Authorization: "Bearer " + getToken() } })',
    b'      .then(r => r.json())',
    b'      .then(d => { setList(d.playbooks || []); setLd(false); })',
    b'      .catch(() => { setList([]); setLd(false); });',
    b'  };',
    b'  useEffect(() => {',
    b'    if (!aapId) { setList([]); setQ(""); return; }',
    b'    setQ(""); setList([]);',
    b'  }, [aapId, groupId]);',
    b'  const handleSearch = (val) => {',
    b'    setQ(val);',
    b'    if (debounceTimer) clearTimeout(debounceTimer);',
    b'    if (val.length >= 2) {',
    b'      setDebounceTimer(setTimeout(() => doSearch(val), 400));',
    b'    } else {',
    b'      setList([]);',
    b'    }',
    b'  };',
    b'  if (!aapId) return null;',
    b'  return (',
    b'    <div>',
    b'      <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: "block" }}>',
    b'        Playbook / Job Template {ld && "(searching...)"}',
    b'      </label>',
    b'      <input placeholder="Type 2+ chars to search playbooks..." value={q} onChange={e => handleSearch(e.target.value)}',
    b'        style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 12, marginBottom: 6, boxSizing: "border-box" }} />',
    b'      {ld ? <div style={{ color: p.textMute, fontSize: 12, padding: 8 }}>Searching...</div> :',
    b'       list.length > 0 ? (',
    b'         <select value={value || ""} onChange={e => onSelect(e.target.value)}',
    b'           style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 13 }}',
    b'           size={Math.min(list.length + 1, 12)}>',
    b'           <option value="">-- {list.length} playbooks found --</option>',
    b'           {list.map(pb => <option key={pb.aap_instance_id + ":" + pb.id} value={pb.aap_instance_id + ":" + pb.id}>{pb.name}{pb.playbook ? " (" + pb.playbook + ")" : ""}</option>)}',
    b'         </select>',
    b'       ) : q.length >= 2 ? <div style={{ color: p.textMute, fontSize: 12, padding: 8 }}>No playbooks found</div> : null}',
    b'    </div>',
    b'  );',
    b'}',
    b'',
]

lines[start:end] = new_lines
data = NL.join(lines)
open(path, "wb").write(data)
print("Done - PlaybookDropdown fixed, AapDropdown preserved")
