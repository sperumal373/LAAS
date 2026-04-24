import re

with open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", "rb") as f:
    text = f.read().decode("utf-8")

# Step 1: Add AapDropdown and PlaybookDropdown components
COMP = """
function AapDropdown({ value, onSelect, p }) {
  const [list, setList] = React.useState([]);
  const [ld, setLd] = React.useState(true);
  React.useEffect(() => {
    fetch("/api/ansible/instances", { headers: { Authorization: "Bearer " + localStorage.getItem("token") } })
      .then(r => r.json())
      .then(d => { setList((d.instances || []).filter(i => i.status === "ok")); setLd(false); })
      .catch(() => setLd(false));
  }, []);
  return (
    <div>
      <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: "block" }}>AAP Instance</label>
      {ld ? <div style={{ color: p.textMute, fontSize: 12, padding: 8 }}>Loading instances...</div> :
       list.length === 0 ? <div style={{ color: "#f59e0b", fontSize: 12, padding: 8 }}>No AAP instances configured.</div> :
       <select value={value || ""} onChange={e => onSelect(e.target.value)}
         style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 13 }}>
         <option value="">-- Select AAP Instance ({list.length} available) --</option>
         {list.map(i => <option key={i.id} value={String(i.id)}>{i.name} ({i.url}) - {i.env}</option>)}
       </select>}
    </div>
  );
}

function PlaybookDropdown({ aapId, groupId, value, onSelect, p }) {
  const [list, setList] = React.useState([]);
  const [ld, setLd] = React.useState(false);
  const [q, setQ] = React.useState("");
  React.useEffect(() => {
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
}

"""

marker = "export default function MigrationPage"
text = text.replace(marker, COMP + marker, 1)
print("1. Added components")

# Step 2: Find and replace the old dropdown block
lines = text.split("\n")
start_line = None
end_line = None

for i, line in enumerate(lines):
    if "AAP Instance</label>" in line and start_line is None:
        for j in range(i-1, max(0, i-5), -1):
            if "<div>" in lines[j].strip():
                start_line = j
                break
    if start_line is not None and i > start_line + 5:
        if "{ptSelAapInst &&" in line or "{ptSelAapInst&&" in line:
            for k in range(i+1, min(len(lines), i+25)):
                if ")}" in lines[k] and "map" not in lines[k] and "filter" not in lines[k]:
                    end_line = k
                    break
            if end_line:
                break

print(f"2. Found block: lines {start_line+1 if start_line else '?'} to {end_line+1 if end_line else '?'}")

if start_line is not None and end_line is not None:
    new_lines = lines[:start_line]
    new_lines.append('                  <AapDropdown value={ptSelAapInst} onSelect={v => { setPtSelAapInst(v); setPtSelTemplate(""); }} p={p} />')
    new_lines.append('                  <PlaybookDropdown aapId={ptSelAapInst} groupId={ptGroupId} value={ptSelTemplate} onSelect={v => setPtSelTemplate(v)} p={p} />')
    new_lines.extend(lines[end_line+1:])
    text = "\n".join(new_lines)
    print("3. Replaced dropdown block")
else:
    print("ERROR: Could not find block boundaries")
    exit(1)

# Step 3: Remove alert if present
text = text.replace('    window.alert("AAP instances found: " + _inst.length + " - " + _inst.map(i=>i.name).join(", ") + " | Tasks: " + _tasks.length);\n', '')

with open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", "wb") as f:
    f.write(text.encode("utf-8"))

print("DONE")