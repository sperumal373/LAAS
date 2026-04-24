path = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
content = open(path, "rb").read()

# Find the PlaybookDropdown function and its end
start = content.find(b"function PlaybookDropdown")
# Find the closing } by counting braces
depth = 0
i = start
found_first = False
end = -1
while i < len(content):
    if content[i:i+1] == b"{":
        depth += 1
        found_first = True
    elif content[i:i+1] == b"}":
        depth -= 1
        if found_first and depth == 0:
            end = i + 1
            break
    i += 1

if start == -1 or end == -1:
    print("Could not find PlaybookDropdown boundaries")
else:
    old = content[start:end]
    print(f"Found PlaybookDropdown: {len(old)} bytes, lines {content[:start].count(b'\\n')+1} to {content[:end].count(b'\\n')+1}")
    
    # Use CRLF
    NL = b"\r\n"
    new = (
        b"function PlaybookDropdown({ aapId, groupId, value, onSelect, p }) {" + NL +
        b'  const [list, setList] = useState([]);' + NL +
        b'  const [ld, setLd] = useState(false);' + NL +
        b'  const [q, setQ] = useState("");' + NL +
        b'  const [debounceTimer, setDebounceTimer] = useState(null);' + NL +
        b'  const doSearch = (searchTerm) => {' + NL +
        b'    if (!aapId) return;' + NL +
        b'    setLd(true);' + NL +
        b'    const url = "/api/migration/move-groups/" + groupId + "/post-tasks/playbooks?aap_id=" + aapId + (searchTerm ? "&search=" + encodeURIComponent(searchTerm) : "");' + NL +
        b'    fetch(url, { headers: { Authorization: "Bearer " + getToken() } })' + NL +
        b'      .then(r => r.json())' + NL +
        b'      .then(d => { setList(d.playbooks || []); setLd(false); })' + NL +
        b'      .catch(() => { setList([]); setLd(false); });' + NL +
        b'  };' + NL +
        b'  useEffect(() => {' + NL +
        b'    if (!aapId) { setList([]); setQ(""); return; }' + NL +
        b'    setQ(""); setList([]);' + NL +
        b'  }, [aapId, groupId]);' + NL +
        b'  const handleSearch = (val) => {' + NL +
        b'    setQ(val);' + NL +
        b'    if (debounceTimer) clearTimeout(debounceTimer);' + NL +
        b'    if (val.length >= 2) {' + NL +
        b'      setDebounceTimer(setTimeout(() => doSearch(val), 400));' + NL +
        b'    } else {' + NL +
        b'      setList([]);' + NL +
        b'    }' + NL +
        b'  };' + NL +
        b'  if (!aapId) return null;' + NL +
        b'  return (' + NL +
        b'    <div>' + NL +
        b'      <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: "block" }}>' + NL +
        b'        Playbook / Job Template {ld && "(searching...)"}' + NL +
        b'      </label>' + NL +
        b'      <input placeholder="Type 2+ chars to search playbooks..." value={q} onChange={e => handleSearch(e.target.value)}' + NL +
        b'        style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 12, marginBottom: 6, boxSizing: "border-box" }} />' + NL +
        b'      {ld ? <div style={{ color: p.textMute, fontSize: 12, padding: 8 }}>Searching...</div> :' + NL +
        b'       list.length > 0 ? (' + NL +
        b'         <select value={value || ""} onChange={e => onSelect(e.target.value)}' + NL +
        b'           style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 13 }}' + NL +
        b'           size={Math.min(list.length + 1, 12)}>' + NL +
        b'           <option value="">-- {list.length} playbooks found --</option>' + NL +
        b'           {list.map(pb => <option key={pb.aap_instance_id + ":" + pb.id} value={pb.aap_instance_id + ":" + pb.id}>{pb.name}{pb.playbook ? " (" + pb.playbook + ")" : ""}</option>)}' + NL +
        b'         </select>' + NL +
        b'       ) : q.length >= 2 ? <div style={{ color: p.textMute, fontSize: 12, padding: 8 }}>No playbooks found</div> : null}' + NL +
        b'    </div>' + NL +
        b'  );' + NL +
        b'}'
    )
    
    content = content[:start] + new + content[end:]
    open(path, "wb").write(content)
    print("Updated PlaybookDropdown to server-side search")
