"""
test_actions.py — Run this on the Windows Server to verify all VM actions work.
Usage:  python test_actions.py
It will list all vCenters + their VMs, then let you test each action.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from vmware_client import (
    get_vcenter_list, get_all_data, _vc_by_id, _connect, _find_vm,
    vm_power_action, vm_snapshot, vm_clone, vm_migrate, get_vc_resources
)
from pyVim.connect import Disconnect

SEP = "─" * 60

def test_vcenter_ids():
    print(SEP)
    print("1. vCenter IDs (these are what the frontend sends)")
    print(SEP)
    vcs = get_vcenter_list()
    for vc in vcs:
        found = _vc_by_id(vc["id"])
        status = "✅ FOUND" if found else "❌ NOT FOUND"
        print(f"  {status}  id={vc['id']}  name={vc['name']}")
    return vcs

def test_find_vm(vc_id, vm_name):
    print(SEP)
    print(f"2. Find VM '{vm_name}' in vCenter '{vc_id}'")
    print(SEP)
    vc = _vc_by_id(vc_id)
    if not vc:
        print(f"  ❌ vCenter {vc_id} not found!")
        return False
    si = None
    try:
        si = _connect(vc)
        c  = si.RetrieveContent()
        vm = _find_vm(c, vm_name)
        if vm:
            print(f"  ✅ VM found: {vm.name} | state={vm.runtime.powerState}")
            return True
        else:
            print(f"  ❌ VM '{vm_name}' not found")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    finally:
        if si:
            try: Disconnect(si)
            except: pass

def test_list_vms(vc_id):
    print(SEP)
    print(f"3. List first 5 VMs in vCenter '{vc_id}'")
    print(SEP)
    vc = _vc_by_id(vc_id)
    if not vc:
        print(f"  ❌ vCenter {vc_id} not found!")
        return []
    si = None
    try:
        si = _connect(vc)
        c  = si.RetrieveContent()
        view = c.viewManager.CreateContainerView(c.rootFolder, [], True)
        from pyVmomi import vim
        view = c.viewManager.CreateContainerView(c.rootFolder, [vim.VirtualMachine], True)
        vms  = view.view[:5]
        view.Destroy()
        names = []
        for vm in vms:
            state = str(vm.runtime.powerState)
            print(f"  {vm.name:40s} | {state}")
            names.append((vm.name, state))
        return names
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return []
    finally:
        if si:
            try: Disconnect(si)
            except: pass

def test_resources(vc_id):
    print(SEP)
    print(f"4. Resources (hosts/datastores) for vCenter '{vc_id}'")
    print(SEP)
    r = get_vc_resources(vc_id)
    print(f"  Hosts ({len(r['hosts'])}):")
    for h in r['hosts'][:3]:
        print(f"    {h['name']}")
    print(f"  Datastores ({len(r['datastores'])}):")
    for d in r['datastores'][:3]:
        print(f"    {d['name']}  {d['free_gb']}GB free")

def test_power_action(vc_id, vm_name, action):
    print(SEP)
    print(f"5. Power action '{action}' on VM '{vm_name}'")
    print(SEP)
    result = vm_power_action(vc_id, vm_name, action)
    status = "✅" if result["success"] else "❌"
    print(f"  {status} {result['message']}")
    return result["success"]

def test_snapshot(vc_id, vm_name):
    print(SEP)
    print(f"6. Snapshot VM '{vm_name}'")
    print(SEP)
    result = vm_snapshot(vc_id, vm_name, "test-snap-dashboard", "Test from dashboard", memory=False)
    status = "✅" if result["success"] else "❌"
    print(f"  {status} {result['message']}")

if __name__ == "__main__":
    print("\n" + "═" * 60)
    print("  CaaS Dashboard — VM Action Tests")
    print("═" * 60 + "\n")

    # Step 1: list vCenters
    vcs = test_vcenter_ids()
    if not vcs:
        print("❌ No vCenters found! Check .env file.")
        sys.exit(1)

    # Use first vCenter
    vc_id = vcs[0]["id"]
    print(f"\nUsing vCenter: {vcs[0]['name']} ({vc_id})\n")

    # Step 2: list VMs
    vms = test_list_vms(vc_id)

    # Step 3: resources
    test_resources(vc_id)

    if vms:
        vm_name, vm_state = vms[0]
        print(f"\nUsing VM: {vm_name} (state={vm_state})")

        # Step 4: find VM
        test_find_vm(vc_id, vm_name)

        # Step 5: snapshot (safest test - doesn't change power state)
        print("\nWould you like to test snapshot? (y/n): ", end="")
        if input().strip().lower() == "y":
            test_snapshot(vc_id, vm_name)

        # Step 6: power action
        if vm_state == "poweredOff":
            action = "start"
        else:
            action = "restart"
        print(f"\nWould you like to test '{action}' on '{vm_name}'? (y/n): ", end="")
        if input().strip().lower() == "y":
            test_power_action(vc_id, vm_name, action)

    print("\n" + "═" * 60)
    print("  Tests complete")
    print("═" * 60 + "\n")
