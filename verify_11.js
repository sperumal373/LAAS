const fs = require('fs');
const app = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const ocp = fs.readFileSync('C:/caas-dashboard/frontend/src/OpenShiftPage.jsx', 'utf8');
const main = fs.readFileSync('C:/caas-dashboard/backend/main.py', 'utf8');
const appLines = app.split('\r\n').length;

const chk = (label, cond) => console.log((cond ? '' : '') + ' ' + label);

console.log('=== ALL 11 FEATURES CHECK ===\n');

// #1 Tag selector  always visible (no outer conditional hide)
chk('#1 Tag selector: availTags state exists', app.includes('availTags') && app.includes('setAvailTags'));
chk('#1 Tag selector: fetch on vcId change', app.includes('fetchProjectUtilization(vcId)'));
chk('#1 Tag selector: NOT hidden when empty (no outer conditional)', !app.includes('availTags.length>0||tagsLoading'));
chk('#1 Tag selector: "No tags" message shown', app.includes('No tags configured'));
chk('#1 Tag selector: chips render when tags exist', app.includes('availTags.map(tag=>'));

// #2 Snapshot Taken By
chk('#2 Snapshot Age: snapAge function', app.includes('function snapAge'));
chk('#2 Snapshot: TAKEN BY header', app.includes('TAKEN BY'));
chk('#2 Snapshot: created_by in TD cell', app.includes('s.created_by'));
chk('#2 Snapshot: backend enriches created_by from audit', main.includes('created_by') && main.includes('VM_SNAPSHOT'));

// #3 VMware-only modal
chk('#3 VMware-only VM Request modal', app.includes('vmwareOnly') || app.includes('platform==="vmware"'));

// #4 OCP: Request VM button removed from header
const ocpLines = ocp.split('\n');
let headerHasReqVM = false;
for (let i = 835; i < 870 && i < ocpLines.length; i++) {
  if (ocpLines[i].includes('Request VM') && (ocpLines[i].includes('button') || ocpLines[i].includes('btn'))) headerHasReqVM = true;
}
chk('#4 OCP: No "Request VM" button in header', !headerHasReqVM);

// #5 USD/INR
chk('#5 Chargeback: USD shown', app.includes('/VM/mo') && (app.includes('$') || app.includes('usd') || app.includes('USD')));

// #6 IPAM admin
chk('#6 IPAM: Add subnet', app.includes('Add Subnet') || app.includes('addSubnet') || app.includes('add_subnet'));
chk('#6 IPAM: Edit subnet', app.includes('editSubnet') || app.includes('Edit Subnet'));
chk('#6 IPAM: Delete subnet', app.includes('deleteSubnet') || app.includes('Delete Subnet'));

// #7 vCenter real count
chk('#7 vCenter connected count on overview', app.includes('connected') && (app.includes('vcenters.filter') || app.includes('conn')));

// #8 Snapshot delete tile
chk('#8 Snapshot: Deleting Now tile', app.includes('Deleting Now'));

// #9 Capacity KPIs
chk('#9 Capacity: VM count KPI', app.includes('VM Count') || (app.includes('vm_count') && app.includes('Capacity')));
chk('#9 Capacity: CPU Free KPI', app.includes('CPU Free') || app.includes('cpu_free'));

// #10 Audit log
chk('#10 Audit: risk badges', app.includes('HIGH') && app.includes('MEDIUM') && app.includes('risk'));
chk('#10 Audit: CSV export', app.includes('audit') && app.includes('csv'));

// #11 Overview graphics
chk('#11 Overview: heatmap or mini bars', app.includes('heatmap') || app.includes('Heatmap') || (app.includes('Overview') && app.includes('platform')));

console.log('\nApp.jsx total lines:', appLines);
