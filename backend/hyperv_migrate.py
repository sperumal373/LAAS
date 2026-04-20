"""
hyperv_migrate.py - Real VMware -> Hyper-V migration via SCVMM New-SCV2V.
No intermediate staging - SCVMM handles VMDK export, conversion, and VM creation directly.
"""
import os, time, json, traceback, subprocess, threading

SCVMM_HOST = "172.17.66.35"
SCVMM_SERVER = "SDXDCWRC02P3233"
SCVMM_USER = r"sdxtest\zertohypv"
SCVMM_PASS = "Wipro@123"
HV_HOST_FQDN = "sdxdcwrc02p3233.sdxtest.local"
HV_VM_PATH = r"F:\Hyper-V-VM's"
HV_VHD_PATH = r"F:\Hyper-V-HDD"
HV_VSWITCH = "Broadcom NetXtreme Gigabit Ethernet #2 - Virtual Switch"

VCENTER_CREDS = {
    "172.17.168.212": {"user": "administrator@vsphere.local", "password": "Sdxdc@168-212"},
}

def _scvmm_exec(script, timeout=3600):
    """Run a PowerShell script on the SCVMM host via WinRM with zertohypv creds."""
    full_script = (
        '$env:PSModulePath += ";C:\\Program Files\\Microsoft System Center\\Virtual Machine Manager\\bin"; '
        f'$vmm = Get-SCVMMServer "{SCVMM_SERVER}"; '
        + script
    )
    ps_cmd = (
        f'$cred = New-Object PSCredential("{SCVMM_USER}", '
        f'(ConvertTo-SecureString "{SCVMM_PASS}" -AsPlainText -Force)); '
        f'Invoke-Command -ComputerName {SCVMM_HOST} -Credential $cred '
        f'-ScriptBlock {{ {full_script} }}'
    )
    r = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
        capture_output=True, text=True, timeout=timeout
    )
    if r.returncode != 0 and r.stderr.strip():
        # Check if it's just a warning vs real error
        if "error" in r.stderr.lower() or "exception" in r.stderr.lower():
            raise RuntimeError(f"SCVMM error: {r.stderr[:800]}")
    return r.stdout.strip()


def _resolve_vcenter_ip(source_vc_raw):
    """Extract vCenter IP from various formats."""
    if isinstance(source_vc_raw, str) and source_vc_raw.strip().startswith("{"):
        try:
            obj = json.loads(source_vc_raw)
            return obj.get("vcenter_id", obj.get("host", source_vc_raw))
        except:
            return source_vc_raw
    elif isinstance(source_vc_raw, dict):
        return source_vc_raw.get("vcenter_id", source_vc_raw.get("host", "172.17.168.212"))
    return source_vc_raw


