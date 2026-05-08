"""
compliance_rules.py  --  COE Compliance Scoring Engine  v2
===========================================================
9 toggleable compliance rules based on:
  - CIS Benchmarks (patching, AV, uptime)
  - VMware HCL best practices (Tools, HW version, snapshots)
  - COE operational standards (EOL OS, resource ratios, uptime)

Each rule has:
  - id          : unique key (used in toggle config)
  - weight      : contribution to 0-100 score
  - default_on  : enabled by default

Status thresholds:
  score >= 80  → compliant     (green)
  score 50-79  → warning       (yellow)
  score  < 50  → non_compliant (red)
"""

from datetime import datetime, timezone
import re

# ── All rules catalogue (shown in UI for toggle) ────────────────────────────
ALL_RULES = [
    {
        "id": "eol_os", "label": "EOL Operating System", "icon": "💀",
        "weight": 20, "default_on": True, "category": "Security",
        "description": "Detects end-of-life OSes (Win2012, RHEL5/6, CentOS 6/7, Ubuntu 16/18) that no longer receive vendor security patches.",
        "green": "Supported OS", "yellow": "OS info unavailable", "red": "EOL OS — no vendor patches",
    },
    {
        "id": "os_patch_age", "label": "OS Patch Currency", "icon": "🔄",
        "weight": 20, "default_on": True, "category": "Patching",
        "description": "Days since last OS patch/reboot. Uses SSH (Linux) or WinRM (Windows) for last-patch date; falls back to vCenter boot time.",
        "green": "Patched ≤ 30 days", "yellow": "31–90 days", "red": "> 90 days — critical SLA breach",
    },
    {
        "id": "uptime", "label": "System Uptime", "icon": "⏱️",
        "weight": 10, "default_on": True, "category": "Availability",
        "description": "Very long uptime (> 180 days) means patches are not applied via reboots. Retrieved via SSH/WinRM or vCenter boot time.",
        "green": "1–180 days", "yellow": "181–365 days (reboot overdue)", "red": "> 365 days or < 1 day",
    },
    {
        "id": "vmware_tools", "label": "VMware Tools Version", "icon": "🔧",
        "weight": 12, "default_on": True, "category": "VMware",
        "description": "Outdated/missing VMware Tools causes degraded performance, failed snapshots and broken guest OS operations.",
        "green": "Current (toolsOk)", "yellow": "Outdated (toolsOld)", "red": "Not installed",
    },
    {
        "id": "hw_version", "label": "VM Hardware Version", "icon": "🖥️",
        "weight": 8, "default_on": True, "category": "VMware",
        "description": "Old HW versions miss CPU security mitigations (Spectre/Meltdown), vTPM support and vNVMe storage capabilities.",
        "green": "vmx-19+", "yellow": "vmx-17/18", "red": "vmx-16 or older",
    },
    {
        "id": "snapshot_age", "label": "Snapshot Age", "icon": "📸",
        "weight": 10, "default_on": True, "category": "VMware",
        "description": "Stale snapshots degrade VM performance, consume storage and block storage vMotion. Best practice: no snapshots > 7 days in prod.",
        "green": "None or ≤ 7 days", "yellow": "8–30 days", "red": "> 30 days — must delete",
    },
    {
        "id": "cpu_ratio", "label": "vCPU:pCPU Overcommit", "icon": "⚙️",
        "weight": 5, "default_on": True, "category": "Performance",
        "description": "High vCPU:pCPU ratio causes CPU ready latency. VMware recommended limit: 4:1 per core; hard ceiling 8:1.",
        "green": "≤ 4:1", "yellow": "4:1 – 8:1", "red": "> 8:1",
    },
    {
        "id": "power_state", "label": "Power State / Ghost VMs", "icon": "🔌",
        "weight": 5, "default_on": True, "category": "Inventory",
        "description": "Powered-off VMs are potential ghost assets consuming storage. Suspended VMs block vMotion.",
        "green": "Powered On", "yellow": "Powered Off > 30 days", "red": "Suspended",
    },
    {
        "id": "antivirus", "label": "Antivirus / EDR Agent", "icon": "🛡️",
        "weight": 10, "default_on": True, "category": "Security",
        "description": "Checks for AV/EDR via SSH (Linux: CrowdStrike/Defender/Trend) or WinRM (Windows services). Partial credit if unreachable.",
        "green": "AV/EDR detected", "yellow": "Status unknown", "red": "No AV/EDR found",
    },
    {
        "id": "disk_space", "label": "Disk Space Utilisation", "icon": "💾",
        "weight": 8, "default_on": True, "category": "Capacity",
        "description": "High disk utilisation risks application crashes and failed patch installs. Threshold: warn ≥ 80 %, critical ≥ 90 %.",
        "green": "< 80 % used", "yellow": "80–90 % used", "red": "> 90 % used — critical",
    },
]

