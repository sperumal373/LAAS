// api.js â€” CaaS Dashboard API client v5.5
// HTTPS: API calls go to same origin (proxied by Node HTTPS server -> backend 8000)
// HTTP:  API calls go directly to port 8000
const BASE = window.location.protocol === "https:"
  ? `${window.location.protocol}//${window.location.hostname}`   // same origin, Node proxies /api/*
  : `http://${window.location.hostname}:8000`;

// Fix #10: persist token + user in sessionStorage so page reload keeps session
let _token       = sessionStorage.getItem("caas_token")       || null;
let _currentUser = JSON.parse(sessionStorage.getItem("caas_user") || "null");
let _page        = sessionStorage.getItem("caas_page")        || "overview";

export function getToken()        { return _token; }
export function getCurrentUser()  { return _currentUser; }
export function isLoggedIn()      { return !!_token; }
export function getSavedPage()    { return _page; }
export function savePage(page)    { _page = page; sessionStorage.setItem("caas_page", page); }

export function clearSession() {
  _token = null; _currentUser = null; _page = "overview";
  sessionStorage.removeItem("caas_token");
  sessionStorage.removeItem("caas_user");
  sessionStorage.removeItem("caas_page");
}

function _saveSession(token, user) {
  _token = token; _currentUser = user;
  sessionStorage.setItem("caas_token", token);
  sessionStorage.setItem("caas_user", JSON.stringify(user));
}

function authHeader() {
  if (!_token) throw new Error("Not authenticated");
  return { Authorization: `Bearer ${_token}`, "Content-Type": "application/json" };
}

// Convert FastAPI error detail (string or Pydantic v2 array) to a readable message
function _detailMsg(e, status) {
  const d = e.detail;
  if (!d) return `API error ${status}`;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d.map(err => {
      const loc  = Array.isArray(err.loc) ? err.loc.filter(l => l !== "body").join(" â†’ ") : "";
      const msg  = err.msg || err.message || JSON.stringify(err);
      return loc ? `${loc}: ${msg}` : msg;
    }).join("; ");
  }
  try { return JSON.stringify(d); } catch { return `API error ${status}`; }
}

async function _get(path) {
  const res = await fetch(`${BASE}${path}`, { headers: authHeader() });
  if (res.status === 401) { clearSession(); throw new Error("Session expired"); }
  if (res.status === 403) throw new Error("Permission denied");
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(_detailMsg(e, res.status)); }
  return res.json();
}

async function _post(path, body) {
  const headers = _token ? authHeader() : { "Content-Type": "application/json" };
  const res = await fetch(`${BASE}${path}`, { method:"POST", headers, body: JSON.stringify(body) });
  if (res.status === 401) { clearSession(); throw new Error("Session expired"); }
  if (res.status === 403) throw new Error("Permission denied");
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(_detailMsg(e, res.status)); }
  return res.json();
}

async function _put(path, body) {
  const res = await fetch(`${BASE}${path}`, { method:"PUT", headers: authHeader(), body: JSON.stringify(body) });
  if (res.status === 401) { clearSession(); throw new Error("Session expired"); }
  if (res.status === 403) throw new Error("Permission denied");
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(_detailMsg(e, res.status)); }
  return res.json();
}

async function _patch(path, body) {
  const res = await fetch(`${BASE}${path}`, { method:"PATCH", headers: authHeader(), body: JSON.stringify(body) });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(_detailMsg(e, res.status)); }
  return res.json();
}

async function _delete(path) {
  const res = await fetch(`${BASE}${path}`, { method:"DELETE", headers: authHeader() });
  if (res.status === 401) { clearSession(); throw new Error("Session expired"); }
  if (res.status === 403) throw new Error("Permission denied");
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(_detailMsg(e, res.status)); }
  return res.status === 204 ? {} : res.json().catch(()=>({}));
}

// â”€â”€ Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function login(username, password) {
  const data = await _post("/api/auth/login", { username, password });
  _saveSession(data.token, data.user);
  return data.user;
}
export async function logout() {
  try { await _post("/api/auth/logout", {}); } catch {}
  clearSession();
}
export async function fetchMe()       { return _get("/api/auth/me"); }
export async function fetchADStatus() { return _get("/api/auth/ad-status"); }

export async function verifySession() {
  if (!_token) return null;
  try {
    const user = await fetchMe();
    _currentUser = user;
    sessionStorage.setItem("caas_user", JSON.stringify(user));
    return user;
  } catch {
    clearSession();
    return null;
  }
}

export function setCredentials() {}
export async function checkAuth(u, p) {
  try { await login(u, p); return true; } catch { return false; }
}

// â”€â”€ vCenters â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchVCenters() { const d = await _get("/api/vcenters"); return d.vcenters; }

