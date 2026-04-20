"""
Adds topology buttons to HPE Nimble, Dell PowerFlex volume rows in App.jsx
and adds the get_volume_topology function to storage_client.py
"""

# ─── 1. App.jsx: HPE Nimble + Dell PowerFlex topology buttons ───────────────

with open(r'c:\caas-dashboard\frontend\src\App.jsx', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Find the sections dynamically
nim_thead_idx = -1
nim_row_end_idx = -1
pfx_thead_idx = -1
pfx_row_end_idx = -1

for i, line in enumerate(lines):
    # Nimble: find thead inside nim_vols section
    if 'nim_vols' in line and 'isNimble' in line:
        # Look ahead for the thead
        for j in range(i, i+10):
            if 'Name' in lines[j] and 'Online' in lines[j] and 'Thin' in lines[j]:
                nim_thead_idx = j
                break
    # Nimble: find the closing </tr>)}</tbody> right after nim vol row
    if nim_thead_idx > 0 and i > nim_thead_idx and '</tr>)}</tbody>' in line and nim_row_end_idx < 0:
        # Make sure it's in nim section (before nim_pools)
        if i < nim_thead_idx + 30:
            nim_row_end_idx = i

    # PowerFlex: find thead inside pfx_vols section
    if 'pfx_vols' in line and 'isPflex' in line:
        for j in range(i, i+10):
            if 'Size (GB)' in lines[j] and 'VTree' in lines[j]:
                pfx_thead_idx = j
                break
    # PowerFlex: find closing </tr> of pflex vol row
    if pfx_thead_idx > 0 and i > pfx_thead_idx and pfx_row_end_idx < 0:
        if 'vtree_id' in lines[i] or ('vtree_id' in lines[i-1]):
            # Find the </tr> on this or next line
            if '</tr>' in line:
                pfx_row_end_idx = i
            elif i+1 < len(lines) and '</tr>' in lines[i+1]:
                pfx_row_end_idx = i+1

print(f"Nimble thead at: {nim_thead_idx+1}, row end at: {nim_row_end_idx+1}")
print(f"PowerFlex thead at: {pfx_thead_idx+1}, row end at: {pfx_row_end_idx+1}")

# ── HPE Nimble thead: add empty Actions column ──
if nim_thead_idx > 0:
    old = lines[nim_thead_idx]
    # Replace the closing list ] with ,""] 
    if '"Connections"' in old or '"Conns"' in old:
        new = old.replace('"Connections"', '"Connections",""').replace('"Conns"', '"Connections",""')
        lines[nim_thead_idx] = new
        print(f"Nimble thead updated at line {nim_thead_idx+1}")

# ── HPE Nimble row end: add topo button before </tr> ──
if nim_row_end_idx > 0:
    old = lines[nim_row_end_idx]
    btn = '                      <td style={{padding:"4px 6px",textAlign:"center"}}><button title={"Topology for "+v.name} onClick={()=>setTopoModal(v)} style={{padding:"3px 9px",borderRadius:6,border:"1px solid #01A98240",background:"#01A98210",color:"#01A982",fontSize:10,fontWeight:700,cursor:"pointer"}}>🔗 Topo</button></td>\n'
    lines[nim_row_end_idx] = btn + old
    print(f"Nimble topo button inserted before line {nim_row_end_idx+1}")

# ── PowerFlex thead: add empty Actions column ──
if pfx_thead_idx > 0:
    old = lines[pfx_thead_idx]
    if '"VTree ID"' in old:
        lines[pfx_thead_idx] = old.replace('"VTree ID"', '"VTree ID",""')
        print(f"PowerFlex thead updated at line {pfx_thead_idx+1}")

# ── PowerFlex row end: add topo button ──
if pfx_row_end_idx > 0:
    old = lines[pfx_row_end_idx]
    btn = '                          <td style={{padding:"4px 6px",textAlign:"center"}}><button title={"Topology for "+v.name} onClick={()=>setTopoModal(v)} style={{padding:"3px 9px",borderRadius:6,border:"1px solid #0076CE40",background:"#0076CE10",color:"#0076CE",fontSize:10,fontWeight:700,cursor:"pointer"}}>🔗 Topo</button></td>\n'
    lines[pfx_row_end_idx] = btn + old
    print(f"PowerFlex topo button inserted before line {pfx_row_end_idx+1}")

with open(r'c:\caas-dashboard\frontend\src\App.jsx', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f"App.jsx saved. Lines: {len(lines)}")

# ─── 2. storage_client.py: add get_volume_topology function ─────────────────

sc_path = r'c:\caas-dashboard\backend\storage_client.py'
with open(sc_path, encoding='utf-8', errors='replace') as f:
    sc = f.read()

topo_func = '''

def get_volume_topology(arr: dict, volume_name: str) -> dict:
    """
    Build a rich topology map for a single volume.
    Returns:
      {
        volume_name, vendor, protocol, serial, wwn, naa_id,
        size, used, state, pool, svm, pod, data_reduction, thin,
        replication: [{direction, peer_volume, peer_svm, peer_site, state, healthy, lag, policy}],
        topology: [{
          host_name, os_type, host_type, protocol,
          lun_id, volume_wwn, port, active,
          iqns, wwns, nqns, initiators,
          host_group, host_set,
          sdc_ip, sdc_os, chap_enabled
        }]
      }
    """
    vendor = arr.get("vendor", "")
    try:
        data = get_array_data(arr)
    except Exception as e:
        return {"error": str(e), "volume_name": volume_name, "topology": []}

    result = {
        "volume_name": volume_name,
        "vendor": vendor,
        "protocol": "",
        "serial": "",
        "wwn": "",
        "naa_id": "",
        "size": "",
        "used": "",
        "state": "",
        "pool": "",
        "svm": "",
        "pod": "",
        "data_reduction": None,
        "thin": None,
        "replication": [],
        "topology": [],
    }

    def fmt(b):
        if not b or not isinstance(b, (int, float)): return ""
        for u, t in [("PB", 1e15), ("TB", 1e12), ("GB", 1e9), ("MB", 1e6)]:
            if b >= t: return f"{b/t:.2f} {u}"
        return f"{b/1e6:.0f} MB"

    # ─── Pure FlashArray ─────────────────────────────────────────────────────
    if vendor == "Pure FlashArray":
        vol_list   = data.get("volume_list", [])
        host_list  = data.get("host_list", [])
        conn_list  = data.get("connection_list", [])

        vol = next((v for v in vol_list if v.get("name") == volume_name), None)
        if vol:
            serial = vol.get("serial", "")
            result.update({
                "serial":         serial,
                "naa_id":         ("naa.624a9370" + serial.lower()) if serial else "",
                "size":           fmt(vol.get("provisioned_bytes")),
                "used":           fmt(vol.get("used_bytes")),
                "state":          "online",
                "pod":            vol.get("pod", ""),
                "data_reduction": vol.get("data_reduction"),
                "protocol":       "iSCSI / FC",
            })

        host_map = {h["name"]: h for h in host_list}
        for conn in conn_list:
            if conn.get("volume") != volume_name:
                continue
            hname = conn.get("host", "")
            h = host_map.get(hname, {})
            iqns = h.get("iqns") or []
            wwns = h.get("wwns") or []
            nqns = h.get("nqns") or []
            proto = h.get("protocol", "")
            if not proto:
                proto = "iSCSI" if iqns else ("FC" if wwns else ("NVMe" if nqns else ""))
            result["topology"].append({
                "host_name":  hname,
                "os_type":    h.get("os_type", ""),
                "host_type":  "",
                "protocol":   proto,
                "lun_id":     conn.get("lun"),
                "volume_wwn": "",
                "port":       "",
                "active":     True,
                "iqns":       iqns,
                "wwns":       wwns,
                "nqns":       nqns,
                "initiators": [],
                "host_group": conn.get("host_group", "") or h.get("host_group", ""),
                "host_set":   "",
                "sdc_ip":     "",
                "sdc_os":     "",
                "chap_enabled": False,
            })
        if result["topology"]:
            protos = set(e["protocol"] for e in result["topology"] if e["protocol"])
            result["protocol"] = " / ".join(protos) if protos else "SAN"

    # ─── NetApp ONTAP ────────────────────────────────────────────────────────
    elif vendor == "NetApp":
        vol_list    = data.get("volume_list", [])
        lun_list    = data.get("lun_list", [])
        igroup_list = data.get("igroup_list", [])
        sm_list     = data.get("snapmirror_list", [])
        nic_list    = data.get("nic_list", [])

        vol = next((v for v in vol_list if v.get("name") == volume_name), None)
        if vol:
            result.update({
                "size":  fmt(vol.get("total_bytes")),
                "used":  fmt(vol.get("used_bytes")),
                "state": vol.get("state", ""),
                "svm":   vol.get("svm", ""),
                "protocol": "NFS/iSCSI",
            })

        # Replication
        for r in sm_list:
            if r.get("source_vol") == volume_name:
                result["replication"].append({
                    "direction":   "outbound",
                    "peer_volume": r.get("dest_vol", ""),
                    "peer_svm":    r.get("dest_svm", ""),
                    "peer_site":   "",
                    "state":       r.get("state", ""),
                    "healthy":     r.get("healthy"),
                    "lag":         r.get("lag_time", ""),
                    "policy":      r.get("policy", "SnapMirror"),
                })
            elif r.get("dest_vol") == volume_name:
                result["replication"].append({
                    "direction":   "inbound",
                    "peer_volume": r.get("source_vol", ""),
                    "peer_svm":    r.get("source_svm", ""),
                    "peer_site":   "",
                    "state":       r.get("state", ""),
                    "healthy":     r.get("healthy"),
                    "lag":         r.get("lag_time", ""),
                    "policy":      r.get("policy", "SnapMirror"),
                })

        # LUNs in this volume → iGroups
        vol_luns = [l for l in lun_list if l.get("volume") == volume_name]
        ig_map = {ig["name"]: ig for ig in igroup_list}
        seen_ig = set()
        for lun in vol_luns:
            # Find iGroups that map to this LUN path
            for ig in igroup_list:
                if ig["name"] in seen_ig:
                    continue
                seen_ig.add(ig["name"])
                proto = ig.get("protocol", "")
                initiators = [ini.get("name", "") if isinstance(ini, dict) else str(ini) for ini in (ig.get("initiators") or [])]
                iqns = [x for x in initiators if x.startswith("iqn.")]
                wwns = [x for x in initiators if not x.startswith("iqn.") and not x.startswith("nqn.")]
                nqns = [x for x in initiators if x.startswith("nqn.")]
                result["topology"].append({
                    "host_name":   ig.get("name", ""),
                    "os_type":     ig.get("os_type", ""),
                    "host_type":   "iGroup",
                    "protocol":    proto,
                    "lun_id":      None,
                    "volume_wwn":  "",
                    "port":        "",
                    "active":      lun.get("mapped", False),
                    "iqns":        iqns,
                    "wwns":        wwns,
                    "nqns":        nqns,
                    "initiators":  initiators,
                    "host_group":  "",
                    "host_set":    "",
                    "sdc_ip":      "",
                    "sdc_os":      "",
                    "chap_enabled": False,
                })
        result["protocol"] = "iSCSI / NFS"

    # ─── HPE Alletra ─────────────────────────────────────────────────────────
    elif vendor == "HPE":
        vol_list  = data.get("volume_list", []) or data.get("vol_list", [])
        host_list = data.get("host_list", [])
        vlun_list = data.get("vlun_list", [])

        vol = next((v for v in vol_list if v.get("name") == volume_name), None)
        if vol:
            result.update({
                "wwn":   vol.get("wwn", ""),
                "size":  fmt(vol.get("size_bytes")),
                "used":  fmt(vol.get("used_bytes")),
                "state": vol.get("state", ""),
                "pool":  vol.get("cpg", ""),
                "protocol": "iSCSI / FC",
            })

        host_map = {h["name"]: h for h in host_list}
        for vl in vlun_list:
            if vl.get("volume") != volume_name:
                continue
            hname = vl.get("host", "")
            h = host_map.get(hname, {})
            wwns  = h.get("fc_wwns") or []
            iqns  = h.get("iscsi_names") or []
            proto = h.get("protocol", "")
            if not proto:
                proto = "FC" if wwns else ("iSCSI" if iqns else "")
            result["topology"].append({
                "host_name":  hname,
                "os_type":    "",
                "host_type":  h.get("persona", ""),
                "protocol":   proto,
                "lun_id":     vl.get("lun"),
                "volume_wwn": vl.get("volume_wwn", ""),
                "port":       vl.get("port", ""),
                "active":     vl.get("active", False),
                "iqns":       iqns,
                "wwns":       wwns,
                "nqns":       [],
                "initiators": [],
                "host_group": "",
                "host_set":   h.get("host_set", ""),
                "sdc_ip":     "",
                "sdc_os":     "",
                "chap_enabled": h.get("chap_enabled", False),
            })

    # ─── Dell PowerStore ─────────────────────────────────────────────────────
    elif vendor == "Dell-EMC":
        vol_list  = data.get("volume_list", [])
        host_list = data.get("host_list", [])

        vol = next((v for v in vol_list if v.get("name") == volume_name), None)
        if vol:
            result.update({
                "wwn":   vol.get("wwn", ""),
                "size":  fmt(vol.get("size")),
                "state": vol.get("state", ""),
                "protocol": "FC / iSCSI",
            })
            # Try to find host mappings from host_list
            for h in host_list:
                result["topology"].append({
                    "host_name":   h.get("name", ""),
                    "os_type":     h.get("os_type", ""),
                    "host_type":   h.get("type", ""),
                    "protocol":    "FC / iSCSI",
                    "lun_id":      None,
                    "volume_wwn":  vol.get("wwn", ""),
                    "port":        "",
                    "active":      True,
                    "iqns":        [],
                    "wwns":        [],
                    "nqns":        [],
                    "initiators":  [],
                    "host_group":  h.get("host_group_id", ""),
                    "host_set":    "",
                    "sdc_ip":      "",
                    "sdc_os":      "",
                    "chap_enabled": False,
                })

    # ─── Dell PowerFlex ──────────────────────────────────────────────────────
    elif vendor == "Dell PowerFlex":
        vol_list = data.get("volume_list", [])
        sdc_list = data.get("sdc_list", [])

        vol = next((v for v in vol_list if v.get("name") == volume_name), None)
        if vol:
            result.update({
                "serial":   vol.get("id", ""),
                "size":     str(vol.get("size_gb", "")) + " GB",
                "state":    "online",
                "pool":     vol.get("storage_pool", ""),
                "protocol": "SDC (NVMe/TCP)",
            })
            mapped = vol.get("mapped_sdc_count", 0)
            result["topology"] = [{
                "host_name":  sdc.get("name", sdc.get("id", "")),
                "os_type":    sdc.get("os_type", ""),
                "host_type":  "SDC",
                "protocol":   "SDC",
                "lun_id":     None,
                "volume_wwn": "",
                "port":       "",
                "active":     sdc.get("state", "") == "Active",
                "iqns":       [],
                "wwns":       [],
                "nqns":       [],
                "initiators": [],
                "host_group": "",
                "host_set":   "",
                "sdc_ip":     sdc.get("ip", ""),
                "sdc_os":     sdc.get("host_os", sdc.get("os_type", "")),
                "chap_enabled": False,
            } for sdc in sdc_list[:mapped or len(sdc_list)]]

    # ─── HPE Nimble ──────────────────────────────────────────────────────────
    elif vendor == "HPE Nimble":
        vol_list = data.get("volume_list", []) or data.get("vol_list", [])
        ig_list  = data.get("initiator_group_list", [])

        vol = next((v for v in vol_list if v.get("name") == volume_name), None)
        if vol:
            result.update({
                "serial":   vol.get("serial", ""),
                "size":     fmt(vol.get("size_bytes")),
                "used":     fmt(vol.get("used_bytes")),
                "state":    "online" if vol.get("online") else "offline",
                "pool":     vol.get("pool", ""),
                "protocol": "iSCSI / FC",
                "thin":     vol.get("thin", True),
            })
        for ig in ig_list:
            result["topology"].append({
                "host_name":  ig.get("name", ""),
                "os_type":    ig.get("host_type", ""),
                "host_type":  "Initiator Group",
                "protocol":   (ig.get("protocol") or "").upper(),
                "lun_id":     None,
                "volume_wwn": "",
                "port":       "",
                "active":     True,
                "iqns":       [],
                "wwns":       [],
                "nqns":       [],
                "initiators": [],
                "host_group": "",
                "host_set":   "",
                "sdc_ip":     "",
                "sdc_os":     "",
                "chap_enabled": False,
            })

    return result
'''

if 'def get_volume_topology' not in sc:
    sc = sc + topo_func
    with open(sc_path, 'w', encoding='utf-8') as f:
        f.write(sc)
    print("storage_client.py: get_volume_topology added")
else:
    print("storage_client.py: get_volume_topology already present")
