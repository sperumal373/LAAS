path = r"C:\caas-dashboard\add_posttasks.py"
content = open(path, "r", encoding="utf-8").read()

old_pb = '''function PlaybookDropdown({ aapId, groupId, value, onSelect, p }) {
  const [list, setList] = useState([]);
  const [ld, setLd] = useState(false);
  const [q, setQ] = useState("");
  useEffect(() => {
    if (!aapId) { setList([]); return; }
    setLd(true); setQ("");
    fetch("/api/migration/move-groups/" + groupId + "/post-tasks/playbooks?aap_id=" + aapId,
      { headers: { Authorization: "Bearer " + localStorage.getItem("token") } })
      .then(r => r.json())
      .then(d => { setList(d.playbooks || []); setLd(false); })
      .catch(() => setLd(false));
  }, [aapId, groupId]);
  const filtered = list.filter(i => !q || i.name.toLowerCase().includes(q.toLowerCase()));
  if (!aapId) return null;
  return (
    <div>
      <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: "block" }}>
        Playbook / Job Template {ld && "(loading...)"}
      </label>
      {ld ? <div style={{ color: p.textMute, fontSize: 12, padding: 8 }}>Loading playbooks...</div> :
       <>
         {list.length > 10 && <input placeholder={"Search " + list.length + " playbooks..."} value={q} onChange={e => setQ(e.target.value)}
           style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 12, marginBottom: 6, boxSizing: "border-box" }} />}
         <select value={value || ""} onChange={e => onSelect(e.target.value)}
           style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 13 }}>
           <option value="">-- {filtered.length} playbooks available --</option>
           {filtered.map(pb => <option key={pb.aap_instance_id + ":" + pb.id} value={pb.aap_instance_id + ":" + pb.id}>{pb.name}{pb.playbook ? " (" + pb.playbook + ")" : ""}</option>)}
         </select>
       </>}
    </div>
  );
}'''

new_pb = '''function PlaybookDropdown({ aapId, groupId, value, onSelect, p }) {
  const [list, setList] = useState([]);
  const [ld, setLd] = useState(false);
  const [q, setQ] = useState("");
  const [debounceTimer, setDebounceTimer] = useState(null);
  const doSearch = (searchTerm) => {
    if (!aapId) return;
    setLd(true);
    const url = "/api/migration/move-groups/" + groupId + "/post-tasks/playbooks?aap_id=" + aapId + (searchTerm ? "&search=" + encodeURIComponent(searchTerm) : "");
    fetch(url, { headers: { Authorization: "Bearer " + getToken() } })
      .then(r => r.json())
      .then(d => { setList(d.playbooks || []); setLd(false); })
      .catch(() => { setList([]); setLd(false); });
  };
  useEffect(() => {
    if (!aapId) { setList([]); setQ(""); return; }
    setQ(""); setList([]);
  }, [aapId, groupId]);
  const handleSearch = (val) => {
    setQ(val);
    if (debounceTimer) clearTimeout(debounceTimer);
    if (val.length >= 2) {
      setDebounceTimer(setTimeout(() => doSearch(val), 400));
    } else {
      setList([]);
    }
  };
  if (!aapId) return null;
  return (
    <div>
      <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: "block" }}>
        Playbook / Job Template {ld && "(searching...)"}
      </label>
      <input placeholder="Type 2+ chars to search playbooks..." value={q} onChange={e => handleSearch(e.target.value)}
        style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 12, marginBottom: 6, boxSizing: "border-box" }} />
      {ld ? <div style={{ color: p.textMute, fontSize: 12, padding: 8 }}>Searching...</div> :
       list.length > 0 ? (
         <select value={value || ""} onChange={e => onSelect(e.target.value)}
           style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 13 }}
           size={Math.min(list.length + 1, 12)}>
           <option value="">-- {list.length} playbooks found --</option>
           {list.map(pb => <option key={pb.aap_instance_id + ":" + pb.id} value={pb.aap_instance_id + ":" + pb.id}>{pb.name}{pb.playbook ? " (" + pb.playbook + ")" : ""}</option>)}
         </select>
       ) : q.length >= 2 ? <div style={{ color: p.textMute, fontSize: 12, padding: 8 }}>No playbooks found</div> : null}
    </div>
  );
}'''

if old_pb in content:
    content = content.replace(old_pb, new_pb)
    open(path, "w", encoding="utf-8").write(content)
    print("Updated add_posttasks.py with server-side search PlaybookDropdown")
else:
    print("ERROR: old PlaybookDropdown not found in add_posttasks.py")