// â”€â”€ VMware data â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const qs = (id) => id && id !== "all" ? `?vcenter_id=${encodeURIComponent(id)}` : "";
export async function fetchSummary(id)    { return _get(`/api/vmware/summary${qs(id)}`); }
export async function fetchVMs(id)        { const d = await _get(`/api/vmware/vms${qs(id)}`);        return d.vms; }
export async function fetchHosts(id)      { const d = await _get(`/api/vmware/hosts${qs(id)}`);      return d.hosts; }
export async function fetchDatastores(id) { const d = await _get(`/api/vmware/datastores${qs(id)}`); return d.datastores; }
export async function fetchNetworks(id)   { const d = await _get(`/api/vmware/networks${qs(id)}`);   return d.networks; }
export async function fetchSnapshots(id)  { const d = await _get(`/api/vmware/snapshots${qs(id)}`);  return d.snapshots; }
export async function fetchAlerts(id)     { const d = await _get(`/api/alerts${qs(id)}`);            return d.alerts; }
export async function fetchProjectUtilization(id) {
  const controller = new AbortController();
  const timeoutMs = 45000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}/api/vmware/project-utilization${qs(id)}`, {
      headers: authHeader(),
      signal: controller.signal,
    });
    if (res.status === 401) { clearSession(); throw new Error("Session expired"); }
    if (res.status === 403) throw new Error("Permission denied");
    if (!res.ok) {
      const e = await res.json().catch(()=>({}));
      throw new Error(e.detail || `API error ${res.status}`);
    }
    return res.json();
  } catch (e) {
    if (e?.name === "AbortError") {
      throw new Error("Project utilization request timed out. Please try a single vCenter or retry.");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}
export async function updateProjectTagOwner(tag, owner_name, owner_email="", vcenter_scope="all") {
  return _patch(`/api/vmware/project-utilization/owner`, { tag, owner_name, owner_email, vcenter_scope });
}
export async function fetchVCResources(id){ return _get(`/api/vmware/resources/${encodeURIComponent(id)}`); }
export async function fetchVCTemplates(id) { return _get(`/api/vmware/templates/${encodeURIComponent(id)}`); }

// â”€â”€ VM Actions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function vmPowerAction(vcenter_id, vm_name, action) {
  return _post("/api/vmware/power", { vcenter_id, vm_name, action });
}
export async function createSnapshot(vcenter_id, vm_name, snap_name, description="", memory=false) {
  return _post("/api/vmware/snapshot", { vcenter_id, vm_name, snap_name, description, memory });
}
export async function deleteSnapshot(vcenter_id, vm_name, snap_name) {
  return _post("/api/vmware/snapshot/delete", { vcenter_id, vm_name, snap_name });
}
export async function cloneVM(vcenter_id, vm_name, clone_name, dest_host, dest_datastore, dest_vcenter_id, power_on=false) {
  return _post("/api/vmware/clone", { vcenter_id, vm_name, clone_name, dest_host, dest_datastore, dest_vcenter_id, power_on });
}
export async function migrateVM(vcenter_id, vm_name, dest_host, dest_datastore, dest_vcenter_id) {
  return _post("/api/vmware/migrate", { vcenter_id, vm_name, dest_host, dest_datastore, dest_vcenter_id });
}
export async function reconfigVM(vcenter_id, vm_name, cpu, ram_gb, disk_gb) {
  return _post("/api/vmware/reconfig", { vcenter_id, vm_name, cpu, ram_gb, disk_gb });
}
export async function bulkVMAction(vms, action) {
  return _post("/api/vmware/bulk-power", { vms, action });
}
export async function hostAction(vcenter_id, host_name, action) {
  return _post("/api/vmware/host-action", { vcenter_id, host_name, action });
}
export async function bulkHostAction(hosts, action) {
  return _post("/api/vmware/bulk-host-action", { hosts, action });
}

// â”€â”€ VM Requests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function submitVMRequest(data)  { return _post("/api/requests", data); }
export async function fetchRequests()        { const d = await _get("/api/requests");         return d.requests; }
export async function fetchPendingRequests() { const d = await _get("/api/requests/pending"); return d.requests; }
export async function reviewRequest(req_number, decision, admin_notes="", overrides={}) {
  return _post(`/api/requests/${req_number}/review`, { decision, admin_notes, overrides });
}

// â”€â”€ Users â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchUsers()               { const d = await _get("/api/users"); return d.users; }
export async function updateUserRole(username, role) { return _patch(`/api/users/${username}/role`, { role }); }
export async function deleteUser(username) {
  const res = await fetch(`${BASE}/api/users/${encodeURIComponent(username)}`, { method:"DELETE", headers: authHeader() });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||`API error ${res.status}`); }
  return res.json();
}
export async function searchADUsers(q)           { const d = await _get(`/api/users/search?q=${encodeURIComponent(q)}`); return d.users||[]; }

// â”€â”€ Audit Log â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchAuditLog(limit=200)   { const d = await _get(`/api/audit?limit=${limit}`); return d.logs; }
export async function fetchMyAudit()             { const d = await _get("/api/audit/me");              return d.logs; }

// â”€â”€ CSV Export â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export function downloadCSV(type, vcenter_id) {
  if (!_token) return;
  fetch(`${BASE}/api/export/${type}${qs(vcenter_id)}`, { headers: { Authorization: `Bearer ${_token}` } })
    .then(r => r.blob())
    .then(blob => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = `${type}_export.csv`; a.click();
      URL.revokeObjectURL(a.href);
    });
}

// â”€â”€ vCenter Management (Admin only) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function addVCenter(data)    { return _post("/api/admin/vcenters", data); }
export async function deleteVCenter(id)  { return _post("/api/admin/vcenters/delete", { vcenter_id: id }); }
export async function testVCenter(data)  { return _post("/api/admin/vcenters/test", data); }

// â”€â”€ VM Delete from disk (Admin only) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function deleteVMFromDisk(vcenter_id, vm_name) {
  return _post("/api/vmware/delete", { vcenter_id, vm_name });
}

// â”€â”€ VM Snapshots for single VM â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchVMSnapshots(vcenter_id, vm_name) {
  return _get(`/api/vmware/vm-snapshots?vcenter_id=${encodeURIComponent(vcenter_id)}&vm_name=${encodeURIComponent(vm_name)}`);
}

// â”€â”€ Pricing Config (Admin only) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchPricing()          { return _get("/api/admin/pricing"); }
export async function savePricing(data)       { return _post("/api/admin/pricing", data); }

// â”€â”€ Internet VM Config (Admin only) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// fetchInternetConfig â€” get current internet VM mode/excluded/extra config
export async function fetchInternetConfig()   { return _get("/api/admin/internet-vms"); }
// toggleInternetVM â€” admin: enable/disable internet charge for a specific VM
export async function toggleInternetVM(vm_name, enabled) { return _post("/api/admin/internet-vms/toggle", {vm_name, enabled}); }

// â”€â”€ vCenter .env reload â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function reloadVCenters()        { return _post("/api/admin/vcenters/reload", {}); }


// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// ADD THESE EXPORTS TO THE BOTTOM OF api.js
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

// â”€â”€ OpenShift â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchOCPClusters()               { const d = await _get("/api/openshift/clusters");          return d.clusters; }
export async function fetchOCPCluster(id)              { return _get(`/api/openshift/clusters/${id}`); }
export async function createOCPCluster(data)           { return _post("/api/openshift/clusters", data); }
export async function updateOCPCluster(id, data)       { return _patch(`/api/openshift/clusters/${id}`, data); }
export async function deleteOCPCluster(id)             {
  const res = await fetch(`${BASE}/api/openshift/clusters/${id}`, { method:"DELETE", headers: authHeader() });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||`API error ${res.status}`); }
  return res.json();
}
export async function testOCPCluster(id)               { return _post(`/api/openshift/clusters/${id}/test`, {}); }
export async function fetchOCPOverview(id)             { return _get(`/api/openshift/clusters/${id}/overview`); }
export async function fetchOCPLiveNodes(id)            { const d = await _get(`/api/openshift/clusters/${id}/live/nodes`);      return d.nodes; }
export async function fetchOCPPods(id, namespace="")   { const qs = namespace ? `?namespace=${encodeURIComponent(namespace)}` : ""; const d = await _get(`/api/openshift/clusters/${id}/live/pods${qs}`); return d.pods; }
export async function fetchOCPNamespaces(id)           { const d = await _get(`/api/openshift/clusters/${id}/live/namespaces`); return d.namespaces; }
export async function fetchOCPOperators(id)            { const d = await _get(`/api/openshift/clusters/${id}/live/operators`);  return d.operators; }
export async function fetchOCPEvents(id)               { const d = await _get(`/api/openshift/clusters/${id}/live/events`);    return d.events; }
export async function ocpNodeAction(cluster_id, node_name, action) {
  return _post(`/api/openshift/clusters/${cluster_id}/nodes/${node_name}/action`, { action });
}
export async function fetchOCPPodDetail(cluster_id, namespace, pod_name) {
  return _get(`/api/openshift/clusters/${cluster_id}/live/pods/${encodeURIComponent(namespace)}/${encodeURIComponent(pod_name)}/detail`);
}
export async function fetchOCPPodLogs(cluster_id, namespace, pod_name, container="", tail=200) {
  const qs = new URLSearchParams({tail});
  if (container) qs.set("container", container);
  return _get(`/api/openshift/clusters/${cluster_id}/live/pods/${encodeURIComponent(namespace)}/${encodeURIComponent(pod_name)}/logs?${qs}`);
}
export async function fetchOCPNamespaceDetail(cluster_id, ns_name) {
  return _get(`/api/openshift/clusters/${cluster_id}/live/namespaces/${encodeURIComponent(ns_name)}/detail`);
}
export async function fetchOCPRoutes(id) {
  const d = await _get(`/api/openshift/clusters/${id}/live/routes`);
  return d.routes || [];
}
export async function fetchOCPStorageClasses(cluster_id) {
  const d = await _get(`/api/openshift/clusters/${cluster_id}/live/storageclasses`);
  return d.storage_classes;
}
export async function fetchOCPPVs(cluster_id) {
  const d = await _get(`/api/openshift/clusters/${cluster_id}/live/pvs`);
  return d.pvs || [];
}
export async function fetchOCPPVCs(cluster_id) {
  const d = await _get(`/api/openshift/clusters/${cluster_id}/live/pvcs`);
  return d.pvcs || [];
}
export async function fetchOCPDescribeSC(cluster_id, name) {
  return _get(`/api/openshift/clusters/${cluster_id}/live/storageclasses/${encodeURIComponent(name)}/describe`);
}
export async function fetchOCPDescribePV(cluster_id, name) {
  return _get(`/api/openshift/clusters/${cluster_id}/live/pvs/${encodeURIComponent(name)}/describe`);
}
export async function fetchOCPDescribePVC(cluster_id, namespace, name) {
  return _get(`/api/openshift/clusters/${cluster_id}/live/pvcs/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}/describe`);
}
export async function fetchOCPPVEvents(cluster_id, name) {
  const d = await _get(`/api/openshift/clusters/${cluster_id}/live/pvs/${encodeURIComponent(name)}/events`);
  return d.events || [];
}
export async function fetchOCPPVCEvents(cluster_id, namespace, name) {
  const d = await _get(`/api/openshift/clusters/${cluster_id}/live/pvcs/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}/events`);
  return d.events || [];
}
export async function deleteOCPSC(cluster_id, name) {
  const res = await fetch(`${BASE}/api/openshift/clusters/${cluster_id}/live/storageclasses/${encodeURIComponent(name)}`,
    { method: "DELETE", headers: authHeader() });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||`API error ${res.status}`); }
  return res.json();
}
export async function deleteOCPPV(cluster_id, name) {
  const res = await fetch(`${BASE}/api/openshift/clusters/${cluster_id}/live/pvs/${encodeURIComponent(name)}`,
    { method: "DELETE", headers: authHeader() });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||`API error ${res.status}`); }
  return res.json();
}
export async function deleteOCPPVC(cluster_id, namespace, name) {
  const res = await fetch(`${BASE}/api/openshift/clusters/${cluster_id}/live/pvcs/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}`,
    { method: "DELETE", headers: authHeader() });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||`API error ${res.status}`); }
  return res.json();
}
export async function createOCPPVC(cluster_id, data) {
  return _post(`/api/openshift/clusters/${cluster_id}/live/pvcs`, data);
}

// â”€â”€ OCP Workloads â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchOCPDeployments(cluster_id) {
  const d = await _get(`/api/openshift/clusters/${cluster_id}/live/workloads/deployments`);
  return d.items || [];
}
export async function fetchOCPDeploymentConfigs(cluster_id) {
  const d = await _get(`/api/openshift/clusters/${cluster_id}/live/workloads/deploymentconfigs`);
  return d.items || [];
}
export async function fetchOCPStatefulSets(cluster_id) {
  const d = await _get(`/api/openshift/clusters/${cluster_id}/live/workloads/statefulsets`);
  return d.items || [];
}
export async function fetchOCPDaemonSets(cluster_id) {
  const d = await _get(`/api/openshift/clusters/${cluster_id}/live/workloads/daemonsets`);
  return d.items || [];
}
export async function fetchOCPReplicaSets(cluster_id) {
  const d = await _get(`/api/openshift/clusters/${cluster_id}/live/workloads/replicasets`);
  return d.items || [];
}
export async function fetchOCPSecrets(cluster_id) {
  const d = await _get(`/api/openshift/clusters/${cluster_id}/live/workloads/secrets`);
  return d.items || [];
}
export async function fetchOCPConfigMaps(cluster_id) {
  const d = await _get(`/api/openshift/clusters/${cluster_id}/live/workloads/configmaps`);
  return d.items || [];
}
export async function fetchOCPWorkloadDescribe(cluster_id, kind, namespace, name) {
  return _get(`/api/openshift/clusters/${cluster_id}/live/workloads/${encodeURIComponent(kind)}/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}/describe`);
}
export async function deleteOCPWorkload(cluster_id, kind, namespace, name) {
  const res = await fetch(`${BASE}/api/openshift/clusters/${cluster_id}/live/workloads/${encodeURIComponent(kind)}/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}`,
    { method: "DELETE", headers: authHeader() });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||`API error ${res.status}`); }
  return res.json();
}
export async function fetchOCPWorkloadLogs(cluster_id, kind, namespace, name) {
  return _get(`/api/openshift/clusters/${cluster_id}/live/workloads/${encodeURIComponent(kind)}/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}/logs`);
}

// â”€â”€ OCP VM Requests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function createOCPVMRequest(data)         { return _post("/api/openshift/vm-requests", data); }
export async function fetchOCPVMRequests()             { const d = await _get("/api/openshift/vm-requests"); return d.requests; }
export async function fetchOCPVMRequest(id)            { return _get(`/api/openshift/vm-requests/${id}`); }
export async function reviewOCPVMRequest(id, data)     { return _patch(`/api/openshift/vm-requests/${id}/review`, data); }

// â”€â”€ Baremetal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchBMServers()                 { const d = await _get("/api/baremetal/servers");           return d.servers; }
export async function fetchBMServer(id)                { return _get(`/api/baremetal/servers/${id}`); }
export async function addBMServer(data)                { return _post("/api/baremetal/servers", data); }
export async function updateBMServer(id, data)         { return _patch(`/api/baremetal/servers/${id}`, data); }
export async function deleteBMServer(id) {
  const res = await fetch(`${BASE}/api/baremetal/servers/${id}`, { method:"DELETE", headers: authHeader() });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||`API error ${res.status}`); }
  return res.json();
}
export async function fetchBMPowerState(id)            { return _get(`/api/baremetal/servers/${id}/power`); }
export async function bmAction(id, action)             { return _post(`/api/baremetal/servers/${id}/action`, { action }); }
export async function fetchBMServerInfo(id)            { return _get(`/api/baremetal/servers/${id}/info`); }
export async function fetchBMEventLog(id, limit=20)    { return _get(`/api/baremetal/servers/${id}/logs?limit=${limit}`); }
export async function testBMConnection(data)           { return _post("/api/baremetal/test", data); }

// â”€â”€ Notifications â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchNotifications()             { const d = await _get("/api/notifications"); return d.notifications || []; }
export async function saveNotifications(notifs)        { return _post("/api/notifications", { notifications: notifs }); }

// â”€â”€ Local & AD User Management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function createLocalUser(data)            { return _post("/api/users/local", data); }
export async function addADUser(data)                  { return _post("/api/users/ad", data); }

// â”€â”€ Topology â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchVMTopology(vcenter_id, vm_name) {
  return _get(`/api/vmware/topology/vm?vcenter_id=${encodeURIComponent(vcenter_id)}&vm_name=${encodeURIComponent(vm_name)}`);
}
export async function fetchHostTopology(vcenter_id, host_name) {
  return _get(`/api/vmware/topology/host?vcenter_id=${encodeURIComponent(vcenter_id)}&host_name=${encodeURIComponent(host_name)}`);
}
// â”€â”€ IPAM â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchIPAMSubnets() {
  return _get("/api/ipam/subnets");
}
export async function refreshIPAMCache() {
  return _post("/api/ipam/refresh", {});
}
export async function fetchIPAMSubnetIPs(subnet_id) {
  return _get(`/api/ipam/subnet/${subnet_id}/ips`);
}
export async function addIPAMManualSubnet(data) {
  return _post("/api/ipam/manual", data);
}
export async function editIPAMManualSubnet(subnet_id, data) {
  return _put(`/api/ipam/manual/${subnet_id}`, data);
}
export async function deleteIPAMManualSubnet(subnet_id) {
  return _delete(`/api/ipam/manual/${subnet_id}`);
}
// â”€â”€ Asset Management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchAssetInventory(site="dc") {
  return _get(`/api/assets/inventory?site=${site}`);
}
export async function pingAssets(ips) {
  return _post("/api/assets/ping", { ips });
}
export async function assetPowerAction(payload) {
  return _post("/api/assets/action", payload);
}
export async function addAssetRow(site, sheet_name, asset) {
  return _post("/api/assets/row", { site, sheet_name, asset });
}
export async function updateAssetRow(site, sheet_name, asset) {
  const res = await fetch(`${BASE}/api/assets/row`, { method:"PUT", headers: authHeader(), body: JSON.stringify({ site, sheet_name, asset }) });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||`API error ${res.status}`); }
  return res.json();
}
export async function deleteAssetRow(site, sheet_name, asset_id) {
  const res = await fetch(`${BASE}/api/assets/row`, { method:"DELETE", headers: authHeader(), body: JSON.stringify({ site, sheet_name, asset_id }) });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||`API error ${res.status}`); }
  return res.json();
}
export async function fetchAssetEol(site="dc") {
  return _get(`/api/assets/eol?site=${site}`);
}

// â”€â”€ AD & DNS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function adListUsers(q="")           { return _get(`/api/ad/users?q=${encodeURIComponent(q)}`); }
export async function adCreateUser(payload)        { return _post("/api/ad/users", payload); }
export async function adSetEnabled(dn, enabled)    { return _post("/api/ad/users/enable", { dn, enabled }); }
export async function adResetPassword(dn, password){ return _post("/api/ad/users/reset-password", { dn, password }); }
export async function adUnlockUser(dn)             { return _post("/api/ad/users/unlock", { dn }); }
export async function adDeleteUser(dn) {
  const res = await fetch(`${BASE}/api/ad/users`, { method:"DELETE", headers: authHeader(), body: JSON.stringify({ dn }) });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||`API error ${res.status}`); }
  return res.json();
}
export async function adListGroups(q="")           { return _get(`/api/ad/groups?q=${encodeURIComponent(q)}`); }
export async function adCreateGroup(payload)       { return _post("/api/ad/groups", payload); }
export async function adGroupMember(group_dn, user_dn, add) { return _post("/api/ad/groups/member", { group_dn, user_dn, add }); }
export async function adDeleteGroup(dn) {
  const res = await fetch(`${BASE}/api/ad/groups`, { method:"DELETE", headers: authHeader(), body: JSON.stringify({ dn }) });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||`API error ${res.status}`); }
  return res.json();
}
export async function adListOUs()                  { return _get("/api/ad/ous"); }
export async function adListComputers(q="")        { return _get(`/api/ad/computers?q=${encodeURIComponent(q)}`); }
export async function dnsListZones()               { return _get("/api/dns/zones"); }
export async function dnsListRecords(zone)         { return _get(`/api/dns/records?zone=${encodeURIComponent(zone)}`); }
export async function dnsAddRecord(payload)        { return _post("/api/dns/records", payload); }
export async function dnsDeleteRecord(zone, hostname, rtype) {
  const res = await fetch(`${BASE}/api/dns/records`, { method:"DELETE", headers: authHeader(), body: JSON.stringify({ zone, hostname, rtype }) });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||`API error ${res.status}`); }
  return res.json();
}
export async function dnsFlushCache()              { return _post("/api/dns/flush-cache", {}); }

// â”€â”€ Nutanix â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchNutanixPCs()            { const d=await _get("/api/nutanix/prism_centrals"); return d.prism_centrals; }
export async function createNutanixPC(body)         { return _post("/api/nutanix/prism_centrals", body); }
export async function updateNutanixPC(id, body)     { return _patch(`/api/nutanix/prism_centrals/${id}`, body); }
export async function deleteNutanixPC(id)           { return _delete(`/api/nutanix/prism_centrals/${id}`); }
export async function testNutanixPC(id)             { return _post(`/api/nutanix/prism_centrals/${id}/test`, {}); }
export async function fetchNutanixOverview(id)      { return _get(`/api/nutanix/prism_centrals/${id}/live/overview`); }
export async function fetchNutanixClusters(id)      { const d=await _get(`/api/nutanix/prism_centrals/${id}/live/clusters`); return d.clusters; }
export async function fetchNutanixVMs(id)           { const d=await _get(`/api/nutanix/prism_centrals/${id}/live/vms`); return d.vms; }
export async function fetchNutanixHosts(id)         { const d=await _get(`/api/nutanix/prism_centrals/${id}/live/hosts`); return d.hosts; }
export async function fetchNutanixStorage(id)       { const d=await _get(`/api/nutanix/prism_centrals/${id}/live/storage`); return d.containers; }
export async function fetchNutanixAlerts(id)        { const d=await _get(`/api/nutanix/prism_centrals/${id}/live/alerts`); return d.alerts; }
export async function fetchNutanixNetworks(id)      { const d=await _get(`/api/nutanix/prism_centrals/${id}/live/networks`); return d.networks; }
export async function nutanixVMPower(id, vmUuid, action) { return _post(`/api/nutanix/prism_centrals/${id}/vms/${vmUuid}/power`, { action }); }
export async function nutanixVMSnapshot(id, vmUuid, name){ return _post(`/api/nutanix/prism_centrals/${id}/vms/${vmUuid}/snapshot`, { name }); }
export async function fetchNutanixImages(id)        { const d=await _get(`/api/nutanix/prism_centrals/${id}/live/images`); return d.images||[]; }
export async function submitNutanixVMRequest(body)  { return _post("/api/nutanix/vm_requests", body); }

// â”€â”€ Ansible Automation Platform (AAP) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const AAP = (id) => `/api/ansible/instances/${id}`;

export async function fetchAAPInstances()           { const d=await _get("/api/ansible/instances"); return d.instances||[]; }
export async function createAAPInstance(body)       { return _post("/api/ansible/instances", body); }
export async function updateAAPInstance(id, body)   { return _patch(`${AAP(id)}`, body); }
export async function deleteAAPInstance(id)         { return _delete(`${AAP(id)}`); }
export async function testAAPInstance(id)           { return _post(`${AAP(id)}/test`, {}); }

export async function fetchAAPDashboard(id)         { return _get(`${AAP(id)}/live/dashboard`); }
export async function fetchAAPJobs(id, limit=100)   { const d=await _get(`${AAP(id)}/live/jobs?limit=${limit}`); return d.jobs||[]; }
export async function fetchAAPJobOutput(id, jobId)  { const d=await _get(`${AAP(id)}/live/jobs/${jobId}/output`); return d.output||""; }
export async function fetchAAPTemplates(id)         { const d=await _get(`${AAP(id)}/live/job_templates`); return d.job_templates||[]; }
export async function fetchAAPInventories(id)       { const d=await _get(`${AAP(id)}/live/inventories`); return d.inventories||[]; }
export async function fetchAAPProjects(id)          { const d=await _get(`${AAP(id)}/live/projects`); return d.projects||[]; }
export async function fetchAAPHosts(id)             { const d=await _get(`${AAP(id)}/live/hosts`); return d.hosts||[]; }
export async function fetchAAPCredentials(id)       { const d=await _get(`${AAP(id)}/live/credentials`); return d.credentials||[]; }
export async function fetchAAPOrganizations(id)     { const d=await _get(`${AAP(id)}/live/organizations`); return d.organizations||[]; }
export async function fetchAAPUsers(id)             { const d=await _get(`${AAP(id)}/live/users`); return d.users||[]; }
export async function fetchAAPTeams(id)             { const d=await _get(`${AAP(id)}/live/teams`); return d.teams||[]; }
export async function fetchAAPSchedules(id)         { const d=await _get(`${AAP(id)}/live/schedules`); return d.schedules||[]; }
export async function fetchAAPExecutionEnvironments(id) { const d=await _get(`${AAP(id)}/live/execution_environments`); return d.execution_environments||[]; }
export async function fetchAAPProjectLocalPaths(id)     { const d=await _get(`${AAP(id)}/live/project_local_paths`); return d.paths||[]; }

export async function launchAAPTemplate(id, templateId, extra_vars="") {
  return _post(`${AAP(id)}/live/job_templates/${templateId}/launch`, { extra_vars });
}
export async function cancelAAPJob(id, jobId) {
  return _post(`${AAP(id)}/live/jobs/${jobId}/cancel`, {});
}
export async function deleteAAPJob(id, jobId) {
  return _delete(`${AAP(id)}/live/jobs/${jobId}`);
}
export async function deleteAAPTemplate(id, templateId) {
  return _delete(`${AAP(id)}/live/job_templates/${templateId}`);
}
export async function syncAAPInventory(id, invId) {
  return _post(`${AAP(id)}/live/inventories/${invId}/sync`, {});
}
export async function deleteAAPInventory(id, invId) {
  return _delete(`${AAP(id)}/live/inventories/${invId}`);
}
export async function syncAAPProject(id, projId) {
  return _post(`${AAP(id)}/live/projects/${projId}/sync`, {});
}
export async function deleteAAPProject(id, projId) {
  return _delete(`${AAP(id)}/live/projects/${projId}`);
}
export async function toggleAAPHost(id, hostId, enabled) {
  return _patch(`${AAP(id)}/live/hosts/${hostId}/toggle`, { enabled });
}
export async function deleteAAPHost(id, hostId) {
  return _delete(`${AAP(id)}/live/hosts/${hostId}`);
}
export async function deleteAAPCredential(id, credId) {
  return _delete(`${AAP(id)}/live/credentials/${credId}`);
}
export async function toggleAAPSchedule(id, schedId, enabled) {
  return _patch(`${AAP(id)}/live/schedules/${schedId}/toggle`, { enabled });
}
export async function deleteAAPSchedule(id, schedId) {
  return _delete(`${AAP(id)}/live/schedules/${schedId}`);
}
export async function createAAPUser(id, body) {
  return _post(`${AAP(id)}/live/users`, body);
}
export async function deleteAAPUser(id, userId) {
  return _delete(`${AAP(id)}/live/users/${userId}`);
}

// â”€â”€ AAP resource create / update â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function createAAPTemplate(id, body)           { return _post(`${AAP(id)}/live/job_templates`, body); }
export async function updateAAPTemplate(id, tplId, body)    { return _patch(`${AAP(id)}/live/job_templates/${tplId}`, body); }
export async function createAAPInventory(id, body)          { return _post(`${AAP(id)}/live/inventories`, body); }
export async function updateAAPInventory(id, invId, body)   { return _patch(`${AAP(id)}/live/inventories/${invId}`, body); }
export async function createAAPProject(id, body)            { return _post(`${AAP(id)}/live/projects`, body); }
export async function updateAAPProject(id, projId, body)    { return _patch(`${AAP(id)}/live/projects/${projId}`, body); }
export async function createAAPCredential(id, body)         { return _post(`${AAP(id)}/live/credentials`, body); }
export async function updateAAPCredential(id, credId, body) { return _patch(`${AAP(id)}/live/credentials/${credId}`, body); }

// â”€â”€ AAP Workflow Job Templates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchAAPWorkflows(id)                         { return _get(`${AAP(id)}/live/workflow_job_templates`); }
export async function createAAPWorkflow(id, body)                   { return _post(`${AAP(id)}/live/workflow_job_templates`, body); }
export async function updateAAPWorkflow(id, wfId, body)             { return _patch(`${AAP(id)}/live/workflow_job_templates/${wfId}`, body); }
export async function deleteAAPWorkflow(id, wfId)                   { return _delete(`${AAP(id)}/live/workflow_job_templates/${wfId}`); }
export async function launchAAPWorkflow(id, wfId)                   { return _post(`${AAP(id)}/live/workflow_job_templates/${wfId}/launch`, {}); }

// â”€â”€ Storage Arrays â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchStorageArrays()           { return _get("/api/storage/arrays"); }
export async function testStorageConnection(body)    { return _post("/api/storage/test", body); }
export async function createStorageArray(body)       { return _post("/api/storage/arrays", body); }
export async function deleteStorageArray(id)         { return _delete(`/api/storage/arrays/${id}`); }
export async function updateStorageConsoleUrl(id, url)  { return _patch(`/api/storage/arrays/${id}/console_url`, {console_url: url}); }

export async function fetchStorageArrayData(id)      { return _get(`/api/storage/arrays/${id}/data`); }
export async function fetchStorageTopology(id, volume) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 125000); // 125s: array(~17s) + parallel vCenter scan(~15s) + margin
  try {
    const res = await fetch(`${BASE}/api/storage/arrays/${id}/topology?volume=${encodeURIComponent(volume)}`, {
      headers: authHeader(),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (res.status === 401) { clearSession(); throw new Error("Session expired"); }
    if (res.status === 403) throw new Error("Permission denied");
    if (res.status === 504) throw new Error("Topology timed out â€” the storage array took too long to respond. Please try again.");
    if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail || `Error ${res.status}`); }
    return res.json();
  } catch (e) {
    clearTimeout(timer);
    if (e.name === 'AbortError') throw new Error("Topology is taking longer than expected. The array data may be loading â€” please wait a moment and try again.");
    throw e;
  }
}
// NetApp admin
const _NA = (id) => `/api/storage/arrays/${id}/netapp`;
export async function fetchNetAppSvms(id)                             { return _get(`${_NA(id)}/svms`); }
export async function fetchNetAppAggregates(id)                       { return _get(`${_NA(id)}/aggregates`); }
export async function createNetAppVolume(id, body)                    { return _post(`${_NA(id)}/volumes`, body); }
export async function deleteNetAppVolume(id, vuuid)                   { return _delete(`${_NA(id)}/volumes/${vuuid}`); }
export async function fetchNetAppSnapshots(id, vuuid)                 { return _get(`${_NA(id)}/volumes/${vuuid}/snapshots`); }
export async function createNetAppSnapshot(id, vuuid, body)           { return _post(`${_NA(id)}/volumes/${vuuid}/snapshots`, body); }
export async function deleteNetAppSnapshot(id, vuuid, suuid)          { return _delete(`${_NA(id)}/volumes/${vuuid}/snapshots/${suuid}`); }
export async function createNetAppIgroup(id, body)                    { return _post(`${_NA(id)}/igroups`, body); }
export async function deleteNetAppIgroup(id, iguuid)                  { return _delete(`${_NA(id)}/igroups/${iguuid}`); }
export async function createNetAppLun(id, body)                       { return _post(`${_NA(id)}/luns`, body); }
export async function deleteNetAppLun(id, luuid)                      { return _delete(`${_NA(id)}/luns/${luuid}`); }

// â”€â”€ Rubrik Security Cloud â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchRubrikConnections()           { return _get("/api/rubrik/connections"); }
export async function testRubrikConnection(body)         { return _post("/api/rubrik/test", body); }
export async function createRubrikConnection(body)       { return _post("/api/rubrik/connections", body); }
export async function deleteRubrikConnection(id)         { return _delete(`/api/rubrik/connections/${id}`); }
export async function fetchRubrikData(id)                { return _get(`/api/rubrik/connections/${id}/data`); }
// Rubrik Management
export async function rubrikSnapshot(id,body)            { return _post(`/api/rubrik/connections/${id}/snapshot`, body); }
export async function rubrikBulkSnapshot(id,body)        { return _post(`/api/rubrik/connections/${id}/bulk-snapshot`, body); }
export async function rubrikAssignSla(id,body)           { return _post(`/api/rubrik/connections/${id}/assign-sla`, body); }
export async function rubrikUnassignSla(id,body)         { return _post(`/api/rubrik/connections/${id}/unassign-sla`, body); }
export async function rubrikLiveMount(id,body)           { return _post(`/api/rubrik/connections/${id}/live-mount`, body); }
export async function rubrikExportVm(id,body)            { return _post(`/api/rubrik/connections/${id}/export-vm`, body); }
export async function rubrikInstantRecovery(id,body)     { return _post(`/api/rubrik/connections/${id}/instant-recovery`, body); }
export async function rubrikFileRecovery(id,body)        { return _post(`/api/rubrik/connections/${id}/file-recovery`, body); }
export async function rubrikDownloadFiles(id,body)       { return _post(`/api/rubrik/connections/${id}/download-files`, body); }
export async function rubrikDeleteSnapshot(id,body)      { return _post(`/api/rubrik/connections/${id}/delete-snapshot`, body); }
export async function rubrikPauseSla(id,body)            { return _post(`/api/rubrik/connections/${id}/pause-sla`, body); }
export async function rubrikPauseCluster(id,body)        { return _post(`/api/rubrik/connections/${id}/pause-cluster`, body); }
export async function rubrikVmSnapshots(id,vmId)         { return _get(`/api/rubrik/connections/${id}/vms/${vmId}/snapshots`); }
export async function rubrikRetryJob(id,body)            { return _post(`/api/rubrik/connections/${id}/retry-job`, body); }
export async function rubrikSearchVms(id,q)              { return _get(`/api/rubrik/connections/${id}/search-vms?q=${encodeURIComponent(q)}`); }

// â”€â”€ Cohesity DataProtect â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchCohesityConnections()           { return _get("/api/cohesity/connections"); }
export async function testCohesityConnection(body)         { return _post("/api/cohesity/test", body); }
export async function createCohesityConnection(body)       { return _post("/api/cohesity/connections", body); }
export async function deleteCohesityConnection(id)         { return _delete(`/api/cohesity/connections/${id}`); }
export async function fetchCohesityData(id)                { return _get(`/api/cohesity/connections/${id}/data`); }
// Cohesity Management
export async function cohesityRunJob(id,body)              { return _post(`/api/cohesity/connections/${id}/run-job`, body); }
export async function cohesityCancelRun(id,body)           { return _post(`/api/cohesity/connections/${id}/cancel-run`, body); }
export async function cohesityPauseJob(id,body)            { return _post(`/api/cohesity/connections/${id}/pause-job`, body); }
export async function cohesityDeleteJob(id,body)           { return _post(`/api/cohesity/connections/${id}/delete-job`, body); }
export async function cohesityUpdateJob(id,body)           { return _post(`/api/cohesity/connections/${id}/update-job`, body); }
export async function cohesityCreateJob(id,body)           { return _post(`/api/cohesity/connections/${id}/create-job`, body); }
export async function cohesityResolveAlert(id,body)        { return _post(`/api/cohesity/connections/${id}/resolve-alert`, body); }
export async function cohesityJobRuns(id,jobId)            { return _get(`/api/cohesity/connections/${id}/job-runs/${jobId}`); }
export async function cohesityRecover(id,body)             { return _post(`/api/cohesity/connections/${id}/recover`, body); }
export async function cohesitySearchObjects(id,q,env)      { return _get(`/api/cohesity/connections/${id}/search-objects?q=${encodeURIComponent(q||"*")}${env?"&env="+encodeURIComponent(env):""}`); }
export async function cohesityObjectSnapshots(id,objId)    { return _get(`/api/cohesity/connections/${id}/object-snapshots/${objId}`); }
export async function cohesityAssignPolicy(id,body)        { return _post(`/api/cohesity/connections/${id}/assign-policy`, body); }
export async function cohesitySources(id,env)              { return _get(`/api/cohesity/connections/${id}/sources${env?"?env="+encodeURIComponent(env):""}`); }

// â”€â”€ Veeam Backup & Replication â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchVeeamConnections()              { return _get("/api/veeam/connections"); }
export async function testVeeamConnection(body)            { return _post("/api/veeam/test", body); }
export async function createVeeamConnection(body)          { return _post("/api/veeam/connections", body); }
export async function deleteVeeamConnection(id)            { return _del(`/api/veeam/connections/${id}`); }
export async function fetchVeeamData(id)                   { return _get(`/api/veeam/connections/${id}/data`); }
// Veeam Management
export async function veeamStartJob(id,body)               { return _post(`/api/veeam/connections/${id}/start-job`, body); }
export async function veeamStopJob(id,body)                { return _post(`/api/veeam/connections/${id}/stop-job`, body); }
export async function veeamEnableJob(id,body)              { return _post(`/api/veeam/connections/${id}/enable-job`, body); }
export async function veeamDisableJob(id,body)             { return _post(`/api/veeam/connections/${id}/disable-job`, body); }
export async function veeamDeleteJob(id,body)              { return _post(`/api/veeam/connections/${id}/delete-job`, body); }
export async function veeamJobSessions(id,jobId)           { return _get(`/api/veeam/connections/${id}/job-sessions/${jobId}`); }
export async function veeamRetrySession(id,body)           { return _post(`/api/veeam/connections/${id}/retry-session`, body); }
export async function veeamStopSession(id,body)            { return _post(`/api/veeam/connections/${id}/stop-session`, body); }
export async function veeamInstantRecovery(id,body)        { return _post(`/api/veeam/connections/${id}/instant-recovery`, body); }
export async function veeamSearchObjects(id,q)             { return _get(`/api/veeam/connections/${id}/search?q=${encodeURIComponent(q||"")}`); }

// â”€â”€ RVTools â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchRVToolsStatus()               { return _get("/api/rvtools/status"); }
export async function fetchRVToolsReports()              { return _get("/api/rvtools/reports"); }
export async function fetchRVToolsScan()                 { return _get("/api/rvtools/scan"); }
export async function fetchRVToolsVMs(file)              { return _post("/api/rvtools/vms", { file }); }
export async function runRVToolsForVCenter(vcenter_id)   { return _post("/api/rvtools/run", { vcenter_id }); }
export async function runRVToolsAll()                    { return _post("/api/rvtools/run-all", {}); }
export async function installRVTools()                   { return _post("/api/rvtools/install", {}); }

// â”€â”€ AWS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchAWSStatus()                   { return _get("/api/aws/status"); }
export async function saveAWSCredentials(data)           { return _post("/api/aws/credentials", data); }
// Front-end discovery cache â€” 20 min TTL matching SSO credential lifetime
const _AWS_CACHE_TTL_MS = 20 * 60 * 1000;
let _awsDiscCache = null; // { ts, data }

export function invalidateAWSCache() { _awsDiscCache = null; }
export function getAWSCachedDiscovery() {
  if (!_awsDiscCache) return null;
  if (Date.now() - _awsDiscCache.ts > _AWS_CACHE_TTL_MS) { _awsDiscCache = null; return null; }
  return _awsDiscCache.data;
}

export async function fetchAWSDiscovery(region, force) {
  if (!force && _awsDiscCache && (Date.now() - _awsDiscCache.ts < _AWS_CACHE_TTL_MS)) {
    return { ..._awsDiscCache.data, _fromCache: true };
  }
  const data = await _post("/api/aws/discover", { region: region||"", force: !!force });
  if (data && !data.error) { _awsDiscCache = { ts: Date.now(), data }; }
  return data;
}
export async function fetchAWSEC2(region)                { return _post("/api/aws/ec2", { region: region||"" }); }
export async function fetchAWSS3()                       { return _get("/api/aws/s3"); }
export async function fetchAWSRDS(region)                { return _post("/api/aws/rds", { region: region||"" }); }
export async function fetchAWSCosts()                    { return _get("/api/aws/costs"); }
export async function awsEC2Action(instance_id, action, region) { return _post("/api/aws/ec2/action", { instance_id, action, region: region||"" }); }
export async function fetchAWSSubnets(region)            { return _post("/api/aws/subnets", { region: region||"" }); }

// â”€â”€ AWS SSO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchAWSSSOStatus()                { return _get("/api/aws/sso/status"); }
export async function initAWSSSO(data)                   { return _post("/api/aws/sso/init", data); }
export async function pollAWSSSO()                       { return _post("/api/aws/sso/poll", {}); }
export async function refreshAWSSSO()                    { return _post("/api/aws/sso/refresh", {}); }
export async function collectAWSSnapshot()               { return _post("/api/history/collect_aws",  {}); }
export async function collectIPAMSnapshot()              { return _post("/api/history/collect_ipam", {}); }

// â”€â”€ Live data version check (no auth needed) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchDataVersion() {
  const base = window.location.protocol === "https:"
    ? `${window.location.protocol}//${window.location.hostname}`
    : `http://${window.location.hostname}:8000`;
  const res = await fetch(`${base}/api/data/version`);
  return res.ok ? res.json() : null;
}