EOL_OS_PATTERNS = [
    r"windows server 2003", r"windows server 2008", r"windows server 2012",
    r"windows xp", r"windows 7", r"windows 8\.?1?",
    r"red hat.*release [45]", r"rhel [45]",
    r"centos [567]", r"centos linux [567]",
    r"ubuntu 1[04]\.", r"ubuntu 16\.", r"ubuntu 18\.",
    r"suse.*11\.", r"debian [789]\.", r"oracle linux [56]",
]
TOOLS_OK = {"toolsOk", "guestToolsCurrent", "toolsCurrent"}


def _now():
    return datetime.now(timezone.utc)


def _is_eol(os_str):
    s = (os_str or "").lower()
    return any(re.search(p, s) for p in EOL_OS_PATTERNS)


def _days_from_iso(iso_str):
    if not iso_str:
        return None
    try:
        s = iso_str
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (_now() - dt).days
    except Exception:
        return None


def score_asset(asset: dict, enabled_checks: list = None) -> dict:
    """
    Score a single asset against enabled compliance rules.

    asset keys (all optional except hostname/asset_type):
      hostname, ip_address, os_name, asset_type (vm|baremetal),
      vcenter, cpu_count, host_pcpu_count, power_state,
      tools_status, hw_version, last_boot (ISO), last_patch (ISO),
      uptime_days (int), snapshot_age_days (int), av_present (bool|None)

    enabled_checks: list of rule ids. None = all default_on rules.
    """
    if enabled_checks is None:
        active = {r["id"] for r in ALL_RULES if r["default_on"]}
    else:
        active = set(enabled_checks)

    rule_map    = {r["id"]: r for r in ALL_RULES}
    active_rules = [r for r in ALL_RULES if r["id"] in active]
    total_weight = sum(r["weight"] for r in active_rules) or 1

    checks = []
    earned = 0

    os_str   = (asset.get("os_name") or "").strip()
    tools_st = asset.get("tools_status") or ""
    hw_ver   = asset.get("hw_version") or ""
    snap_age = asset.get("snapshot_age_days")
    vcpu     = asset.get("cpu_count") or 0
    pcpu     = asset.get("host_pcpu_count") or 0
    power    = (asset.get("power_state") or "").lower()
    av       = asset.get("av_present")
    atype    = asset.get("asset_type", "vm")
    uptime   = asset.get("uptime_days")

    # patch_age: ONLY from actual SSH/WinRM last_patch date — never from boot time
    # boot time ≠ patch time (live-kernel patches, Windows updates don't always reboot, etc.)
    last_patch_str = asset.get("last_patch")   # set only when SSH/WinRM succeeded
    patch_age_days = _days_from_iso(last_patch_str) if last_patch_str else None
    ssh_succeeded  = bool(last_patch_str)       # True = we have real patch data

    missing_patches = asset.get("missing_patches") or 0  # set only via SSH

    def _add(rule_id, status, msg, frac=1.0):
        r = rule_map.get(rule_id, {})
        w = r.get("weight", 0)
        norm_w = round(w / total_weight * 100)
        pts = round(norm_w * frac)
        checks.append({
            "name": rule_id, "label": r.get("label", rule_id),
            "status": status, "weight": norm_w, "earned": pts, "message": msg,
        })
        return pts

    # 1. EOL OS
    if "eol_os" in active:
        eol = _is_eol(os_str)
        if eol:
            earned += _add("eol_os", "non_compliant", f"EOL OS: {os_str}")
        elif not os_str:
            earned += _add("eol_os", "warning", "OS info unavailable", 0.5)
        else:
            earned += _add("eol_os", "compliant", f"Supported OS: {os_str}")
    else:
        eol = False

    # 2. Patch Currency — only scored when SSH/WinRM data is available
    if "os_patch_age" in active:
        if not ssh_succeeded:
            # No SSH data — cannot determine patch status, mark warning (not non-compliant)
            earned += _add("os_patch_age", "warning",
                           "Patch date unknown — enable SSH/WinRM scan for accurate data", 0.7)
        elif patch_age_days is None:
            earned += _add("os_patch_age", "warning", "Patch date unavailable (SSH returned no data)", 0.6)
        elif patch_age_days <= 30:
            earned += _add("os_patch_age", "compliant", f"Patched {patch_age_days}d ago ✓")
        elif patch_age_days <= 90:
            earned += _add("os_patch_age", "warning",
                           f"{patch_age_days}d since last patch — exceeds 30d recommended SLA", 0.6)
        else:
            earned += _add("os_patch_age", "non_compliant",
                           f"CRITICAL: {patch_age_days}d since last patch — exceeds 90d compliance limit")

    # 3. Uptime — purely about system stability, NOT about patching
    if "uptime" in active:
        if power == "poweredoff":
            earned += _add("uptime", "warning", "VM is powered off — uptime unavailable", 0.8)
        elif uptime is None:
            earned += _add("uptime", "warning", "Uptime unavailable — SSH/WinRM or vCenter data missing", 0.7)
        elif uptime < 1:
            earned += _add("uptime", "warning", "Uptime < 1d — VM recently rebooted or unstable", 0.7)
        elif uptime <= 180:
            earned += _add("uptime", "compliant", f"Uptime {uptime}d — healthy")
        elif uptime <= 365:
            earned += _add("uptime", "warning", f"Uptime {uptime}d — approaching 1 year without reboot", 0.6)
        else:
            earned += _add("uptime", "non_compliant",
                           f"CRITICAL: Uptime {uptime}d — over 1 year without reboot")

    # 4. VMware Tools
    if "vmware_tools" in active:
        if atype == "baremetal":
            earned += _add("vmware_tools", "compliant", "N/A — baremetal")
        elif not tools_st:
            earned += _add("vmware_tools", "warning", "VMware Tools status unknown", 0.5)
        elif tools_st in TOOLS_OK:
            earned += _add("vmware_tools", "compliant", f"VMware Tools current ({tools_st})")
        elif tools_st == "toolsOld":
            earned += _add("vmware_tools", "warning", "VMware Tools outdated — update recommended", 0.7)
        elif tools_st == "toolsNotInstalled":
            earned += _add("vmware_tools", "non_compliant", "VMware Tools NOT installed")
        else:
            earned += _add("vmware_tools", "warning", f"VMware Tools status: {tools_st}", 0.5)

    # 5. HW Version
    if "hw_version" in active:
        if atype == "baremetal":
            earned += _add("hw_version", "compliant", "N/A — baremetal")
        else:
            hw_num = 0
            m = re.search(r"vmx-(\d+)", hw_ver, re.IGNORECASE)
            if m:
                hw_num = int(m.group(1))
            if hw_num == 0:
                earned += _add("hw_version", "warning", "HW version undetermined", 0.6)
            elif hw_num >= 19:
                earned += _add("hw_version", "compliant", f"vmx-{hw_num} — current")
            elif hw_num >= 17:
                earned += _add("hw_version", "warning", f"vmx-{hw_num} — update to vmx-19+ recommended", 0.7)
            else:
                earned += _add("hw_version", "non_compliant", f"vmx-{hw_num} — significantly outdated")

    # 6. Snapshot Age
    if "snapshot_age" in active:
        if snap_age is None:
            earned += _add("snapshot_age", "compliant", "No snapshots present")
        elif snap_age <= 7:
            earned += _add("snapshot_age", "compliant", f"Snapshot {snap_age}d old — within 7d best practice")
        elif snap_age <= 30:
            earned += _add("snapshot_age", "warning", f"Snapshot {snap_age}d old — exceeds 7d best practice", 0.5)
        else:
            earned += _add("snapshot_age", "non_compliant", f"CRITICAL: Snapshot {snap_age}d old — delete immediately")

    # 7. CPU Ratio
    if "cpu_ratio" in active:
        if vcpu == 0 or pcpu == 0:
            earned += _add("cpu_ratio", "compliant", "CPU ratio N/A")
        else:
            ratio = vcpu / pcpu
            if ratio <= 4:
                earned += _add("cpu_ratio", "compliant", f"vCPU:pCPU {ratio:.1f}:1 — within 4:1 best practice")
            elif ratio <= 8:
                earned += _add("cpu_ratio", "warning", f"vCPU:pCPU {ratio:.1f}:1 — exceeds 4:1 recommendation", 0.6)
            else:
                earned += _add("cpu_ratio", "non_compliant", f"vCPU:pCPU {ratio:.1f}:1 — critical overcommit")

    # 8. Power State
    if "power_state" in active:
        if power in ("poweredon", "powered on", "on", "running"):
            earned += _add("power_state", "compliant", "VM is powered on")
        elif "suspend" in power:
            earned += _add("power_state", "non_compliant", "VM is suspended — blocks vMotion")
        elif "off" in power:
            earned += _add("power_state", "warning", f"VM powered off — potential ghost asset", 0.4)
        else:
            earned += _add("power_state", "compliant", f"Power state: {power or 'N/A'}")

    # 9. Antivirus
    if "antivirus" in active:
        if av is True:
            earned += _add("antivirus", "compliant", "AV/EDR agent detected")
        elif av is False:
            earned += _add("antivirus", "non_compliant", "No AV/EDR agent detected — security risk")
        else:
            earned += _add("antivirus", "warning", "AV/EDR status unknown (SSH/WinRM not reachable)", 0.7)

    # 10. Disk Space
    if "disk_space" in active:
        disk_gb  = float(asset.get("disk_gb") or 0)
        disk_prov = float(asset.get("disk_prov_gb") or asset.get("disk_provisioned_gb") or 0)
        # Use provisioned vs committed ratio as a proxy for utilisation
        # If SSH disk_pct is present, prefer it
        disk_pct = asset.get("disk_pct")
        if disk_pct is not None:
            dp = float(disk_pct)
            if dp < 80:
                earned += _add("disk_space", "compliant", f"Disk utilisation {dp:.0f}% — within threshold")
            elif dp < 90:
                earned += _add("disk_space", "warning", f"Disk utilisation {dp:.0f}% — approaching limit (warn ≥ 80%)", 0.6)
            else:
                earned += _add("disk_space", "non_compliant", f"Disk utilisation {dp:.0f}% — critical (≥ 90%)")
        elif disk_prov > 0 and disk_gb > 0:
            pct = (disk_gb / disk_prov * 100) if disk_prov > disk_gb else (disk_prov / disk_gb * 100)
            if pct < 80:
                earned += _add("disk_space", "compliant", f"Disk usage est. {pct:.0f}% of provisioned")
            elif pct < 90:
                earned += _add("disk_space", "warning", f"Disk usage est. {pct:.0f}% — approaching limit", 0.6)
            else:
                earned += _add("disk_space", "non_compliant", f"Disk usage est. {pct:.0f}% — critical")
        else:
            earned += _add("disk_space", "warning", "Disk utilisation unknown — no data", 0.8)

    score  = max(0, min(100, earned))
    status = "compliant" if score >= 80 else "warning" if score >= 50 else "non_compliant"

    return {
        "score":           score,
        "status":          status,
        "checks":          checks,
        "patch_age_days":  patch_age_days,
        "uptime_days":     uptime,
        "tools_ok":        any(c["name"] == "vmware_tools" and c["status"] == "compliant" for c in checks),
        "hw_version_ok":   any(c["name"] == "hw_version"   and c["status"] == "compliant" for c in checks),
        "snapshot_ok":     any(c["name"] == "snapshot_age" and c["status"] == "compliant" for c in checks),
        "eol_os":          eol,
        "missing_patches": missing_patches,
    }
