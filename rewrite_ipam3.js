const fs = require('fs');
const lines = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8').split('\r\n');

// Find boundaries
let ipamFuncLine = -1, ipamEnd = -1;

for (let i = 0; i < lines.length; i++) {
  if (lines[i].startsWith('function IPAMPage(') && ipamFuncLine === -1) {
    ipamFuncLine = i;
    console.log('IPAMPage function at line', i+1);
  }
  if (lines[i].includes('ASSET MANAGEMENT PAGE') && ipamFuncLine !== -1 && ipamEnd === -1) {
    ipamEnd = i;
    console.log('IPAMPage end at line', i+1);
    break;
  }
}

if (ipamFuncLine === -1 || ipamEnd === -1) {
  console.error('Boundaries not found. func:', ipamFuncLine, 'end:', ipamEnd);
  // Print lines around 3300-3340 to debug
  for (let i = 3290; i < 3350; i++) console.log(i+1, lines[i]);
  process.exit(1);
}

// The ipamStart is the blank line before the function (include the section comment)
// Go back from ipamFuncLine to find section header comment
let ipamStart = ipamFuncLine - 1;
while (ipamStart > 0 && lines[ipamStart].trim() === '') ipamStart--;
// If there's a comment line, include it
if (lines[ipamStart].startsWith('// ')) {
  // keep going back for blank lines
  ipamStart--;
  while (ipamStart > 0 && lines[ipamStart].trim() === '') ipamStart--;
  ipamStart++; // back to the blank line before comment
} else {
  ipamStart = ipamFuncLine;
}
console.log('ipamStart:', ipamStart+1, '  ipamFuncLine:', ipamFuncLine+1, '  ipamEnd:', ipamEnd+1);

// Find the openVlanTab part (preserved)
let vlanTabLine = -1;
for (let i = ipamFuncLine; i < ipamEnd; i++) {
  if (lines[i].includes('Open VLAN detail tab')) {
    vlanTabLine = i;
    break;
  }
}
console.log('vlanTabLine:', vlanTabLine === -1 ? 'NOT FOUND' : vlanTabLine+1);

if (vlanTabLine === -1) {
  // Print some lines to debug
  for (let i = ipamFuncLine; i < Math.min(ipamFuncLine+50, ipamEnd); i++) {
    console.log(i+1, lines[i].substring(0, 80));
  }
  process.exit(1);
}

// Extract preserved vlanTab + return part
const preserved = lines.slice(vlanTabLine, ipamEnd).join('\r\n');

// Now we need to fix the preserved section too:
// 1. Add "+ Add Subnet" button after the Refresh button
// 2. Add ACTIONS column header
// 3. Add row actions cells
// 4. Add subnet message + modal at end

let fixed = preserved;

// 1. Add Subnet button
const btnOld = '{canRefresh && (\r\n          <button onClick={handleRefresh}';
const btnNew = `{canManage && (\r\n          <button onClick={()=>{ setSubnetForm({vlan:"",address_cidr:"",name:"",location:"",comments:"",status:"Up"}); setAddModal(true); setEditEntry(null); }}\r\n            style={{padding:"7px 14px",borderRadius:8,border:"none",background:"linear-gradient(135deg,#10b981,#059669)",color:"#fff",fontWeight:600,fontSize:13,cursor:"pointer"}}>\r\n            + Add Subnet\r\n          </button>\r\n        )}\r\n        {canRefresh && (\r\n          <button onClick={handleRefresh}`;
if (fixed.includes(btnOld)) {
  fixed = fixed.replace(btnOld, btnNew);
  console.log('+ Added Subnet button');
} else { console.log('WARN: btnOld not found'); }

// 2. ACTIONS column header
const thOld = 'onClick={()=>toggleSort("status")}>Status{sortIcon("status")}</th>\r\n              </tr>';
const thNew = 'onClick={()=>toggleSort("status")}>Status{sortIcon("status")}</th>\r\n                {canManage&&<th style={{padding:"8px 10px",fontSize:11,color:"#64748b",borderBottom:`1px solid ${p.border}`}}>ACTIONS</th>}\r\n              </tr>';
if (fixed.includes(thOld)) {
  fixed = fixed.replace(thOld, thNew);
  console.log('+ Added ACTIONS column header');
} else {
  // Try alternate ending
  const thOld2 = 'onClick={()=>toggleSort("status")}>Status{sortIcon("status")}</th>\r\n                {canManage&&<th';
  if (!fixed.includes(thOld2)) {
    console.log('WARN: thOld not found. Looking for Status column...');
    const idx = fixed.indexOf('toggleSort("status")');
    if (idx > -1) console.log('Found toggleSort at:', idx, fixed.substring(idx, idx+100));
  } else console.log('ACTIONS header already present');
}

