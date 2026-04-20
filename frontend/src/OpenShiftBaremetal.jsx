/**
 * OpenShiftPanel.jsx + BaremetalPanel.jsx
 * Drop-in React components for the CaaS dashboard.
 * 
 * Usage in your existing app — add to your page/tab router:
 *   import { OpenShiftPanel } from "./OpenShiftPanel";
 *   import { BaremetalPanel } from "./BaremetalPanel";
 * 
 * Props for both:
 *   currentUser  — { role, username, display_name }
 *   api          — all exported functions from api.js (pass as object or import directly)
 */

import { useState, useEffect, useCallback, useRef } from "react";

// ─── Shared Utilities ──────────────────────────────────────────────────────────
const isAdmin    = (u) => u?.role === "admin";
const isOperator = (u) => ["admin","operator"].includes(u?.role);

function Badge({ text, color }) {
  const map = {
    green:  "bg-green-900/50 text-green-300 border border-green-700",
    red:    "bg-red-900/50 text-red-300 border border-red-700",
    yellow: "bg-yellow-900/50 text-yellow-300 border border-yellow-700",
    gray:   "bg-gray-700/50 text-gray-300 border border-gray-600",
    blue:   "bg-blue-900/50 text-blue-300 border border-blue-700",
    purple: "bg-purple-900/50 text-purple-300 border border-purple-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${map[color]||map.gray}`}>
      {text}
    </span>
  );
}

function StatusBadge({ status }) {
  const s = (status||"").toLowerCase();
  if (s.includes("on") || s.includes("ready") || s.includes("connected") || s.includes("running"))
    return <Badge text={status} color="green"/>;
  if (s.includes("off") || s.includes("not") || s.includes("error") || s.includes("fail"))
    return <Badge text={status} color="red"/>;
  if (s.includes("unknown") || s.includes("unreachable"))
    return <Badge text={status} color="gray"/>;
  return <Badge text={status} color="yellow"/>;
}

function RoleBadge({ role }) {
  const map = { master:"purple", "control-plane":"purple", worker:"blue", infra:"yellow" };
  return <Badge text={role} color={map[role]||"gray"}/>;
}

function Modal({ title, onClose, children, wide }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className={`bg-gray-900 border border-gray-700 rounded-xl shadow-2xl
        ${wide ? "w-full max-w-3xl" : "w-full max-w-lg"} mx-4 max-h-[90vh] flex flex-col`}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <h2 className="text-lg font-bold text-white">{title}</h2>
          <button onClick={onClose}
            className="text-gray-400 hover:text-white text-2xl leading-none transition-colors">×</button>
        </div>
        <div className="p-6 overflow-y-auto flex-1">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wider">
        {label}
      </label>
      {children}
    </div>
  );
}

function Input({ value, onChange, placeholder, type="text", disabled, mono }) {
  return (
    <input
      type={type} value={value} onChange={e=>onChange(e.target.value)}
      placeholder={placeholder} disabled={disabled}
      className={`w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm
        text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors
        disabled:opacity-50 ${mono ? "font-mono" : ""}`}
    />
  );
}

function Select({ value, onChange, options, disabled }) {
  return (
    <select value={value} onChange={e=>onChange(e.target.value)} disabled={disabled}
      className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm
        text-white focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-50">
      {options.map(o => (
        <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>
      ))}
    </select>
  );
}

function Btn({ onClick, disabled, loading, children, color="blue", size="md", className="" }) {
  const colors = {
    blue:  "bg-blue-600 hover:bg-blue-500 text-white",
    red:   "bg-red-700 hover:bg-red-600 text-white",
    green: "bg-green-700 hover:bg-green-600 text-white",
    gray:  "bg-gray-700 hover:bg-gray-600 text-white",
    amber: "bg-amber-700 hover:bg-amber-600 text-white",
  };
  const sizes = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2 text-sm", lg: "px-5 py-2.5 text-base" };
  return (
    <button onClick={onClick} disabled={disabled||loading}
      className={`rounded-lg font-semibold transition-all disabled:opacity-50
        ${colors[color]||colors.blue} ${sizes[size]||sizes.md} ${className}`}>
      {loading ? "…" : children}
    </button>
  );
}

function Alert({ msg, type="error", onClose }) {
  if (!msg) return null;
  const cls = type==="error"
    ? "bg-red-900/40 border-red-700 text-red-300"
    : "bg-green-900/40 border-green-700 text-green-300";
  return (
    <div className={`border rounded-lg px-4 py-3 text-sm flex items-start gap-3 ${cls}`}>
      <span className="flex-1">{msg}</span>
      {onClose && <button onClick={onClose} className="shrink-0 opacity-60 hover:opacity-100">×</button>}
    </div>
  );
}

function Spinner() {
  return <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"/>;
}