// â”€â”€ Microsoft Hyper-V â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function fetchHVHosts()                          { return _get("/api/hyperv/hosts"); }
export async function saveHVHosts(hosts)                      { return _post("/api/hyperv/hosts", { hosts }); }
export async function fetchHVStatus()                         { return _get("/api/hyperv/status"); }
export async function fetchHVVMs(host_id)                     { return _get(`/api/hyperv/vms${host_id ? "?host_id=" + encodeURIComponent(host_id) : ""}`); }
export async function hvVMAction(host_id, vm_name, action)    { return _post("/api/hyperv/vm/action", { host_id, vm_name, action }); }
export async function fetchHVCheckpoints(host_id, vm_name)    { return _get(`/api/hyperv/checkpoints/${encodeURIComponent(host_id)}/${encodeURIComponent(vm_name)}`); }
export async function createHVCheckpoint(host_id, vm_name, name) { return _post("/api/hyperv/checkpoint/create", { host_id, vm_name, name }); }
export async function deleteHVCheckpoint(host_id, vm_name, name) { return _post("/api/hyperv/checkpoint/delete", { host_id, vm_name, name }); }
export async function restoreHVCheckpoint(host_id, vm_name, name){ return _post("/api/hyperv/checkpoint/restore", { host_id, vm_name, name }); }

