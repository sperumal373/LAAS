"""
Patch ad_dns_client.py:
  1. dns_list_zones  - scan ALL partitions (Domain + Forest + System), return every zone with its partition_dn
  2. dns_list_records - find zone's correct partition, use size_limit=0 so no records are truncated
  3. dns_add_record   - look up zone partition before writing
  4. dns_delete_record - look up zone partition before writing
"""

fpath = r"C:\caas-dashboard\backend\ad_dns_client.py"

with open(fpath, "r", encoding="utf-8") as f:
    src = f.read()

# ── OLD BLOCK (lines 507-657): everything from dns_list_zones through end of dns_delete_record ──
OLD = '''def dns_list_zones() -> dict:
    try:
        from ldap3 import SUBTREE
        root, conn = _dns_search_root()
        conn.search(root, "(objectClass=dnsZone)", search_scope=SUBTREE,
                    attributes=["dc", "distinguishedName"])
        zones = []
        for e in conn.entries:
            name = _str(e.dc)
            if not name or name in _SKIP_ZONES:
                continue
            zones.append({
                "name":        name,
                "dn":          _str(e.distinguishedName),
                "type":        "Primary",
                "ds_integrated": True,
                "is_reverse":  "in-addr.arpa" in name or "ip6.arpa" in name,
            })
        conn.unbind()
        return {"zones": sorted(zones, key=lambda x: x["name"])}
    except Exception as ex:
        log.error("dns_list_zones: %s", ex)
        return {"zones": [], "error": str(ex)}


def dns_list_records(zone: str) -> dict:
    try:
        from ldap3 import SUBTREE
        root, conn = _dns_search_root()
        zone_dn = f"DC={zone},{root}"
        conn.search(zone_dn, "(objectClass=dnsNode)", search_scope=SUBTREE,
                    attributes=["dc", "dnsRecord"])
        records = []
        for e in conn.entries:
            hostname = _str(e.dc)
            raws = e.dnsRecord.values if hasattr(e.dnsRecord, "values") else []
            if not raws and e.dnsRecord.value:
                raws = [e.dnsRecord.value]
            for raw in raws:
                parsed = _parse_record_blob(raw)
                if parsed:
                    records.append({"hostname": hostname, **parsed,
                                    "ttl": str(parsed["ttl"])})
        conn.unbind()
        # Sort: hostname alpha, then type
        records.sort(key=lambda x: (x["hostname"].lower(), x["type"]))
        return {"records": records}
    except Exception as ex:
        log.error("dns_list_records: %s", ex)
        return {"records": [], "error": str(ex)}'''

NEW = '''def dns_list_zones() -> dict:
    """Return every DNS zone from ALL AD-integrated partitions (Domain, Forest, System)."""
    try:
        from ldap3 import SUBTREE
        conn = _conn()
        zones = []
        seen = set()
        for tpl in _DNS_ROOTS:
            root = tpl.format(base=AD_BASE_DN)
            try:
                conn.search(root, "(objectClass=dnsZone)",
                            search_scope=SUBTREE,
                            attributes=["dc", "distinguishedName"],
                            size_limit=0)
                for e in conn.entries:
                    name = _str(e.dc)
                    if not name or name in _SKIP_ZONES or name in seen:
                        continue
                    seen.add(name)
                    zones.append({
                        "name":         name,
                        "dn":           _str(e.distinguishedName),
                        "partition_dn": root,
                        "type":         "Primary",
                        "ds_integrated": True,
                        "is_reverse":   "in-addr.arpa" in name or "ip6.arpa" in name,
                    })
            except Exception as ex:
                log.warning("dns_list_zones partition %s: %s", root, ex)
        conn.unbind()
        return {"zones": sorted(zones, key=lambda x: (x["is_reverse"], x["name"]))}
    except Exception as ex:
        log.error("dns_list_zones: %s", ex)
        return {"zones": [], "error": str(ex)}


def _zone_partition(zone: str, conn) -> str:
    """Return the partition_dn that contains the given zone, checking all partitions."""
    from ldap3 import SUBTREE
    for tpl in _DNS_ROOTS:
        root = tpl.format(base=AD_BASE_DN)
        try:
            conn.search(root, f"(&(objectClass=dnsZone)(dc={zone}))",
                        search_scope=SUBTREE, attributes=["dc"], size_limit=1)
            if conn.entries:
                return root
        except Exception:
            pass
    # Default fallback
    return _DNS_ROOTS[0].format(base=AD_BASE_DN)


def dns_list_records(zone: str) -> dict:
    """Return ALL records for a zone.  size_limit=0 ensures no truncation."""
    try:
        from ldap3 import SUBTREE
        conn = _conn()
        root = _zone_partition(zone, conn)
        zone_dn = f"DC={zone},{root}"
        conn.search(zone_dn, "(objectClass=dnsNode)",
                    search_scope=SUBTREE,
                    attributes=["dc", "dnsRecord"],
                    size_limit=0)
        records = []
        for e in conn.entries:
            hostname = _str(e.dc)
            raws = list(e.dnsRecord.values) if hasattr(e.dnsRecord, "values") else []
            if not raws and e.dnsRecord.value:
                raws = [e.dnsRecord.value]
            for raw in raws:
                parsed = _parse_record_blob(raw)
                if parsed:
                    records.append({"hostname": hostname, **parsed,
                                    "ttl": str(parsed["ttl"])})
        conn.unbind()
        records.sort(key=lambda x: (x["hostname"].lower(), x["type"]))
        return {"records": records}
    except Exception as ex:
        log.error("dns_list_records: %s", ex)
        return {"records": [], "error": str(ex)}'''