function EmptyState({ icon, title, subtitle }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-500">
      <span className="text-5xl mb-4">{icon}</span>
      <p className="text-lg font-semibold text-gray-400">{title}</p>
      {subtitle && <p className="text-sm mt-1">{subtitle}</p>}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
//  OPENSHIFT PANEL
// ═══════════════════════════════════════════════════════════════════════════════
export function OpenShiftPanel({ currentUser, api }) {
  const [clusters,     setClusters]     = useState([]);
  const [selected,     setSelected]     = useState(null);   // active cluster obj
  const [nodes,        setNodes]        = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [nodesLoading, setNodesLoading] = useState(false);
  const [syncing,      setSyncing]      = useState(false);
  const [err,          setErr]          = useState("");
  const [ok,           setOk]           = useState("");

  // Modals
  const [showAddCluster, setShowAddCluster] = useState(false);
  const [showAddNode,    setShowAddNode]    = useState(false);
  const [showEditCluster,setShowEditCluster]= useState(null);
  const [confirmDelete,  setConfirmDelete]  = useState(null); // {type,id,name}
  const [actionModal,    setActionModal]    = useState(null); // {node, action}
  const [statusModal,    setStatusModal]    = useState(null);

  const flash = (msg, type="ok") => {
    if (type==="ok") { setOk(msg); setTimeout(()=>setOk(""),4000); }
    else setErr(msg);
  };

  const loadClusters = useCallback(async () => {
    setLoading(true);
    try { setClusters(await api.fetchOCPClusters()); }
    catch(e) { setErr(e.message); }
    finally { setLoading(false); }
  }, [api]);

  const loadNodes = useCallback(async (clusterId) => {
    setNodesLoading(true);
    try { setNodes(await api.fetchOCPNodes(clusterId)); }
    catch(e) { setErr(e.message); }
    finally { setNodesLoading(false); }
  }, [api]);

  useEffect(() => { loadClusters(); }, [loadClusters]);
  useEffect(() => {
    if (selected) loadNodes(selected.id);
    else setNodes([]);
  }, [selected, loadNodes]);

  const handleSync = async () => {
    if (!selected) return;
    setSyncing(true); setErr("");
    try {
      const r = await api.syncOCPClusterNodes(selected.id);
      setNodes(r.nodes);
      flash(`Synced ${r.synced} nodes from cluster`);
    } catch(e) { setErr(e.message); }
    finally { setSyncing(false); }
  };

  const handleNodeAction = async (node, action) => {
    setActionModal(null);
    setErr("");
    try {
      const r = await api.ocpNodeAction(selected.id, node.id, action);
      flash(`${action} on ${node.name}: ${r.message.slice(0,120)}`);
    } catch(e) { setErr(e.message); }
  };

  const handleDeleteCluster = async () => {
    if (!confirmDelete || confirmDelete.type !== "cluster") return;
    try {
      await api.deleteOCPCluster(confirmDelete.id);
      if (selected?.id === confirmDelete.id) setSelected(null);
      await loadClusters();
      flash("Cluster removed");
    } catch(e) { setErr(e.message); }
    finally { setConfirmDelete(null); }
  };

  const handleDeleteNode = async () => {
    if (!confirmDelete || confirmDelete.type !== "node") return;
    try {
      await api.removeOCPNode(selected.id, confirmDelete.id);
      await loadNodes(selected.id);
      flash("Node removed");
    } catch(e) { setErr(e.message); }
    finally { setConfirmDelete(null); }
  };

  const masters = nodes.filter(n => n.role==="master" || n.role==="control-plane");
  const workers = nodes.filter(n => !["master","control-plane"].includes(n.role));

  return (
    <div className="flex h-full gap-4">
      {/* ── Left sidebar: cluster list ── */}
      <div className="w-72 shrink-0 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <span>🔴</span> OpenShift Clusters
          </h2>
          {isAdmin(currentUser) && (
            <Btn size="sm" onClick={()=>setShowAddCluster(true)}>+ Add</Btn>
          )}
        </div>

        {loading && <div className="flex justify-center py-8"><Spinner/></div>}

        {!loading && clusters.length === 0 && (
          <div className="text-gray-500 text-sm text-center py-8">
            No clusters registered yet
          </div>
        )}

        <div className="flex flex-col gap-2 overflow-y-auto">
          {clusters.map(c => (
            <button key={c.id}
              onClick={() => setSelected(c)}
              className={`text-left rounded-xl p-3 border transition-all
                ${selected?.id===c.id
                  ? "border-red-500 bg-red-900/20"
                  : "border-gray-700 bg-gray-800/60 hover:border-gray-500"}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-sm text-white truncate">{c.name}</span>
                <StatusBadge status={c.status}/>
              </div>
              <p className="text-xs text-gray-500 mt-1 truncate font-mono">{c.api_url}</p>
              {c.version && <p className="text-xs text-gray-600 mt-0.5">v{c.version}</p>}
            </button>
          ))}
        </div>
      </div>

      {/* ── Main area ── */}
      <div className="flex-1 min-w-0 flex flex-col gap-4">
        {(err || ok) && (
          <div className="flex flex-col gap-2">
            {err && <Alert msg={err} type="error" onClose={()=>setErr("")}/>}
            {ok  && <Alert msg={ok}  type="ok"    onClose={()=>setOk("")}/>}
          </div>
        )}

        {!selected ? (
          <div className="flex-1 flex items-center justify-center">
            <EmptyState icon="🔴" title="Select a cluster"
              subtitle="Choose a cluster from the left to view and manage its nodes"/>
          </div>
        ) : (
          <>
            {/* Cluster header */}
            <div className="bg-gray-800/60 border border-gray-700 rounded-xl p-4">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <h3 className="text-xl font-bold text-white">{selected.name}</h3>
                    <StatusBadge status={selected.status}/>
                    {selected.version && <Badge text={`v${selected.version}`} color="gray"/>}
                  </div>
                  <p className="text-sm text-gray-400 mt-1 font-mono">{selected.api_url}</p>
                  {selected.console_url && (
                    <a href={selected.console_url} target="_blank" rel="noreferrer"
                      className="text-xs text-blue-400 hover:underline mt-0.5 block">
                      🔗 Console →
                    </a>
                  )}
                  {selected.description && (
                    <p className="text-xs text-gray-500 mt-1">{selected.description}</p>
                  )}
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Btn size="sm" color="gray"
                    onClick={()=>api.fetchOCPClusterStatus(selected.id).then(s=>setStatusModal(s)).catch(e=>setErr(e.message))}>
                    Health
                  </Btn>
                  {isOperator(currentUser) && (
                    <Btn size="sm" color="gray" loading={syncing} onClick={handleSync}>
                      🔄 Sync Nodes
                    </Btn>
                  )}
                  {isAdmin(currentUser) && (
                    <>
                      <Btn size="sm" color="gray" onClick={()=>setShowEditCluster(selected)}>
                        ✏️ Edit
                      </Btn>
                      <Btn size="sm" color="red"
                        onClick={()=>setConfirmDelete({type:"cluster",id:selected.id,name:selected.name})}>
                        🗑 Delete
                      </Btn>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Node stats */}
            <div className="grid grid-cols-3 gap-3">
              {[
                { label:"Total Nodes",  val: nodes.length,    color:"text-blue-400" },
                { label:"Masters",      val: masters.length,  color:"text-purple-400" },
                { label:"Workers",      val: workers.length,  color:"text-green-400" },
              ].map(s => (
                <div key={s.label}
                  className="bg-gray-800/60 border border-gray-700 rounded-xl p-4 text-center">
                  <p className={`text-3xl font-bold ${s.color}`}>{s.val}</p>
                  <p className="text-xs text-gray-500 mt-1">{s.label}</p>
                </div>
              ))}
            </div>

            {/* Nodes table */}
            <div className="bg-gray-800/60 border border-gray-700 rounded-xl flex-1 flex flex-col min-h-0">
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
                <h4 className="font-semibold text-white text-sm">Nodes</h4>
                <div className="flex gap-2">
                  {nodesLoading && <Spinner/>}
                  {isAdmin(currentUser) && (
                    <Btn size="sm" onClick={()=>setShowAddNode(true)}>+ Add Node</Btn>
                  )}
                </div>
              </div>
              <div className="overflow-y-auto flex-1">
                {nodes.length === 0 && !nodesLoading && (
                  <EmptyState icon="🖥" title="No nodes"
                    subtitle="Add nodes manually or sync from the cluster"/>
                )}
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-gray-500 uppercase border-b border-gray-700/50">
                      {["Name","Role","Status","CPU","Memory","OS","Actions"].map(h=>(
                        <th key={h} className="text-left px-4 py-2 font-semibold">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {nodes.map(node => (
                      <tr key={node.id}
                        className="border-b border-gray-700/30 hover:bg-gray-700/20 transition-colors">
                        <td className="px-4 py-3 font-mono text-xs text-white">{node.name}</td>
                        <td className="px-4 py-3"><RoleBadge role={node.role}/></td>
                        <td className="px-4 py-3"><StatusBadge status={node.status||"unknown"}/></td>
                        <td className="px-4 py-3 text-gray-300 text-xs">{node.cpu||"—"}</td>
                        <td className="px-4 py-3 text-gray-300 text-xs">{node.memory||"—"}</td>
                        <td className="px-4 py-3 text-gray-400 text-xs truncate max-w-[200px]">
                          {node.os_image||"—"}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1 flex-wrap">
                            {isOperator(currentUser) && (
                              <>
                                {["cordon","uncordon","drain"].map(a=>(
                                  <Btn key={a} size="sm" color="gray"
                                    onClick={()=>setActionModal({node, action:a})}>
                                    {a}
                                  </Btn>
                                ))}
                              </>
                            )}
                            {isAdmin(currentUser) && (
                              <Btn size="sm" color="red"
                                onClick={()=>setConfirmDelete({type:"node",id:node.id,name:node.name})}>
                                ✕
                              </Btn>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>

      {/* ── Modals ── */}
      {showAddCluster && (
        <AddClusterModal
          api={api}
          onClose={()=>setShowAddCluster(false)}
          onSuccess={async c => {
            setShowAddCluster(false);
            await loadClusters();
            setSelected(c);
            flash(`Cluster '${c.name}' added`);
          }}
          onError={setErr}
        />
      )}

      {showEditCluster && (
        <EditClusterModal
          api={api}
          cluster={showEditCluster}
          onClose={()=>setShowEditCluster(null)}
          onSuccess={async c => {
            setShowEditCluster(null);
            await loadClusters();
            setSelected(c);
            flash("Cluster updated");
          }}
          onError={setErr}
        />
      )}

      {showAddNode && selected && (
        <AddNodeModal
          api={api}
          clusterId={selected.id}
          onClose={()=>setShowAddNode(false)}
          onSuccess={async () => {
            setShowAddNode(false);
            await loadNodes(selected.id);
            flash("Node added");
          }}
          onError={setErr}
        />
      )}

      {actionModal && (
        <Modal title={`${actionModal.action} — ${actionModal.node.name}`}
          onClose={()=>setActionModal(null)}>
          <p className="text-gray-300 mb-6">
            Are you sure you want to <strong className="text-white">{actionModal.action}</strong> node{" "}
            <code className="text-yellow-400">{actionModal.node.name}</code>?
            {actionModal.action==="drain" && (
              <span className="block text-yellow-400 mt-2 text-xs">
                ⚠️ This will evict all pods from the node (ignoring DaemonSets).
              </span>
            )}
          </p>
          <div className="flex gap-3 justify-end">
            <Btn color="gray" onClick={()=>setActionModal(null)}>Cancel</Btn>
            <Btn color={actionModal.action==="drain"?"red":"amber"}
              onClick={()=>handleNodeAction(actionModal.node, actionModal.action)}>
              Confirm
            </Btn>
          </div>
        </Modal>
      )}

      {confirmDelete && (
        <Modal title="Confirm Delete" onClose={()=>setConfirmDelete(null)}>
          <p className="text-gray-300 mb-6">
            Delete <strong className="text-white">{confirmDelete.type}</strong>{" "}
            <code className="text-red-400">{confirmDelete.name}</code>?
            {confirmDelete.type==="cluster" && (
              <span className="block text-red-400 mt-2 text-xs">
                This will remove the cluster and all its associated nodes from the dashboard.
              </span>
            )}
          </p>
          <div className="flex gap-3 justify-end">
            <Btn color="gray" onClick={()=>setConfirmDelete(null)}>Cancel</Btn>
            <Btn color="red"
              onClick={confirmDelete.type==="cluster" ? handleDeleteCluster : handleDeleteNode}>
              Delete
            </Btn>
          </div>
        </Modal>
      )}

      {statusModal && (
        <Modal title="Cluster Health" onClose={()=>setStatusModal(null)}>
          {statusModal.reachable === false ? (
            <Alert msg={statusModal.message} type="error"/>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-gray-800 rounded-lg p-4 text-center">
                  <p className="text-3xl font-bold text-green-400">{statusModal.ready_nodes}</p>
                  <p className="text-xs text-gray-400 mt-1">Ready Nodes</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 text-center">
                  <p className="text-3xl font-bold text-blue-400">{statusModal.total_nodes}</p>
                  <p className="text-xs text-gray-400 mt-1">Total Nodes</p>
                </div>
              </div>
              <Alert msg={statusModal.message} type="ok"/>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

function AddClusterModal({ api, onClose, onSuccess, onError }) {
  const [form, setForm] = useState({
    name:"", api_url:"", console_url:"", version:"", description:"", token:"", kubeconfig:""
  });
  const [loading, setLoading] = useState(false);
  const set = k => v => setForm(f=>({...f,[k]:v}));

  const submit = async () => {
    if (!form.name || !form.api_url) { onError("Name and API URL are required"); return; }
    setLoading(true);
    try {
      const c = await api.createOCPCluster(form);
      onSuccess(c);
    } catch(e) { onError(e.message); }
    finally { setLoading(false); }
  };

  return (
    <Modal title="Add OpenShift Cluster" onClose={onClose} wide>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Cluster Name *">
          <Input value={form.name} onChange={set("name")} placeholder="prod-ocp4"/>
        </Field>
        <Field label="API URL *">
          <Input value={form.api_url} onChange={set("api_url")} placeholder="https://api.cluster:6443" mono/>
        </Field>
        <Field label="Console URL">
          <Input value={form.console_url} onChange={set("console_url")} placeholder="https://console-openshift..."/>
        </Field>
        <Field label="Version">
          <Input value={form.version} onChange={set("version")} placeholder="4.14.6"/>
        </Field>
        <div className="col-span-2">
          <Field label="Description">
            <Input value={form.description} onChange={set("description")} placeholder="Production OpenShift cluster"/>
          </Field>
        </div>
        <div className="col-span-2">
          <Field label="Service Account Token (for API access)">
            <Input value={form.token} onChange={set("token")} type="password"
              placeholder="sha256~... or eyJhbGci..." mono/>
          </Field>
        </div>
      </div>
      <p className="text-xs text-gray-500 mt-3">
        💡 Get token: <code className="text-gray-400">oc create token dashboard-sa -n kube-system</code>
      </p>
      <div className="flex gap-3 justify-end mt-6">
        <Btn color="gray" onClick={onClose}>Cancel</Btn>
        <Btn loading={loading} onClick={submit}>Add Cluster</Btn>
      </div>
    </Modal>
  );
}

function EditClusterModal({ api, cluster, onClose, onSuccess, onError }) {
  const [form, setForm] = useState({
    name: cluster.name, api_url: cluster.api_url,
    console_url: cluster.console_url, version: cluster.version,
    description: cluster.description, token: cluster.token || "",
  });
  const [loading, setLoading] = useState(false);
  const set = k => v => setForm(f=>({...f,[k]:v}));

  const submit = async () => {
    setLoading(true);
    try {
      const c = await api.updateOCPCluster(cluster.id, form);
      onSuccess(c);
    } catch(e) { onError(e.message); }
    finally { setLoading(false); }
  };

  return (
    <Modal title={`Edit — ${cluster.name}`} onClose={onClose} wide>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Name"><Input value={form.name} onChange={set("name")}/></Field>
        <Field label="API URL"><Input value={form.api_url} onChange={set("api_url")} mono/></Field>
        <Field label="Console URL"><Input value={form.console_url} onChange={set("console_url")}/></Field>
        <Field label="Version"><Input value={form.version} onChange={set("version")}/></Field>
        <div className="col-span-2">
          <Field label="Description"><Input value={form.description} onChange={set("description")}/></Field>
        </div>
        <div className="col-span-2">
          <Field label="Token">
            <Input value={form.token} onChange={set("token")} type="password" mono
              placeholder="Leave blank to keep existing"/>
          </Field>
        </div>
      </div>
      <div className="flex gap-3 justify-end mt-6">
        <Btn color="gray" onClick={onClose}>Cancel</Btn>
        <Btn loading={loading} onClick={submit}>Save Changes</Btn>
      </div>
    </Modal>
  );
}

function AddNodeModal({ api, clusterId, onClose, onSuccess, onError }) {
  const [form, setForm] = useState({
    name:"", role:"worker", ip:"", cpu:"", memory:"", os_image:"", ssh_user:"", ssh_key:""
  });
  const [loading, setLoading] = useState(false);
  const set = k => v => setForm(f=>({...f,[k]:v}));

  const submit = async () => {
    if (!form.name) { onError("Node name is required"); return; }
    setLoading(true);
    try {
      await api.addOCPNode(clusterId, form);
      onSuccess();
    } catch(e) { onError(e.message); }
    finally { setLoading(false); }
  };

  return (
    <Modal title="Add Node" onClose={onClose} wide>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Node Name *">
          <Input value={form.name} onChange={set("name")}
            placeholder="worker-0.cluster.example.com" mono/>
        </Field>
        <Field label="Role">
          <Select value={form.role} onChange={set("role")}
            options={["worker","master","infra"]}/>
        </Field>
        <Field label="IP Address">
          <Input value={form.ip} onChange={set("ip")} placeholder="192.168.1.10" mono/>
        </Field>
        <Field label="OS Image">
          <Input value={form.os_image} onChange={set("os_image")} placeholder="Red Hat Enterprise Linux CoreOS"/>
        </Field>
        <Field label="CPU (vCPUs)">
          <Input value={form.cpu} onChange={set("cpu")} placeholder="8"/>
        </Field>
        <Field label="Memory">
          <Input value={form.memory} onChange={set("memory")} placeholder="32Gi"/>
        </Field>
        <Field label="SSH User">
          <Input value={form.ssh_user} onChange={set("ssh_user")} placeholder="core"/>
        </Field>
        <Field label="SSH Key Path">
          <Input value={form.ssh_key} onChange={set("ssh_key")}
            placeholder="/home/user/.ssh/id_rsa" mono/>
        </Field>
      </div>
      <div className="flex gap-3 justify-end mt-6">
        <Btn color="gray" onClick={onClose}>Cancel</Btn>
        <Btn loading={loading} onClick={submit}>Add Node</Btn>
      </div>
    </Modal>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
//  BAREMETAL PANEL
// ═══════════════════════════════════════════════════════════════════════════════
const BM_ACTIONS = [
  { key:"power_on",          label:"Power On",          color:"green", icon:"⚡" },
  { key:"graceful_shutdown", label:"Graceful Shutdown",  color:"amber", icon:"🔽" },
  { key:"power_off",         label:"Force Power Off",   color:"red",   icon:"⛔" },
  { key:"graceful_reboot",   label:"Graceful Reboot",   color:"blue",  icon:"🔄" },
  { key:"reboot",            label:"Force Reboot",      color:"amber", icon:"↺" },
  { key:"power_cycle",       label:"Power Cycle",       color:"gray",  icon:"🔁" },
  { key:"pxe_boot",          label:"PXE Boot",          color:"purple",icon:"🌐" },
  { key:"nmi",               label:"Send NMI",          color:"red",   icon:"🔔" },
];

export function BaremetalPanel({ currentUser, api }) {
  const [servers,    setServers]    = useState([]);
  const [selected,   setSelected]   = useState(null);
  const [detail,     setDetail]     = useState(null);   // {power, health, sensors}
  const [eventLog,   setEventLog]   = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [detLoading, setDetLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState("");
  const [err, setErr] = useState("");
  const [ok,  setOk]  = useState("");

  const [showAdd,    setShowAdd]    = useState(false);
  const [showEdit,   setShowEdit]   = useState(null);
  const [confirmDel, setConfirmDel] = useState(null);
  const [confirmAct, setConfirmAct] = useState(null);   // {action, server}
  const [showLog,    setShowLog]    = useState(false);

  const flash = (msg, type="ok") => {
    if (type==="ok") { setOk(msg); setTimeout(()=>setOk(""),4000); }
    else setErr(msg);
  };

  const loadServers = useCallback(async () => {
    setLoading(true);
    try { setServers(await api.fetchBMServers()); }
    catch(e) { setErr(e.message); }
    finally { setLoading(false); }
  }, [api]);

  const loadDetail = useCallback(async (s) => {
    setDetLoading(true); setDetail(null); setEventLog(null);
    try { setDetail(await api.fetchBMServerInfo(s.id)); }
    catch(e) { setDetail({success:false, message:e.message}); }
    finally { setDetLoading(false); }
  }, [api]);

  useEffect(() => { loadServers(); }, [loadServers]);
  useEffect(() => {
    if (selected) loadDetail(selected);
    else { setDetail(null); setEventLog(null); }
  }, [selected, loadDetail]);

  const handleAction = async () => {
    if (!confirmAct) return;
    const { action, server } = confirmAct;
    setConfirmAct(null);
    setActionLoading(action);
    setErr("");
    try {
      const r = await api.bmAction(server.id, action);
      flash(r.message || `${action} sent successfully`);
      setTimeout(() => loadDetail(server), 3000);
    } catch(e) { setErr(e.message); }
    finally { setActionLoading(""); }
  };

  const handleDelete = async () => {
    if (!confirmDel) return;
    try {
      await api.deleteBMServer(confirmDel.id);
      if (selected?.id === confirmDel.id) setSelected(null);
      await loadServers();
      flash("Server removed");
    } catch(e) { setErr(e.message); }
    finally { setConfirmDel(null); }
  };

  const loadLog = async () => {
    setShowLog(true);
    try {
      const r = await api.fetchBMEventLog(selected.id, 50);
      setEventLog(r.logs || []);
    } catch(e) { setEventLog([]); flash(e.message,"error"); }
  };

  // Power state colour
  const psColor = (ps) => {
    const s = (ps||"").toLowerCase();
    if (s.includes("on"))  return "text-green-400";
    if (s.includes("off")) return "text-red-400";
    return "text-gray-400";
  };

  return (
    <div className="flex h-full gap-4">
      {/* ── Server list ── */}
      <div className="w-72 shrink-0 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <span>🖧</span> Bare Metal Servers
          </h2>
          {isAdmin(currentUser) && (
            <Btn size="sm" onClick={()=>setShowAdd(true)}>+ Add</Btn>
          )}
        </div>

        {loading && <div className="flex justify-center py-8"><Spinner/></div>}

        {!loading && servers.length === 0 && (
          <div className="text-gray-500 text-sm text-center py-8">No servers added yet</div>
        )}

        <div className="flex flex-col gap-2 overflow-y-auto">
          {servers.map(s => (
            <button key={s.id}
              onClick={()=>setSelected(s)}
              className={`text-left rounded-xl p-3 border transition-all
                ${selected?.id===s.id
                  ? "border-blue-500 bg-blue-900/20"
                  : "border-gray-700 bg-gray-800/60 hover:border-gray-500"}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-sm text-white truncate">{s.name}</span>
                <Badge text={s.bmc_type} color={
                  {ILO:"green",IDRAC:"blue",CIMC:"purple",IPMI:"gray"}[s.bmc_type]||"gray"}/>
              </div>
              <p className="text-xs text-gray-500 mt-1 font-mono">{s.ip}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-xs font-semibold ${psColor(s.power_state)}`}>
                  {s.power_state || "unknown"}
                </span>
                {s.location && <span className="text-xs text-gray-600">• {s.location}</span>}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* ── Main detail ── */}
      <div className="flex-1 min-w-0 flex flex-col gap-4">
        {(err || ok) && (
          <div className="flex flex-col gap-2">
            {err && <Alert msg={err} type="error" onClose={()=>setErr("")}/>}
            {ok  && <Alert msg={ok}  type="ok"    onClose={()=>setOk("")}/>}
          </div>
        )}

        {!selected ? (
          <div className="flex-1 flex items-center justify-center">
            <EmptyState icon="🖧" title="Select a server"
              subtitle="Choose a bare metal server to view details and perform actions"/>
          </div>
        ) : (
          <>
            {/* Server header */}
            <div className="bg-gray-800/60 border border-gray-700 rounded-xl p-4">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <h3 className="text-xl font-bold text-white">{selected.name}</h3>
                    <Badge text={selected.bmc_type} color={
                      {ILO:"green",IDRAC:"blue",CIMC:"purple",IPMI:"gray"}[selected.bmc_type]||"gray"}/>
                    <StatusBadge status={selected.status||"unknown"}/>
                  </div>
                  <p className="text-sm text-gray-400 mt-1 font-mono">
                    {selected.ip}:{selected.port}
                  </p>
                  {selected.model && (
                    <p className="text-xs text-gray-500 mt-0.5">
                      {selected.model} {selected.serial ? `· S/N: ${selected.serial}` : ""}
                    </p>
                  )}
                  {selected.location && (
                    <p className="text-xs text-gray-600 mt-0.5">📍 {selected.location}</p>
                  )}
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Btn size="sm" color="gray" onClick={()=>loadDetail(selected)}>↺ Refresh</Btn>
                  <Btn size="sm" color="gray" onClick={loadLog}>📋 Event Log</Btn>
                  {isAdmin(currentUser) && (
                    <>
                      <Btn size="sm" color="gray" onClick={()=>setShowEdit(selected)}>✏️ Edit</Btn>
                      <Btn size="sm" color="red" onClick={()=>setConfirmDel(selected)}>🗑 Delete</Btn>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Detail cards */}
            {detLoading && (
              <div className="flex justify-center py-8"><Spinner/></div>
            )}

            {detail && detail.success && (
              <div className="grid grid-cols-2 gap-4">
                {/* Power & Hardware */}
                <div className="bg-gray-800/60 border border-gray-700 rounded-xl p-4">
                  <h4 className="text-sm font-semibold text-gray-300 mb-3">Hardware</h4>
                  <dl className="space-y-2 text-sm">
                    {[
                      ["Power State",  detail.power?.power_state],
                      ["Model",        detail.power?.model],
                      ["Manufacturer", detail.power?.manufacturer],
                      ["BIOS",         detail.power?.bios_version],
                      ["Hostname",     detail.power?.hostname],
                      ["CPUs",         detail.power?.processors],
                      ["Memory",       detail.power?.memory_gb ? `${detail.power.memory_gb} GiB` : null],
                    ].filter(([,v])=>v).map(([k,v])=>(
                      <div key={k} className="flex justify-between gap-2">
                        <dt className="text-gray-500">{k}</dt>
                        <dd className={`font-mono text-right ${k==="Power State" ? psColor(v) : "text-gray-200"}`}>
                          {v}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>

                {/* Health */}
                <div className="bg-gray-800/60 border border-gray-700 rounded-xl p-4">
                  <h4 className="text-sm font-semibold text-gray-300 mb-3">Health</h4>
                  {detail.health && Object.keys(detail.health).length > 0 ? (
                    <dl className="space-y-2 text-sm">
                      {Object.entries(detail.health).filter(([,v])=>v).map(([k,v])=>(
                        <div key={k} className="flex justify-between gap-2">
                          <dt className="text-gray-500 capitalize">{k.replace(/_/g," ")}</dt>
                          <dd className={`font-semibold ${
                            v==="OK"?"text-green-400":v==="Warning"?"text-yellow-400":"text-red-400"
                          }`}>{v}</dd>
                        </div>
                      ))}
                    </dl>
                  ) : (
                    <p className="text-gray-500 text-sm">Health data not available via IPMI</p>
                  )}
                </div>

                {/* Temperatures */}
                {detail.sensors?.temperature?.length > 0 && (
                  <div className="bg-gray-800/60 border border-gray-700 rounded-xl p-4">
                    <h4 className="text-sm font-semibold text-gray-300 mb-3">Temperatures</h4>
                    <div className="space-y-1 max-h-40 overflow-y-auto">
                      {detail.sensors.temperature.slice(0,10).map((t,i)=>(
                        <div key={i} className="flex justify-between text-xs">
                          <span className="text-gray-400 truncate">{t.name}</span>
                          <span className={`font-mono ml-2 ${
                            t.reading > 70 ? "text-red-400" :
                            t.reading > 50 ? "text-yellow-400" : "text-green-400"
                          }`}>{t.reading}°C</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Power */}
                {detail.sensors?.power?.length > 0 && (
                  <div className="bg-gray-800/60 border border-gray-700 rounded-xl p-4">
                    <h4 className="text-sm font-semibold text-gray-300 mb-3">Power Draw</h4>
                    {detail.sensors.power.map((p,i)=>(
                      <div key={i} className="space-y-1 text-xs">
                        <div className="flex justify-between">
                          <span className="text-gray-400">{p.name||"System"}</span>
                          <span className="text-blue-400 font-mono">{p.consumed_watts}W</span>
                        </div>
                        {p.limit_watts && (
                          <div className="w-full bg-gray-700 rounded-full h-1.5">
                            <div className="bg-blue-500 h-1.5 rounded-full"
                              style={{width:`${Math.min((p.consumed_watts/p.limit_watts)*100,100)}%`}}/>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {detail && !detail.success && (
              <Alert msg={`Cannot reach server: ${detail.message}`} type="error"/>
            )}

            {/* Actions */}
            {isOperator(currentUser) && (
              <div className="bg-gray-800/60 border border-gray-700 rounded-xl p-4">
                <h4 className="text-sm font-semibold text-gray-300 mb-3">Power Actions</h4>
                <div className="flex flex-wrap gap-2">
                  {BM_ACTIONS.map(a => (
                    <Btn key={a.key} size="sm" color={a.color}
                      loading={actionLoading===a.key}
                      onClick={()=>setConfirmAct({action:a.key, server:selected, label:a.label})}>
                      {a.icon} {a.label}
                    </Btn>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Modals ── */}
      {showAdd && (
        <AddServerModal
          api={api}
          onClose={()=>setShowAdd(false)}
          onSuccess={async s => {
            setShowAdd(false);
            await loadServers();
            setSelected(s);
            flash(`Server '${s.name}' added`);
          }}
          onError={setErr}
        />
      )}

      {showEdit && (
        <EditServerModal
          api={api}
          server={showEdit}
          onClose={()=>setShowEdit(null)}
          onSuccess={async s => {
            setShowEdit(null);
            await loadServers();
            setSelected(s);
            flash("Server updated");
          }}
          onError={setErr}
        />
      )}

      {confirmAct && (
        <Modal title={`Confirm: ${confirmAct.label}`} onClose={()=>setConfirmAct(null)}>
          <p className="text-gray-300 mb-6">
            Send <strong className="text-white">{confirmAct.label}</strong> to{" "}
            <code className="text-yellow-400">{confirmAct.server.name}</code> ({confirmAct.server.ip})?
            {["power_off","reboot","nmi"].includes(confirmAct.action) && (
              <span className="block text-red-400 mt-2 text-xs">
                ⚠️ This is a hard/forced action and may cause data loss.
              </span>
            )}
          </p>
          <div className="flex gap-3 justify-end">
            <Btn color="gray" onClick={()=>setConfirmAct(null)}>Cancel</Btn>
            <Btn color="red" onClick={handleAction}>Confirm</Btn>
          </div>
        </Modal>
      )}

      {confirmDel && (
        <Modal title="Delete Server" onClose={()=>setConfirmDel(null)}>
          <p className="text-gray-300 mb-6">
            Remove <code className="text-red-400">{confirmDel.name}</code> from the dashboard?
            <span className="block text-gray-500 mt-1 text-xs">
              This only removes it from CaaS — the physical server is not affected.
            </span>
          </p>
          <div className="flex gap-3 justify-end">
            <Btn color="gray" onClick={()=>setConfirmDel(null)}>Cancel</Btn>
            <Btn color="red" onClick={handleDelete}>Delete</Btn>
          </div>
        </Modal>
      )}

      {showLog && (
        <Modal title={`Event Log — ${selected?.name}`} onClose={()=>setShowLog(false)} wide>
          {!eventLog ? (
            <div className="flex justify-center py-8"><Spinner/></div>
          ) : eventLog.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-8">No log entries found</p>
          ) : (
            <div className="space-y-1 max-h-96 overflow-y-auto font-mono text-xs">
              {eventLog.map((e,i) => (
                <div key={i} className={`flex gap-3 p-2 rounded ${
                  e.severity==="Critical"?"bg-red-900/30":
                  e.severity==="Warning"?"bg-yellow-900/30":"bg-gray-800/40"
                }`}>
                  <span className="text-gray-500 shrink-0 w-36">{e.created?.slice(0,19)||""}</span>
                  <span className={`shrink-0 w-16 ${
                    e.severity==="Critical"?"text-red-400":
                    e.severity==="Warning"?"text-yellow-400":"text-gray-400"
                  }`}>{e.severity||""}</span>
                  <span className="text-gray-300">{e.message}</span>
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

function AddServerModal({ api, onClose, onSuccess, onError }) {
  const [form, setForm] = useState({
    name:"", ip:"", bmc_type:"ILO", username:"", password:"",
    port:"443", description:"", location:"", model:""
  });
  const [testing,  setTesting]  = useState(false);
  const [testRes,  setTestRes]  = useState(null);
  const [loading,  setLoading]  = useState(false);
  const set = k => v => setForm(f=>({...f,[k]:v}));

  const handleTest = async () => {
    if (!form.ip || !form.username || !form.password) {
      setTestRes({success:false, message:"Fill in IP, username, and password first"});
      return;
    }
    setTesting(true); setTestRes(null);
    try {
      const r = await api.testBMConnection({
        ip:form.ip, username:form.username, password:form.password,
        bmc_type:form.bmc_type, port:parseInt(form.port)||443
      });
      setTestRes(r);
    } catch(e) { setTestRes({success:false, message:e.message}); }
    finally { setTesting(false); }
  };

  const submit = async () => {
    if (!form.name||!form.ip||!form.username||!form.password) {
      onError("Name, IP, username and password are required");
      return;
    }
    setLoading(true);
    try {
      const s = await api.addBMServer({...form, port:parseInt(form.port)||443});
      onSuccess(s);
    } catch(e) { onError(e.message); }
    finally { setLoading(false); }
  };

  const defaultPort = { ILO:"443", IDRAC:"443", CIMC:"443", IPMI:"623" };

  return (
    <Modal title="Add Bare Metal Server" onClose={onClose} wide>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Server Name *">
          <Input value={form.name} onChange={set("name")} placeholder="rack01-node01"/>
        </Field>
        <Field label="BMC Type">
          <Select value={form.bmc_type}
            onChange={v => { set("bmc_type")(v); set("port")(defaultPort[v]||"443"); }}
            options={["ILO","IDRAC","CIMC","IPMI"]}/>
        </Field>
        <Field label="BMC IP Address *">
          <Input value={form.ip} onChange={set("ip")} placeholder="192.168.1.10" mono/>
        </Field>
        <Field label="Port">
          <Input value={form.port} onChange={set("port")} placeholder="443" mono/>
        </Field>
        <Field label="Username *">
          <Input value={form.username} onChange={set("username")} placeholder="Administrator"/>
        </Field>
        <Field label="Password *">
          <Input value={form.password} onChange={set("password")} type="password"/>
        </Field>
        <Field label="Description">
          <Input value={form.description} onChange={set("description")} placeholder="HPE ProLiant DL380 Gen10"/>
        </Field>
        <Field label="Location / Rack">
          <Input value={form.location} onChange={set("location")} placeholder="DC1 / Rack 3 / U12"/>
        </Field>
      </div>

      <div className="mt-4 flex gap-3 items-center">
        <Btn color="gray" size="sm" loading={testing} onClick={handleTest}>
          🔌 Test Connection
        </Btn>
        {testRes && (
          <span className={`text-sm ${testRes.success?"text-green-400":"text-red-400"}`}>
            {testRes.success ? "✓" : "✗"} {testRes.message}
          </span>
        )}
      </div>

      {testRes?.success && testRes.info && (
        <div className="mt-3 bg-gray-800 rounded-lg p-3 text-xs font-mono text-gray-300 grid grid-cols-2 gap-1">
          {Object.entries(testRes.info).filter(([,v])=>v).map(([k,v])=>(
            <div key={k}><span className="text-gray-500">{k}:</span> {v}</div>
          ))}
        </div>
      )}

      <div className="flex gap-3 justify-end mt-6">
        <Btn color="gray" onClick={onClose}>Cancel</Btn>
        <Btn loading={loading} onClick={submit}>Add Server</Btn>
      </div>
    </Modal>
  );
}

function EditServerModal({ api, server, onClose, onSuccess, onError }) {
  const [form, setForm] = useState({
    name: server.name, ip: server.ip, bmc_type: server.bmc_type,
    username: server.username || "", password: "",
    port: String(server.port||443), description: server.description||"",
    location: server.location||"", model: server.model||""
  });
  const [loading, setLoading] = useState(false);
  const set = k => v => setForm(f=>({...f,[k]:v}));

  const submit = async () => {
    setLoading(true);
    try {
      const data = {...form, port:parseInt(form.port)||443};
      if (!data.password) delete data.password;
      const s = await api.updateBMServer(server.id, data);
      onSuccess(s);
    } catch(e) { onError(e.message); }
    finally { setLoading(false); }
  };

  return (
    <Modal title={`Edit — ${server.name}`} onClose={onClose} wide>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Name"><Input value={form.name} onChange={set("name")}/></Field>
        <Field label="BMC Type">
          <Select value={form.bmc_type} onChange={set("bmc_type")}
            options={["ILO","IDRAC","CIMC","IPMI"]}/>
        </Field>
        <Field label="IP"><Input value={form.ip} onChange={set("ip")} mono/></Field>
        <Field label="Port"><Input value={form.port} onChange={set("port")} mono/></Field>
        <Field label="Username"><Input value={form.username} onChange={set("username")}/></Field>
        <Field label="Password (leave blank to keep)">
          <Input value={form.password} onChange={set("password")} type="password"
            placeholder="••••••••"/>
        </Field>
        <Field label="Description"><Input value={form.description} onChange={set("description")}/></Field>
        <Field label="Location"><Input value={form.location} onChange={set("location")}/></Field>
      </div>
      <div className="flex gap-3 justify-end mt-6">
        <Btn color="gray" onClick={onClose}>Cancel</Btn>
        <Btn loading={loading} onClick={submit}>Save Changes</Btn>
      </div>
    </Modal>
  );
}
