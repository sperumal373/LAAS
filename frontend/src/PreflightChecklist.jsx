import { useState, useEffect, useCallback } from "react";

async function _post(url, body) {
  const token = sessionStorage.getItem("caas_token") || localStorage.getItem("caas_token") || "";
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

/* ═══════════════════════════════════════════════════════════
   PLATFORM-SPECIFIC CHECKLISTS
═══════════════════════════════════════════════════════════ */

// VMware → OpenShift (MTV)
const CHECKLIST_OCP = [
  { id: "vmware_tools",     label: "VMware Tools Updated",                    category: "VMware Tools", cold: "req", warm: "req" },
  { id: "snapshots_clear",  label: "All Snapshots Deleted",                   category: "Disk",         cold: "req", warm: "req" },
  { id: "cbt_enabled",      label: "CBT Enabled (VM + Each Disk)",            category: "Disk",         cold: "na",  warm: "req" },
  { id: "hotplug_disabled", label: "CPU / Memory Hotplug Disabled",           category: "Firmware",     cold: "req", warm: "req" },
  { id: "no_rdm",           label: "No RDM / Shared / Independent Disks",     category: "Disk",         cold: "req", warm: "req" },
  { id: "no_usb_floppy_cd", label: "No USB / Floppy / CD Attached",           category: "Hardware",     cold: "req", warm: "req" },
  { id: "secure_boot_off",  label: "Secure Boot Disabled",                    category: "Firmware",     cold: "req", warm: "req" },
  { id: "virtio_drivers",   label: "VirtIO Drivers Installed (Windows)",      category: "Drivers",      cold: "req", warm: "req" },
  { id: "qemu_agent",       label: "QEMU Guest Agent Installed",              category: "Drivers",      cold: "req", warm: "req" },
  { id: "fstab_uuid",       label: "fstab Uses UUID (Linux)",                 category: "OS Config",    cold: "req", warm: "req" },
  { id: "network_mapped",   label: "Network Mapping Defined in MTV",          category: "Networking",   cold: "req", warm: "req" },
  { id: "vddk_configured",  label: "VDDK Configured in MTV",                  category: "MTV",          cold: "req", warm: "req" },
  { id: "ds_free_space",    label: "Datastore 15-20% Free Space",             category: "Storage",      cold: "rec", warm: "req" },
  { id: "app_stopped",      label: "App / DB Gracefully Stopped",             category: "Application",  cold: "req", warm: "na"  },
  { id: "bitlocker_off",    label: "BitLocker Disabled (Windows)",            category: "Security",     cold: "req", warm: "req" },
  { id: "console_ok",       label: "Console Access Verified",                 category: "Access",       cold: "req", warm: "req" },
];

// VMware → Nutanix AHV (Move)
const CHECKLIST_NUT = [
  { id: "snapshots_clear",  label: "All Snapshots Deleted",                           category: "Disk",         cold: "req", warm: "req" },
  { id: "no_rdm",           label: "No RDM / Shared / Independent Disks",             category: "Disk",         cold: "req", warm: "req" },
  { id: "vmware_tools",     label: "VMware Tools Updated",                            category: "VMware Tools", cold: "req", warm: "req" },
  { id: "no_usb_floppy_cd", label: "No ISO / CD / USB Attached",                      category: "Hardware",     cold: "req", warm: "req" },
  { id: "secure_boot_off",  label: "Secure Boot Disabled (if OS issue)",              category: "Firmware",     cold: "req", warm: "req" },
  { id: "nvme_disks",       label: "Remove NVMe Disks (if unsupported)",              category: "Disk",         cold: "req", warm: "req" },
  { id: "network_mapped",   label: "Network Mapping Defined (PortGroup → AHV)",  category: "Networking",   cold: "req", warm: "req" },
  { id: "nutanix_access",   label: "Nutanix Move / Prism Access Validated",           category: "Nutanix",      cold: "req", warm: "req" },
  { id: "ds_free_space",    label: "Adequate Storage Space Available",                category: "Storage",      cold: "req", warm: "req" },
  { id: "app_stopped",      label: "Application Stopped (consistency)",               category: "Application",  cold: "req", warm: "na"  },
];

// VMware → Microsoft Hyper-V
const CHECKLIST_HV = [
  { id: "snapshots_clear",  label: "All Snapshots Deleted",                           category: "Disk",         cold: "req", warm: "req" },
  { id: "no_rdm",           label: "No RDM / Shared Disks",                           category: "Disk",         cold: "req", warm: "req" },
  { id: "vmware_tools",     label: "VMware Tools Removed (before cutover)",           category: "VMware Tools", cold: "req", warm: "req" },
  { id: "disk_conversion",  label: "Disk Conversion Planned (VMDK → VHD/VDX)",   category: "Disk",         cold: "req", warm: "req" },
  { id: "bios_uefi_compat", label: "BIOS/UEFI Compatibility (Gen1/Gen2)",             category: "Firmware",     cold: "req", warm: "req" },
  { id: "no_usb_floppy_cd", label: "No ISO / CD Attached",                            category: "Hardware",     cold: "req", warm: "req" },
  { id: "network_mapped",   label: "Network Mapping (vSwitch) Defined",               category: "Networking",   cold: "req", warm: "req" },
  { id: "hyperv_access",    label: "Hyper-V / SCVMM Access Validated",                category: "Hyper-V",      cold: "req", warm: "req" },
  { id: "ds_free_space",    label: "Adequate Storage Space",                          category: "Storage",      cold: "req", warm: "req" },
  { id: "app_stopped",      label: "Application Stopped (consistency)",               category: "Application",  cold: "req", warm: "na"  },
];

// VMware → HPE VM Essentials
const CHECKLIST_HPE = [
  { id: "snapshots_clear",  label: "All Snapshots Deleted",                           category: "Disk",         cold: "req", warm: "req" },
  { id: "no_rdm",           label: "No RDM / Shared Disks",                           category: "Disk",         cold: "req", warm: "req" },
  { id: "vmware_tools",     label: "VMware Tools Updated (or removed if needed)",     category: "VMware Tools", cold: "req", warm: "req" },
  { id: "disk_conversion",  label: "Disk Conversion (VMDK → QCOW2/RAW)",          category: "Disk",         cold: "req", warm: "req" },
  { id: "virtio_drivers",   label: "VirtIO Drivers Installed (Windows)",              category: "Drivers",      cold: "req", warm: "req" },
  { id: "qemu_agent",       label: "QEMU Guest Agent Installed",                      category: "Drivers",      cold: "req", warm: "req" },
  { id: "no_usb_floppy_cd", label: "No ISO / CD Devices Attached",                   category: "Hardware",     cold: "req", warm: "req" },
  { id: "network_mapped",   label: "Network Mapping Defined",                         category: "Networking",   cold: "req", warm: "req" },
  { id: "hpe_access",       label: "HPE / Morpheus Platform Access Validated",        category: "HPE",          cold: "req", warm: "req" },
  { id: "app_stopped",      label: "Application Stopped (consistency)",               category: "Application",  cold: "req", warm: "na"  },
];

/* fix hints */
const HINTS = {
  vmware_tools:    "vCenter - right-click VM - Guest OS - Install/Upgrade VMware Tools.",
  snapshots_clear: "vSphere - right-click VM - Snapshots - Delete All Snapshots.",
  cbt_enabled:     "Power off VM - Edit Settings - VM Options - Advanced - Enable Changed Block Tracking.",
  hotplug_disabled:"Power off VM - Edit Settings - VM Options - Advanced - disable CPU/Memory Hot Add.",
  no_rdm:          "Convert RDM disks to VMDK. Remove independent disk mode before migration.",
  no_usb_floppy_cd:"Remove USB controllers, floppy drives, unmount CD-ROM in VM Edit Settings.",
  secure_boot_off: "Power off VM - Edit Settings - VM Options - Boot Options - uncheck Secure Boot.",
  virtio_drivers:  "Install VirtIO drivers ISO inside Windows VM, or use virt-v2v for injection.",
  qemu_agent:      "Linux: dnf install qemu-guest-agent. Then: systemctl enable --now qemu-guest-agent",
  fstab_uuid:      "Edit /etc/fstab: replace /dev/sdX with UUID=... format. Use blkid to find UUIDs.",
  network_mapped:  "Map VMware portgroup to target network in the migration tool (MTV / Nutanix Move).",
  vddk_configured: "MTV - Settings - VDDK - configure init image and vCenter credentials.",
  ds_free_space:   "Free up datastore space or expand datastore before migration.",
  app_stopped:     "Gracefully stop application/database services before cold migration.",
  bitlocker_off:   "Control Panel - BitLocker - Turn Off BitLocker. Wait for decryption to complete.",
  console_ok:      "Verify VM console access in vSphere and on the target platform post-migration.",
  nvme_disks:      "Check VM disk controller type. If NVMe, change to SCSI/SATA or remove disk before migration to AHV.",
  nutanix_access:  "Ensure Nutanix Move service is running and Prism Central/Element credentials are entered in the Move UI.",
  disk_conversion: "Use disk2vhd, MVMC, or Hyper-V migration tools to convert VMDK disks to VHD/VHDX before cutover.",
  bios_uefi_compat:"Check VM firmware: BIOS-based VMs map to Gen1 Hyper-V; UEFI-based VMs map to Gen2. Adjust Hyper-V VM generation accordingly.",
  hyperv_access:   "Verify Hyper-V host WinRM is enabled and SCVMM credentials are correctly configured in the migration plan.",
  hpe_access:      "Ensure HPE VM Essentials / Morpheus platform API credentials are configured and the migration agent can reach the HPE environment.",
};

/* platform config */
const PLATFORM_META = {
  openshift: {
    badge: "VMware • OpenShift / MTV",
    badgeColor: "#a78bfa", badgeBg: "#8b5cf620", badgeBd: "#8b5cf640",
    checklist: CHECKLIST_OCP,
  },
  nutanix: {
    badge: "VMware → Nutanix AHV",
    badgeColor: "#34d399", badgeBg: "#10b98120", badgeBd: "#10b98140",
    checklist: CHECKLIST_NUT,
  },
  hyperv: {
    badge: "VMware → Microsoft Hyper-V",
    badgeColor: "#60a5fa", badgeBg: "#2563eb20", badgeBd: "#2563eb40",
    checklist: CHECKLIST_HV,
  },
  hpevme: {
    badge: "VMware → HPE VM Essentials",
    badgeColor: "#fb923c", badgeBg: "#ea580c20", badgeBd: "#ea580c40",
    checklist: CHECKLIST_HPE,
  },
};

/* colours */
const C  = { pass: "#22c55e", fail: "#ef4444", warn: "#f59e0b", na: "#4b5563" };
const BG = { pass: "#16a34a20", fail: "#dc262620", warn: "#d9770620", na: "#00000000" };

const CAT_COLORS = {
  "VMware Tools": { bg: "#8b5cf620", fg: "#a78bfa" },
  "Disk":         { bg: "#0ea5e920", fg: "#38bdf8" },
  "Firmware":     { bg: "#f59e0b20", fg: "#fbbf24" },
  "Hardware":     { bg: "#6b728020", fg: "#9ca3af" },
  "Drivers":      { bg: "#10b98120", fg: "#34d399" },
  "OS Config":    { bg: "#3b82f620", fg: "#60a5fa" },
  "Networking":   { bg: "#0891b220", fg: "#22d3ee" },
  "MTV":          { bg: "#8b5cf620", fg: "#c084fc" },
  "Storage":      { bg: "#f9731620", fg: "#fb923c" },
  "Application":  { bg: "#ec489920", fg: "#f472b6" },
  "Security":     { bg: "#dc262620", fg: "#f87171" },
  "Access":       { bg: "#22c55e20", fg: "#4ade80" },
  "Nutanix":      { bg: "#10b98120", fg: "#34d399" },
  "Hyper-V":      { bg: "#2563eb20", fg: "#60a5fa" },
  "HPE":          { bg: "#ea580c20", fg: "#fb923c" },
};

/* ── small atoms ─────────────────────────────────────────── */
function ReqBadge({ req }) {
  if (req === "na") return <span style={{ fontSize: 11, color: "#4b5563", fontStyle: "italic" }}>N/A</span>;
  if (req === "rec") return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 3, fontSize: 11, fontWeight: 700,
      color: "#f59e0b", background: "#d9770618", border: "1px solid #f59e0b40", borderRadius: 20, padding: "3px 9px",
    }}>
      &#9733; REC
    </span>
  );
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 3, fontSize: 11, fontWeight: 700,
      color: "#22c55e", background: "#16a34a18", border: "1px solid #22c55e40", borderRadius: 20, padding: "3px 9px",
    }}>
      &#10003; REQ
    </span>
  );
}