# ── patch add_record ──
OLD_ADD = '''        from ldap3 import SUBTREE, MODIFY_ADD, MODIFY_REPLACE
        root, conn = _dns_search_root(write=True)
        zone_dn = f"DC={zone},{root}"
        node_dn = f"DC={hostname},{zone_dn}"

        # Check if node already exists
        conn.search(zone_dn, f"(dc={hostname})", search_scope=SUBTREE,
                    attributes=["dnsRecord"])'''

NEW_ADD = '''        from ldap3 import SUBTREE, MODIFY_ADD, MODIFY_REPLACE
        conn = _conn_write()
        root = _zone_partition(zone, conn)
        zone_dn = f"DC={zone},{root}"
        node_dn = f"DC={hostname},{zone_dn}"

        # Check if node already exists
        conn.search(zone_dn, f"(dc={hostname})", search_scope=SUBTREE,
                    attributes=["dnsRecord"], size_limit=0)'''

# ── patch delete_record ──
OLD_DEL = '''        from ldap3 import SUBTREE, MODIFY_DELETE, MODIFY_REPLACE
        root, conn = _dns_search_root(write=True)
        zone_dn = f"DC={zone},{root}"
        node_dn = f"DC={hostname},{zone_dn}"
        conn.search(zone_dn, f"(dc={hostname})", search_scope=SUBTREE,
                    attributes=["dnsRecord"])'''

NEW_DEL = '''        from ldap3 import SUBTREE, MODIFY_DELETE, MODIFY_REPLACE
        conn = _conn_write()
        root = _zone_partition(zone, conn)
        zone_dn = f"DC={zone},{root}"
        node_dn = f"DC={hostname},{zone_dn}"
        conn.search(zone_dn, f"(dc={hostname})", search_scope=SUBTREE,
                    attributes=["dnsRecord"], size_limit=0)'''

# Apply all patches
if OLD not in src:
    # Try to find it with normalised whitespace
    print("ERROR: OLD block not found verbatim — trying line-by-line...")
    # Print first 200 chars around "def dns_list_zones"
    idx = src.find("def dns_list_zones")
    print(repr(src[idx:idx+300]))
else:
    src = src.replace(OLD, NEW, 1)
    print("OK: dns_list_zones + dns_list_records patched")

if OLD_ADD not in src:
    print("ERROR: OLD_ADD block not found")
    idx = src.find("def dns_add_record")
    print(repr(src[idx:idx+400]))
else:
    src = src.replace(OLD_ADD, NEW_ADD, 1)
    print("OK: dns_add_record patched")

if OLD_DEL not in src:
    print("ERROR: OLD_DEL block not found")
    idx = src.find("def dns_delete_record")
    print(repr(src[idx:idx+400]))
else:
    src = src.replace(OLD_DEL, NEW_DEL, 1)
    print("OK: dns_delete_record patched")

with open(fpath, "w", encoding="utf-8") as f:
    f.write(src)

print("DONE — file written.")
