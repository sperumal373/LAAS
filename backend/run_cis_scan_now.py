"""
run_cis_scan_now.py — Immediately scan known-reachable VMs and insert results.
Run: cd C:\caas-dashboard\backend && venv\Scripts\python run_cis_scan_now.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from cis_scanner import (
    _ssh_run_checks, _winrm_run_checks, _detect_os_via_ssh, _detect_os_via_winrm,
    _write_vm_scan, _load_creds_for_os, get_db, log, get_checks_for_os
)
import socket

# ── Target VMs (confirmed reachable + OS known) ──────────────────────────────
TARGETS = [
    # (hostname,           ip,              os_family, asset_id)
    ("ANSIBLE-TOWER-92.146",   "172.17.92.146",  "linux",   1395),
    ("bastion",                "172.17.70.26",   "linux",   1573),
    ("bastionvmlab",           "172.17.91.107",  "linux",   1491),
    ("dataconfdrvm",           "172.17.85.237",  "linux",   1507),
    ("cicdJFrog",              "172.17.65.115",  "linux",    602),
    ("ATT_CE-1-Engg",          "172.17.91.88",   "linux",   1798),
    ("24112025SDXDCWADDNS",    "172.17.65.134",  "windows",  715),
    ("AD_SDXLAB",              "172.17.90.119",  "windows",  653),
]

LINUX_CREDS   = [
    {"username": "root", "password": "Wipro@123",  "port": 22},
    {"username": "root", "password": "sdxcoe@123", "port": 22},
]
WINDOWS_CREDS = [
    {"username": "Administrator",    "password": "Wipro@123",  "port": 5985},
    {"username": "sdxtest\\azurehci","password": "Wipro@123",  "port": 5985},
]


def port_open(ip, port, timeout=5):
    try:
        s = socket.create_connection((ip, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def main():
    conn = get_db()
    conn.autocommit = False

    # Create a new scan job
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO cis_scan_jobs (triggered_by, status, target_vms)
            VALUES ('system', 'running', %s) RETURNING id
        """, (len(TARGETS),))
        job_id = cur.fetchone()["id"]
    conn.commit()
    print(f"\n=== CIS Scan Job #{job_id} started for {len(TARGETS)} VMs ===\n")

    total_checks = total_passed = total_failed = total_skipped = scanned = 0

    for (hostname, ip, os_family, asset_id) in TARGETS:
        check_port = 22 if os_family == "linux" else 5985
        print(f"→ {hostname} ({ip})  ", end="", flush=True)

        if not port_open(ip, check_port, timeout=6):
            print(f"SKIP — port {check_port} unreachable")
            continue

        creds = LINUX_CREDS if os_family == "linux" else WINDOWS_CREDS

        if os_family == "linux":
            os_info = _detect_os_via_ssh(ip, creds)
            os_info.setdefault("os_family", "linux")
            if not os_info.get("os_name"):
                os_info["os_name"]    = "Linux"
                os_info["os_version"] = ""
                os_info["benchmark"]  = "CIS_RHEL_Generic"
            checks = get_checks_for_os("linux", os_info.get("benchmark", ""))
            results = _ssh_run_checks(ip, checks, creds, hostname)
        else:
            os_info = _detect_os_via_winrm(ip, creds)
            os_info.setdefault("os_family", "windows")
            if not os_info.get("os_name"):
                os_info["os_name"]    = "Windows"
                os_info["os_version"] = ""
                os_info["benchmark"]  = "CIS_Windows_Generic"
            checks = get_checks_for_os("windows", os_info.get("benchmark", ""))
            results = _winrm_run_checks(ip, checks, creds, hostname)

        passed  = sum(1 for r in results if r["status"] == "pass")
        failed  = sum(1 for r in results if r["status"] == "fail")
        skipped = sum(1 for r in results if r["status"] == "skip")
        eligible = len(results) - skipped
        score = round(passed / eligible * 100, 2) if eligible > 0 else 0.0

        try:
            _write_vm_scan(conn, job_id, asset_id, hostname, ip, os_info, results)
            conn.commit()
            scanned += 1
            total_checks  += len(results)
            total_passed  += passed
            total_failed  += failed
            total_skipped += skipped
            print(f"OK  {os_info['benchmark']}  {passed}/{len(results)} pass  score={score}%")
        except Exception as ex:
            conn.rollback()
            print(f"DB ERROR: {ex}")

    # Finalise job
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE cis_scan_jobs
            SET status='completed', completed_at=NOW(), scanned_vms=%s,
                total_checks=%s, passed_checks=%s, failed_checks=%s, skipped_checks=%s
            WHERE id=%s
        """, (scanned, total_checks, total_passed, total_failed, total_skipped, job_id))
    conn.commit()
    conn.close()

    print(f"\n=== Done: {scanned} VMs scanned, "
          f"{total_passed}/{total_checks} checks passed "
          f"({round(total_passed/total_checks*100,1) if total_checks else 0}% fleet avg) ===\n")


if __name__ == "__main__":
    main()
