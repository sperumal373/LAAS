"""Fix mtv_client.py orchestration to auto-discover VM networks/datastores."""
M = r"C:\caas-dashboard\backend\mtv_client.py"
data = open(M, "r", encoding="utf-8").read()

# 1. Fix create_mtv_plan to not set preserveStaticIPs and use warm=False by default
old1 = '''            "preserveStaticIPs": True,
            "runPreflightInspection": True,'''
new1 = '''            "preserveStaticIPs": False,
            "runPreflightInspection": True,'''
data = data.replace(old1, new1)

# 2. Add a function to auto-discover VM networks and datastores
# Find "# ---- Full orchestration ----" and insert before it
marker = "# ---- Full orchestration ----"
idx = data.find(marker)

new_func = '''
def discover_vm_resources(cluster, provider_name, vm_ids):
    """Auto-discover actual networks and datastores used by VMs from inventory."""
    inv = _inventory_url(cluster)
    headers = _inv_headers(cluster)
    uid = resolve_provider_uid(cluster, provider_name)
    networks = set()
    datastores = set()
    for vm in vm_ids:
        try:
            r = requests.get(f"{inv}/providers/vsphere/{uid}/vms/{vm['id']}", headers=headers, verify=False, timeout=15)
            r.raise_for_status()
            vd = r.json()
            for net in vd.get("networks", []):
                networks.add(net.get("id", ""))
            for disk in vd.get("disks", []):
                ds = disk.get("datastore", {})
                if ds.get("id"):
                    datastores.add(ds["id"])
            # Check CBT
            for disk in vd.get("disks", []):
                if not disk.get("changeTrackingEnabled", False):
                    vm["cbt_disabled"] = True
        except Exception as e:
            log.warning(f"Could not get VM detail for {vm['id']}: {e}")
    return list(networks), list(datastores)


'''

data = data[:idx] + new_func + data[idx:]

# 3. Replace the network/storage mapping logic in orchestrate_migration
# The old logic tries to use user-selected mappings. We need to auto-discover.
old_mapping = '''    # 4. Build network mappings
    # Get all source networks and datastores for default mapping
    src_networks = lookup_networks(cluster, source_provider)
    src_datastores = lookup_datastores(cluster, source_provider)
    net_id_map = {n["name"]: n["id"] for n in src_networks}
    ds_id_map = {d["name"]: d["id"] for d in src_datastores}

    nw_name = f"{plan_name}-nw"
    st_name = f"{plan_name}-st"

    # Build network map entries
    nw_entries = []
    if net_mapping:
        for m in net_mapping:
            src_name = m.get("source", "")
            tgt_name = m.get("target", "Pod Network (default)")
            src_id = net_id_map.get(src_name, "")
            if not src_id:
                # Try to find by partial match
                for k, v in net_id_map.items():
                    if src_name.lower() in k.lower():
                        src_id = v
                        src_name = k
                        break
            if not src_id and src_networks:
                # Default to first network
                src_id = src_networks[0]["id"]
                src_name = src_networks[0]["name"]
            if "pod" in tgt_name.lower() or tgt_name == "Pod Network (default)":
                nw_entries.append({"source_id": src_id, "source_name": src_name, "dest_type": "pod"})
            else:
                nw_entries.append({"source_id": src_id, "source_name": src_name,
                                   "dest_type": "multus", "dest_name": tgt_name, "dest_namespace": "default"})
    if not nw_entries and src_networks:
        # Fallback: map first network to pod network
        nw_entries.append({"source_id": src_networks[0]["id"], "source_name": src_networks[0]["name"], "dest_type": "pod"})

    # Build storage map entries
    st_entries = []
    if stor_mapping:
        for m in stor_mapping:
            src_name = m.get("source", "")
            tgt_sc = m.get("target", "purestorage-sc")
            src_id = ds_id_map.get(src_name, "")
            if not src_id:
                for k, v in ds_id_map.items():
                    if src_name.lower() in k.lower():
                        src_id = v
                        break
            if not src_id and src_datastores:
                src_id = src_datastores[0]["id"]
            st_entries.append({"source_id": src_id, "dest_storage_class": tgt_sc})
    if not st_entries and src_datastores:
        st_entries.append({"source_id": src_datastores[0]["id"], "dest_storage_class": "purestorage-sc"})'''

new_mapping = '''    # 4. Auto-discover actual VM networks and datastores
    _log("Discovering VM networks and datastores from inventory...")
    vm_net_ids, vm_ds_ids = discover_vm_resources(cluster, source_provider, vm_ids)
    _log(f"VM networks: {vm_net_ids}, datastores: {vm_ds_ids}")

    # Check if any VM has CBT disabled -> use cold migration
    use_warm = True
    for v in vm_ids:
        if v.get("cbt_disabled"):
            use_warm = False
            _log(f"VM '{v['name']}' has CBT disabled - using COLD migration")
            break

    nw_name = f"{plan_name}-nw"
    st_name = f"{plan_name}-st"

    # Determine target storage class from user mapping or default
    tgt_sc = "purestorage-sc"
    if stor_mapping:
        for m in stor_mapping:
            if m.get("target"):
                tgt_sc = m["target"]
                break

    # Determine target network from user mapping
    tgt_net_type = "pod"
    tgt_net_name = ""
    tgt_net_ns = "default"
    if net_mapping:
        for m in net_mapping:
            tgt = m.get("target", "Pod Network (default)")
            if "pod" not in tgt.lower():
                tgt_net_type = "multus"
                tgt_net_name = tgt
                break

    # Build network map: map EACH actual VM network to the target
    nw_entries = []
    for nid in vm_net_ids:
        nw_entries.append({"source_id": nid, "source_name": "", "dest_type": tgt_net_type,
                           "dest_name": tgt_net_name, "dest_namespace": tgt_net_ns})
    if not nw_entries:
        nw_entries.append({"source_id": "network-0", "source_name": "", "dest_type": "pod"})
    _log(f"Network mappings: {len(nw_entries)} source network(s) -> {tgt_net_type}")

    # Build storage map: map EACH actual VM datastore to the target SC
    st_entries = []
    for dsid in vm_ds_ids:
        st_entries.append({"source_id": dsid, "dest_storage_class": tgt_sc})
    if not st_entries:
        st_entries.append({"source_id": "datastore-0", "dest_storage_class": tgt_sc})
    _log(f"Storage mappings: {len(st_entries)} datastore(s) -> {tgt_sc}")'''

if old_mapping in data:
    data = data.replace(old_mapping, new_mapping)
    print("Replaced mapping logic")
else:
    print("ERROR: Could not find old mapping logic")

# 4. Fix create_mtv_plan call to pass use_warm
old_call = '''    create_mtv_plan(cluster, plan_name, source_provider, nw_name, st_name, vm_ids)'''
new_call = '''    create_mtv_plan(cluster, plan_name, source_provider, nw_name, st_name, vm_ids, warm=use_warm)'''
data = data.replace(old_call, new_call)

open(M, "w", encoding="utf-8").write(data)
print(f"Done. File size: {len(data)}")