// â”€â”€ LaaS AI â€” OpenAI Natural Language Chat â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function sendAIChat(query, contextData) {
  return _post("/api/ai/chat", { query, context: contextData });
}

//  History & Forecast (nightly collector) 
export async function fetchHistoryAll(days)    { return _get(`/api/history/all?days=${days||30}`); }
export async function fetchForecastAll(horizon){ return _get(`/api/forecast/all?horizon=${horizon||30}`); }
export async function fetchHistoryKPI(days)    { return _get(`/api/history/kpi?days=${days||30}`); }
export async function fetchHistoryPlatforms(days){ return _get(`/api/history/platforms?days=${days||30}`); }
export async function fetchLastRun()           { return _get("/api/history/last_run"); }

//  IPAM v2 (Self-hosted PostgreSQL) -----------------------------------------
export async function fetchIPAM2Summary()                    { return _get("/api/ipam2/summary"); }
export async function fetchIPAM2VLANs(site)                  { return _get(`/api/ipam2/vlans${site ? "?site=" + encodeURIComponent(site) : ""}`); }
export async function createIPAM2VLAN(data)                  { return _post("/api/ipam2/vlans", data); }
export async function updateIPAM2VLAN(id, data)              { return _put(`/api/ipam2/vlans/${id}`, data); }
export async function deleteIPAM2VLAN(id)                    { return _delete(`/api/ipam2/vlans/${id}`); }
export async function fetchIPAM2IPs(vlanId, status, q)       { let u = `/api/ipam2/vlans/${vlanId}/ips`; const p=[]; if(status) p.push("status="+encodeURIComponent(status)); if(q) p.push("q="+encodeURIComponent(q)); if(p.length) u+="?"+p.join("&"); return _get(u); }
export async function updateIPAM2IP(ipId, data)              { return _put(`/api/ipam2/ips/${ipId}`, data); }
export async function bulkUpdateIPAM2IPs(ipIds, update)      { return _post("/api/ipam2/ips/bulk-update", { ip_ids: ipIds, update }); }
export async function pingIPAM2VLAN(vlanId)                  { return _post(`/api/ipam2/vlans/${vlanId}/ping`, {}); }
export async function pollIPAM2PingStatus(vlanId)            { return _get(`/api/ipam2/vlans/${vlanId}/ping/status`); }
export async function dnsLookupIPAM2VLAN(vlanId)             { return _post(`/api/ipam2/vlans/${vlanId}/dns-lookup`, {}); }
export async function fetchIPAM2Changelog(vlanId, limit)     { let u = "/api/ipam2/changelog"; const p=[]; if(vlanId) p.push("vlan_db_id="+vlanId); if(limit) p.push("limit="+limit); if(p.length) u+="?"+p.join("&"); return _get(u); }
export async function fetchIPAM2Conflicts()                  { return _get("/api/ipam2/conflicts"); }