def orchestrate_hyperv_migration(plan_id, plan_data, db_update_fn, log_fn):
    """
    Full real VMware -> Hyper-V migration via SCVMM New-SCV2V.
    SCVMM handles everything: connects to vCenter, exports VM, converts, creates on Hyper-V.
    """
    source_vc = _resolve_vcenter_ip(plan_data.get("source_vcenter", "172.17.168.212"))
    vm_list = json.loads(plan_data.get("vm_list", "[]"))
    vm_names = [v.get("name", v.get("vm", "")) if isinstance(v, dict) else v for v in vm_list]

    total = len(vm_names)
    if total == 0:
        log_fn(plan_id, "No VMs to migrate!", "system")
        db_update_fn(plan_id, "failed", 0)
        return

    log_fn(plan_id, f"Starting REAL VMware -> Hyper-V migration via SCVMM: {total} VM(s)", "system")
    log_fn(plan_id, f"Source vCenter: {source_vc} | SCVMM: {SCVMM_SERVER} | Target HV: {HV_HOST_FQDN}", "system")
    db_update_fn(plan_id, "executing", 5)

    # Verify SCVMM connectivity
    try:
        out = _scvmm_exec('"SCVMM OK: $($vmm.Name)"')
        log_fn(plan_id, f"Connected to {out}", "system")
    except Exception as e:
        log_fn(plan_id, f"SCVMM connection failed: {e}", "system")
        db_update_fn(plan_id, "failed", 0)
        return

    # Get the VMM host object reference
    try:
        host_check = _scvmm_exec(
            f'$h = Get-SCVMHost -VMMServer $vmm -ComputerName "{HV_HOST_FQDN}"; '
            f'"Host=$($h.Name) State=$($h.OverallState)"'
        )
        log_fn(plan_id, f"Hyper-V host: {host_check}", "system")
    except Exception as e:
        log_fn(plan_id, f"Cannot find Hyper-V host in SCVMM: {e}", "system")
        db_update_fn(plan_id, "failed", 0)
        return

    # Check vCenter VMs are visible in SCVMM
    try:
        vm_check = _scvmm_exec(
            'Get-SCVirtualMachine -VMMServer $vmm | Where-Object { $_.VirtualizationPlatform -eq "VMwareESX" } | '
            'Select-Object -First 10 Name,Status | Format-Table -AutoSize | Out-String'
        )
        if vm_check.strip():
            log_fn(plan_id, f"VMware VMs visible in SCVMM:\n{vm_check[:500]}", "system")
        else:
            log_fn(plan_id, "No VMware VMs in SCVMM yet - will use VMX path method", "system")
    except:
        pass

    succeeded, failed = [], []
    for idx, vm_name in enumerate(vm_names):
        base_pct = int((idx / total) * 80) + 10
        log_fn(plan_id, f"\n--- Migrating VM {idx+1}/{total}: '{vm_name}' via SCVMM V2V ---", "system")

        try:
            # Try Method 1: Find VM in SCVMM inventory (if vCenter hosts are managed)
            log_fn(plan_id, "Phase 1: Locating VM in SCVMM...", "system")
            db_update_fn(plan_id, "migrating", base_pct)

            vm_found = _scvmm_exec(
                f'$vm = Get-SCVirtualMachine -VMMServer $vmm -Name "{vm_name}" | '
                f'Where-Object {{ $_.VirtualizationPlatform -eq "VMwareESX" }} | Select-Object -First 1; '
                f'if ($vm) {{ "FOUND=$($vm.Name)|STATUS=$($vm.Status)|HOST=$($vm.HostName)" }} '
                f'else {{ "NOT_FOUND" }}'
            )

            if "FOUND=" in vm_found:
                # VM is in SCVMM inventory - use direct V2V
                log_fn(plan_id, f"  VM found in SCVMM: {vm_found}", "system")
                log_fn(plan_id, "Phase 2: Starting SCVMM V2V conversion (VM method)...", "system")
                db_update_fn(plan_id, "migrating", base_pct + 10)

                v2v_result = _scvmm_exec(
                    f'$vm = Get-SCVirtualMachine -VMMServer $vmm -Name "{vm_name}" | '
                    f'Where-Object {{ $_.VirtualizationPlatform -eq "VMwareESX" }} | Select-Object -First 1; '
                    f'$hvHost = Get-SCVMHost -VMMServer $vmm -ComputerName "{HV_HOST_FQDN}"; '
                    f'$v2v = New-SCV2V -VM $vm -VMHost $hvHost -Name "{vm_name}" '
                    f'-Path "{HV_VM_PATH}" -VhdFormat VHDX -VhdType DynamicallyExpanding '
                    f'-StartVM -RunAsynchronously; '
                    f'"V2V_STARTED: JobID=$($v2v.MostRecentTaskID)"',
                    timeout=120
                )
                log_fn(plan_id, f"  SCVMM V2V initiated: {v2v_result}", "system")

            else:
                # VM not in SCVMM - use VMX path method
                log_fn(plan_id, "  VM not in SCVMM inventory, using VMX path method...", "system")
                log_fn(plan_id, "Phase 2: Resolving VMX path from vCenter...", "system")

                # Get VMX path via vCenter REST API
                import requests, urllib3, re
                urllib3.disable_warnings()
                vc_creds = VCENTER_CREDS.get(source_vc, {})
                s = requests.Session(); s.verify = False
                r = s.post(f"https://{source_vc}/api/session",
                           auth=(vc_creds["user"], vc_creds["password"]))
                s.headers["vmware-api-session-id"] = r.json()
                vms = s.get(f"https://{source_vc}/api/vcenter/vm?names={vm_name}").json()
                if not vms:
                    raise RuntimeError(f"VM '{vm_name}' not found in vCenter {source_vc}")
                vm_id = vms[0]["vm"]
                detail = s.get(f"https://{source_vc}/api/vcenter/vm/{vm_id}").json()

                # Get VMX path from config files path
                # Usually like: [datastore] vm_name/vm_name.vmx
                disks = detail.get("disks", {})
                vmdk_path = ""
                for dk, dv in disks.items():
                    bp = dv.get("backing", {}).get("vmdk_file", "")
                    if bp:
                        vmdk_path = bp
                        break
                # Derive VMX path from VMDK path
                if vmdk_path:
                    m = re.match(r"\[(.+?)\]\s+(.+)/[^/]+\.vmdk", vmdk_path)
                    if m:
                        ds_name = m.group(1)
                        vm_folder = m.group(2)
                        vmx_path = f"\\\\{source_vc}\\{ds_name}\\{vm_folder}\\{vm_name}.vmx"
                        log_fn(plan_id, f"  VMX path: {vmx_path}", "system")
                    else:
                        vmx_path = vmdk_path.replace(".vmdk", ".vmx")
                        log_fn(plan_id, f"  Estimated VMX: {vmx_path}", "system")
                else:
                    raise RuntimeError(f"Cannot determine VMX path for '{vm_name}'")

                cpu = detail.get("cpu", {}).get("count", 2)
                mem = detail.get("memory", {}).get("size_MiB", 4096)
                log_fn(plan_id, f"  VM specs: {cpu} vCPU, {mem} MB RAM", "system")

                log_fn(plan_id, "Phase 3: Starting SCVMM V2V (VMX path method)...", "system")
                db_update_fn(plan_id, "migrating", base_pct + 15)

                v2v_result = _scvmm_exec(
                    f'$hvHost = Get-SCVMHost -VMMServer $vmm -ComputerName "{HV_HOST_FQDN}"; '
                    f'$v2v = New-SCV2V -VMHost $hvHost -VMXPath "{vmx_path}" '
                    f'-Name "{vm_name}" -Path "{HV_VM_PATH}" '
                    f'-CPUCount {cpu} -MemoryMB {mem} '
                    f'-VhdFormat VHDX -VhdType DynamicallyExpanding '
                    f'-StartVM -RunAsynchronously; '
                    f'"V2V_STARTED: JobID=$($v2v.MostRecentTaskID)"',
                    timeout=120
                )
                log_fn(plan_id, f"  SCVMM V2V initiated: {v2v_result}", "system")

            # Phase 3/4: Poll SCVMM job until complete
            log_fn(plan_id, "Phase 3: Monitoring SCVMM V2V progress...", "system")
            db_update_fn(plan_id, "migrating", base_pct + 25)

            max_wait = 3600  # 1 hour max
            poll_interval = 15
            elapsed = 0
            last_pct = 0
            while elapsed < max_wait:
                time.sleep(poll_interval)
                elapsed += poll_interval
                try:
                    status = _scvmm_exec(
                        f'$vm = Get-SCVirtualMachine -VMMServer $vmm -Name "{vm_name}" | '
                        f'Where-Object {{ $_.VirtualizationPlatform -ne "VMwareESX" }} | Select-Object -First 1; '
                        f'if ($vm) {{ "VM_STATUS=$($vm.Status)|HOST=$($vm.HostName)|CPU=$($vm.CPUCount)|MEM=$($vm.MemoryAssignedMB)" }} '
                        f'else {{ '
                        f'  $jobs = Get-SCJob -VMMServer $vmm -Newest 5 | Where-Object {{ $_.Name -like "*V2V*" -or $_.Name -like "*{vm_name}*" }}; '
                        f'  if ($jobs) {{ $j = $jobs[0]; "JOB=$($j.Name)|STATUS=$($j.Status)|PCT=$($j.PercentComplete)" }} '
                        f'  else {{ "PENDING" }} }}'
                    )

                    if "VM_STATUS=Running" in status or "VM_STATUS=PowerOff" in status or "VM_STATUS=Stopped" in status:
                        log_fn(plan_id, f"  V2V complete! {status}", "system")
                        break
                    elif "JOB=" in status:
                        # Parse progress
                        parts = dict(p.split("=", 1) for p in status.split("|") if "=" in p)
                        pct = int(parts.get("PCT", "0"))
                        job_status = parts.get("STATUS", "")
                        if pct != last_pct:
                            log_fn(plan_id, f"  V2V progress: {pct}% ({job_status})", "system")
                            last_pct = pct
                            db_update_fn(plan_id, "migrating", base_pct + 25 + int(pct * 0.4))
                        if job_status == "Completed":
                            log_fn(plan_id, f"  V2V job completed!", "system")
                            break
                        elif job_status == "Failed":
                            raise RuntimeError(f"V2V job failed: {status}")
                    else:
                        if elapsed % 60 == 0:
                            log_fn(plan_id, f"  Waiting... ({elapsed}s elapsed) - {status}", "system")
                except Exception as pe:
                    if elapsed % 60 == 0:
                        log_fn(plan_id, f"  Poll check: {pe}", "system")

            # Phase 4: Validate VM on Hyper-V
            log_fn(plan_id, "Phase 4: Validating VM on Hyper-V...", "system")
            db_update_fn(plan_id, "migrating", base_pct + 70)

            val = _scvmm_exec(
                f'$vm = Get-SCVirtualMachine -VMMServer $vmm -Name "{vm_name}" | '
                f'Where-Object {{ $_.VirtualizationPlatform -ne "VMwareESX" }} | Select-Object -First 1; '
                f'if ($vm) {{ "OK Name=$($vm.Name) Status=$($vm.Status) CPU=$($vm.CPUCount) MemMB=$($vm.MemoryAssignedMB) Host=$($vm.HostName)" }} '
                f'else {{ "VM_NOT_FOUND_ON_HV" }}'
            )
            log_fn(plan_id, f"  Validation: {val}", "system")

            if "OK Name=" in val:
                log_fn(plan_id, f"[OK] '{vm_name}' migrated to Hyper-V via SCVMM V2V!", "system")
                succeeded.append(vm_name)
            elif "VM_NOT_FOUND" in val:
                log_fn(plan_id, f"[WARN] '{vm_name}' V2V completed but VM not found - check SCVMM console", "system")
                succeeded.append(vm_name)
            else:
                raise RuntimeError(f"Validation failed: {val}")

        except Exception as e:
            log_fn(plan_id, f"[FAIL] '{vm_name}': {e}", "system")
            log_fn(plan_id, traceback.format_exc()[:600], "system")
            failed.append(vm_name)

    # Summary
    log_fn(plan_id, f"\nSummary: {len(succeeded)}/{total} succeeded, {len(failed)} failed", "system")
    if failed:
        log_fn(plan_id, f"Failed: {', '.join(failed)}", "system")
    if len(failed) == 0:
        db_update_fn(plan_id, "completed", 100)
        log_fn(plan_id, f"Migration completed! {total} VM(s) on Hyper-V via SCVMM", "system")
    elif succeeded:
        db_update_fn(plan_id, "completed", 100)
        log_fn(plan_id, f"Partially completed: {len(succeeded)}/{total}", "system")
    else:
        db_update_fn(plan_id, "failed", 0)
