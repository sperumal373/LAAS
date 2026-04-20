"""
Fix all topology issues:
1. Add get_volume_vcenter_mapping to vmware_client.py
2. Wire it into storage topology endpoint in main.py
3. Rewrite VolumeTopologyModal in App.jsx
"""
import re, sys
sys.stdout.reconfigure(encoding='utf-8')

# ═══════════════════════════════════════════════════════
# 1. vmware_client.py — append new function at end
# ═══════════════════════════════════════════════════════
vc_path = r'c:\caas-dashboard\backend\vmware_client.py'
with open(vc_path, encoding='utf-8', errors='replace') as f:
    vc = f.read()

NEW_VC_FN = '''

def get_volume_vcenter_mapping(naa_id: str = "", wwn: str = "") -> list:
    """
    Query all configured vCenters for ESXi hosts that see a storage LUN
    identified by its NAA canonical name or WWN.
    Returns a list of dicts:
      { vcenter, esxi_host, datastores:[{name,type,total_gb,free_gb}],
        hba_wwpns:[str], lun_seen:bool }
    Safe / best-effort — never raises.
    """
    results = []
    if not naa_id and not wwn:
        return results

    # normalise identifiers for comparison
    naa_lower = (naa_id or "").lower().replace(" ", "")
    wwn_lower = (wwn  or "").lower().replace(":", "").replace(" ", "")

    for vc_cfg in VCENTERS:
        si = None
        try:
            si = _connect(vc_cfg)
            content = si.RetrieveContent()
            h_view = content.viewManager.CreateContainerView(
                content.rootFolder, [vim.HostSystem], True)

            for host in h_view.view:
                try:
                    hname = ""
                    try: hname = host.summary.config.name
                    except Exception: pass

                    seen_naa   = False
                    seen_wwn   = False
                    hba_wwpns  = []
                    ds_names   = []   # datastore names backed by this LUN

                    ss = None
                    try: ss = host.configManager.storageSystem
                    except Exception: pass

                    if ss:
                        # ── Check scsiLun for canonical name match ──
                        try:
                            for lun in (ss.storageDeviceInfo.scsiLun or []):
                                cname = (getattr(lun, "canonicalName", "") or "").lower()
                                uid   = (getattr(lun, "uuid",          "") or "").lower()
                                if naa_lower and (naa_lower in cname or naa_lower in uid):
                                    seen_naa = True
                                    break
                        except Exception:
                            pass

                        # ── Map LUN → datastores via VMFS extents ──
                        if seen_naa:
                            try:
                                for mount in (ss.fileSystemVolumeInfo.mountInfo or []):
                                    vol = mount.volume
                                    if not hasattr(vol, "extent"):
                                        continue
                                    for ext in (vol.extent or []):
                                        dn = getattr(ext, "diskName", "") or ""
                                        if naa_lower and naa_lower in dn.lower():
                                            ds_names.append(vol.name)
                                            break
                            except Exception:
                                pass

                    # ── Check FC HBA WWPNs ───────────────────────────
                    try:
                        if host.config and host.config.storageDevice:
                            for hba in (host.config.storageDevice.hostBusAdapter or []):
                                wp = getattr(hba, "portWorldWideName", None)
                                if wp:
                                    wp_hex = format(wp, '016x') if isinstance(wp, int) else str(wp).replace(":", "").lower()
                                    hba_wwpns.append(wp_hex)
                                    if wwn_lower and wwn_lower in wp_hex:
                                        seen_wwn = True
                    except Exception:
                        pass

                    if seen_naa or seen_wwn:
                        # build datastore detail list
                        ds_detail = []
                        try:
                            for ds in (host.datastore or []):
                                try:
                                    s = ds.summary
                                    if s.name in ds_names or not ds_names:
                                        ds_detail.append({
                                            "name":     s.name,
                                            "type":     s.type,
                                            "total_gb": round((s.capacity  or 0) / 1024**3, 1),
                                            "free_gb":  round((s.freeSpace or 0) / 1024**3, 1),
                                        })
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        results.append({
                            "vcenter":     vc_cfg.get("name", vc_cfg.get("host", "")),
                            "esxi_host":   hname,
                            "datastores":  ds_detail,
                            "hba_wwpns":   hba_wwpns,
                            "lun_seen":    True,
                            "match_type":  "naa" if seen_naa else "wwn",
                        })
                except Exception:
                    pass

            try: h_view.Destroy()
            except Exception: pass

        except Exception:
            pass
        finally:
            if si:
                try:
                    from pyVim.connect import Disconnect as _D; _D(si)
                except Exception:
                    pass

    return results
'''

if 'get_volume_vcenter_mapping' not in vc:
    vc2 = vc + NEW_VC_FN
    with open(vc_path, 'w', encoding='utf-8') as f:
        f.write(vc2)
    print("OK: get_volume_vcenter_mapping added to vmware_client.py")
else:
    print("SKIP: get_volume_vcenter_mapping already in vmware_client.py")

# ═══════════════════════════════════════════════════════
# 2. main.py — import + use get_volume_vcenter_mapping
# ═══════════════════════════════════════════════════════
mp_path = r'c:\caas-dashboard\backend\main.py'
with open(mp_path, encoding='utf-8', errors='replace') as f:
    mp = f.read()

# a) add to import
old_import = 'get_vm_topology, get_host_topology'
new_import = 'get_vm_topology, get_host_topology, get_volume_vcenter_mapping'
if old_import in mp and new_import not in mp:
    mp = mp.replace(old_import, new_import, 1)
    print("OK: import updated in main.py")
else:
    print("SKIP: import already updated or pattern not found")

# b) update topology endpoint to include vcenter mapping
old_ep = '''    try:
        topo = get_volume_topology(arr, volume)
        return topo
    except Exception as e:
        raise HTTPException(502, detail=f"Topology fe'''

new_ep = '''    try:
        topo = get_volume_topology(arr, volume)
        # Enrich with vCenter/ESXi mapping using NAA id or WWN
        try:
            naa = topo.get("naa_id", "") or ""
            wwn = topo.get("wwn", "") or ""
            if naa or wwn:
                topo["vcenter_mapping"] = get_volume_vcenter_mapping(naa_id=naa, wwn=wwn)
            else:
                topo["vcenter_mapping"] = []
        except Exception:
            topo["vcenter_mapping"] = []
        return topo
    except Exception as e:
        raise HTTPException(502, detail=f"Topology fe'''

if old_ep in mp:
    mp = mp.replace(old_ep, new_ep, 1)
    print("OK: topology endpoint updated in main.py")
else:
    print("WARN: endpoint pattern not found in main.py — check manually")
    # show what's there
    idx = mp.find('arrays/{arr_id}/topology')
    print(repr(mp[idx:idx+400]))

with open(mp_path, 'w', encoding='utf-8') as f:
    f.write(mp)

print("Done backend changes")
