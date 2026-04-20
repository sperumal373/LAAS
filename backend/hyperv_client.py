"""
hyperv_client.py â€” Microsoft Hyper-V management via PowerShell Remoting
=========================================================================
â€¢ Connects to standalone Hyper-V hosts over WinRM (same domain / same network)
â€¢ Uses PowerShell -ComputerName remoting â€” no extra Python packages required
â€¢ Hosts/credentials stored in .env  (HV_HOST_1, HV_NAME_1, HV_USER_1, HV_PASS_1 â€¦)
â€¢
â€¢ Pre-requisites on each Hyper-V host:
â€¢   Enable-PSRemoting -Force
â€¢   Set-NetFirewallRule -Name "WINRM-HTTP-In-TCP" -Enabled True   (or port 5985 open)
â€¢   Dashboard server: Set-Item WSMan:\\localhost\\Client\\TrustedHosts -Value "host1,host2"
"""

import os
import json
import subprocess
import datetime
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = str(Path(__file__).parent / ".env")
load_dotenv(dotenv_path=ENV_PATH)

# â”€â”€ Credential helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def get_hv_hosts() -> list:
    """Return list of configured Hyper-V hosts from .env."""
    hosts = []
    count = int(os.getenv("HV_HOST_COUNT", "0"))
    for i in range(1, count + 1):
        h = os.getenv(f"HV_HOST_{i}", "").strip()
        if not h:
            continue
        hosts.append({
            "id":       str(i),
            "host":     h,
            "name":     os.getenv(f"HV_NAME_{i}", h).strip(),
            "username": os.getenv(f"HV_USER_{i}", "").strip(),
            "password": os.getenv(f"HV_PASS_{i}", "").strip(),
        })
    return hosts


def save_hv_hosts(hosts_list: list) -> dict:
    """Write host list back to .env."""
    from dotenv import set_key
    # Clear old slots beyond new count
    old_count = int(os.getenv("HV_HOST_COUNT", "0"))
    for i in range(len(hosts_list) + 1, old_count + 1):
        set_key(ENV_PATH, f"HV_HOST_{i}", "")
        set_key(ENV_PATH, f"HV_NAME_{i}", "")
        set_key(ENV_PATH, f"HV_USER_{i}", "")
        set_key(ENV_PATH, f"HV_PASS_{i}", "")
    set_key(ENV_PATH, "HV_HOST_COUNT", str(len(hosts_list)))
    for i, h in enumerate(hosts_list, 1):
        set_key(ENV_PATH, f"HV_HOST_{i}", h.get("host", "").strip())
        set_key(ENV_PATH, f"HV_NAME_{i}", h.get("name", h.get("host", "")).strip())
        set_key(ENV_PATH, f"HV_USER_{i}", h.get("username", "").strip())
        set_key(ENV_PATH, f"HV_PASS_{i}", h.get("password", "").strip())
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    return {"success": True, "message": f"Saved {len(hosts_list)} Hyper-V host(s)."}


# â”€â”€ PowerShell remote execution â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _escape_ps(s: str) -> str:
    """Escape single-quotes for PowerShell string literals."""
    return s.replace("'", "''") if s else ""


