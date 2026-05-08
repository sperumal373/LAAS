import sys

content = '''"""
hyperv_migrate.py - VMware -> Hyper-V via SCVMM (VM object method ONLY)

ROOT CAUSE FIX:
  vCenter 172.17.168.212 is registered in SCVMM as 'vcsa80u3-rookie.sdxtest.local'
  (by hostname, not IP). Previous code searched by IP -> not found -> refresh never ran.
  FIX: After any registration attempt, REFRESH ALL VirtualizationManagers (not just by IP).

Migration flow:
  1. Connect to SCVMM
  2. List ALL registered vCenters (log them for debug)
  3. If vc_ip not found by IP: try Add-SCVirtualizationManager (may get 400=already exists)
  4. Refresh ALL VirtualizationManagers -> this ensures hostname-registered vCenters are refreshed
  5. Wait for VM to appear in SCVMM VMwareESX inventory
  6. New-SCV2V -VM  (VM object method ONLY - no VMXPath - avoids Error 20413)
  7. Poll job, validate on Hyper-V
"""
import os, time, json, traceback, subprocess

SCVMM_HOST   = "172.17.66.35"
SCVMM_SERVER = "SDXDCWRC02P3233"
SCVMM_USER   = r"sdxtest\\zertohypv"
SCVMM_PASS   = "Wipro@123"
HV_HOST_FQDN = "sdxdcwrc02p3233.sdxtest.local"
HV_VM_PATH   = r"F:\\Hyper-V-VM\'s"

VCENTER_CREDS = {
    "172.17.101.15":  {"user": "administrator@vsphere.local", "password": "Sdxdc@101-15"},
    "172.17.101.17":  {"user": "administrator@vsphere.local", "password": "Sdxdc@101-17"},
    "172.17.168.212": {"user": "administrator@vsphere.local", "password": "Sdxdc@168-212"},
    "172.17.80.150":  {"user": "administrator@vsphere.local", "password": "Sdxdc@80-150"},
    "172.17.73.191":  {"user": "administrator@vsphere.local", "password": "Sdxdc@73-191"},
    "172.16.6.125":   {"user": "administrator@vsphere.local", "password": "Sdxdr@6-125"},
}


def _ps(script, timeout=120):
    """Run PowerShell on SCVMM host via WinRM. Returns stdout."""
    wrapped = (
        \'C:\Users\Administrator\Documents\WindowsPowerShell\Modules;C:\Program Files\WindowsPowerShell\Modules;C:\Windows\system32\WindowsPowerShell\v1.0\Modules += ";C:\\\\Program Files\\\\Microsoft System Center\'
        \'\\\\Virtual Machine Manager\\\\bin"; \'
        f\' = Get-SCVMMServer "{SCVMM_SERVER}"; \'
        + script
    )
    cmd = (
        f\' = New-Object PSCredential("{SCVMM_USER}",\'
        f\'(ConvertTo-SecureString "{SCVMM_PASS}" -AsPlainText -Force));\'
        f\'Invoke-Command -ComputerName {SCVMM_HOST} -Credential  \'
        f\'-ScriptBlock {{ {wrapped} }}\'
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True, text=True, timeout=timeout
    )
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0 and err:
        low = err.lower()
        if "error" in low or "exception" in low or "fail" in low:
            raise RuntimeError(err[:1500])
    return out


def _resolve_vcenter_ip(raw):
    """Parse vCenter IP from string, JSON string, or dict."""
    if isinstance(raw, dict):
        return raw.get("vcenter_id", raw.get("host", "172.17.168.212"))
    if isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            obj = json.loads(raw)
            return obj.get("vcenter_id", obj.get("host", raw))
        except Exception:
            pass
    return raw or "172.17.168.212"


def _ensure_vcenter_and_refresh(vc_ip, vc_user, vc_pass, log_fn, plan_id):
    """
    KEY FIX: List all registered VirtualizationManagers first.
    vCenter may be registered under its hostname (e.g. vcsa80u3-rookie.sdxtest.local)
    not by IP. We ALWAYS refresh ALL managers to ensure inventory is current.
    """
    # Step 1: List ALL registered managers (for debug + to check if vc_ip appears)
    log_fn(plan_id, "  Listing ALL SCVMM VirtualizationManagers...", "system")
    all_mgrs_out = ""
    try:
        all_mgrs_out = _ps(
            \' = Get-SCVirtualizationManager -VMMServer  2>; \'
            \'if () { \'
            \'   | ForEach-Object { Write-Host "MGR|Name=|FQDN=|State=|Addr=" } \'
            \'} else { Write-Host "NO_MANAGERS_REGISTERED" }\',
            timeout=60
        )
        log_fn(plan_id, f"  Registered managers:\\n{all_mgrs_out}", "system")
    except Exception as e:
        log_fn(plan_id, f"  [WARN] Cannot list managers: {e}", "system")

    # Step 2: Check if vc_ip is already registered (by IP or hostname lookup)
    vc_found_in_scvmm = (vc_ip in all_mgrs_out)

    if not vc_found_in_scvmm:
        log_fn(plan_id, f"  vCenter {vc_ip} not found by IP in manager list. Attempting registration...", "system")
        try:
            reg = _ps(
                f\' = New-Object PSCredential("{vc_user}",\'
                f\'(ConvertTo-SecureString "{vc_pass}" -AsPlainText -Force)); \'
                f\' = Get-SCCertificate -ComputerName "{vc_ip}" -TCPPort 443 -ErrorAction SilentlyContinue; \'
                f\'if () {{ \'
                f\'   = Add-SCVirtualizationManager -VMMServer  \'
                f\'  -ComputerName "{vc_ip}" -Credential  \'
                f\'  -TCPPort 443 -Certificate  -RunAsynchronously:False; \'
                f\'  if () {{ "ADDED|" }} else {{ "ADDED_EMPTY" }} \'
                f\'}} else {{ "CERT_FAILED" }}\',
                timeout=300
            )
            log_fn(plan_id, f"  Registration: {reg}", "system")
            time.sleep(10)
        except Exception as e:
            err_str = str(e)
            if "400" in err_str or "already associated" in err_str.lower():
                log_fn(plan_id,
                    f"  [INFO] SCVMM Error 400: vCenter {vc_ip} is already registered under its "
                    f"hostname (e.g. vcsa80u3-rookie.sdxtest.local). "
                    f"Will refresh ALL managers to pick up VMware VMs.", "system")
            else:
                log_fn(plan_id, f"  [WARN] Registration attempt: {err_str[:300]}", "system")
    else:
        log_fn(plan_id, f"  vCenter {vc_ip} confirmed in SCVMM.", "system")

    # Step 3: REFRESH ALL registered VirtualizationManagers
    # This is the critical fix - we don't filter by IP, we refresh everything
    log_fn(plan_id, "  Refreshing ALL VirtualizationManagers in SCVMM (60-180s)...", "system")
    try:
        refresh_out = _ps(
            \' = Get-SCVirtualizationManager -VMMServer  2>; \'
            \'if (-not ) { Write-Host "NO_MANAGERS_TO_REFRESH"; return }; \'
            \'foreach ( in ) { \'
            \'  Write-Host "REFRESHING|"; \'
            \'  try { \'
            \'    Read-SCVirtualizationManager -VirtualizationManager  2> | Out-Null; \'
            \'    Write-Host "REFRESHED_OK|" \'
            \'  } catch { \'
            \'    Write-Host "REFRESH_ERR||" \'
            \'  } \'
            \'}\',
            timeout=600
        )
        log_fn(plan_id, f"  Refresh results:\\n{refresh_out}", "system")
        ok = "REFRESHED_OK" in refresh_out
        if ok:
            log_fn(plan_id, "  Inventory refresh complete. Waiting 20s for SCVMM to process VMs...", "system")
            time.sleep(20)
        else:
            log_fn(plan_id, "  [WARN] No successful refreshes - VMs may not appear in inventory.", "system")
        return ok
    except Exception as e:
        log_fn(plan_id, f"  [WARN] Refresh error: {e}", "system")
        return False


def _wait_for_vm_in_scvmm(vm_name, log_fn, plan_id, max_wait=240):
    """
    Poll SCVMM until the VMware VM appears in inventory.
    max_wait=240s (4 min) to allow for slow inventory sync.
    Also logs how many total VMware VMs SCVMM can see (helps debug).
    Returns (found: bool, info: str).
    """
    interval = 20
    elapsed  = 0
    while elapsed <= max_wait:
        try:
            out = _ps(
                f\' = Get-SCVirtualMachine -VMMServer  2> | \'
                f\'Where-Object {{ .Name -eq "{vm_name}" \'
                f\'-and .VirtualizationPlatform -eq "VMwareESX" }}; \'
                f\'if () {{ \'
                f\'   =  | Select-Object -First 1; \'
                f\'  "FOUND|Name=|Status=|Host=|CPU=|MemMB=" \'
                f\'}} else {{ \'
                f\'   = (Get-SCVirtualMachine -VMMServer  2> | \'
                f\'    Where-Object {{ .VirtualizationPlatform -eq "VMwareESX" }} | Measure-Object).Count; \'
                f\'  "NOT_FOUND|TotalVMwareVMsInSCVMM=" \'
                f\'}}\',
                timeout=60
            )
            if "FOUND|" in out:
                log_fn(plan_id, f"  VM found: {out}", "system")
                return True, out
            log_fn(plan_id, f"  {out} | elapsed={elapsed}s/{max_wait}s", "system")
        except Exception as e:
            log_fn(plan_id, f"  [WARN] VM lookup error: {e}", "system")
        time.sleep(interval)
        elapsed += interval
    return False, "NOT_FOUND"


def _start_v2v(vm_name, log_fn, plan_id):
    """
    Start New-SCV2V using SCVMM VM object. No VMXPath - avoids Error 20413.
    """
    out = _ps(
        f\' = Get-SCVirtualMachine -VMMServer  2> | \'
        f\'Where-Object {{ .Name -eq "{vm_name}" \'
        f\'-and .VirtualizationPlatform -eq "VMwareESX" }} | \'
        f\'Select-Object -First 1; \'
        f\'if (-not ) {{ throw "VM [{vm_name}] not found in SCVMM VMwareESX inventory." }}; \'
        f\' = Get-SCVMHost -VMMServer  -ComputerName "{HV_HOST_FQDN}" 2>; \'
        f\'if (-not ) {{ throw "Hyper-V host [{HV_HOST_FQDN}] not found in SCVMM." }}; \'
        f\'Write-Host "V2V:  -> "; \'
        f\' = New-SCV2V \'
        f\'-VM  \'
        f\'-VMHost  \'
        f\'-Name "{vm_name}" \'
        f\'-Path "{HV_VM_PATH}" \'
        f\'-VhdFormat VHDX \'
        f\'-VhdType DynamicallyExpanding \'
        f\'-RunAsynchronously; \'
        f\'"V2V_STARTED|JobID="\',
        timeout=300
    )
    return out


def _poll_v2v(vm_name, plan_id, base_pct, log_fn, db_update_fn, max_wait=7200):
    """Poll SCVMM until V2V finishes. Returns (success, detail)."""
    elapsed  = 0
    interval = 20
    last_pct = -1

    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            status = _ps(
                f\' = Get-SCVirtualMachine -VMMServer  2> | \'
                f\'Where-Object {{ .Name -eq "{vm_name}" \'
                f\'-and .VirtualizationPlatform -ne "VMwareESX" }} | \'
                f\'Select-Object -First 1; \'
                f\'if () {{ \'
                f\'  "DONE|Status=|Host=|CPU=|MemMB=" \'
                f\'}} else {{ \'
                f\'   = Get-SCJob -VMMServer  -Newest 50 2> | \'
                f\'  Where-Object {{ .Name -like "*{vm_name}*" -or .Name -like "*V2V*" -or .Name -like "*Convert*" }} | \'
                f\'  Sort-Object StartTime -Descending | Select-Object -First 1; \'
                f\'  if () {{ \'
                f\'    "JOB|Status=|PCT=|Name=|Err=" \'
                f\'  }} else {{ "PENDING" }} \'
                f\'}}\',
                timeout=60
            )
            if "DONE|" in status:
                log_fn(plan_id, f"  V2V complete: {status}", "system")
                return True, status
            elif "JOB|" in status:
                parts   = dict(x.split("=", 1) for x in status.split("|") if "=" in x)
                pct     = int(parts.get("PCT", "0") or "0")
                jstatus = parts.get("Status", "")
                jerr    = parts.get("Err", "")
                if pct != last_pct or elapsed % 60 == 0:
                    log_fn(plan_id, f"  V2V: {pct}% [{jstatus}] ({elapsed}s)", "system")
                    last_pct = pct
                    db_update_fn(plan_id, "migrating", min(base_pct + 10 + int(pct * 0.5), 95))
                if jstatus.lower() in ("completed", "success"):
                    return True, status
                elif jstatus.lower() in ("failed", "error"):
                    return False, f"Job failed ({pct}%): {jerr[:400]}"
            else:
                if elapsed % 60 == 0:
                    log_fn(plan_id, f"  Waiting for V2V job... ({elapsed}s)", "system")
        except Exception as e:
            if elapsed % 60 == 0:
                log_fn(plan_id, f"  Poll error: {e}", "system")
    return False, f"TIMEOUT after {max_wait}s"


def orchestrate_hyperv_migration(plan_id, plan_data, db_update_fn, log_fn):
    """Orchestrate VMware -> Hyper-V via SCVMM (VM object method only)."""
    source_vc = _resolve_vcenter_ip(plan_data.get("source_vcenter", "172.17.168.212"))
    vm_list   = json.loads(plan_data.get("vm_list", "[]"))
    vm_names  = [
        v.get("name", v.get("vm", "")) if isinstance(v, dict) else v
        for v in vm_list
    ]
    total = len(vm_names)

    if total == 0:
        log_fn(plan_id, "No VMs selected.", "system")
        db_update_fn(plan_id, "failed", 0)
        return

    vc_creds = VCENTER_CREDS.get(source_vc, {})
    if not vc_creds:
        log_fn(plan_id, f"[ERROR] No credentials for vCenter {source_vc}. Known: {list(VCENTER_CREDS.keys())}", "system")
        db_update_fn(plan_id, "failed", 0)
        return

    log_fn(plan_id, "=== VMware -> Hyper-V Migration (via SCVMM) ===", "system")
    log_fn(plan_id, f"SCVMM: {SCVMM_HOST} ({SCVMM_SERVER})", "system")
    log_fn(plan_id, f"Source vCenter: {source_vc}", "system")
    log_fn(plan_id, f"Target Hyper-V: {HV_HOST_FQDN}", "system")
    log_fn(plan_id, f"VMs to migrate: {total} -> {vm_names}", "system")
    db_update_fn(plan_id, "executing", 5)

    # Step 1: SCVMM connectivity
    try:
        ping = _ps(\'"SCVMM_OK: " + .Name\', timeout=60)
        log_fn(plan_id, f"SCVMM connected: {ping}", "system")
    except Exception as e:
        log_fn(plan_id, f"[ERROR] Cannot connect to SCVMM {SCVMM_HOST}: {e}", "system")
        db_update_fn(plan_id, "failed", 0)
        return

    # Step 2: Hyper-V host check
    try:
        hv = _ps(
            f\' = Get-SCVMHost -VMMServer  -ComputerName "{HV_HOST_FQDN}" 2>; \'
            f\'if () {{ "HV_OK||" }} else {{ "HV_NOT_FOUND" }}\',
            timeout=60
        )
        log_fn(plan_id, f"Hyper-V host: {hv}", "system")
        if "HV_NOT_FOUND" in hv:
            log_fn(plan_id, f"[ERROR] Hyper-V host {HV_HOST_FQDN} not in SCVMM.", "system")
            db_update_fn(plan_id, "failed", 0)
            return
    except Exception as e:
        log_fn(plan_id, f"[ERROR] Hyper-V host check: {e}", "system")
        db_update_fn(plan_id, "failed", 0)
        return

    # Step 3: Register/refresh vCenter (refreshes ALL managers - key fix)
    db_update_fn(plan_id, "executing", 10)
    _ensure_vcenter_and_refresh(source_vc, vc_creds["user"], vc_creds["password"], log_fn, plan_id)

    # Step 4: Migrate each VM
    succeeded, failed_vms = [], []
    for idx, vm_name in enumerate(vm_names):
        base_pct = int((idx / total) * 70) + 15
        log_fn(plan_id, f"\\n--- [{idx+1}/{total}] Migrating \'{vm_name}\' ---", "system")
        db_update_fn(plan_id, "migrating", base_pct)

        try:
            # Wait for VM in SCVMM inventory (4 min max)
            log_fn(plan_id, f"  Waiting for \'{vm_name}\' in SCVMM VMwareESX inventory...", "system")
            vm_found, vm_info = _wait_for_vm_in_scvmm(vm_name, log_fn, plan_id, max_wait=240)
            if not vm_found:
                raise RuntimeError(
                    f"VM \'{vm_name}\' not found in SCVMM VMwareESX inventory after 4 minutes. "
                    "Verify: (1) vCenter is registered in SCVMM Console > Fabric > vCenter Servers, "
                    "(2) SCVMM Console shows VMware VMs under VMs and Services > All Hosts, "
                    "(3) VM name matches exactly (case-sensitive)."
                )

            # Start V2V (SCVMM VM object method - no VMXPath)
            log_fn(plan_id, "  Starting New-SCV2V via SCVMM VM object...", "system")
            db_update_fn(plan_id, "migrating", base_pct + 5)
            v2v = _start_v2v(vm_name, log_fn, plan_id)
            log_fn(plan_id, f"  V2V started: {v2v}", "system")

            # Poll
            log_fn(plan_id, "  Monitoring V2V job...", "system")
            db_update_fn(plan_id, "migrating", base_pct + 10)
            ok, detail = _poll_v2v(vm_name, plan_id, base_pct, log_fn, db_update_fn)
            if not ok:
                raise RuntimeError(f"V2V failed: {detail}")

            # Validate
            val = _ps(
                f\' = Get-SCVirtualMachine -VMMServer  2> | \'
                f\'Where-Object {{ .Name -eq "{vm_name}" \'
                f\'-and .VirtualizationPlatform -ne "VMwareESX" }} | Select-Object -First 1; \'
                f\'if () {{ "OK|Name=|Status=|Host=" }} \'
                f\'else {{ "NOT_FOUND_ON_HV" }}\',
                timeout=60
            )
            log_fn(plan_id, f"  Validation: {val}", "system")
            if "OK|" in val:
                log_fn(plan_id, f"[OK] \'{vm_name}\' migrated to Hyper-V!", "system")
            else:
                log_fn(plan_id, f"[WARN] Job done but VM not yet visible - check SCVMM Console.", "system")
            succeeded.append(vm_name)

        except Exception as e:
            log_fn(plan_id, f"[FAIL] \'{vm_name}\': {e}", "system")
            log_fn(plan_id, traceback.format_exc()[:600], "system")
            failed_vms.append(vm_name)

    log_fn(plan_id, f"\\n=== {len(succeeded)}/{total} succeeded, {len(failed_vms)} failed ===", "system")
    if failed_vms:
        log_fn(plan_id, f"Failed: {', '.join(failed_vms)}", "system")
    if not failed_vms:
        db_update_fn(plan_id, "completed", 100)
        log_fn(plan_id, "All VMs migrated to Hyper-V successfully.", "system")
    elif succeeded:
        db_update_fn(plan_id, "completed", 100)
        log_fn(plan_id, f"Partial: {len(succeeded)}/{total}.", "system")
    else:
        db_update_fn(plan_id, "failed", 0)
        log_fn(plan_id, "All migrations failed.", "system")
'''

with open(r'C:\caas-dashboard\backend\hyperv_migrate.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("DONE:", len(content.splitlines()), "lines")