// 3. Row actions
const rowEnd = '                  </tr>\r\n                );\r\n              })}\r\n            </tbody>';
const rowNew = `                    {canManage&&<td style={{...tdS,whiteSpace:"nowrap"}}>\r\n                      {s.is_manual?(\r\n                        <div style={{display:"flex",gap:5}}>\r\n                          <button onClick={()=>{ setEditEntry(s); setSubnetForm({vlan:s.vlan||"",address_cidr:s.address_cidr||"",name:s.name||"",location:s.location||"",comments:s.comments||"",status:s.status||"Up"}); setAddModal(true); }}\r\n                            style={{padding:"2px 8px",borderRadius:5,fontSize:11,fontWeight:600,background:"#3b82f615",border:"1px solid #3b82f640",color:"#3b82f6",cursor:"pointer"}}>✏️</button>\r\n                          <button onClick={()=>handleDeleteSubnet(s)}\r\n                            style={{padding:"2px 8px",borderRadius:5,fontSize:11,fontWeight:600,background:"#ef444415",border:"1px solid #ef444440",color:"#ef4444",cursor:"pointer"}}>🗑</button>\r\n                        </div>\r\n                      ):(\r\n                        <span style={{fontSize:10,color:"#64748b"}}>SolarWinds</span>\r\n                      )}\r\n                    </td>}\r\n                  </tr>\r\n                );\r\n              })}\r\n            </tbody>`;
if (!fixed.includes('is_manual') && fixed.includes(rowEnd)) {
  fixed = fixed.replace(rowEnd, rowNew);
  console.log('+ Added row actions');
} else if (fixed.includes('is_manual')) {
  console.log('Row actions already present');
} else {
  console.log('WARN: rowEnd not found');
}

// 4. Modal at end
const tableEndOld = '        </div>\r\n      </div>\r\n    </div>\r\n  );\r\n}';
const tableEndNew = `        </div>\r\n      </div>\r\n\r\n      {/* Subnet message */}\r\n      {subnetMsg&&<div style={{padding:"10px 14px",borderRadius:8,fontSize:13,fontWeight:500,\r\n        background:subnetMsg.ok?\`\${p.green}15\`:\`\${p.red}15\`,border:\`1px solid \${subnetMsg.ok?p.green:p.red}40\`,\r\n        color:subnetMsg.ok?p.green:p.red}}>\r\n        {subnetMsg.ok?"✓":"✗"} {subnetMsg.text}\r\n      </div>}\r\n\r\n      {/* Add/Edit Subnet Modal */}\r\n      {addModal&&(\r\n        <div className="overlay" onClick={()=>setAddModal(false)}>\r\n          <div className="modal" style={{width:480}} onClick={e=>e.stopPropagation()}>\r\n            <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16}}>\r\n              <div style={{fontWeight:800,fontSize:16}}>{editEntry?"✏️ Edit Subnet":"➕ Add Manual Subnet"}</div>\r\n              <button className="btn btn-ghost btn-sm" onClick={()=>{ setAddModal(false); setEditEntry(null); }}>✕</button>\r\n            </div>\r\n            <div style={{display:"flex",flexDirection:"column",gap:12}}>\r\n              <div className="g2">\r\n                <div><label>VLAN ID</label><input value={subnetForm.vlan} onChange={e=>setSubnetForm(f=>({...f,vlan:e.target.value}))} placeholder="e.g. 100"/></div>\r\n                <div><label>Subnet / CIDR *</label><input value={subnetForm.address_cidr} onChange={e=>setSubnetForm(f=>({...f,address_cidr:e.target.value}))} placeholder="e.g. 10.0.1.0/24"/></div>\r\n              </div>\r\n              <div><label>Name / Description</label><input value={subnetForm.name} onChange={e=>setSubnetForm(f=>({...f,name:e.target.value}))} placeholder="e.g. Management Network"/></div>\r\n              <div className="g2">\r\n                <div><label>Location / Site</label><input value={subnetForm.location} onChange={e=>setSubnetForm(f=>({...f,location:e.target.value}))} placeholder="e.g. DC1-Row3"/></div>\r\n                <div><label>Status</label><select value={subnetForm.status} onChange={e=>setSubnetForm(f=>({...f,status:e.target.value}))}><option>Up</option><option>Down</option></select></div>\r\n              </div>\r\n              <div><label>Comments</label><input value={subnetForm.comments} onChange={e=>setSubnetForm(f=>({...f,comments:e.target.value}))} placeholder="Optional notes"/></div>\r\n              <div style={{display:"flex",gap:8,justifyContent:"flex-end",marginTop:4}}>\r\n                <button className="btn btn-ghost btn-sm" onClick={()=>{ setAddModal(false); setEditEntry(null); }}>Cancel</button>\r\n                <button className="btn btn-primary btn-sm" disabled={!subnetForm.address_cidr||subnetBusy} onClick={editEntry?handleEditSubnet:handleAddSubnet}>\r\n                  {subnetBusy?"⏳ Saving…":editEntry?"💾 Save Changes":"➕ Add Subnet"}\r\n                </button>\r\n              </div>\r\n            </div>\r\n          </div>\r\n        </div>\r\n      )}\r\n    </div>\r\n  );\r\n}`;
if (!fixed.includes('addModal&&') && fixed.includes(tableEndOld)) {
  fixed = fixed.replace(tableEndOld, tableEndNew);
  console.log('+ Added subnet modal');
} else if (fixed.includes('addModal&&')) {
  console.log('Modal already present');
} else {
  console.log('WARN: tableEndOld not found');
}