def _run_remote(hcfg: dict, script: str, timeout: int = 60) -> dict:
    """
    Execute a PowerShell scriptblock on a remote Hyper-V host.
    Returns {"success": True, "data": <parsed JSON>} or {"success": False, "error": str}
    """
    host = hcfg["host"]
    user = hcfg.get("username", "")
    pwd  = hcfg.get("password", "")

    if user and pwd:
        cred_block = (
            f"$pw   = ConvertTo-SecureString '{_escape_ps(pwd)}' -AsPlainText -Force\n"
            f"$cred = New-Object System.Management.Automation.PSCredential('{_escape_ps(user)}', $pw)\n"
            f"$so   = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck\n"
        )
        invoke = (
            f"$out = Invoke-Command -ComputerName '{_escape_ps(host)}' "
            f"-Credential $cred -SessionOption $so -Authentication Basic -ErrorAction Stop -ScriptBlock {{\n"
            f"  $ErrorActionPreference = 'Stop'\n"
            f"  {script}\n"
            f"}}\n"
        )
    else:
        cred_block = ""
        invoke = (
            f"$out = Invoke-Command -ComputerName '{_escape_ps(host)}' "
            f"-ErrorAction Stop -ScriptBlock {{\n"
            f"  $ErrorActionPreference = 'Stop'\n"
            f"  {script}\n"
            f"}}\n"
        )

    full_script = (
        "$ErrorActionPreference = 'Continue'\n"
        + cred_block
        + "try {\n"
        + invoke
        + "  $out | ConvertTo-Json -Compress -Depth 6\n"
        + "} catch {\n"
        + '  Write-Output ("{""__error"":""" + $_.Exception.Message.Replace("`"","\'") + """}")\n'
        + "}\n"
    )

    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", full_script],
            capture_output=True, text=True, timeout=timeout
        )
        out = r.stdout.strip()
        err = r.stderr.strip()

        if not out:
            return {"success": False, "error": err or "No output from PowerShell"}

        # Try to parse last valid JSON block
        parsed = None
        for line in reversed(out.split("\n")):
            line = line.strip()
            if line.startswith(("{", "[")):
                try:
                    parsed = json.loads(line)
                    break
                except Exception:
                    continue

        if parsed is None:
            try:
                parsed = json.loads(out)
            except Exception:
                return {"success": False, "error": f"Cannot parse PS output: {out[:300]}"}

        if isinstance(parsed, dict) and "__error" in parsed:
            return {"success": False, "error": parsed["__error"]}

        return {"success": True, "data": parsed}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timed out after {timeout}s"}
    except FileNotFoundError:
        return {"success": False, "error": "PowerShell not found on dashboard server"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# â”€â”€ Scripts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_SCRIPT_HOST_INFO = r"""
$cs  = Get-CimInstance Win32_ComputerSystem
$os  = Get-CimInstance Win32_OperatingSystem
$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
$vmh = Get-VMHost
[PSCustomObject]@{
    Hostname       = $env:COMPUTERNAME
    OSCaption      = $os.Caption
    TotalRAMGB     = [math]::Round($cs.TotalPhysicalMemory/1GB,1)
    FreeRAMGB      = [math]::Round($os.FreePhysicalMemory/1MB,1)
    CPUPct         = [int]$cpu
    LogicalProcs   = $cs.NumberOfLogicalProcessors
    HVDataPath     = $vmh.VirtualMachinePath
    HVVersion      = (Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -ErrorAction SilentlyContinue).State
    Uptime         = [math]::Round(($os.LocalDateTime - $os.LastBootUpTime).TotalHours, 1)
}
"""

_SCRIPT_VMS = r"""
$vms = Get-VM
$result = $vms | ForEach-Object {
    $vm   = $_
    $nics = @($vm | Get-VMNetworkAdapter -ErrorAction SilentlyContinue)
    $snaps = @(Get-VMSnapshot -VMName $vm.Name -ErrorAction SilentlyContinue)
    $disks = @()
    try { $disks = Get-VMHardDiskDrive -VMName $vm.Name -ErrorAction SilentlyContinue }
    catch {}
    $diskGB = 0
    foreach ($d in $disks) {
        try {
            $vhd = Get-VHD -Path $d.Path -ErrorAction SilentlyContinue
            if ($vhd) { $diskGB += [math]::Round($vhd.Size/1GB,1) }
        } catch {}
    }
    [PSCustomObject]@{
        Name            = $vm.Name
        Id              = $vm.Id.ToString()
        State           = $vm.State.ToString()
        CPUUsage        = [int]$vm.CPUUsage
        MemAssignedGB   = [math]::Round($vm.MemoryAssigned/1GB,1)
        MemDemandGB     = [math]::Round($vm.MemoryDemand/1GB,1)
        UptimeHours     = [math]::Round($vm.Uptime.TotalHours,1)
        Generation      = [int]$vm.Generation
        ProcessorCount  = [int]$vm.ProcessorCount
        Version         = $vm.Version
        DiskGB          = $diskGB
        SnapshotCount   = $snaps.Count
        SwitchNames     = ($nics.SwitchName -join ',')
        IPAddresses     = (($nics | ForEach-Object { $_.IPAddresses } | Where-Object { $_ -and $_ -notlike '*:*' }) -join ',')
        Notes           = $vm.Notes
    }
}
$result
"""

_SCRIPT_CHECKPOINTS = r"""
param([string]$VMName)
Get-VMSnapshot -VMName $VMName -ErrorAction SilentlyContinue | Select-Object @{n='Name';e={$_.Name}}, @{n='Created';e={$_.CreationTime.ToString('yyyy-MM-dd HH:mm:ss')}}, @{n='Type';e={$_.SnapshotType.ToString()}}, @{n='ParentName';e={$_.ParentSnapshotName}}, @{n='SizeGB';e={[math]::Round($_.FileSize/1GB,2)}}
"""


# â”€â”€ High-level API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_hv_connection(hcfg: dict) -> dict:
    """Quick connectivity + credential test."""
    r = _run_remote(hcfg, "$env:COMPUTERNAME", timeout=20)
    if r["success"]:
        d = r["data"]
        # PowerShell remote wraps scalars as {"value": "...", "PSComputerName": ...}
        if isinstance(d, dict):
            hostname = str(d.get("value") or d.get("Value") or hcfg["host"])
        else:
            hostname = str(d).strip('"')
        return {"success": True, "message": f"Connected to {hostname}", "hostname": hostname}
    return {"success": False, "message": r["error"]}


_PS_META = {"PSComputerName", "RunspaceId", "PSShowComputerName"}

def _clean_ps(obj):
    """Strip PowerShell remoting metadata keys, unwrap {value:...} objects."""
    if isinstance(obj, dict):
        # Unwrap PS scalar wrapper
        if "value" in obj and set(obj.keys()) <= {"value", "Value", "PSComputerName", "RunspaceId", "PSShowComputerName"}:
            return obj.get("value") or obj.get("Value")
        return {k: _clean_ps(v) for k, v in obj.items() if k not in _PS_META}
    if isinstance(obj, list):
        return [_clean_ps(i) for i in obj]
    return obj


def get_hv_host_info(hcfg: dict) -> dict:
    r = _run_remote(hcfg, _SCRIPT_HOST_INFO)
    if not r["success"]:
        return {"error": r["error"]}
    d = r["data"]
    if isinstance(d, list):
        d = d[0] if d else {}
    d = _clean_ps(d)
    # Normalise HVVersion (may come as {value:2, Value:"Enabled"})
    hv = d.get("HVVersion")
    if isinstance(hv, dict):
        d["HVVersion"] = hv.get("Value") or hv.get("value") or str(hv)
    total = float(d.get("TotalRAMGB") or 0)
    free  = float(d.get("FreeRAMGB")  or 0)
    d["UsedRAMGB"]  = round(total - free, 1)
    d["RAMUsedPct"] = round((total - free) / total * 100, 0) if total > 0 else 0
    return d


def get_hv_vms(hcfg: dict) -> list:
    r = _run_remote(hcfg, _SCRIPT_VMS, timeout=120)
    if not r["success"]:
        return [{"__error": r["error"]}]
    data = r["data"]
    if not isinstance(data, list):
        data = [data] if data else []
    # Normalise: strip PS metadata, attach host info
    clean = []
    for vm in data:
        vm = _clean_ps(vm)
        vm["_host"]      = hcfg["host"]
        vm["_host_name"] = hcfg.get("name", hcfg["host"])
        vm["_host_id"]   = hcfg["id"]
        clean.append(vm)
    return clean


def get_hv_checkpoints(hcfg: dict, vm_name: str) -> list:
    script = f"Get-VMSnapshot -VMName '{_escape_ps(vm_name)}' -ErrorAction SilentlyContinue | Select-Object @{{n='Name';e={{$_.Name}}}}, @{{n='Created';e={{$_.CreationTime.ToString('yyyy-MM-dd HH:mm:ss')}}}}, @{{n='Type';e={{$_.SnapshotType.ToString()}}}}, @{{n='ParentName';e={{$_.ParentSnapshotName}}}}, @{{n='SizeGB';e={{[math]::Round($_.FileSize/1GB,2)}}}}"
    r = _run_remote(hcfg, script)
    if not r["success"]:
        return [{"error": r["error"]}]
    data = r["data"]
    if not isinstance(data, list):
        data = [data] if data else []
    return [_clean_ps(c) for c in data]


def hv_vm_action(hcfg: dict, vm_name: str, action: str) -> dict:
    """
    action: start | stop | forcestop | restart | save | pause | resume
    """
    vm_safe = _escape_ps(vm_name)
    scripts = {
        "start":     f"Start-VM -Name '{vm_safe}' -ErrorAction Stop",
        "stop":      f"Stop-VM  -Name '{vm_safe}' -ErrorAction Stop",
        "forcestop": f"Stop-VM  -Name '{vm_safe}' -Force -ErrorAction Stop",
        "restart":   f"Restart-VM -Name '{vm_safe}' -Force -ErrorAction Stop",
        "save":      f"Save-VM  -Name '{vm_safe}' -ErrorAction Stop",
        "pause":     f"Suspend-VM -Name '{vm_safe}' -ErrorAction Stop",
        "resume":    f"Resume-VM  -Name '{vm_safe}' -ErrorAction Stop",
    }
    if action not in scripts:
        return {"success": False, "message": f"Unknown action: {action}"}
    script = scripts[action] + "\nWrite-Output '{\"ok\":true}'"
    r = _run_remote(hcfg, script, timeout=60)
    if r["success"]:
        return {"success": True, "message": f"VM '{vm_name}': {action} completed"}
    return {"success": False, "message": r["error"]}


def hv_create_checkpoint(hcfg: dict, vm_name: str, checkpoint_name: str) -> dict:
    vm_safe = _escape_ps(vm_name)
    cp_safe = _escape_ps(checkpoint_name)
    script = (
        f"Checkpoint-VM -Name '{vm_safe}' -SnapshotName '{cp_safe}' -ErrorAction Stop\n"
        f"Write-Output '{{\"ok\":true}}'"
    )
    r = _run_remote(hcfg, script, timeout=120)
    if r["success"]:
        return {"success": True, "message": f"Checkpoint '{checkpoint_name}' created on '{vm_name}'"}
    return {"success": False, "message": r["error"]}


def hv_delete_checkpoint(hcfg: dict, vm_name: str, checkpoint_name: str) -> dict:
    vm_safe = _escape_ps(vm_name)
    cp_safe = _escape_ps(checkpoint_name)
    script = (
        f"Remove-VMSnapshot -VMName '{vm_safe}' -Name '{cp_safe}' -ErrorAction Stop\n"
        f"Write-Output '{{\"ok\":true}}'"
    )
    r = _run_remote(hcfg, script, timeout=60)
    if r["success"]:
        return {"success": True, "message": f"Checkpoint '{checkpoint_name}' deleted from '{vm_name}'"}
    return {"success": False, "message": r["error"]}


def hv_restore_checkpoint(hcfg: dict, vm_name: str, checkpoint_name: str) -> dict:
    vm_safe = _escape_ps(vm_name)
    cp_safe = _escape_ps(checkpoint_name)
    script = (
        f"Restore-VMSnapshot -VMName '{vm_safe}' -Name '{cp_safe}' -Confirm:$false -ErrorAction Stop\n"
        f"Write-Output '{{\"ok\":true}}'"
    )
    r = _run_remote(hcfg, script, timeout=120)
    if r["success"]:
        return {"success": True, "message": f"VM '{vm_name}' restored to checkpoint '{checkpoint_name}'"}
    return {"success": False, "message": r["error"]}


def get_all_hv_data() -> dict:
    """Full discovery across all configured hosts in parallel."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    hosts = get_hv_hosts()
    if not hosts:
        return {"hosts": [], "vms": [], "summary": {}, "errors": {}}

    host_infos, all_vms, errors = {}, [], {}

    def fetch_host(h):
        info = get_hv_host_info(h)
        vms  = get_hv_vms(h)
        return h["id"], h, info, vms

    with ThreadPoolExecutor(max_workers=min(8, len(hosts))) as ex:
        futs = {ex.submit(fetch_host, h): h for h in hosts}
        for f in as_completed(futs):
            try:
                hid, hcfg, info, vms = f.result()
                has_vm_err = vms and isinstance(vms[0], dict) and "__error" in vms[0]
                if "error" in info:
                    errors[hcfg["host"]] = info["error"]
                    info = {}
                if has_vm_err:
                    errors[hcfg["host"]] = vms[0]["__error"]
                    vms = []
                host_infos[hid] = {"config": hcfg, "info": info}
                all_vms.extend(vms)
            except Exception as e:
                h = futs[f]
                errors[h["host"]] = str(e)

    # Summary stats
    total = len(all_vms)
    running  = sum(1 for v in all_vms if v.get("State") == "Running")
    stopped  = sum(1 for v in all_vms if v.get("State") == "Off")
    saved    = sum(1 for v in all_vms if v.get("State") == "Saved")
    paused   = sum(1 for v in all_vms if v.get("State") == "Paused")
    snaps    = sum(int(v.get("SnapshotCount", 0)) for v in all_vms)
    mem_used = sum(float(v.get("MemAssignedGB", 0)) for v in all_vms)

    return {
        "hosts":    list(host_infos.values()),
        "vms":      all_vms,
        "errors":   errors,
        "summary": {
            "total_vms":  total,
            "running":    running,
            "stopped":    stopped,
            "saved":      saved,
            "paused":     paused,
            "total_snapshots": snaps,
            "total_mem_assigned_gb": round(mem_used, 1),
            "host_count": len(hosts),
        },
        "discovered_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
