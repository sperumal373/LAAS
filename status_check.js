const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
console.log('Total lines:', lines.length);

function check(label, test) {
  console.log(label + ':', test ? '✅' : '❌');
}

// #1 Tag Selector
console.log('\n=== #1: VM Request Tag Selector ===');
check('availTags state declared', c.includes('const [availTags'));
check('useEffect fetches tags on vcId change', c.includes('fetchProjectUtilization(vcId)'));
check('Tag chip UI rendered', c.includes('VM Tags'));
check('Tags included in payload', c.includes('tags:selTags'));
// Check the condition guards:
const tagUILine = lines.findIndex(l => l.includes('availTags.length>0||tagsLoading'));
console.log('Tag UI condition at line:', tagUILine + 1);
for (let i = tagUILine - 3; i <= tagUILine + 3; i++) {
  if (i >= 0) console.log('  ' + (i+1) + ': ' + lines[i].substring(0, 110));
}

// #2 Snapshot age + taken-by
console.log('\n=== #2: Snapshot Age + Taken By ===');
check('snapAge function', c.includes('function snapAge'));
check('Age column', c.includes('"Age"') || c.includes("'Age'") || c.includes('AGE') || c.includes('age column') || c.includes('snapAge('));
check('Taken By column', c.includes('Taken By') || c.includes('taken_by') || c.includes('takenBy'));

// #3 VMware-only modal
console.log('\n=== #3: VMware-only VM Request ===');
check('vmReqVmwareOnly state', c.includes('vmReqVmwareOnly'));
check('vmwareOnly prop on VMRequestForm', c.includes('vmwareOnly=false') || c.includes('vmwareOnly={vmReqVmwareOnly}'));
check('Platform filter when vmwareOnly', c.includes('!vmwareOnly||pl.id') || c.includes('vmwareOnly||'));

// #4 Remove OCP VM Request button
console.log('\n=== #4: OCP VM Request Removed ===');
const ocpFile = fs.readFileSync('C:/caas-dashboard/frontend/src/OpenShiftPage.jsx', 'utf8');
check('No "+ Request VM" button in OCP', !ocpFile.includes('+ Request VM'));
check('No "VM Requests" queue in OCP', !ocpFile.includes('VM Requests'));

// #5 USD/INR swap
console.log('\n=== #5: USD/INR Swap in Chargeback ===');
check('USD shown prominently ($/mo)', c.includes('$/mo') || c.includes('/mo'));
check('PricingFieldRow shows USD first', c.includes('toFixed(2)}/mo'));

// #6 IPAM admin functions
console.log('\n=== #6: IPAM Admin Functions ===');
check('addIPAMManualSubnet in api.js', fs.readFileSync('C:/caas-dashboard/frontend/src/api.js','utf8').includes('addIPAMManualSubnet'));
check('canManage in IPAMPage', c.includes('canManage'));
check('Add Subnet button', c.includes('+ Add Subnet'));
check('Edit/Delete row actions', c.includes('handleDeleteSubnet'));
check('IPAM manual endpoints in backend', fs.readFileSync('C:/caas-dashboard/backend/main.py','utf8').includes('/api/ipam/manual'));

// #7 vCenter real count
console.log('\n=== #7: vCenter Real Connected Count ===');
check('Real vcErrorCount logic', c.includes('s.total_hosts>0 && (s.connected_hosts||0)===0'));

// #8 Snapshot deleting tile
console.log('\n=== #8: Snapshot Deleting Tile ===');
check('deletingCount or Deleting Now tile', c.includes('Deleting Now') || c.includes('deletingCount'));

// #9 Capacity VM count + CPU
console.log('\n=== #9: Capacity VM/CPU KPIs ===');
check('summaries prop in CapacityPage', c.includes('summaries,p}){') || c.includes('summaries, p}){'));
check('totalVMs / runVMs computed', c.includes('totalVMs') && c.includes('runVMs'));
check('CPU Free KPI', c.includes('CPU Free'));
check('summaries passed to CapacityPage render', c.includes('summaries={summaries}'));

// #10 Audit log improvements
console.log('\n=== #10: Audit Log ===');
check('riskLevel function', c.includes('function riskLevel') || c.includes('riskLevel('));
check('HIGH/MEDIUM/LOW badges', c.includes('"HIGH"') && c.includes('"MEDIUM"') && c.includes('"LOW"'));
check('Export CSV button', c.includes('Export CSV') || c.includes('exportCSV'));
check('Filter chips (8)', c.includes('actionFilter'));
check('IP address in user column', c.includes('l.ip'));

// #11 Overview graphics
console.log('\n=== #11: Overview Better Graphics ===');
check('Cross-Platform Heatmap', c.includes('Cross-Platform Resource'));
check('Platform pill mini-bar', c.includes('pl.connCount/pl.totalCount'));
check('RingChart component', c.includes('RingChart'));

console.log('\n=== DONE ===');