function ResultBadge({ status, onClick }) {
  const col = C[status] || C.na;
  const bg  = BG[status] || BG.na;
  if (status === "na") return <span style={{ fontSize: 11, color: "#4b5563", fontStyle: "italic" }}>N/A</span>;
  const icon = status === "pass" ? "✓" : status === "fail" ? "✕" : "⚠";
  const lbl  = status === "pass" ? "PASS" : status === "fail" ? "FAIL" : "WARN";
  return (
    <span onClick={onClick} style={{
      display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, fontWeight: 700,
      color: col, background: bg, border: `1px solid ${col}50`, borderRadius: 20, padding: "3px 10px",
      cursor: onClick ? "pointer" : "default", userSelect: "none",
    }}>
      {icon} {lbl}{onClick && <span style={{ fontSize: 9, opacity: 0.7 }}> i</span>}
    </span>
  );
}

function CatBadge({ cat }) {
  const cc = CAT_COLORS[cat] || { bg: "#37415120", fg: "#9ca3af" };
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, color: cc.fg, background: cc.bg,
      border: `1px solid ${cc.fg}30`, borderRadius: 12, padding: "2px 8px", whiteSpace: "nowrap",
    }}>
      {cat}
    </span>
  );
}

/* ── detail modal ────────────────────────────────────────── */
function Modal({ checkId, vm, mode, checklist, onClose }) {
  const cl     = checklist.find(c => c.id === checkId);
  const chk    = vm?.checks?.[checkId] || {};
  const status = chk[mode] || "na";
  const col    = C[status];
  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "#000000bb", zIndex: 9999,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: "#1a1d2e", border: "1px solid #374151", borderRadius: 16,
        padding: 28, maxWidth: 500, width: "90%", color: "#e2e8f0",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: col }}>
            {status === "pass" ? "✓" : status === "fail" ? "✕" : "⚠"} {cl?.label || checkId}
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#6b7280", fontSize: 22, cursor: "pointer" }}>
            &times;
          </button>
        </div>
        <div style={{
          background: BG[status], border: `1px solid ${col}33`, borderRadius: 10,
          padding: "12px 16px", marginBottom: 14, fontSize: 13, color: "#d1d5db", lineHeight: 1.6,
        }}>
          {chk.detail || "No detail available."}
        </div>
        <div style={{ fontSize: 11, color: "#6b7280" }}>
          <b>VM:</b> {vm?.vm_name} &nbsp;|&nbsp; <b>OS:</b> {vm?.guest_os || "Unknown"} &nbsp;|&nbsp;
          <b>Mode:</b> {mode === "warm" ? "Warm" : "Cold"}
        </div>
        {(status === "fail" || status === "warn") && (
          <div style={{ marginTop: 14, borderTop: "1px solid #374151", paddingTop: 12 }}>
            <div style={{ color: "#f59e0b", fontWeight: 700, fontSize: 12, marginBottom: 6 }}>How to fix:</div>
            <div style={{ fontSize: 12, color: "#9ca3af", lineHeight: 1.7 }}>
              {HINTS[checkId] || "Refer to migration tool documentation."}
            </div>
          </div>
        )}
        <div style={{ textAlign: "right", marginTop: 16 }}>
          <button onClick={onClose} style={{
            background: "#374151", border: "none", borderRadius: 8,
            padding: "8px 20px", color: "#e2e8f0", cursor: "pointer",
          }}>Close</button>
        </div>
      </div>
    </div>
  );
}

