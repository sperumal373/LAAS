const fs = require('fs');
let content = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');

// Find the start of IPAMPage function
const start = content.indexOf('\r\n// ─── IPAM PAGE ────────────────────────────────────────────────────────────────\r\nfunction IPAMPage(');
// Find the start of ASSET MANAGEMENT PAGE
const end = content.indexOf('\r\n// ─── ASSET MANAGEMENT PAGE ────────────────────────────────────────────────────');

if (start === -1 || end === -1) {
  console.error('Could not find IPAMPage section. start:', start, 'end:', end);
  process.exit(1);
}

console.log('IPAMPage section from', start, 'to', end, '(', end-start, 'chars)');

// Read pages 3540-3641 from a known-good area to extract the VlanTab and table rendering
// We'll keep the openVlanTab function intact - it's between the handlers and the return
// Extract just the openVlanTab + return statement part from current content (after the first good canManage line)
// Find openVlanTab start
const vlanTabStart = content.indexOf('  // Open VLAN detail tab\r\n  const openVlanTab', start);
const returnStart = content.indexOf('\r\n  if (loading) return (\r\n    <div style={{display', start);

if (vlanTabStart === -1 || returnStart === -1) {
  console.error('Cannot find vlanTabStart or returnStart');
  process.exit(1);
}

// The "return" part - find the IPAMPage closing }
// It ends before // ─── ASSET MANAGEMENT PAGE
const iPageEnd = end;

const vlanTabAndReturn = content.substring(vlanTabStart, iPageEnd);
console.log('vlanTabAndReturn length:', vlanTabAndReturn.length);

// Build clean IPAMPage
const cleanPage = `
// ─── IPAM PAGE ────────────────────────────────────────────────────────────────
function IPAMPage({ currentUser, p }) {
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

  ` + vlanTabAndReturn;

// Replace section
const before = content.substring(0, start);
const after  = content.substring(iPageEnd);
const newContent = before + cleanPage + after;

fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', newContent, 'utf8');
console.log('IPAMPage rewritten successfully');
console.log('canManage occurrences:', newContent.split('canManage').length - 1);