// Build clean IPAMPage
const cleanIPAM = `function IPAMPage({ currentUser, p }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [q, setQ]             = useState("");
  const [statusF, setStatusF] = useState("all");
  const [sortKey, setSortKey] = useState("vlan");
  const [sortDir, setSortDir] = useState("asc");
  const [refreshing, setRefreshing] = useState(false);
  const [addModal,   setAddModal]   = useState(false);
  const [editEntry,  setEditEntry]  = useState(null);
  const [subnetForm, setSubnetForm] = useState({vlan:"",address_cidr:"",name:"",location:"",comments:"",status:"Up"});
  const [subnetBusy, setSubnetBusy] = useState(false);
  const [subnetMsg,  setSubnetMsg]  = useState(null);

  const load = async () => {
    setLoading(true); setError(null);
    try { setData(await fetchIPAMSubnets()); }
    catch(e) { setError(e.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try { await refreshIPAMCache(); await load(); }
    catch(e) { setError(e.message); }
    finally { setRefreshing(false); }
  };

  const role = currentUser?.role || "viewer";
  const canRefresh = ["admin","operator"].includes(role);
  const canManage  = role === "admin";

  async function handleAddSubnet(){
    if(!subnetForm.address_cidr) return;
    setSubnetBusy(true); setSubnetMsg(null);
    try{ await addIPAMManualSubnet(subnetForm); setSubnetMsg({ok:true,text:"Subnet added"}); setAddModal(false); setSubnetForm({vlan:"",address_cidr:"",name:"",location:"",comments:"",status:"Up"}); await load(); }catch(e){ setSubnetMsg({ok:false,text:e.message}); }
    setSubnetBusy(false);
  }
  async function handleEditSubnet(){
    if(!editEntry) return;
    setSubnetBusy(true); setSubnetMsg(null);
    try{ await editIPAMManualSubnet(editEntry.subnet_id, subnetForm); setSubnetMsg({ok:true,text:"Subnet updated"}); setEditEntry(null); setSubnetForm({vlan:"",address_cidr:"",name:"",location:"",comments:"",status:"Up"}); await load(); }catch(e){ setSubnetMsg({ok:false,text:e.message}); }
    setSubnetBusy(false);
  }
  async function handleDeleteSubnet(s){
    if(!window.confirm("Delete manual subnet "+s.address_cidr+"?")) return;
    try{ await deleteIPAMManualSubnet(s.subnet_id); setSubnetMsg({ok:true,text:"Subnet deleted"}); await load(); }catch(e){ setSubnetMsg({ok:false,text:e.message}); }
  }

  ${fixed}`;

const before = lines.slice(0, ipamStart).join('\r\n');
const after  = lines.slice(ipamEnd).join('\r\n');
const newContent = before + '\r\n' + cleanIPAM + '\r\n' + after;

fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', newContent, 'utf8');
const newLines = newContent.split('\r\n').length;
console.log('\nDone! Lines:', newLines);
console.log('canManage count:', (newContent.match(/canManage/g)||[]).length);