/* ── per-VM card ─────────────────────────────────────────── */
function VMCard({ vmIdx, vm, mode, checklist, p, defaultOpen, isExcluded, toggleExclude }) {
  const [open,  setOpen]  = useState(defaultOpen);
  const [modal, setModal] = useState(null);

  const sf   = vm.score_fail  || 0;
  const sw   = vm.score_warn  || 0;
  const sp   = vm.score_pass  || 0;
  const st   = vm.score_total || 0;
  const sexc = vm.score_excl  || 0;

  const borderLeft = sf > 0 ? "3px solid #ef4444" : sw > 0 ? "3px solid #f59e0b" : "3px solid #22c55e";
  const headerBg   = sf > 0 ? "#dc262610" : sw > 0 ? "#d9770610" : "#16a34a10";
  const statusIcon = sf > 0
    ? <span style={{ color: "#ef4444", fontSize: 22 }}>&#10005;</span>
    : sw > 0
      ? <span style={{ color: "#f59e0b", fontSize: 20 }}>&#9888;</span>
      : <span style={{ color: "#22c55e", fontSize: 20 }}>&#10003;</span>;

  const TH = {
    padding: "8px 14px", fontSize: 10, fontWeight: 700, color: "#6b7280",
    textTransform: "uppercase", letterSpacing: ".6px", background: "#0d1117",
    borderBottom: "1px solid #1f2937", textAlign: "center",
  };
  const TD = {
    padding: "9px 14px", fontSize: 12,
    borderBottom: "1px solid #1f293740", verticalAlign: "middle", textAlign: "center",
  };

  return (
    <div style={{ background: "#111827", border: "1px solid #1f2937", borderLeft, borderRadius: 12, marginBottom: 12, overflow: "hidden" }}>
      <div onClick={() => setOpen(o => !o)} style={{ display: "flex", alignItems: "center", gap: 14, padding: "12px 18px", cursor: "pointer", background: headerBg }}>
        {statusIcon}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 800, fontSize: 14, color: "#e2e8f0" }}>{vm.vm_name}</div>
          <div style={{ fontSize: 11, color: "#6b7280", marginTop: 2 }}>
            {vm.guest_os || "Unknown"} &nbsp;&middot;&nbsp;
            {vm.num_cpu || "-"} vCPU &nbsp;&middot;&nbsp;
            {vm.mem_mb ? Math.round(vm.mem_mb / 1024) + " GB RAM" : "-"} &nbsp;&middot;&nbsp;
            <span style={{ color: vm.power_on ? "#22c55e" : "#6b7280", fontWeight: 700 }}>
              {vm.power_on ? "Powered ON" : "Powered OFF"}
            </span>
            {mode === "warm" && <span style={{ marginLeft: 6, color: "#f97316", fontWeight: 700 }}> Warm</span>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: "#9ca3af" }}>{sp}/{st}</span>
          {sf > 0 && (
            <span style={{ fontSize: 11, fontWeight: 700, color: "#ef4444", background: "#dc262620", border: "1px solid #ef444440", borderRadius: 20, padding: "3px 10px" }}>
              {sf} FAIL
            </span>
          )}
          {sw > 0 && (
            <span style={{ fontSize: 11, fontWeight: 700, color: "#f59e0b", background: "#d9770620", border: "1px solid #f59e0b40", borderRadius: 20, padding: "3px 10px" }}>
              {sw} WARN
            </span>
          )}
        </div>
        <span style={{ color: "#4b5563", fontSize: 14, marginLeft: 4 }}>{open ? "▲" : "▼"}</span>
      </div>

      {open && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 560 }}>
            <thead>
              <tr>
                <th style={{ ...TH, textAlign: "left", minWidth: 260, paddingLeft: 18 }}>Check Item</th>
                <th style={{ ...TH, minWidth: 110 }}>Category</th>
                <th style={{ ...TH, minWidth: 82 }}>Cold</th>
                <th style={{ ...TH, minWidth: 82 }}>Warm</th>
                <th style={{ ...TH, minWidth: 90, color: "#6b7280" }}>Exclude</th>
                <th style={{ ...TH, minWidth: 130, color: "#e2e8f0" }}>Result ({mode === "warm" ? "Warm" : "Cold"})</th>
              </tr>
            </thead>
            <tbody>
              {checklist.map((cl, ri) => {
                const chk    = vm.checks?.[cl.id] || {};
                const status = chk[mode] || "na";
                const excl   = isExcluded(vmIdx, cl.id);
                return (
                  <tr key={cl.id} style={{ background: ri % 2 === 0 ? "transparent" : "#0d111740", opacity: excl ? 0.45 : 1, transition: "opacity .2s" }}>
                    <td style={{ ...TD, textAlign: "left", fontWeight: 600, color: excl ? "#4b5563" : "#d1d5db", paddingLeft: 18, textDecoration: excl ? "line-through" : "none" }}>
                      {cl.label}
                    </td>
                    <td style={TD}><CatBadge cat={cl.category} /></td>
                    <td style={TD}><ReqBadge req={cl.cold} /></td>
                    <td style={TD}><ReqBadge req={cl.warm} /></td>
                    <td style={TD}>
                      {(status === "fail" || status === "warn" || isExcluded(vmIdx, cl.id)) ? (
                        <button
                          onClick={() => toggleExclude(vmIdx, cl.id)}
                          title={isExcluded(vmIdx, cl.id) ? "Click to re-include this check" : "Click to exclude this check from blocking"}
                          style={{
                            fontSize: 10, fontWeight: 700, padding: "3px 9px", borderRadius: 20, cursor: "pointer",
                            border: "1px solid " + (isExcluded(vmIdx, cl.id) ? "#4b5563" : "#6b7280"),
                            background: isExcluded(vmIdx, cl.id) ? "#37415130" : "transparent",
                            color: isExcluded(vmIdx, cl.id) ? "#9ca3af" : "#6b7280",
                            transition: "all .15s",
                          }}
                        >
                          {isExcluded(vmIdx, cl.id) ? "+ Include" : "- Exclude"}
                        </button>
                      ) : <span style={{ color: "#2d3748", fontSize: 11 }}>—</span>}
                    </td>
                    <td style={{ ...TD, opacity: isExcluded(vmIdx, cl.id) ? 0.35 : 1 }}>
                      {isExcluded(vmIdx, cl.id)
                        ? <span style={{ fontSize: 11, fontWeight: 700, color: "#4b5563", background: "#37415120", border: "1px solid #4b556340", borderRadius: 20, padding: "3px 10px", textDecoration: "line-through" }}>EXCL</span>
                        : <ResultBadge status={status} onClick={(status === "fail" || status === "warn") ? () => setModal(cl.id) : null} />}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {modal && <Modal checkId={modal} vm={vm} mode={mode} checklist={checklist} onClose={() => setModal(null)} />}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   MAIN EXPORT
═══════════════════════════════════════════════════════════ */
export default function PreflightChecklist({ selectedVMList, targetPlatform, migWarm, targetDetail, p, onBack, onContinue }) {
  const [loading,  setLoading]  = useState(false);
  const [results,  setResults]  = useState([]);
  const [error,    setError]    = useState(null);
  // excluded: { "vmIdx:checkId": true } — per-VM per-check exclusions
  const [excluded, setExcluded] = useState({});

  const meta      = PLATFORM_META[targetPlatform];
  const checklist = meta?.checklist || CHECKLIST_OCP;
  const mode      = migWarm ? "warm" : "cold";
  const vcenter_id = selectedVMList?.[0]?.vcenter_id || selectedVMList?.[0]?.vcenter || "";
  const vm_names   = (selectedVMList || []).map(v => v.name);

  const toggleExclude = (vmIdx, checkId) => {
    const key = `${vmIdx}:${checkId}`;
    setExcluded(prev => ({ ...prev, [key]: !prev[key] }));
  };
  const isExcluded = (vmIdx, checkId) => !!excluded[`${vmIdx}:${checkId}`];

  const runChecks = useCallback(() => {
    if (!vcenter_id || !vm_names.length) return;
    setLoading(true);
    setError(null);
    setExcluded({});  // reset exclusions on re-run
    _post("/api/migration/preflight/live", { vcenter_id, vm_names, warm: migWarm, target_platform: targetPlatform })
      .then(r => setResults(r.results || []))
      .catch(e => setError(e?.message || "Pre-flight check failed"))
      .finally(() => setLoading(false));
  }, [vcenter_id, vm_names.join(","), migWarm, targetPlatform]);

  useEffect(() => { runChecks(); }, [runChecks]);

  /* ── unsupported platform: just let them continue ── */
  if (!meta) return (
    <div style={{ background: "#111827", borderRadius: 14, border: "1px solid #1f2937", padding: 32 }}>
      <div style={{ fontSize: 16, fontWeight: 800, color: "#e2e8f0", marginBottom: 8 }}>Pre-flight Assessment</div>
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 24 }}>
        Automated pre-flight checks are not available for{" "}
        <b style={{ color: "#e2e8f0" }}>{targetPlatform || "this platform"}</b>.
        Please complete your manual checklist before proceeding.
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <button onClick={onBack} style={{ padding: "10px 22px", borderRadius: 10, border: "1px solid #374151", background: "none", color: "#e2e8f0", cursor: "pointer", fontSize: 13 }}>
          Back
        </button>
        <button onClick={onContinue} style={{ padding: "10px 24px", borderRadius: 10, border: "none", background: p.accent, color: "#fff", cursor: "pointer", fontSize: 13, fontWeight: 700 }}>
          Continue to Mapping
        </button>
      </div>
    </div>
  );

  /* compute platform-scoped scores — skips excluded checks */
  function platformScore(vm, vmIdx) {
    if (vm.error) return { sp: 0, sf: 0, sw: 0, st: 0, excl: 0 };
    let sp = 0, sf = 0, sw = 0, st = 0, excl = 0;
    checklist.forEach(cl => {
      const status = vm.checks?.[cl.id]?.[mode] || "na";
      if (status === "na") return;
      if (isExcluded(vmIdx, cl.id)) { excl++; return; }
      st++;
      if (status === "pass") sp++;
      else if (status === "fail") sf++;
      else if (status === "warn") sw++;
    });
    return { sp, sf, sw, st, excl };
  }

  const gPass    = results.reduce((s, r, i) => s + platformScore(r, i).sp, 0);
  const gFail    = results.reduce((s, r, i) => s + platformScore(r, i).sf, 0);
  const gWarn    = results.reduce((s, r, i) => s + platformScore(r, i).sw, 0);
  const gExcl    = results.reduce((s, r, i) => s + platformScore(r, i).excl, 0);
  const blocking = gFail > 0;

  function downloadReport() {
    const title = targetPlatform === "nutanix" ? "VMware to Nutanix AHV" : "VMware to OpenShift";
    let txt = title + " Pre-flight Report\n";
    txt += "Generated: " + new Date().toLocaleString() + "\n";
    txt += "Mode: " + mode.toUpperCase() + " | VMs: " + results.length + "\n\n";
    results.forEach((vm, vi) => {
      const sc = platformScore(vm, vi);
      txt += "VM: " + vm.vm_name + "\n  OS: " + (vm.guest_os || "Unknown") + " | Power: " + (vm.power_on ? "ON" : "OFF") + "\n";
      if (vm.error) { txt += "  ERROR: " + vm.error + "\n"; }
      else {
        txt += "  Score: " + sc.sp + "/" + sc.st + " (Fail:" + sc.sf + " Warn:" + sc.sw + ")\n";
        checklist.forEach(cl => {
          const st2 = vm.checks?.[cl.id]?.[mode] || "na";
          const excTag = isExcluded(vi, cl.id) ? " [EXCLUDED]" : "";
          txt += "  [" + (st2 === "pass" ? "PASS" : st2 === "fail" ? "FAIL" : st2 === "warn" ? "WARN" : "N/A ") + excTag + "] " + cl.label + "\n";
          if (st2 !== "pass" && st2 !== "na" && vm.checks?.[cl.id]?.detail && !isExcluded(vi, cl.id))
            txt += "       " + vm.checks[cl.id].detail + "\n";
        });
      }
      txt += "\n";
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([txt], { type: "text/plain" }));
    a.download = "preflight_" + targetPlatform + "_" + Date.now() + ".txt";
    a.click();
  }

  /* ── loading ── */
  if (loading) return (
    <div style={{ background: "#111827", borderRadius: 14, border: "1px solid #1f2937", padding: 32 }}>
      <div style={{ fontSize: 16, fontWeight: 800, color: "#e2e8f0", marginBottom: 16 }}>Pre-Flight Checklist</div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, color: "#6b7280", fontSize: 13 }}>
        <div style={{
          width: 18, height: 18, border: "3px solid " + p.accent, borderTopColor: "transparent",
          borderRadius: "50%", animation: "spin 1s linear infinite",
        }} />
        Connecting to vCenter and running checks on {vm_names.length} VM{vm_names.length !== 1 ? "s" : ""}...
      </div>
      <style>{"@keyframes spin{to{transform:rotate(360deg)}}"}</style>
    </div>
  );

  /* ── error ── */
  if (error) return (
    <div style={{ background: "#111827", borderRadius: 14, border: "1px solid #1f2937", padding: 28 }}>
      <div style={{ fontSize: 16, fontWeight: 800, color: "#e2e8f0", marginBottom: 14 }}>Pre-Flight Checklist</div>
      <div style={{ padding: 14, borderRadius: 10, background: "#dc262618", border: "1px solid #dc262640", color: "#ef4444", fontSize: 13, marginBottom: 16 }}>
        Error: {error}
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <button onClick={onBack} style={{ padding: "9px 20px", borderRadius: 9, border: "1px solid #374151", background: "none", color: "#e2e8f0", cursor: "pointer" }}>Back</button>
        <button onClick={runChecks} style={{ padding: "9px 18px", borderRadius: 9, border: "none", background: p.accent, color: "#fff", cursor: "pointer" }}>Retry</button>
      </div>
    </div>
  );

  const vmCount = results.length;

  return (
    <div>
      {/* ── header bar ── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12,
        background: "#0d1117", border: "1px solid #1f2937", borderRadius: 14, padding: "14px 22px", marginBottom: 14,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <div style={{ fontSize: 18, fontWeight: 900, color: "#e2e8f0" }}>Pre-Flight Checklist</div>
          <span style={{
            fontSize: 11, fontWeight: 700, color: meta.badgeColor,
            background: meta.badgeBg, border: `1px solid ${meta.badgeBd}`, borderRadius: 20, padding: "4px 12px",
          }}>
            {meta.badge}
          </span>
          <span style={{ fontSize: 12, color: "#6b7280" }}>{vmCount} VM{vmCount !== 1 ? "s" : ""}</span>
          {migWarm
            ? <span style={{ fontSize: 12, fontWeight: 700, color: "#f97316" }}>Warm</span>
            : <span style={{ fontSize: 12, fontWeight: 700, color: "#38bdf8" }}>Cold</span>}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={runChecks} style={{ padding: "8px 16px", borderRadius: 9, border: "1px solid #374151", background: "none", color: "#e2e8f0", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
            Re-run
          </button>
          <button onClick={downloadReport} style={{ padding: "8px 16px", borderRadius: 9, border: "none", background: "#16a34a", color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
            Download Report
          </button>
        </div>
      </div>

      {/* ── overall status card ── */}
      {results.length > 0 && (
        <div style={{ display: "flex", gap: 10, alignItems: "stretch", marginBottom: 14, flexWrap: "wrap" }}>
          <div style={{
            flex: "1 1 300px", display: "flex", alignItems: "center", gap: 20, padding: "20px 26px",
            background: blocking ? "#dc262612" : "#16a34a12",
            border: `1px solid ${blocking ? "#ef444440" : "#22c55e40"}`, borderRadius: 14,
          }}>
            <div style={{ fontSize: 48, lineHeight: 1 }}>
              {blocking
                ? <span style={{ color: "#ef4444" }}>&#10007;</span>
                : <span style={{ color: "#22c55e" }}>&#10003;</span>}
            </div>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: "#6b7280", letterSpacing: 1, marginBottom: 4 }}>OVERALL STATUS</div>
              <div style={{ fontSize: 24, fontWeight: 900, color: blocking ? "#ef4444" : "#22c55e" }}>
                {blocking ? "NOT READY" : "READY"}
              </div>
              <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 3 }}>
                {blocking
                  ? `${gFail} required check${gFail !== 1 ? "s" : ""} failing`
                  : gWarn > 0 ? `${gWarn} warning${gWarn !== 1 ? "s" : ""} to review` : "All checks passed"}
              </div>
            </div>
          </div>
          {[
            { label: "PASSED",   val: gPass, col: "#22c55e", bg: "#16a34a20", bd: "#22c55e40" },
            { label: "FAILED",   val: gFail, col: "#ef4444", bg: "#dc262620", bd: "#ef444440" },
            { label: "WARNINGS", val: gWarn, col: "#f59e0b", bg: "#d9770620", bd: "#f59e0b40" },
            { label: "EXCLUDED", val: gExcl, col: "#6b7280", bg: "#37415120", bd: "#4b556340" },
          ].map(s => (
            <div key={s.label} style={{
              flex: "0 0 120px", display: "flex", flexDirection: "column", alignItems: "center",
              justifyContent: "center", background: s.bg, border: `1px solid ${s.bd}`, borderRadius: 14, padding: "18px 10px",
            }}>
              <div style={{ fontSize: 36, fontWeight: 900, color: s.col, lineHeight: 1 }}>{s.val}</div>
              <div style={{ fontSize: 10, fontWeight: 700, color: s.col, marginTop: 5, letterSpacing: 0.8 }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── per-VM cards ── */}
      {results.map((vm, i) => {
        if (vm.error) return (
          <div key={i} style={{
            background: "#111827", border: "1px solid #dc262640",
            borderLeft: "3px solid #ef4444", borderRadius: 12, padding: "14px 18px", marginBottom: 12,
          }}>
            <span style={{ color: "#ef4444", fontWeight: 700 }}>{vm.vm_name}</span>
            <span style={{ color: "#9ca3af", marginLeft: 10, fontSize: 12 }}>Error: {vm.error}</span>
          </div>
        );
        const sc = platformScore(vm, i);
        const vmS = { ...vm, score_pass: sc.sp, score_fail: sc.sf, score_warn: sc.sw, score_total: sc.st, score_excl: sc.excl };
        return <VMCard key={i} vmIdx={i} vm={vmS} mode={mode} checklist={checklist} p={p} defaultOpen={results.length === 1} isExcluded={isExcluded} toggleExclude={toggleExclude} />;
      })}

      {/* ── bottom nav ── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
        <button onClick={onBack} style={{ padding: "10px 22px", borderRadius: 10, border: "1px solid #374151", background: "none", color: "#e2e8f0", cursor: "pointer", fontSize: 13 }}>
          Back
        </button>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {blocking && (
            <span style={{ fontSize: 12, color: "#ef4444", fontWeight: 700 }}>
              {gFail} blocking issue{gFail !== 1 ? "s" : ""} - fix before proceeding
            </span>
          )}
          <button
            onClick={blocking ? undefined : onContinue}
            disabled={blocking}
            style={{
              padding: "10px 26px", borderRadius: 10, border: "none", fontSize: 13, fontWeight: 700,
              background: blocking ? "#374151" : p.accent,
              color: blocking ? "#6b7280" : "#fff",
              cursor: blocking ? "not-allowed" : "pointer",
              opacity: blocking ? 0.6 : 1,
            }}
          >
            {blocking ? "Blocked - fix issues" : "Continue to Mapping"}
          </button>
        </div>
      </div>
    </div>
  );
}
