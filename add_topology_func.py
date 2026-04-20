"""
Append get_volume_topology() to storage_client.py
This is purely additive - no existing code is modified.
"""

path = r'c:\caas-dashboard\backend\storage_client.py'
content = open(path, encoding='utf-8', errors='replace').read()

# Check it's not already there
if 'get_volume_topology' in content:
    print("Already present - skipping")
    exit(0)

new_func = '''

# ─── Volume Topology Assembly ─────────────────────────────────────────────────
def get_volume_topology(arr: dict, volume_name: str) -> dict:
    """
    Build a rich topology map for a single volume across all vendors.
    Returns:
      volume_name, serial, wwn, naa_id, size, used, state, protocol,
      pool, svm, pod, data_reduction, thin,
      replication: [{direction, peer_volume, peer_svm, peer_site, policy, state, healthy, lag}],
      topology:    [{host_name, host_group, host_set, os_type, protocol,
                    lun_id, volume_wwn, port, active,
                    iqns[], wwns[], nqns[], initiators[],
                    sdc_ip, sdc_os, chap_enabled}]
    """
    vendor  = arr.get("vendor", "")
    data    = get_array_data(arr)
    result  = {
        "volume_name":    volume_name,
        "vendor":         vendor,
        "serial":         None,
        "wwn":            None,
        "naa_id":         None,
        "size":           None,
        "used":           None,
        "state":          None,
        "protocol":       None,
        "pool":           None,
        "svm":            None,
        "pod":            None,
        "data_reduction": None,
        "thin":           None,
        "lun_id":         None,
        "replication":    [],
        "topology":       [],
    }

    def _fmt(b):
        if not b or not isinstance(b, (int, float)) or b == 0:
            return None
        for unit, div in [("PB", 1e15), ("TB", 1e12), ("GB", 1e9), ("MB", 1e6)]:
            if b >= div:
                return f"{b/div:.2f} {unit}"
        return f"{b/1e6:.0f} MB"

    # ── Pure FlashArray ───────────────────────────────────────────
    if vendor == "Pure FlashArray":
        vols  = data.get("volume_list", [])
        hosts = data.get("host_list", [])
        conns = data.get("connection_list", [])
        vol   = next((v for v in vols if v.get("name") == volume_name), None)
        if vol:
            serial = vol.get("serial", "")
            result.update({
                "serial":         serial,
                "naa_id":         f"naa.{serial.lower()}" if serial else None,
                "size":           _fmt(vol.get("provisioned_bytes")),
                "used":           _fmt(vol.get("used_bytes")),
                "state":          "online",
                "protocol":       "iSCSI/FC",
                "pod":            vol.get("pod"),
                "data_reduction": vol.get("data_reduction"),
            })
        # Build topology from connection_list
        vol_conns = [c for c in conns if c.get("volume") == volume_name]
        for conn in vol_conns:
            host_name = conn.get("host") or conn.get("host_group")
            host_obj  = next((h for h in hosts if h.get("name") == host_name), {})
            entry = {
                "host_name":    host_name,
                "host_group":   conn.get("host_group"),
                "os_type":      host_obj.get("os", host_obj.get("host_type")),
                "protocol":     host_obj.get("protocol"),
                "lun_id":       conn.get("lun"),
                "iqns":         host_obj.get("iqns") or [],
                "wwns":         host_obj.get("wwns") or [],
                "nqns":         host_obj.get("nqns") or [],
                "active":       True,
            }
            result["topology"].append(entry)
        # Detect protocol from first host
        if result["topology"]:
            h0 = result["topology"][0]
            if h0["iqns"]:
                result["protocol"] = "iSCSI"
            elif h0["wwns"]:
                result["protocol"] = "FC"
            elif h0["nqns"]:
                result["protocol"] = "NVMe"

    # ── NetApp ONTAP ──────────────────────────────────────────────
    elif vendor == "NetApp":
        vols    = data.get("volume_list", [])
        luns    = data.get("lun_list", [])
        igroups = data.get("igroup_list", [])
        mirrors = data.get("snapmirror_list", [])
        vol     = next((v for v in vols if v.get("name") == volume_name), None)
        if vol:
            result.update({
                "size":   _fmt(vol.get("total_bytes")),
                "used":   _fmt(vol.get("used_bytes")),
                "state":  vol.get("state"),
                "svm":    vol.get("svm"),
                "pool":   vol.get("aggregate"),
            })
        # LUNs in this volume → iGroups
        vol_luns = [l for l in luns if l.get("volume") == volume_name]
        seen_ig  = set()
        for lun in vol_luns:
            lun_serial = lun.get("serial", "")
            for ig in igroups:
                if ig.get("name") not in seen_ig:
                    seen_ig.add(ig.get("name"))
                    proto = ig.get("protocol", "").lower()
                    entry = {
                        "host_name":  ig.get("name"),
                        "os_type":    ig.get("os_type"),
                        "protocol":   ig.get("protocol"),
                        "lun_id":     lun.get("id"),
                        "initiators": ig.get("initiators") or [],
                        "iqns":       [x for x in (ig.get("initiators") or []) if x.startswith("iqn.")],
                        "wwns":       [x for x in (ig.get("initiators") or []) if not x.startswith("iqn.") and not x.startswith("nqn.")],
                        "nqns":       [x for x in (ig.get("initiators") or []) if x.startswith("nqn.")],
                        "active":     lun.get("mapped", False),
                    }
                    result["topology"].append(entry)
            # First LUN serial for volume serial
            if lun_serial and not result["serial"]:
                result["serial"] = lun_serial
                result["naa_id"] = f"naa.600a0980{lun_serial.lower()[-8:]}" if lun_serial else None
        # SnapMirror replication
        for m in mirrors:
            if m.get("source_vol") == volume_name:
                result["replication"].append({
                    "direction":   "outbound",
                    "peer_volume": m.get("dest_vol"),
                    "peer_svm":    m.get("dest_svm"),
                    "policy":      m.get("policy"),
                    "state":       m.get("state"),
                    "healthy":     m.get("healthy"),
                    "lag":         m.get("lag_time"),
                })
            elif m.get("dest_vol") == volume_name:
                result["replication"].append({
                    "direction":   "inbound",
                    "peer_volume": m.get("source_vol"),
                    "peer_svm":    m.get("source_svm"),
                    "policy":      m.get("policy"),
                    "state":       m.get("state"),
                    "healthy":     m.get("healthy"),
                    "lag":         m.get("lag_time"),
                })
        proto_set = set(e.get("protocol","").lower() for e in result["topology"])
        if "iscsi" in proto_set:
            result["protocol"] = "iSCSI"
        elif "fcp" in proto_set or "fc" in proto_set:
            result["protocol"] = "FC"

    # ── HPE Alletra (3PAR / Primera) ─────────────────────────────
    elif vendor == "HPE":
        vols  = data.get("volume_list", [])
        hosts = data.get("host_list", [])
        vluns = data.get("vlun_list", [])
        vol   = next((v for v in vols if v.get("name") == volume_name), None)
        if vol:
            result.update({
                "wwn":      vol.get("wwn"),
                "naa_id":   f"naa.{(vol.get('wwn') or '').lower().replace(':','')}",
                "size":     _fmt(vol.get("size_bytes")),
                "used":     _fmt(vol.get("used_bytes")),
                "state":    vol.get("state"),
                "pool":     vol.get("cpg"),
                "protocol": "FC/iSCSI",
            })
        # VLUNs for this volume
        vol_vluns = [vl for vl in vluns if vl.get("volume") == volume_name]
        for vl in vol_vluns:
            host_name = vl.get("host")
            host_obj  = next((h for h in hosts if h.get("name") == host_name), {})
            proto = host_obj.get("protocol", "")
            entry = {
                "host_name":    host_name,
                "host_set":     host_obj.get("host_set"),
                "os_type":      host_obj.get("persona"),
                "protocol":     proto,
                "lun_id":       vl.get("lun"),
                "volume_wwn":   vl.get("volume_wwn"),
                "port":         vl.get("port"),
                "active":       vl.get("active"),
                "iqns":         host_obj.get("iscsi_names") or [],
                "wwns":         host_obj.get("fc_wwns") or [],
                "nqns":         [],
                "chap_enabled": host_obj.get("chap_enabled", False),
            }
            result["topology"].append(entry)
        if vol_vluns:
            first_host = next((h for h in hosts if h.get("name") == vol_vluns[0].get("host")), {})
            if first_host.get("fc_wwns"):
                result["protocol"] = "FC"
            elif first_host.get("iscsi_names"):
                result["protocol"] = "iSCSI"

    # ── Dell PowerStore ───────────────────────────────────────────
    elif vendor == "Dell-EMC":
        vols  = data.get("volume_list", [])
        hosts = data.get("host_list", [])
        vol   = next((v for v in vols if v.get("name") == volume_name), None)
        if vol:
            wwn = vol.get("wwn", "")
            result.update({
                "wwn":      wwn,
                "naa_id":   f"naa.{wwn.lower().replace(':','')}" if wwn else None,
                "size":     _fmt(vol.get("size")),
                "state":    vol.get("state"),
                "protocol": "FC/iSCSI",
            })
        # PowerStore doesn't return per-volume host mapping in the basic data pull
        # Show host list as potential targets
        for h in hosts[:20]:
            result["topology"].append({
                "host_name": h.get("name"),
                "os_type":   h.get("os_type"),
                "protocol":  "FC/iSCSI",
                "iqns": [], "wwns": [], "nqns": [],
            })

    # ── Dell PowerFlex ────────────────────────────────────────────
    elif vendor == "Dell PowerFlex":
        vols = data.get("volume_list", [])
        sdcs = data.get("sdc_list", [])
        vol  = next((v for v in vols if v.get("name") == volume_name), None)
        if vol:
            result.update({
                "serial":   vol.get("id", vol.get("serial")),
                "size":     f"{vol.get('size_gb','—')} GB" if vol.get("size_gb") else None,
                "state":    "online",
                "protocol": "NVMe/TCP (SDC)",
                "pool":     vol.get("storage_pool"),
            })
        # SDC mappings (PowerFlex uses SDC clients, not traditional LUNs)
        for sdc in sdcs:
            result["topology"].append({
                "host_name": sdc.get("name") or sdc.get("ip"),
                "os_type":   sdc.get("os_type") or sdc.get("host_os"),
                "protocol":  "SDC",
                "sdc_ip":    sdc.get("ip"),
                "sdc_os":    sdc.get("os_type") or sdc.get("host_os"),
                "active":    sdc.get("state") == "Active",
                "iqns": [], "wwns": [], "nqns": [],
            })

    # ── HPE Nimble ────────────────────────────────────────────────
    elif vendor == "HPE Nimble":
        vols   = data.get("volume_list", [])
        igroups = data.get("initiator_group_list", [])
        vol    = next((v for v in vols if v.get("name") == volume_name), None)
        if vol:
            serial = str(vol.get("serial", ""))
            result.update({
                "serial":   serial,
                "naa_id":   f"naa.{serial.lower()}" if serial else None,
                "size":     _fmt(vol.get("size_bytes")),
                "used":     _fmt(vol.get("used_bytes")),
                "state":    "online" if vol.get("online") else "offline",
                "pool":     vol.get("pool"),
                "protocol": "iSCSI/FC",
                "thin":     vol.get("thin"),
            })
        for ig in igroups:
            proto = (ig.get("protocol") or "").upper()
            result["topology"].append({
                "host_name": ig.get("name"),
                "os_type":   ig.get("host_type"),
                "protocol":  proto,
                "iqns":      [],
                "wwns":      [],
                "nqns":      [],
            })

    # ── Dell PowerScale (NAS – NFS/SMB) ──────────────────────────
    elif vendor == "Dell PowerScale":
        nfs  = data.get("nfs_export_list", [])
        smb  = data.get("smb_share_list", [])
        result.update({"protocol": "NFS/SMB", "state": "online"})
        # Match exports/shares whose path matches the volume name
        for exp in nfs:
            for path_str in (exp.get("paths") or []):
                if volume_name in path_str:
                    clients = (exp.get("read_write_clients") or []) + (exp.get("read_only_clients") or [])
                    for client in (clients if clients else ["all"]):
                        result["topology"].append({
                            "host_name": client,
                            "protocol":  "NFS",
                            "os_type":   "Linux/Unix",
                            "iqns": [], "wwns": [], "nqns": [],
                        })
        for share in smb:
            if volume_name in (share.get("path") or ""):
                result["topology"].append({
                    "host_name": share.get("name"),
                    "protocol":  "SMB",
                    "os_type":   "Windows",
                    "iqns": [], "wwns": [], "nqns": [],
                })

    return result
'''

content += new_func
open(path, 'w', encoding='utf-8').write(content)
print("get_volume_topology() appended to storage_client.py successfully")
print(f"New file size: {len(content)} chars")