// ── CMDB ────────────────────────────────────────────────────────────────────
export async function fetchCMDBSummary()                     { return _get("/api/cmdb/summary"); }
export async function fetchCMDBCIs(cls, platform, search, limit=5000, offset=0) {
  let u = "/api/cmdb/cis";
  const p = [];
  if (cls)      p.push("cls="      + encodeURIComponent(cls));
  if (platform) p.push("platform=" + encodeURIComponent(platform));
  if (search)   p.push("search="   + encodeURIComponent(search));
  p.push("limit=" + limit, "offset=" + offset);
  return _get(u + "?" + p.join("&"));
}
export async function collectCMDBNow()                       { return _post("/api/cmdb/collect", {}); }
export async function updateCMDBCI(id, data)                 { return _patch(`/api/cmdb/cis/${id}`, data); }
export async function fetchCMDBSNConfig()                    { return _get("/api/cmdb/sn-config"); }
export async function saveCMDBSNConfig(data)                 { return _post("/api/cmdb/sn-config", data); }
export async function exportCMDBCSV(cls, platform, search) {
  let u = "/api/cmdb/export-csv";
  const ps = [];
  if (cls)      ps.push("cls=" + encodeURIComponent(cls));
  if (platform) ps.push("platform=" + encodeURIComponent(platform));
  if (search)   ps.push("search=" + encodeURIComponent(search));
  if (ps.length) u += "?" + ps.join("&");
  const res = await fetch(`${BASE}${u}`, { headers: authHeader() });
  if (!res.ok) throw new Error("CSV export failed");
  return await res.text();
}
export async function pushCMDBToSN(dryRun=false)             { return _post(`/api/cmdb/push-to-sn?dry_run=${dryRun}`, {}); }

//  Magic Migrate API 
export async function fetchMigrationPlans()          { return _get("/api/migration/plans"); }
export async function createMigrationPlan(body)      { return _post("/api/migration/plans", body); }
export async function deleteMigrationPlan(id)        { return _delete(`/api/migration/plans/${id}`); }
export async function updatePlanStatus(id, body)    { return _patch(`/api/migration/plans/${id}/status`, body); }
export async function executeMigrationPlan(id)     { return _post(`/api/migration/plans/${id}/execute`, {}); }
export async function fetchPlanEvents(id)          { return _get(`/api/migration/plans/${id}/events`); }
export async function runPreflightCheck(body)        { return _post("/api/migration/preflight", body); }
