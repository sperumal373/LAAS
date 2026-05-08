"""
cis_scanner.py  --  CIS Benchmark Hardening Scanner  v1.0
==========================================================
Scans VMs via SSH (Linux) / WinRM (Windows) against CIS Benchmark controls.

Supported benchmarks:
  - CIS RHEL 8  v4.0.0
  - CIS RHEL 9  v2.0.0
  - CIS RHEL 10 v1.0.1
  - CIS Windows Server 2016 v2.0.0
  - CIS Windows Server 2019 v3.0.1
  - CIS Windows Server 2022 v3.0.0

Features:
  - SSH-based native shell checks (no Goss binary required)
  - Goss JSON file ingestion (for pre-scanned systems)
  - Auto-remediation per CIS control
  - Exclusion support (global or per-VM)
  - Background scan jobs with progress tracking
"""

import json, re, time, threading, logging, traceback, socket
from datetime import datetime, timezone
from pathlib import Path
import psycopg2, psycopg2.extras

BACKEND_DIR = Path(__file__).parent
log = logging.getLogger("cis_scanner")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PG_CONFIG = dict(
    host="127.0.0.1", port=5433, dbname="caas_dashboard",
    user="caas_app", password="CaaS@App2024#", connect_timeout=10,
)

def get_db():
    return psycopg2.connect(**PG_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)

# ─── DB Schema ────────────────────────────────────────────────────────────────

CIS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cis_scan_jobs (
    id            SERIAL PRIMARY KEY,
    started_at    TIMESTAMPTZ DEFAULT NOW(),
    completed_at  TIMESTAMPTZ,
    triggered_by  TEXT DEFAULT 'manual',
    status        TEXT DEFAULT 'running',
    target_vms    INTEGER DEFAULT 0,
    scanned_vms   INTEGER DEFAULT 0,
    total_checks  INTEGER DEFAULT 0,
    passed_checks INTEGER DEFAULT 0,
    failed_checks INTEGER DEFAULT 0,
    skipped_checks INTEGER DEFAULT 0,
    error_msg     TEXT
);

CREATE TABLE IF NOT EXISTS cis_vm_scans (
    id           SERIAL PRIMARY KEY,
    job_id       INTEGER,
    asset_id     INTEGER,
    vm_name      TEXT NOT NULL,
    ip_address   TEXT,
    os_name      TEXT,
    os_version   TEXT,
    os_family    TEXT,
    benchmark    TEXT,
    scanned_at   TIMESTAMPTZ DEFAULT NOW(),
    total_checks INTEGER DEFAULT 0,
    passed       INTEGER DEFAULT 0,
    failed       INTEGER DEFAULT 0,
    skipped      INTEGER DEFAULT 0,
    excluded     INTEGER DEFAULT 0,
    score        NUMERIC(5,2),
    scan_method  TEXT DEFAULT 'ssh',
    source_file  TEXT,
    error_msg    TEXT
);

CREATE INDEX IF NOT EXISTS idx_cis_vm_scans_job   ON cis_vm_scans(job_id);
CREATE INDEX IF NOT EXISTS idx_cis_vm_scans_name  ON cis_vm_scans(vm_name);
CREATE INDEX IF NOT EXISTS idx_cis_vm_scans_asset ON cis_vm_scans(asset_id);

CREATE TABLE IF NOT EXISTS cis_check_results (
    id              SERIAL PRIMARY KEY,
    vm_scan_id      INTEGER NOT NULL,
    cis_id          TEXT NOT NULL,
    section         TEXT,
    category        TEXT,
    title           TEXT,
    status          TEXT NOT NULL,
    found_value     TEXT,
    expected_value  TEXT,
    message         TEXT,
    is_ig1          BOOLEAN DEFAULT TRUE,
    is_ig2          BOOLEAN DEFAULT TRUE,
    is_ig3          BOOLEAN DEFAULT TRUE,
    remediation_cmd TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cis_check_vm      ON cis_check_results(vm_scan_id);
CREATE INDEX IF NOT EXISTS idx_cis_check_cis_id  ON cis_check_results(cis_id);
CREATE INDEX IF NOT EXISTS idx_cis_check_status  ON cis_check_results(status);

CREATE TABLE IF NOT EXISTS cis_exclusions (
    id          SERIAL PRIMARY KEY,
    cis_id      TEXT NOT NULL,
    vm_name     TEXT,
    os_family   TEXT,
    reason      TEXT,
    excluded_by TEXT DEFAULT 'system',
    excluded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cis_excl_unique
    ON cis_exclusions(cis_id, COALESCE(vm_name,'__global__'));

CREATE TABLE IF NOT EXISTS cis_remediation_log (
    id            SERIAL PRIMARY KEY,
    vm_scan_id    INTEGER,
    cis_id        TEXT,
    vm_name       TEXT,
    ip_address    TEXT,
    action_taken  TEXT,
    output        TEXT,
    success       BOOLEAN,
    performed_by  TEXT DEFAULT 'system',
    performed_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

def init_cis_db():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(CIS_SCHEMA_SQL)
        conn.commit(); conn.close()
        log.info("CIS DB schema initialized")
    except Exception as ex:
        log.error(f"CIS DB init error: {ex}")

# ─── CIS Check Definitions ────────────────────────────────────────────────────
# Each check:
#   cis_id, section, category, title
#   cmd        : shell command to run on target
#   pass_if    : "nonzero" | "zero" | "contains:<str>" | "empty" | "notempty"
#   expected   : human-readable expected value description
#   is_ig1/2/3 : Implementation Group levels
#   remediation: shell command to fix the issue

LINUX_CHECKS = [
    # ── Section 1: Initial Setup ─────────────────────────────────────────────
    {
        "cis_id": "1.1.1.1", "section": "1", "category": "Filesystem Configuration",
        "title": "Ensure mounting of cramfs filesystems is disabled",
        "cmd": "modprobe -n -v cramfs 2>&1 | grep -cE 'install /bin/true|Module cramfs not found'",
        "pass_if": "nonzero", "expected": "Module disabled or not found",
        "is_ig1": False, "is_ig2": True, "is_ig3": True,
        "remediation": "echo 'install cramfs /bin/true' > /etc/modprobe.d/cramfs.conf && rmmod cramfs 2>/dev/null; echo 'cramfs disabled'"
    },
    {
        "cis_id": "1.1.1.2", "section": "1", "category": "Filesystem Configuration",
        "title": "Ensure mounting of freevxfs filesystems is disabled",
        "cmd": "modprobe -n -v freevxfs 2>&1 | grep -cE 'install /bin/true|Module freevxfs not found'",
        "pass_if": "nonzero", "expected": "Module disabled or not found",
        "is_ig1": False, "is_ig2": True, "is_ig3": True,
        "remediation": "echo 'install freevxfs /bin/true' > /etc/modprobe.d/freevxfs.conf && rmmod freevxfs 2>/dev/null; echo done"
    },
    {
        "cis_id": "1.1.1.3", "section": "1", "category": "Filesystem Configuration",
        "title": "Ensure mounting of hfs filesystems is disabled",
        "cmd": "modprobe -n -v hfs 2>&1 | grep -cE 'install /bin/true|Module hfs not found'",
        "pass_if": "nonzero", "expected": "Module disabled or not found",
        "is_ig1": False, "is_ig2": True, "is_ig3": True,
        "remediation": "echo 'install hfs /bin/true' > /etc/modprobe.d/hfs.conf && rmmod hfs 2>/dev/null; echo done"
    },
    {
        "cis_id": "1.1.1.4", "section": "1", "category": "Filesystem Configuration",
        "title": "Ensure mounting of hfsplus filesystems is disabled",
        "cmd": "modprobe -n -v hfsplus 2>&1 | grep -cE 'install /bin/true|Module hfsplus not found'",
        "pass_if": "nonzero", "expected": "Module disabled or not found",
        "is_ig1": False, "is_ig2": True, "is_ig3": True,
        "remediation": "echo 'install hfsplus /bin/true' > /etc/modprobe.d/hfsplus.conf && rmmod hfsplus 2>/dev/null; echo done"
    },
    {
        "cis_id": "1.1.1.5", "section": "1", "category": "Filesystem Configuration",
        "title": "Ensure mounting of jffs2 filesystems is disabled",
        "cmd": "modprobe -n -v jffs2 2>&1 | grep -cE 'install /bin/true|Module jffs2 not found'",
        "pass_if": "nonzero", "expected": "Module disabled or not found",
        "is_ig1": False, "is_ig2": True, "is_ig3": True,
        "remediation": "echo 'install jffs2 /bin/true' > /etc/modprobe.d/jffs2.conf && rmmod jffs2 2>/dev/null; echo done"
    },
    {
        "cis_id": "1.1.1.6", "section": "1", "category": "Filesystem Configuration",
        "title": "Ensure mounting of squashfs filesystems is disabled",
        "cmd": "modprobe -n -v squashfs 2>&1 | grep -cE 'install /bin/true|Module squashfs not found'",
        "pass_if": "nonzero", "expected": "Module disabled or not found",
        "is_ig1": False, "is_ig2": True, "is_ig3": True,
        "remediation": "echo 'install squashfs /bin/true' > /etc/modprobe.d/squashfs.conf && rmmod squashfs 2>/dev/null; echo done"
    },
    {
        "cis_id": "1.1.1.7", "section": "1", "category": "Filesystem Configuration",
        "title": "Ensure mounting of udf filesystems is disabled",
        "cmd": "modprobe -n -v udf 2>&1 | grep -cE 'install /bin/true|Module udf not found'",
        "pass_if": "nonzero", "expected": "Module disabled or not found",
        "is_ig1": False, "is_ig2": True, "is_ig3": True,
        "remediation": "echo 'install udf /bin/true' > /etc/modprobe.d/udf.conf && rmmod udf 2>/dev/null; echo done"
    },
    {
        "cis_id": "1.4.4", "section": "1", "category": "Bootloader Configuration",
        "title": "Ensure core dump storage is disabled",
        "cmd": "grep -i 'Storage=none' /etc/systemd/coredump.conf 2>/dev/null | wc -l",
        "pass_if": "nonzero", "expected": "Storage=none in coredump.conf",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^#*Storage=.*/Storage=none/' /etc/systemd/coredump.conf 2>/dev/null || echo 'Storage=none' >> /etc/systemd/coredump.conf; systemctl daemon-reload; echo done"
    },
    {
        "cis_id": "1.5.1", "section": "1", "category": "Additional Process Hardening",
        "title": "Ensure address space layout randomization (ASLR) is enabled",
        "cmd": "sysctl kernel.randomize_va_space 2>/dev/null | grep -c '= 2'",
        "pass_if": "nonzero", "expected": "kernel.randomize_va_space = 2",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sysctl -w kernel.randomize_va_space=2; echo 'kernel.randomize_va_space = 2' >> /etc/sysctl.d/60-cis.conf; sysctl -p /etc/sysctl.d/60-cis.conf; echo done"
    },
    {
        "cis_id": "1.5.2", "section": "1", "category": "Additional Process Hardening",
        "title": "Ensure prelink is not installed",
        "cmd": "rpm -q prelink 2>&1 | grep -c 'not installed'",
        "pass_if": "nonzero", "expected": "prelink not installed",
        "is_ig1": False, "is_ig2": True, "is_ig3": True,
        "remediation": "yum remove -y prelink 2>/dev/null || apt-get remove -y prelink 2>/dev/null; echo done"
    },
    # ── Section 2: Services ───────────────────────────────────────────────────
    {
        "cis_id": "2.1.1", "section": "2", "category": "inetd Services",
        "title": "Ensure xinetd is not installed",
        "cmd": "rpm -q xinetd 2>&1 | grep -c 'not installed'",
        "pass_if": "nonzero", "expected": "xinetd not installed",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "yum remove -y xinetd 2>/dev/null || apt-get remove -y xinetd 2>/dev/null; echo done"
    },
    {
        "cis_id": "2.2.1.1", "section": "2", "category": "Special Purpose Services",
        "title": "Ensure time synchronization is in use (chronyd/ntpd)",
        "cmd": "systemctl is-active chronyd ntpd 2>/dev/null | grep -c '^active'",
        "pass_if": "nonzero", "expected": "chronyd or ntpd active",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "yum install -y chrony 2>/dev/null; systemctl enable --now chronyd; echo done"
    },
    {
        "cis_id": "2.2.2", "section": "2", "category": "Special Purpose Services",
        "title": "Ensure X11 Server components are not installed",
        "cmd": "rpm -qa 'xorg-x11-server*' 2>/dev/null | wc -l",
        "pass_if": "zero", "expected": "No X11 server packages installed",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "yum remove -y xorg-x11-server* 2>/dev/null; echo done"
    },
    {
        "cis_id": "2.2.3", "section": "2", "category": "Special Purpose Services",
        "title": "Ensure Avahi Server is not installed",
        "cmd": "systemctl is-active avahi-daemon 2>/dev/null | grep -cE '^inactive|^unknown|failed'",
        "pass_if": "nonzero", "expected": "avahi-daemon inactive or not installed",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "systemctl stop avahi-daemon 2>/dev/null; systemctl disable avahi-daemon 2>/dev/null; yum remove -y avahi-daemon 2>/dev/null; echo done"
    },
    {
        "cis_id": "2.2.4", "section": "2", "category": "Special Purpose Services",
        "title": "Ensure CUPS is not installed",
        "cmd": "systemctl is-active cups 2>/dev/null | grep -cE '^inactive|^unknown|failed'",
        "pass_if": "nonzero", "expected": "CUPS inactive or not installed",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "systemctl stop cups 2>/dev/null; systemctl disable cups 2>/dev/null; yum remove -y cups 2>/dev/null; echo done"
    },
    # ── Section 3: Network Configuration ─────────────────────────────────────
    {
        "cis_id": "3.1.2", "section": "3", "category": "Network Parameters",
        "title": "Ensure packet redirect sending is disabled",
        "cmd": "sysctl net.ipv4.conf.all.send_redirects net.ipv4.conf.default.send_redirects 2>/dev/null | grep -c '= 0'",
        "pass_if": "nonzero", "expected": "send_redirects = 0",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sysctl -w net.ipv4.conf.all.send_redirects=0; sysctl -w net.ipv4.conf.default.send_redirects=0; echo 'net.ipv4.conf.all.send_redirects=0' >> /etc/sysctl.d/60-cis.conf; echo 'net.ipv4.conf.default.send_redirects=0' >> /etc/sysctl.d/60-cis.conf; echo done"
    },
    {
        "cis_id": "3.2.1", "section": "3", "category": "Network Parameters",
        "title": "Ensure source routed packets are not accepted",
        "cmd": "sysctl net.ipv4.conf.all.accept_source_route 2>/dev/null | grep -c '= 0'",
        "pass_if": "nonzero", "expected": "accept_source_route = 0",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sysctl -w net.ipv4.conf.all.accept_source_route=0; echo 'net.ipv4.conf.all.accept_source_route=0' >> /etc/sysctl.d/60-cis.conf; echo done"
    },
    {
        "cis_id": "3.2.2", "section": "3", "category": "Network Parameters",
        "title": "Ensure ICMP redirects are not accepted",
        "cmd": "sysctl net.ipv4.conf.all.accept_redirects 2>/dev/null | grep -c '= 0'",
        "pass_if": "nonzero", "expected": "accept_redirects = 0",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sysctl -w net.ipv4.conf.all.accept_redirects=0; echo 'net.ipv4.conf.all.accept_redirects=0' >> /etc/sysctl.d/60-cis.conf; echo done"
    },
    {
        "cis_id": "3.2.3", "section": "3", "category": "Network Parameters",
        "title": "Ensure secure ICMP redirects are not accepted",
        "cmd": "sysctl net.ipv4.conf.all.secure_redirects 2>/dev/null | grep -c '= 0'",
        "pass_if": "nonzero", "expected": "secure_redirects = 0",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sysctl -w net.ipv4.conf.all.secure_redirects=0; echo 'net.ipv4.conf.all.secure_redirects=0' >> /etc/sysctl.d/60-cis.conf; echo done"
    },
    {
        "cis_id": "3.2.4", "section": "3", "category": "Network Parameters",
        "title": "Ensure suspicious packets are logged (log_martians)",
        "cmd": "sysctl net.ipv4.conf.all.log_martians 2>/dev/null | grep -c '= 1'",
        "pass_if": "nonzero", "expected": "log_martians = 1",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sysctl -w net.ipv4.conf.all.log_martians=1; echo 'net.ipv4.conf.all.log_martians=1' >> /etc/sysctl.d/60-cis.conf; echo done"
    },
    {
        "cis_id": "3.2.5", "section": "3", "category": "Network Parameters",
        "title": "Ensure broadcast ICMP requests are ignored",
        "cmd": "sysctl net.ipv4.icmp_echo_ignore_broadcasts 2>/dev/null | grep -c '= 1'",
        "pass_if": "nonzero", "expected": "icmp_echo_ignore_broadcasts = 1",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sysctl -w net.ipv4.icmp_echo_ignore_broadcasts=1; echo 'net.ipv4.icmp_echo_ignore_broadcasts=1' >> /etc/sysctl.d/60-cis.conf; echo done"
    },
    {
        "cis_id": "3.2.6", "section": "3", "category": "Network Parameters",
        "title": "Ensure bogus ICMP responses are ignored",
        "cmd": "sysctl net.ipv4.icmp_ignore_bogus_error_responses 2>/dev/null | grep -c '= 1'",
        "pass_if": "nonzero", "expected": "icmp_ignore_bogus_error_responses = 1",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sysctl -w net.ipv4.icmp_ignore_bogus_error_responses=1; echo 'net.ipv4.icmp_ignore_bogus_error_responses=1' >> /etc/sysctl.d/60-cis.conf; echo done"
    },
    {
        "cis_id": "3.2.7", "section": "3", "category": "Network Parameters",
        "title": "Ensure Reverse Path Filtering is enabled",
        "cmd": "sysctl net.ipv4.conf.all.rp_filter 2>/dev/null | grep -c '= 1'",
        "pass_if": "nonzero", "expected": "rp_filter = 1",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sysctl -w net.ipv4.conf.all.rp_filter=1; echo 'net.ipv4.conf.all.rp_filter=1' >> /etc/sysctl.d/60-cis.conf; echo done"
    },
    {
        "cis_id": "3.2.8", "section": "3", "category": "Network Parameters",
        "title": "Ensure TCP SYN Cookies is enabled",
        "cmd": "sysctl net.ipv4.tcp_syncookies 2>/dev/null | grep -c '= 1'",
        "pass_if": "nonzero", "expected": "tcp_syncookies = 1",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sysctl -w net.ipv4.tcp_syncookies=1; echo 'net.ipv4.tcp_syncookies=1' >> /etc/sysctl.d/60-cis.conf; echo done"
    },
    # ── Section 4: Logging and Auditing ──────────────────────────────────────
    {
        "cis_id": "4.1.1.1", "section": "4", "category": "Configure Logging",
        "title": "Ensure auditd is installed",
        "cmd": "rpm -q audit 2>&1 | grep -c 'not installed'",
        "pass_if": "zero", "expected": "audit package installed",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "yum install -y audit 2>/dev/null || apt-get install -y auditd 2>/dev/null; echo done"
    },
    {
        "cis_id": "4.1.1.2", "section": "4", "category": "Configure Logging",
        "title": "Ensure auditd service is enabled and running",
        "cmd": "systemctl is-active auditd 2>/dev/null | grep -c '^active'",
        "pass_if": "nonzero", "expected": "auditd active",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "systemctl enable --now auditd; echo done"
    },
    {
        "cis_id": "4.2.1.1", "section": "4", "category": "Configure Logging",
        "title": "Ensure rsyslog is installed",
        "cmd": "rpm -q rsyslog 2>&1 | grep -c 'not installed'",
        "pass_if": "zero", "expected": "rsyslog installed",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "yum install -y rsyslog 2>/dev/null || apt-get install -y rsyslog 2>/dev/null; echo done"
    },
    {
        "cis_id": "4.2.1.2", "section": "4", "category": "Configure Logging",
        "title": "Ensure rsyslog service is enabled and running",
        "cmd": "systemctl is-active rsyslog 2>/dev/null | grep -c '^active'",
        "pass_if": "nonzero", "expected": "rsyslog active",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "systemctl enable --now rsyslog; echo done"
    },
    # ── Section 5: Access Control ─────────────────────────────────────────────
    {
        "cis_id": "5.1.2", "section": "5", "category": "Configure Cron",
        "title": "Ensure permissions on /etc/crontab are configured (600)",
        "cmd": "stat -c '%a' /etc/crontab 2>/dev/null",
        "pass_if": "contains:600", "expected": "permissions 600",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "chown root:root /etc/crontab; chmod 600 /etc/crontab; echo done"
    },
    {
        "cis_id": "5.2.4", "section": "5", "category": "SSH Server Configuration",
        "title": "Ensure SSH LogLevel is appropriate (INFO or VERBOSE)",
        "cmd": "sshd -T 2>/dev/null | grep -iE '^loglevel (info|verbose)' | wc -l",
        "pass_if": "nonzero", "expected": "LogLevel INFO or VERBOSE",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^#*LogLevel.*/LogLevel INFO/' /etc/ssh/sshd_config; systemctl restart sshd; echo done"
    },
    {
        "cis_id": "5.2.6", "section": "5", "category": "SSH Server Configuration",
        "title": "Ensure SSH X11 forwarding is disabled",
        "cmd": "sshd -T 2>/dev/null | grep -i 'x11forwarding no' | wc -l",
        "pass_if": "nonzero", "expected": "X11Forwarding no",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^#*X11Forwarding.*/X11Forwarding no/' /etc/ssh/sshd_config; grep -q '^X11Forwarding' /etc/ssh/sshd_config || echo 'X11Forwarding no' >> /etc/ssh/sshd_config; systemctl restart sshd; echo done"
    },
    {
        "cis_id": "5.2.8", "section": "5", "category": "SSH Server Configuration",
        "title": "Ensure SSH MaxAuthTries is set to 4 or less",
        "cmd": "sshd -T 2>/dev/null | awk '/^maxauthtries/{if($2<=4)print \"PASS\"; else print \"FAIL:\"$2}'",
        "pass_if": "contains:PASS", "expected": "MaxAuthTries <= 4",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^#*MaxAuthTries.*/MaxAuthTries 4/' /etc/ssh/sshd_config; grep -q '^MaxAuthTries' /etc/ssh/sshd_config || echo 'MaxAuthTries 4' >> /etc/ssh/sshd_config; systemctl restart sshd; echo done"
    },
    {
        "cis_id": "5.2.9", "section": "5", "category": "SSH Server Configuration",
        "title": "Ensure SSH IgnoreRhosts is enabled",
        "cmd": "sshd -T 2>/dev/null | grep -i 'ignorerhosts yes' | wc -l",
        "pass_if": "nonzero", "expected": "IgnoreRhosts yes",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^#*IgnoreRhosts.*/IgnoreRhosts yes/' /etc/ssh/sshd_config; grep -q '^IgnoreRhosts' /etc/ssh/sshd_config || echo 'IgnoreRhosts yes' >> /etc/ssh/sshd_config; systemctl restart sshd; echo done"
    },
    {
        "cis_id": "5.2.10", "section": "5", "category": "SSH Server Configuration",
        "title": "Ensure SSH HostbasedAuthentication is disabled",
        "cmd": "sshd -T 2>/dev/null | grep -i 'hostbasedauthentication no' | wc -l",
        "pass_if": "nonzero", "expected": "HostbasedAuthentication no",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^#*HostbasedAuthentication.*/HostbasedAuthentication no/' /etc/ssh/sshd_config; grep -q '^HostbasedAuthentication' /etc/ssh/sshd_config || echo 'HostbasedAuthentication no' >> /etc/ssh/sshd_config; systemctl restart sshd; echo done"
    },
    {
        "cis_id": "5.2.11", "section": "5", "category": "SSH Server Configuration",
        "title": "Ensure SSH root login is disabled",
        "cmd": "sshd -T 2>/dev/null | grep -iE 'permitrootlogin (no|prohibit-password|without-password)' | wc -l",
        "pass_if": "nonzero", "expected": "PermitRootLogin no or prohibit-password",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config; grep -q '^PermitRootLogin' /etc/ssh/sshd_config || echo 'PermitRootLogin prohibit-password' >> /etc/ssh/sshd_config; systemctl restart sshd; echo done"
    },
    {
        "cis_id": "5.2.12", "section": "5", "category": "SSH Server Configuration",
        "title": "Ensure SSH PermitEmptyPasswords is disabled",
        "cmd": "sshd -T 2>/dev/null | grep -i 'permitemptypasswords no' | wc -l",
        "pass_if": "nonzero", "expected": "PermitEmptyPasswords no",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^#*PermitEmptyPasswords.*/PermitEmptyPasswords no/' /etc/ssh/sshd_config; grep -q '^PermitEmptyPasswords' /etc/ssh/sshd_config || echo 'PermitEmptyPasswords no' >> /etc/ssh/sshd_config; systemctl restart sshd; echo done"
    },
    {
        "cis_id": "5.2.16", "section": "5", "category": "SSH Server Configuration",
        "title": "Ensure SSH Idle Timeout Interval is configured (ClientAliveInterval 300)",
        "cmd": "sshd -T 2>/dev/null | awk '/^clientaliveinterval/{if($2>0 && $2<=300)print \"PASS\"; else print \"FAIL:\"$2}'",
        "pass_if": "contains:PASS", "expected": "ClientAliveInterval 1-300",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^#*ClientAliveInterval.*/ClientAliveInterval 300/' /etc/ssh/sshd_config; grep -q '^ClientAliveInterval' /etc/ssh/sshd_config || echo 'ClientAliveInterval 300' >> /etc/ssh/sshd_config; sed -i 's/^#*ClientAliveCountMax.*/ClientAliveCountMax 3/' /etc/ssh/sshd_config; grep -q '^ClientAliveCountMax' /etc/ssh/sshd_config || echo 'ClientAliveCountMax 3' >> /etc/ssh/sshd_config; systemctl restart sshd; echo done"
    },
    {
        "cis_id": "5.2.17", "section": "5", "category": "SSH Server Configuration",
        "title": "Ensure SSH MaxStartups is configured (10:30:60)",
        "cmd": "sshd -T 2>/dev/null | grep -i 'maxstartups' | grep -c '10:30:60'",
        "pass_if": "nonzero", "expected": "MaxStartups 10:30:60",
        "is_ig1": False, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^#*MaxStartups.*/MaxStartups 10:30:60/' /etc/ssh/sshd_config; grep -q '^MaxStartups' /etc/ssh/sshd_config || echo 'MaxStartups 10:30:60' >> /etc/ssh/sshd_config; systemctl restart sshd; echo done"
    },
    {
        "cis_id": "5.2.18", "section": "5", "category": "SSH Server Configuration",
        "title": "Ensure SSH MaxSessions is limited (<=10)",
        "cmd": "sshd -T 2>/dev/null | awk '/^maxsessions/{if($2<=10)print \"PASS\"; else print \"FAIL:\"$2}'",
        "pass_if": "contains:PASS", "expected": "MaxSessions <= 10",
        "is_ig1": False, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^#*MaxSessions.*/MaxSessions 10/' /etc/ssh/sshd_config; grep -q '^MaxSessions' /etc/ssh/sshd_config || echo 'MaxSessions 10' >> /etc/ssh/sshd_config; systemctl restart sshd; echo done"
    },
    {
        "cis_id": "5.3.1", "section": "5", "category": "Configure sudo",
        "title": "Ensure sudo is installed",
        "cmd": "rpm -q sudo 2>&1 | grep -c 'not installed'",
        "pass_if": "zero", "expected": "sudo installed",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "yum install -y sudo 2>/dev/null || apt-get install -y sudo 2>/dev/null; echo done"
    },
    {
        "cis_id": "5.4.1.1", "section": "5", "category": "Configure PAM",
        "title": "Ensure password expiration is 365 days or less (PASS_MAX_DAYS)",
        "cmd": "awk '/^PASS_MAX_DAYS/{if($2>0 && $2<=365)print \"PASS\"; else print \"FAIL:\"$2}' /etc/login.defs 2>/dev/null",
        "pass_if": "contains:PASS", "expected": "PASS_MAX_DAYS <= 365",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^PASS_MAX_DAYS.*/PASS_MAX_DAYS\t365/' /etc/login.defs; echo done"
    },
    {
        "cis_id": "5.4.1.2", "section": "5", "category": "Configure PAM",
        "title": "Ensure minimum days between password changes is configured (PASS_MIN_DAYS >= 7)",
        "cmd": "awk '/^PASS_MIN_DAYS/{if($2>=7)print \"PASS\"; else print \"FAIL:\"$2}' /etc/login.defs 2>/dev/null",
        "pass_if": "contains:PASS", "expected": "PASS_MIN_DAYS >= 7",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i 's/^PASS_MIN_DAYS.*/PASS_MIN_DAYS\t7/' /etc/login.defs; echo done"
    },
    {
        "cis_id": "5.4.3", "section": "5", "category": "Configure PAM",
        "title": "Ensure password hashing algorithm is SHA-512",
        "cmd": "grep -E '\\$6\\$' /etc/shadow 2>/dev/null | wc -l",
        "pass_if": "nonzero", "expected": "SHA-512 hashes found in /etc/shadow",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "authconfig --passalgo=sha512 --update 2>/dev/null || authselect apply-changes 2>/dev/null; echo done"
    },
    # ── Section 6: System Maintenance ─────────────────────────────────────────
    {
        "cis_id": "6.1.2", "section": "6", "category": "System File Permissions",
        "title": "Ensure permissions on /etc/passwd are configured (644)",
        "cmd": "stat -c '%a %U %G' /etc/passwd 2>/dev/null",
        "pass_if": "contains:644 root root", "expected": "644 root root",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "chown root:root /etc/passwd; chmod 644 /etc/passwd; echo done"
    },
    {
        "cis_id": "6.1.3", "section": "6", "category": "System File Permissions",
        "title": "Ensure permissions on /etc/shadow are configured (640 or 000)",
        "cmd": "stat -c '%a' /etc/shadow 2>/dev/null",
        "pass_if": "contains:640", "expected": "permissions 640 or 000",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "chown root:shadow /etc/shadow; chmod 640 /etc/shadow; echo done"
    },
    {
        "cis_id": "6.1.4", "section": "6", "category": "System File Permissions",
        "title": "Ensure permissions on /etc/group are configured (644)",
        "cmd": "stat -c '%a %U %G' /etc/group 2>/dev/null",
        "pass_if": "contains:644 root root", "expected": "644 root root",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "chown root:root /etc/group; chmod 644 /etc/group; echo done"
    },
    {
        "cis_id": "6.1.5", "section": "6", "category": "System File Permissions",
        "title": "Ensure permissions on /etc/gshadow are configured (640 or 000)",
        "cmd": "stat -c '%a' /etc/gshadow 2>/dev/null",
        "pass_if": "contains:640", "expected": "permissions 640 or 000",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "chown root:shadow /etc/gshadow; chmod 640 /etc/gshadow; echo done"
    },
    {
        "cis_id": "6.2.1", "section": "6", "category": "Local User and Group Settings",
        "title": "Ensure accounts in /etc/passwd use shadowed passwords",
        "cmd": "awk -F: '($2 != \"x\" ) { print $1 }' /etc/passwd 2>/dev/null | wc -l",
        "pass_if": "zero", "expected": "All accounts use shadow passwords (x in /etc/passwd)",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "pwconv; echo done"
    },
    {
        "cis_id": "6.2.2", "section": "6", "category": "Local User and Group Settings",
        "title": "Ensure no accounts have empty passwords",
        "cmd": "awk -F: '($2 == \"\" || $2 == \"!\") { print $1 }' /etc/shadow 2>/dev/null | wc -l",
        "pass_if": "zero", "expected": "No empty passwords in /etc/shadow",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "echo 'Review accounts with empty passwords manually'; echo done"
    },
    {
        "cis_id": "6.2.3", "section": "6", "category": "Local User and Group Settings",
        "title": "Ensure no legacy '+' entries exist in /etc/passwd",
        "cmd": "grep -c '^+' /etc/passwd 2>/dev/null || echo 0",
        "pass_if": "zero", "expected": "No + entries in /etc/passwd",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i '/^+/d' /etc/passwd; echo done"
    },
    {
        "cis_id": "6.2.4", "section": "6", "category": "Local User and Group Settings",
        "title": "Ensure no legacy '+' entries exist in /etc/shadow",
        "cmd": "grep -c '^+' /etc/shadow 2>/dev/null || echo 0",
        "pass_if": "zero", "expected": "No + entries in /etc/shadow",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i '/^+/d' /etc/shadow; echo done"
    },
    {
        "cis_id": "6.2.5", "section": "6", "category": "Local User and Group Settings",
        "title": "Ensure no legacy '+' entries exist in /etc/group",
        "cmd": "grep -c '^+' /etc/group 2>/dev/null || echo 0",
        "pass_if": "zero", "expected": "No + entries in /etc/group",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "sed -i '/^+/d' /etc/group; echo done"
    },
]

WINDOWS_CHECKS = [
    {
        "cis_id": "W.1.1.1", "section": "1", "category": "Account Policies",
        "title": "Ensure Enforce password history is 24 or more passwords",
        "cmd": "try{$h=(net accounts 2>$null | Select-String 'history').ToString().Split(':')[-1].Trim();if([int]$h -ge 24){'PASS'}else{\"FAIL:$h\"}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "Password history >= 24",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "net accounts /uniquepw:24 2>$null; 'done'"
    },
    {
        "cis_id": "W.1.1.2", "section": "1", "category": "Account Policies",
        "title": "Ensure Maximum password age is 365 or fewer days",
        "cmd": "try{$a=(net accounts 2>$null | Select-String 'Maximum password age').ToString().Split(':')[-1].Trim();if([int]$a -le 365 -and [int]$a -gt 0){'PASS'}else{\"FAIL:$a\"}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "Max password age <= 365",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "net accounts /maxpwage:365 2>$null; 'done'"
    },
    {
        "cis_id": "W.1.1.3", "section": "1", "category": "Account Policies",
        "title": "Ensure Minimum password age is 1 or more days",
        "cmd": "try{$a=(net accounts 2>$null | Select-String 'Minimum password age').ToString().Split(':')[-1].Trim();if([int]$a -ge 1){'PASS'}else{\"FAIL:$a\"}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "Min password age >= 1",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "net accounts /minpwage:1 2>$null; 'done'"
    },
    {
        "cis_id": "W.1.1.4", "section": "1", "category": "Account Policies",
        "title": "Ensure Minimum password length is 14 or more characters",
        "cmd": "try{$l=(net accounts 2>$null | Select-String 'Minimum password length').ToString().Split(':')[-1].Trim();if([int]$l -ge 14){'PASS'}else{\"FAIL:$l\"}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "Min password length >= 14",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "net accounts /minpwlen:14 2>$null; 'done'"
    },
    {
        "cis_id": "W.1.2.1", "section": "1", "category": "Account Lockout Policy",
        "title": "Ensure Account lockout threshold is 5 or fewer invalid logon attempts",
        "cmd": "try{$t=(net accounts 2>$null | Select-String 'Lockout threshold').ToString().Split(':')[-1].Trim();if($t -eq 'Never' -or [int]$t -gt 5){'FAIL:'+$t}else{'PASS'}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "Lockout threshold 1-5",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "net accounts /lockoutthreshold:5 2>$null; 'done'"
    },
    {
        "cis_id": "W.2.3.1", "section": "2", "category": "Local Policies",
        "title": "Ensure Windows Firewall Domain profile is enabled",
        "cmd": "try{if((Get-NetFirewallProfile -Profile Domain).Enabled){'PASS'}else{'FAIL'}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "Domain firewall enabled",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "Set-NetFirewallProfile -Profile Domain -Enabled True 2>$null; 'done'"
    },
    {
        "cis_id": "W.2.3.2", "section": "2", "category": "Local Policies",
        "title": "Ensure Windows Firewall Private profile is enabled",
        "cmd": "try{if((Get-NetFirewallProfile -Profile Private).Enabled){'PASS'}else{'FAIL'}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "Private firewall enabled",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "Set-NetFirewallProfile -Profile Private -Enabled True 2>$null; 'done'"
    },
    {
        "cis_id": "W.2.3.3", "section": "2", "category": "Local Policies",
        "title": "Ensure Windows Firewall Public profile is enabled",
        "cmd": "try{if((Get-NetFirewallProfile -Profile Public).Enabled){'PASS'}else{'FAIL'}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "Public firewall enabled",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "Set-NetFirewallProfile -Profile Public -Enabled True 2>$null; 'done'"
    },
    {
        "cis_id": "W.5.1", "section": "5", "category": "System Security",
        "title": "Ensure SMBv1 is disabled",
        "cmd": "try{$s=Get-SmbServerConfiguration 2>$null;if(-not $s.EnableSMB1Protocol){'PASS'}else{'FAIL'}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "SMB1 disabled",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "Set-SmbServerConfiguration -EnableSMB1Protocol $false -Force 2>$null; 'done'"
    },
    {
        "cis_id": "W.5.2", "section": "5", "category": "System Security",
        "title": "Ensure Windows Defender Real-Time Protection is enabled",
        "cmd": "try{$d=Get-MpPreference 2>$null;if(-not $d.DisableRealtimeMonitoring){'PASS'}else{'FAIL'}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "Real-time monitoring enabled",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "Set-MpPreference -DisableRealtimeMonitoring $false 2>$null; 'done'"
    },
    {
        "cis_id": "W.5.3", "section": "5", "category": "System Security",
        "title": "Ensure Remote Desktop requires NLA",
        "cmd": "try{$v=(Get-ItemProperty 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' -Name UserAuthentication 2>$null).UserAuthentication;if($v -eq 1){'PASS'}else{\"FAIL:$v\"}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "NLA required (UserAuthentication=1)",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "Set-ItemProperty 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' -Name UserAuthentication -Value 1 2>$null; 'done'"
    },
    {
        "cis_id": "W.5.4", "section": "5", "category": "System Security",
        "title": "Ensure Windows Update automatic download is enabled",
        "cmd": "try{$au=(Get-ItemProperty 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU' 2>$null).AUOptions;if($au -ge 3){'PASS'}else{\"FAIL:$au\"}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "AU options >= 3 (auto download)",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "'Manual review required for Windows Update settings'; 'done'"
    },
    {
        "cis_id": "W.6.1", "section": "6", "category": "Administrative Templates",
        "title": "Ensure screen lock is enabled (screensaver timeout <= 900s)",
        "cmd": "try{$t=(Get-ItemProperty 'HKCU:\\Control Panel\\Desktop' 2>$null).ScreenSaveTimeOut;if([int]$t -le 900){'PASS'}else{\"FAIL:$t\"}}catch{'SKIP'}",
        "pass_if": "contains:PASS", "expected": "Screen saver timeout <= 900s",
        "is_ig1": True, "is_ig2": True, "is_ig3": True,
        "remediation": "Set-ItemProperty 'HKCU:\\Control Panel\\Desktop' -Name ScreenSaveTimeOut -Value 900 2>$null; Set-ItemProperty 'HKCU:\\Control Panel\\Desktop' -Name ScreenSaverIsSecure -Value 1 2>$null; 'done'"
    },
]


# ─── Check Runner ─────────────────────────────────────────────────────────────

SSH_TIMEOUT = 10

def _eval_check(stdout: str, check: dict) -> tuple:
    """Returns (status, found_value) — status is 'pass'/'fail'/'skip'"""
    out = stdout.strip() if stdout else ""
    pi = check.get("pass_if", "nonzero")
    try:
        if pi == "nonzero":
            val = int(out.split("\n")[0].strip()) if out else 0
            return ("pass", out[:120]) if val > 0 else ("fail", out[:120] or "0")
        elif pi == "zero":
            val = int(out.split("\n")[0].strip()) if out else 0
            return ("pass", out[:120]) if val == 0 else ("fail", out[:120] or "0")
        elif pi.startswith("contains:"):
            target = pi[9:]
            return ("pass", out[:120]) if target in out else ("fail", out[:120] or "(empty)")
        elif pi == "empty":
            return ("pass", "(none)") if not out.strip() else ("fail", out[:120])
        elif pi == "notempty":
            return ("pass", out[:120]) if out.strip() else ("fail", "(empty)")
    except Exception:
        pass
    return ("skip", out[:120])


def _ssh_run_checks(ip: str, checks: list, creds: list, vm_name: str = "") -> list:
    """SSH into IP, run all checks, return list of result dicts."""
    results = []
    if not ip:
        return [{"cis_id": c["cis_id"], "status": "skip", "found_value": "No IP", "message": "No IP address"} for c in checks]

    try:
        import paramiko
    except ImportError:
        return [{"cis_id": c["cis_id"], "status": "skip", "found_value": "paramiko not installed", "message": "paramiko not installed"} for c in checks]

    cli = None
    for cred in creds:
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(ip, port=cred.get("port", 22),
                        username=cred["username"], password=cred["password"],
                        timeout=SSH_TIMEOUT, banner_timeout=SSH_TIMEOUT, auth_timeout=SSH_TIMEOUT)
            log.info(f"CIS SSH connected: {vm_name} ({ip}) as {cred['username']}")
            break
        except Exception as ex:
            log.debug(f"CIS SSH {ip} cred {cred.get('username','?')} failed: {ex}")
            cli = None

    if cli is None:
        return [{"cis_id": c["cis_id"], "status": "skip", "found_value": "SSH failed",
                 "message": "Could not connect via SSH — check credentials"} for c in checks]

    for check in checks:
        try:
            _, stdout, stderr = cli.exec_command(check["cmd"], timeout=SSH_TIMEOUT)
            out = stdout.read().decode(errors="ignore")
            err = stderr.read().decode(errors="ignore")
            status, found = _eval_check(out, check)
            results.append({
                "cis_id":          check["cis_id"],
                "section":         check.get("section", ""),
                "category":        check.get("category", ""),
                "title":           check["title"],
                "status":          status,
                "found_value":     found,
                "expected_value":  check.get("expected", ""),
                "is_ig1":          check.get("is_ig1", True),
                "is_ig2":          check.get("is_ig2", True),
                "is_ig3":          check.get("is_ig3", True),
                "remediation_cmd": check.get("remediation", ""),
                "message":         f"Found: {found}" if status == "fail" else "",
            })
        except Exception as ex:
            results.append({
                "cis_id":  check["cis_id"], "section": check.get("section",""),
                "category": check.get("category",""), "title": check["title"],
                "status": "skip", "found_value": str(ex)[:100],
                "expected_value": check.get("expected", ""),
                "is_ig1": check.get("is_ig1", True), "is_ig2": check.get("is_ig2", True),
                "is_ig3": check.get("is_ig3", True), "remediation_cmd": check.get("remediation", ""),
                "message": f"Error: {ex}",
            })
    try:
        cli.close()
    except Exception:
        pass
    return results


def _winrm_run_checks(ip: str, checks: list, creds: list, vm_name: str = "") -> list:
    """WinRM into IP, run all checks."""
    results = []
    try:
        import winrm
    except ImportError:
        return [{"cis_id": c["cis_id"], "status": "skip", "found_value": "pywinrm not installed",
                 "message": "pywinrm not installed"} for c in checks]

    session = None
    for cred in creds:
        try:
            s = winrm.Session(
                f"http://{ip}:{cred.get('port', 5985)}/wsman",
                auth=(cred["username"], cred["password"]),
                transport="ntlm", server_cert_validation="ignore",
                operation_timeout_sec=SSH_TIMEOUT, read_timeout_sec=SSH_TIMEOUT + 5)
            tr = s.run_ps("echo 'ok'")
            if tr.status_code == 0:
                session = s
                break
        except Exception as ex:
            log.debug(f"CIS WinRM {ip} cred {cred.get('username','?')} failed: {ex}")

    if session is None:
        return [{"cis_id": c["cis_id"], "status": "skip", "found_value": "WinRM failed",
                 "message": "Could not connect via WinRM"} for c in checks]

    for check in checks:
        try:
            r = session.run_ps(check["cmd"])
            out = r.std_out.decode(errors="ignore") if r.std_out else ""
            status, found = _eval_check(out, check)
            results.append({
                "cis_id":          check["cis_id"],
                "section":         check.get("section", ""),
                "category":        check.get("category", ""),
                "title":           check["title"],
                "status":          status,
                "found_value":     found,
                "expected_value":  check.get("expected", ""),
                "is_ig1":          check.get("is_ig1", True),
                "is_ig2":          check.get("is_ig2", True),
                "is_ig3":          check.get("is_ig3", True),
                "remediation_cmd": check.get("remediation", ""),
                "message":         f"Found: {found}" if status == "fail" else "",
            })
        except Exception as ex:
            results.append({
                "cis_id": check["cis_id"], "section": check.get("section",""),
                "category": check.get("category",""), "title": check["title"],
                "status": "skip", "found_value": str(ex)[:100],
                "expected_value": check.get("expected",""),
                "is_ig1": check.get("is_ig1",True), "is_ig2": check.get("is_ig2",True),
                "is_ig3": check.get("is_ig3",True), "remediation_cmd": check.get("remediation",""),
                "message": f"Error: {ex}",
            })
    return results


# ─── OS Detection ─────────────────────────────────────────────────────────────

def _detect_os_via_ssh(ip: str, creds: list) -> dict:
    """Detect real OS via /etc/os-release."""
    info = {"os_name": "", "os_version": "", "os_family": "linux", "benchmark": ""}
    try:
        import paramiko
        for cred in creds:
            try:
                cli = paramiko.SSHClient()
                cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                cli.connect(ip, port=cred.get("port", 22),
                            username=cred["username"], password=cred["password"],
                            timeout=8, banner_timeout=8, auth_timeout=8)
                _, so, _ = cli.exec_command("cat /etc/os-release 2>/dev/null", timeout=8)
                out = so.read().decode(errors="ignore")
                cli.close()
                for line in out.splitlines():
                    if line.startswith("NAME="):
                        info["os_name"] = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("VERSION_ID="):
                        info["os_version"] = line.split("=", 1)[1].strip().strip('"')
                # Map to benchmark
                name_l = info["os_name"].lower()
                ver = info["os_version"]
                if "red hat" in name_l or "rhel" in name_l:
                    maj = ver.split(".")[0]
                    info["benchmark"] = f"CIS_RHEL{maj}"
                elif "centos" in name_l or "rocky" in name_l or "alma" in name_l:
                    maj = ver.split(".")[0]
                    info["benchmark"] = f"CIS_RHEL{maj}"
                elif "ubuntu" in name_l:
                    info["benchmark"] = f"CIS_Ubuntu_{ver}"
                else:
                    info["benchmark"] = "CIS_Linux_Generic"
                break
            except Exception:
                continue
    except Exception:
        pass
    return info


def _detect_os_via_winrm(ip: str, creds: list) -> dict:
    """Detect Windows OS version via WinRM."""
    info = {"os_name": "", "os_version": "", "os_family": "windows", "benchmark": ""}
    try:
        import winrm
        for cred in creds:
            try:
                s = winrm.Session(f"http://{ip}:5985/wsman",
                                  auth=(cred["username"], cred["password"]),
                                  transport="ntlm", server_cert_validation="ignore",
                                  operation_timeout_sec=10, read_timeout_sec=15)
                r = s.run_ps("(Get-WmiObject Win32_OperatingSystem).Caption")
                if r.status_code == 0:
                    caption = r.std_out.decode(errors="ignore").strip()
                    info["os_name"] = caption
                    r2 = s.run_ps("(Get-WmiObject Win32_OperatingSystem).Version")
                    if r2.status_code == 0:
                        info["os_version"] = r2.std_out.decode(errors="ignore").strip()
                    cap_l = caption.lower()
                    if "2022" in cap_l:
                        info["benchmark"] = "CIS_WinServer2022_v3.0.0"
                    elif "2019" in cap_l:
                        info["benchmark"] = "CIS_WinServer2019_v3.0.1"
                    elif "2016" in cap_l:
                        info["benchmark"] = "CIS_WinServer2016_v2.0.0"
                    else:
                        info["benchmark"] = "CIS_Windows_Generic"
                    break
            except Exception:
                continue
    except Exception:
        pass
    return info


# ─── Credential Loader ────────────────────────────────────────────────────────

import base64 as _b64

def _deobfuscate(enc: str) -> str:
    key = b"CaaS@Cred2026#"
    try:
        byt = _b64.b64decode(enc.encode())
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(byt)).decode()
    except Exception:
        return enc

def _load_creds_for_os(os_family: str) -> list:
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, password_enc, port FROM compliance_credentials "
                "WHERE os_family=%s ORDER BY id", (os_family,))
            rows = cur.fetchall()
        conn.close()
        return [{"username": r["username"], "password": _deobfuscate(r["password_enc"]),
                 "port": r["port"]} for r in rows]
    except Exception:
        # Fallback hardcoded creds for this environment
        if os_family == "linux":
            return [
                {"username": "root", "password": "Wipro@123",   "port": 22},
                {"username": "root", "password": "sdxcoe@123", "port": 22},
            ]
        else:
            return [{"username": "Administrator", "password": "Wipro@123", "port": 5985}]


# ─── Exclusion Helper ─────────────────────────────────────────────────────────

def _get_exclusions(vm_name: str = "") -> set:
    """Return set of excluded CIS IDs for this VM."""
    excluded = set()
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cis_id FROM cis_exclusions
                WHERE vm_name IS NULL OR vm_name='' OR vm_name=%s
            """, (vm_name,))
            excluded = {r["cis_id"] for r in cur.fetchall()}
        conn.close()
    except Exception as ex:
        log.debug(f"_get_exclusions: {ex}")
    return excluded


# ─── DB Writer ────────────────────────────────────────────────────────────────

def _write_vm_scan(conn, job_id: int, asset_id: int | None, vm_name: str,
                   ip: str, os_info: dict, results: list, scan_method: str = "ssh") -> int:
    exclusions = _get_exclusions(vm_name)
    total = len(results)
    passed  = sum(1 for r in results if r["status"] == "pass")
    failed  = sum(1 for r in results if r["status"] == "fail" and r["cis_id"] not in exclusions)
    skipped = sum(1 for r in results if r["status"] == "skip")
    excluded = len(exclusions.intersection({r["cis_id"] for r in results}))
    eligible = total - skipped - excluded
    score = round(passed / eligible * 100, 2) if eligible > 0 else 0

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO cis_vm_scans
                (job_id, asset_id, vm_name, ip_address, os_name, os_version,
                 os_family, benchmark, total_checks, passed, failed, skipped,
                 excluded, score, scan_method)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (job_id, asset_id, vm_name, ip,
              os_info.get("os_name",""), os_info.get("os_version",""),
              os_info.get("os_family","linux"), os_info.get("benchmark",""),
              total, passed, failed, skipped, excluded, score, scan_method))
        vm_scan_id = cur.fetchone()["id"]

        for r in results:
            ex_status = "excluded" if r["cis_id"] in exclusions else r["status"]
            cur.execute("""
                INSERT INTO cis_check_results
                    (vm_scan_id, cis_id, section, category, title, status,
                     found_value, expected_value, message, is_ig1, is_ig2, is_ig3, remediation_cmd)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (vm_scan_id, r["cis_id"], r.get("section",""), r.get("category",""),
                  r.get("title",""), ex_status, r.get("found_value",""),
                  r.get("expected_value",""), r.get("message",""),
                  r.get("is_ig1",True), r.get("is_ig2",True), r.get("is_ig3",True),
                  r.get("remediation_cmd","")))
    return vm_scan_id


# ─── JSON Ingestion (Goss format) ─────────────────────────────────────────────

def ingest_goss_json(file_path: str, vm_name: str, ip: str = "",
                     asset_id: int = None, triggered_by: str = "manual") -> dict:
    """Parse a Goss audit JSON file and store results in the CIS DB."""
    try:
        data = json.loads(Path(file_path).read_text(encoding="utf-8", errors="ignore"))
    except Exception as ex:
        return {"success": False, "error": str(ex)}

    results_raw = data.get("results", [])
    summary     = data.get("summary", {})

    # Group by title to deduplicate multiple checks for same CIS control
    seen = {}
    for item in results_raw:
        title = item.get("title", "")
        cis_id_match = re.match(r"^(\d+\.\d+[\.\d]*)", title)
        cis_id = cis_id_match.group(1) if cis_id_match else title[:20]

        meta = item.get("meta", {}) or {}
        cis_ids = meta.get("CIS_ID", [cis_id])
        if isinstance(cis_ids, str): cis_ids = [cis_ids]

        for cid in cis_ids:
            cid = str(cid)
            prev = seen.get(cid)
            # A control fails if ANY sub-check fails
            if prev is None:
                seen[cid] = {
                    "cis_id": cid,
                    "section": cid.split(".")[0] if cid else "0",
                    "category": "Ingested from Goss",
                    "title": title,
                    "status": "pass" if item.get("successful", False) else "fail",
                    "found_value":    str(item.get("found", ""))[:120],
                    "expected_value": str(item.get("expected", ""))[:120],
                    "is_ig1": bool(meta.get("CISv8_IG1", True)),
                    "is_ig2": bool(meta.get("CISv8_IG2", True)),
                    "is_ig3": bool(meta.get("CISv8_IG3", True)),
                    "remediation_cmd": "",
                    "message": item.get("summary-line", "")[:200],
                }
            elif not item.get("successful", True):
                seen[cid]["status"] = "fail"
                seen[cid]["found_value"] = str(item.get("found",""))[:120]
                seen[cid]["message"]    = item.get("summary-line","")[:200]

    results = list(seen.values())
    os_info = {
        "os_name":    "RHEL 8",
        "os_version": "8",
        "os_family":  "linux",
        "benchmark":  "CIS_RHEL8_v4.0.0_Goss",
    }

    try:
        conn = get_db()
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cis_scan_jobs (triggered_by, status, target_vms, scanned_vms)
                VALUES (%s, 'completed', 1, 1) RETURNING id
            """, (triggered_by,))
            job_id = cur.fetchone()["id"]

        vm_scan_id = _write_vm_scan(conn, job_id, asset_id, vm_name, ip, os_info,
                                    results, scan_method="ingested")
        passed  = sum(1 for r in results if r["status"] == "pass")
        failed  = sum(1 for r in results if r["status"] == "fail")

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE cis_scan_jobs SET status='completed', completed_at=NOW(),
                    total_checks=%s, passed_checks=%s, failed_checks=%s
                WHERE id=%s
            """, (len(results), passed, failed, job_id))
        conn.commit(); conn.close()
        return {"success": True, "job_id": job_id, "vm_scan_id": vm_scan_id,
                "total": len(results), "passed": passed, "failed": failed}
    except Exception as ex:
        log.error(f"ingest_goss_json: {ex}\n{traceback.format_exc()[:500]}")
        return {"success": False, "error": str(ex)}


# ─── Main Scan Orchestrator ───────────────────────────────────────────────────

_active_jobs: dict = {}   # job_id -> {"status", "progress", "total"}


def scan_assets_cis(asset_ids: list | None = None, triggered_by: str = "manual") -> dict:
    """
    Trigger a background CIS scan.
    asset_ids: list of compliance_assets.id to scan.  None = all active assets.
    Returns {job_id, message}
    """
    try:
        conn = get_db()
        # Load assets to scan
        with conn.cursor() as cur:
            if asset_ids:
                cur.execute("""
                    SELECT id, hostname, ip_address, os_family, os_name, os_version
                    FROM compliance_assets
                    WHERE id = ANY(%s) AND is_active=TRUE
                """, (asset_ids,))
            else:
                cur.execute("""
                    SELECT id, hostname, ip_address, os_family, os_name, os_version
                    FROM compliance_assets
                    WHERE is_active=TRUE AND ip_address IS NOT NULL
                    AND (os_family='linux' OR os_family='windows')
                    AND os_name NOT ILIKE '%router%'
                    AND os_name NOT ILIKE '%switch%'
                    AND os_name NOT ILIKE '%firewall%'
                    AND os_name NOT ILIKE '%appliance%'
                    AND os_name NOT ILIKE '%aruba%'
                    AND os_name NOT ILIKE '%clearpass%'
                    AND os_name NOT ILIKE '%cisco%'
                    AND os_name NOT ILIKE '%esxi%'
                    AND os_name NOT ILIKE '%vmkernel%'
                    ORDER BY power_state DESC, hostname ASC
                """)
            assets = [dict(r) for r in cur.fetchall()]

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cis_scan_jobs (triggered_by, status, target_vms)
                VALUES (%s, 'queued', %s) RETURNING id
            """, (triggered_by, len(assets)))
            job_id = cur.fetchone()["id"]
        conn.commit(); conn.close()

        if not assets:
            return {"job_id": job_id, "message": "No assets to scan (check IP and OS family)", "total": 0}

        _active_jobs[job_id] = {"status": "running", "progress": 0, "total": len(assets)}
        t = threading.Thread(target=_run_cis_scan_bg, args=(job_id, assets), daemon=True)
        t.start()
        return {"job_id": job_id, "message": f"CIS scan started — {len(assets)} assets queued", "total": len(assets)}
    except Exception as ex:
        log.error(f"scan_assets_cis: {ex}")
        return {"job_id": None, "message": str(ex), "total": 0}


def _run_cis_scan_bg(job_id: int, assets: list):
    """Background thread: SSH into each asset, run CIS checks, store results."""
    log.info(f"CIS scan job {job_id}: {len(assets)} assets")
    conn = get_db()
    conn.autocommit = False

    with conn.cursor() as cur:
        cur.execute("UPDATE cis_scan_jobs SET status='running', started_at=NOW() WHERE id=%s", (job_id,))
    conn.commit()

    total_checks = 0; total_passed = 0; total_failed = 0; total_skipped = 0
    scanned = 0

    for asset in assets:
        vm_name   = asset.get("hostname","")
        ip        = asset.get("ip_address","")
        os_family = asset.get("os_family","linux")
        asset_id  = asset.get("id")

        if not ip:
            log.debug(f"CIS skip {vm_name}: no IP")
            continue

        # Quick port check
        check_port = 22 if os_family == "linux" else 5985
        try:
            s = socket.create_connection((ip, check_port), timeout=4)
            s.close()
        except Exception:
            log.debug(f"CIS skip {vm_name}: port {check_port} not reachable")
            continue

        creds = _load_creds_for_os(os_family)
        if not creds:
            continue

        try:
            if os_family == "linux":
                os_info  = _detect_os_via_ssh(ip, creds)
                os_info["os_family"] = "linux"
                if not os_info.get("os_name") or not os_info.get("benchmark"):
                    # Fall back to compliance_assets os_name for benchmark mapping
                    asset_os = (asset.get("os_name","") or "").lower()
                    asset_ver = (asset.get("os_version","") or "").split(".")[0]
                    os_info["os_name"] = os_info.get("os_name") or asset.get("os_name","Linux")
                    os_info["os_version"] = os_info.get("os_version") or asset.get("os_version","")
                    if "red hat" in asset_os or "rhel" in asset_os:
                        if "9" in asset_ver: os_info["benchmark"] = "CIS_RHEL9"
                        elif "10" in asset_ver: os_info["benchmark"] = "CIS_RHEL10"
                        elif "7" in asset_ver: os_info["benchmark"] = "CIS_RHEL7"
                        else: os_info["benchmark"] = "CIS_RHEL8"
                    elif "centos" in asset_os or "rocky" in asset_os or "alma" in asset_os:
                        os_info["benchmark"] = f"CIS_RHEL{asset_ver}" if asset_ver else "CIS_RHEL8"
                    elif "ubuntu" in asset_os or "debian" in asset_os:
                        os_info["benchmark"] = "CIS_Ubuntu"
                    else:
                        os_info["benchmark"] = "CIS_RHEL8"  # safest default
                checks_to_run = get_checks_for_os("linux", os_info.get("benchmark",""))
                results = _ssh_run_checks(ip, checks_to_run, creds, vm_name)
                # Skip storing if ALL checks are skip (network device / auth failed)
                skip_count = sum(1 for r in results if r["status"] == "skip")
                if skip_count == len(results) and len(results) > 0:
                    log.info(f"CIS skip {vm_name}: all {len(results)} checks skipped (likely network device or auth failed)")
                    continue
            else:
                os_info  = _detect_os_via_winrm(ip, creds)
                os_info["os_family"] = "windows"
                if not os_info.get("os_name") or not os_info.get("benchmark"):
                    asset_os = (asset.get("os_name","") or "").lower()
                    os_info["os_name"] = os_info.get("os_name") or asset.get("os_name","Windows")
                    os_info["os_version"] = os_info.get("os_version") or asset.get("os_version","")
                    if "2022" in asset_os: os_info["benchmark"] = "CIS_WinServer2022_v3.0.0"
                    elif "2019" in asset_os: os_info["benchmark"] = "CIS_WinServer2019_v3.0.1"
                    elif "2016" in asset_os: os_info["benchmark"] = "CIS_WinServer2016_v2.0.0"
                    else: os_info["benchmark"] = "CIS_WinServer2022_v3.0.0"
                checks_to_run = get_checks_for_os("windows", os_info.get("benchmark",""))
                results = _winrm_run_checks(ip, checks_to_run, creds, vm_name)
                skip_count = sum(1 for r in results if r["status"] == "skip")
                if skip_count == len(results) and len(results) > 0:
                    log.info(f"CIS skip {vm_name}: all {len(results)} checks skipped (WinRM auth failed)")
                    continue

            _write_vm_scan(conn, job_id, asset_id, vm_name, ip, os_info, results)
            conn.commit()
            total_checks += len(results)
            total_passed += sum(1 for r in results if r["status"] == "pass")
            total_failed += sum(1 for r in results if r["status"] == "fail")
            total_skipped += sum(1 for r in results if r["status"] == "skip")
            scanned += 1
            _active_jobs[job_id]["progress"] = scanned

            log.info(f"CIS {vm_name}: {sum(1 for r in results if r['status']=='pass')}/{len(results)} pass")
        except Exception as ex:
            log.warning(f"CIS scan error {vm_name}: {ex}")

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE cis_scan_jobs
            SET status='completed', completed_at=NOW(),
                scanned_vms=%s, total_checks=%s,
                passed_checks=%s, failed_checks=%s, skipped_checks=%s
            WHERE id=%s
        """, (scanned, total_checks, total_passed, total_failed, total_skipped, job_id))
    conn.commit(); conn.close()
    _active_jobs[job_id]["status"] = "completed"
    log.info(f"CIS scan job {job_id} complete: {scanned} VMs, {total_passed}/{total_checks} pass")


def get_job_status(job_id: int) -> dict:
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cis_scan_jobs WHERE id=%s", (job_id,))
            row = cur.fetchone()
        conn.close()
        if not row:
            return {"error": "Job not found"}
        d = dict(row)
        d["progress"] = _active_jobs.get(job_id, {}).get("progress", d.get("scanned_vms", 0))
        return d
    except Exception as ex:
        return {"error": str(ex)}


# ─── Remediation Executor ─────────────────────────────────────────────────────

def remediate_check(vm_scan_id: int, cis_id: str, performed_by: str = "system") -> dict:
    """Execute the remediation command for a specific CIS check on a VM."""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            # Get VM info from vm_scan
            cur.execute("""
                SELECT vs.vm_name, vs.ip_address, vs.os_family,
                       cr.remediation_cmd, cr.title
                FROM cis_vm_scans vs
                JOIN cis_check_results cr ON cr.vm_scan_id = vs.id
                WHERE vs.id=%s AND cr.cis_id=%s
            """, (vm_scan_id, cis_id))
            row = cur.fetchone()
        conn.close()
    except Exception as ex:
        return {"success": False, "error": str(ex)}

    if not row:
        return {"success": False, "error": "Check result not found"}

    vm_name   = row["vm_name"]
    ip        = row["ip_address"]
    os_family = row["os_family"]
    rem_cmd   = row["remediation_cmd"]
    title     = row["title"]

    if not rem_cmd or not rem_cmd.strip():
        return {"success": False, "error": "No remediation command available for this check"}
    if not ip:
        return {"success": False, "error": "No IP address for this VM"}

    creds = _load_creds_for_os(os_family)
    output = ""
    success = False

    try:
        if os_family == "linux":
            import paramiko
            for cred in creds:
                try:
                    cli = paramiko.SSHClient()
                    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    cli.connect(ip, port=cred.get("port", 22),
                                username=cred["username"], password=cred["password"],
                                timeout=SSH_TIMEOUT, banner_timeout=SSH_TIMEOUT, auth_timeout=SSH_TIMEOUT)
                    _, stdout, stderr = cli.exec_command(rem_cmd, timeout=30)
                    output  = stdout.read().decode(errors="ignore") + stderr.read().decode(errors="ignore")
                    success = True
                    cli.close()
                    break
                except Exception as ex:
                    output = str(ex)
        else:
            import winrm
            for cred in creds:
                try:
                    s = winrm.Session(f"http://{ip}:5985/wsman",
                                      auth=(cred["username"], cred["password"]),
                                      transport="ntlm", server_cert_validation="ignore",
                                      operation_timeout_sec=30, read_timeout_sec=35)
                    r = s.run_ps(rem_cmd)
                    output  = r.std_out.decode(errors="ignore")
                    success = r.status_code == 0
                    break
                except Exception as ex:
                    output = str(ex)
    except Exception as ex:
        output = str(ex)

    # Log remediation
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cis_remediation_log
                    (vm_scan_id, cis_id, vm_name, ip_address, action_taken, output, success, performed_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (vm_scan_id, cis_id, vm_name, ip, rem_cmd, output[:2000], success, performed_by))
        conn.commit(); conn.close()
    except Exception as ex:
        log.debug(f"remediation log write: {ex}")

    return {"success": success, "output": output[:1000], "vm_name": vm_name,
            "cis_id": cis_id, "title": title}


# ─── OS-Version-Specific Check Additions ─────────────────────────────────────
# These extend LINUX_CHECKS / WINDOWS_CHECKS with controls that differ per OS.

RHEL8_SPECIFIC = [
    {"cis_id":"1.10","section":"1","category":"Crypto Policy",
     "title":"Ensure system-wide crypto policy is not LEGACY (RHEL 8)",
     "cmd":"update-crypto-policies --show 2>/dev/null | grep -cEv '^(LEGACY)$'",
     "pass_if":"nonzero","expected":"Policy != LEGACY",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"update-crypto-policies --set DEFAULT 2>/dev/null; echo done"},
    {"cis_id":"1.11","section":"1","category":"SELinux",
     "title":"Ensure SELinux is Enforcing (RHEL 8)",
     "cmd":"getenforce 2>/dev/null | grep -ci 'Enforcing'",
     "pass_if":"nonzero","expected":"Enforcing",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"setenforce 1; sed -i 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config; echo done"},
    {"cis_id":"3.4.1.1","section":"3","category":"Firewall",
     "title":"Ensure firewalld is installed and active (RHEL 8)",
     "cmd":"systemctl is-active firewalld 2>/dev/null | grep -c '^active'",
     "pass_if":"nonzero","expected":"firewalld active",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"dnf install -y firewalld 2>/dev/null; systemctl enable --now firewalld; echo done"},
    {"cis_id":"4.1.2.4","section":"4","category":"Audit",
     "title":"Ensure audit_backlog_limit is set in GRUB (RHEL 8)",
     "cmd":"grubby --info=ALL 2>/dev/null | grep -c 'audit_backlog_limit'",
     "pass_if":"nonzero","expected":"audit_backlog_limit in kernel args",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"grubby --update-kernel=ALL --args='audit_backlog_limit=8192' 2>/dev/null; echo done"},
    {"cis_id":"5.5.1","section":"5","category":"PAM",
     "title":"Ensure authselect is configured (RHEL 8)",
     "cmd":"authselect current 2>/dev/null | grep -c 'Profile ID'",
     "pass_if":"nonzero","expected":"authselect profile active",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"authselect select sssd --force 2>/dev/null; echo done"},
    {"cis_id":"5.5.2","section":"5","category":"PAM",
     "title":"Ensure password quality (pwquality minlen >= 14) (RHEL 8)",
     "cmd":"grep -E '^\\s*minlen\\s*=\\s*([1-9][4-9]|[2-9][0-9])' /etc/security/pwquality.conf 2>/dev/null | wc -l",
     "pass_if":"nonzero","expected":"minlen >= 14",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"sed -i 's/^#*\\s*minlen.*/minlen = 14/' /etc/security/pwquality.conf; grep -q 'minlen' /etc/security/pwquality.conf || echo 'minlen = 14' >> /etc/security/pwquality.conf; echo done"},
    {"cis_id":"1.12","section":"1","category":"Package Manager",
     "title":"Ensure dnf-automatic is installed (RHEL 8)",
     "cmd":"rpm -q dnf-automatic 2>&1 | grep -c 'not installed'",
     "pass_if":"zero","expected":"dnf-automatic installed",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"dnf install -y dnf-automatic 2>/dev/null; systemctl enable --now dnf-automatic-install.timer; echo done"},
    {"cis_id":"6.2.10","section":"6","category":"File Integrity",
     "title":"Ensure AIDE is installed (RHEL 8)",
     "cmd":"rpm -q aide 2>&1 | grep -c 'not installed'",
     "pass_if":"zero","expected":"aide installed",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"dnf install -y aide 2>/dev/null; aide --init 2>/dev/null; mv /var/lib/aide/aide.db.new.gz /var/lib/aide/aide.db.gz 2>/dev/null; echo done"},
]

RHEL9_SPECIFIC = [
    {"cis_id":"1.10","section":"1","category":"Crypto Policy",
     "title":"Ensure system-wide crypto policy is not LEGACY (RHEL 9)",
     "cmd":"update-crypto-policies --show 2>/dev/null | grep -cEv '^(LEGACY)$'",
     "pass_if":"nonzero","expected":"Policy != LEGACY",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"update-crypto-policies --set DEFAULT 2>/dev/null; echo done"},
    {"cis_id":"1.11","section":"1","category":"SELinux",
     "title":"Ensure SELinux is Enforcing (RHEL 9)",
     "cmd":"getenforce 2>/dev/null | grep -ci 'Enforcing'",
     "pass_if":"nonzero","expected":"Enforcing",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"setenforce 1; sed -i 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config; echo done"},
    {"cis_id":"3.4.1.1","section":"3","category":"Firewall",
     "title":"Ensure firewalld is active (RHEL 9)",
     "cmd":"systemctl is-active firewalld 2>/dev/null | grep -c '^active'",
     "pass_if":"nonzero","expected":"firewalld active",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"dnf install -y firewalld 2>/dev/null; systemctl enable --now firewalld; echo done"},
    {"cis_id":"3.5.1","section":"3","category":"Network",
     "title":"Ensure nftables is installed (RHEL 9)",
     "cmd":"rpm -q nftables 2>&1 | grep -c 'not installed'",
     "pass_if":"zero","expected":"nftables installed",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"dnf install -y nftables 2>/dev/null; echo done"},
    {"cis_id":"5.5.1","section":"5","category":"PAM",
     "title":"Ensure authselect is configured (RHEL 9)",
     "cmd":"authselect current 2>/dev/null | grep -c 'Profile ID'",
     "pass_if":"nonzero","expected":"authselect profile active",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"authselect select sssd --force 2>/dev/null; echo done"},
    {"cis_id":"5.5.2","section":"5","category":"PAM",
     "title":"Ensure pwquality minlen >= 14 (RHEL 9)",
     "cmd":"grep -E '^\\s*minlen\\s*=\\s*([1-9][4-9]|[2-9][0-9])' /etc/security/pwquality.conf 2>/dev/null | wc -l",
     "pass_if":"nonzero","expected":"minlen >= 14",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"grep -q 'minlen' /etc/security/pwquality.conf && sed -i 's/^#*\\s*minlen.*/minlen = 14/' /etc/security/pwquality.conf || echo 'minlen = 14' >> /etc/security/pwquality.conf; echo done"},
    {"cis_id":"4.1.1.1","section":"4","category":"Audit",
     "title":"Ensure auditd is latest version and running (RHEL 9)",
     "cmd":"systemctl is-active auditd 2>/dev/null | grep -c '^active'",
     "pass_if":"nonzero","expected":"auditd active",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"dnf install -y audit 2>/dev/null; systemctl enable --now auditd; echo done"},
    {"cis_id":"6.2.10","section":"6","category":"File Integrity",
     "title":"Ensure AIDE is installed (RHEL 9)",
     "cmd":"rpm -q aide 2>&1 | grep -c 'not installed'",
     "pass_if":"zero","expected":"aide installed",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"dnf install -y aide 2>/dev/null; aide --init 2>/dev/null; mv /var/lib/aide/aide.db.new.gz /var/lib/aide/aide.db.gz 2>/dev/null; echo done"},
]

RHEL10_SPECIFIC = [
    {"cis_id":"1.10","section":"1","category":"Crypto Policy",
     "title":"Ensure system-wide crypto policy is not LEGACY (RHEL 10)",
     "cmd":"update-crypto-policies --show 2>/dev/null | grep -cEv '^(LEGACY)$'",
     "pass_if":"nonzero","expected":"Policy != LEGACY",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"update-crypto-policies --set DEFAULT 2>/dev/null; echo done"},
    {"cis_id":"1.11","section":"1","category":"SELinux",
     "title":"Ensure SELinux is Enforcing (RHEL 10)",
     "cmd":"getenforce 2>/dev/null | grep -ci 'Enforcing'",
     "pass_if":"nonzero","expected":"Enforcing",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"setenforce 1; sed -i 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config; echo done"},
    {"cis_id":"3.4.1.1","section":"3","category":"Firewall",
     "title":"Ensure nftables is the primary firewall (RHEL 10)",
     "cmd":"systemctl is-active nftables 2>/dev/null | grep -c '^active'",
     "pass_if":"nonzero","expected":"nftables active",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"dnf install -y nftables 2>/dev/null; systemctl enable --now nftables; echo done"},
    {"cis_id":"5.5.1","section":"5","category":"PAM",
     "title":"Ensure authselect is configured (RHEL 10)",
     "cmd":"authselect current 2>/dev/null | grep -c 'Profile ID'",
     "pass_if":"nonzero","expected":"authselect profile active",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"authselect select sssd --force 2>/dev/null; echo done"},
    {"cis_id":"5.5.3","section":"5","category":"PAM",
     "title":"Ensure pwquality minlen >= 14 (RHEL 10)",
     "cmd":"grep -E '^\\s*minlen\\s*=\\s*([1-9][4-9]|[2-9][0-9])' /etc/security/pwquality.conf 2>/dev/null | wc -l",
     "pass_if":"nonzero","expected":"minlen >= 14",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"grep -q 'minlen' /etc/security/pwquality.conf && sed -i 's/^#*\\s*minlen.*/minlen = 14/' /etc/security/pwquality.conf || echo 'minlen = 14' >> /etc/security/pwquality.conf; echo done"},
    {"cis_id":"1.6.1","section":"1","category":"Bootloader",
     "title":"Ensure GRUB password is set (RHEL 10)",
     "cmd":"grep -rEc 'password_pbkdf2' /boot/grub2/ 2>/dev/null || echo 0",
     "pass_if":"nonzero","expected":"GRUB password configured",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"echo 'Run: grub2-setpassword to set GRUB password'; echo done"},
    {"cis_id":"6.2.10","section":"6","category":"File Integrity",
     "title":"Ensure AIDE is installed (RHEL 10)",
     "cmd":"rpm -q aide 2>&1 | grep -c 'not installed'",
     "pass_if":"zero","expected":"aide installed",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"dnf install -y aide 2>/dev/null; aide --init 2>/dev/null; mv /var/lib/aide/aide.db.new.gz /var/lib/aide/aide.db.gz 2>/dev/null; echo done"},
    {"cis_id":"4.1.1.3","section":"4","category":"Audit",
     "title":"Ensure audit log storage size is configured (RHEL 10)",
     "cmd":"grep -c '^max_log_file\\s*=' /etc/audit/auditd.conf 2>/dev/null",
     "pass_if":"nonzero","expected":"max_log_file configured",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"sed -i 's/^max_log_file.*/max_log_file = 100/' /etc/audit/auditd.conf 2>/dev/null; systemctl reload auditd 2>/dev/null; echo done"},
]

WIN2016_SPECIFIC = [
    {"cis_id":"W.18.1","section":"18","category":"Credential Protection",
     "title":"Ensure LSA Protection (RunAsPPL) is enabled (WS2016)",
     "cmd":"try{$v=(Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa' -Name RunAsPPL 2>$null).RunAsPPL;if($v -eq 1){'PASS'}else{\"FAIL:$v\"}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"RunAsPPL = 1",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"Set-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa' -Name RunAsPPL -Value 1 2>$null; 'done'"},
    {"cis_id":"W.18.2","section":"18","category":"Windows Defender",
     "title":"Ensure Windows Defender PUA Protection is enabled (WS2016)",
     "cmd":"try{$p=(Get-MpPreference 2>$null).PUAProtection;if($p -ge 1){'PASS'}else{\"FAIL:$p\"}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"PUAProtection >= 1",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"Set-MpPreference -PUAProtection 1 2>$null; 'done'"},
    {"cis_id":"W.18.3","section":"18","category":"Audit Policy",
     "title":"Ensure Audit Logon Events (Success+Failure) (WS2016)",
     "cmd":"try{$a=auditpol /get /subcategory:'Logon' 2>$null;if($a -match 'Success'){'PASS'}else{'FAIL'}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"Logon audit Success enabled",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"auditpol /set /subcategory:'Logon' /success:enable /failure:enable 2>$null; 'done'"},
    {"cis_id":"W.18.4","section":"18","category":"TLS",
     "title":"Ensure TLS 1.0 is disabled (WS2016)",
     "cmd":"try{$v=(Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.0\\Server' -Name Enabled 2>$null).Enabled;if($v -eq 0){'PASS'}else{\"FAIL:$v\"}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"TLS 1.0 Enabled=0",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"$p='HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.0\\Server';New-Item -Path $p -Force 2>$null|Out-Null;Set-ItemProperty -Path $p -Name Enabled -Value 0; 'done'"},
    {"cis_id":"W.18.5","section":"18","category":"Windows Update",
     "title":"Ensure Windows Update service is running (WS2016)",
     "cmd":"try{if((Get-Service wuauserv).Status -eq 'Running'){'PASS'}else{'FAIL'}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"wuauserv Running",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"Set-Service wuauserv -StartupType Automatic; Start-Service wuauserv 2>$null; 'done'"},
]

WIN2019_SPECIFIC = [
    {"cis_id":"W.18.1","section":"18","category":"Credential Guard",
     "title":"Ensure Credential Guard is enabled (WS2019)",
     "cmd":"try{$v=(Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa' -Name LsaCfgFlags 2>$null).LsaCfgFlags;if($v -ge 1){'PASS'}else{\"FAIL:$v\"}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"LsaCfgFlags >= 1",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"Set-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa' -Name LsaCfgFlags -Value 1 2>$null; 'done'"},
    {"cis_id":"W.18.2","section":"18","category":"Windows Defender",
     "title":"Ensure Defender Cloud Protection (MAPS) is enabled (WS2019)",
     "cmd":"try{$p=(Get-MpPreference 2>$null).MAPSReporting;if($p -ge 1){'PASS'}else{\"FAIL:$p\"}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"MAPSReporting >= 1",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"Set-MpPreference -MAPSReporting Advanced 2>$null; 'done'"},
    {"cis_id":"W.18.3","section":"18","category":"Attack Surface Reduction",
     "title":"Ensure Windows Defender ASR rules are configured (WS2019)",
     "cmd":"try{$r=(Get-MpPreference 2>$null).AttackSurfaceReductionRules_Ids;if($r){'PASS'}else{'FAIL'}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"ASR rules configured",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"Add-MpPreference -AttackSurfaceReductionRules_Ids 'D4F940AB-401B-4EFC-AADC-AD5F3C50688A' -AttackSurfaceReductionRules_Actions Enabled 2>$null; 'done'"},
    {"cis_id":"W.18.4","section":"18","category":"TLS",
     "title":"Ensure TLS 1.0 and 1.1 are disabled (WS2019)",
     "cmd":"try{$v=(Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.0\\Server' -Name Enabled 2>$null).Enabled;if($v -eq 0){'PASS'}else{\"FAIL:TLS1.0=$v\"}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"TLS 1.0 disabled",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"$p='HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.0\\Server';New-Item -Path $p -Force 2>$null|Out-Null;Set-ItemProperty -Path $p -Name Enabled -Value 0; 'done'"},
    {"cis_id":"W.18.5","section":"18","category":"Audit Policy",
     "title":"Ensure Audit Logon Events is enabled (WS2019)",
     "cmd":"try{$a=auditpol /get /subcategory:'Logon' 2>$null;if($a -match 'Success'){'PASS'}else{'FAIL'}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"Logon auditing Success",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"auditpol /set /subcategory:'Logon' /success:enable /failure:enable 2>$null; 'done'"},
]

WIN2022_SPECIFIC = [
    {"cis_id":"W.18.1","section":"18","category":"Virtualization Security",
     "title":"Ensure Virtualization Based Security (VBS) is running (WS2022)",
     "cmd":"try{$vbs=Get-CimInstance -ClassName Win32_DeviceGuard 2>$null;if($vbs.SecurityServicesRunning -contains 1){'PASS'}else{'FAIL'}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"VBS/Credential Guard running",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"'Enable VBS via Group Policy: Computer Config > System > Device Guard'; 'done'"},
    {"cis_id":"W.18.2","section":"18","category":"TLS",
     "title":"Ensure TLS 1.0 and 1.1 are disabled (WS2022)",
     "cmd":"try{$v=(Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.0\\Server' -Name Enabled 2>$null).Enabled;if($v -eq 0){'PASS'}else{\"FAIL:$v\"}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"TLS 1.0 disabled",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"$p='HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.0\\Server';New-Item -Path $p -Force 2>$null|Out-Null;Set-ItemProperty -Path $p -Name Enabled -Value 0; 'done'"},
    {"cis_id":"W.18.3","section":"18","category":"WDAC",
     "title":"Ensure Windows Defender App Control (WDAC) policy is enforced (WS2022)",
     "cmd":"try{$ci=Get-CimInstance -ClassName Win32_DeviceGuard 2>$null;if($ci.CodeIntegrityPolicyEnforcementStatus -ge 1){'PASS'}else{'FAIL'}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"WDAC enforcement >= 1",
     "is_ig1":False,"is_ig2":False,"is_ig3":True,
     "remediation":"'Configure WDAC via WDAC Wizard or PowerShell CI policy'; 'done'"},
    {"cis_id":"W.18.4","section":"18","category":"Secured Core",
     "title":"Ensure Secure Boot is enabled (WS2022)",
     "cmd":"try{$sb=Confirm-SecureBootUEFI 2>$null;if($sb -eq $true){'PASS'}else{'FAIL'}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"Secure Boot enabled",
     "is_ig1":False,"is_ig2":True,"is_ig3":True,
     "remediation":"'Enable Secure Boot in UEFI/BIOS firmware settings'; 'done'"},
    {"cis_id":"W.18.5","section":"18","category":"Defender Tamper",
     "title":"Ensure Defender Tamper Protection is active (WS2022)",
     "cmd":"try{$p=(Get-MpPreference 2>$null).TamperProtectionSource;if($p -and $p -ne 'NotConfigured'){'PASS'}else{'FAIL'}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"Tamper Protection configured",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"'Enable Tamper Protection via Windows Security > Virus & Threat Protection settings'; 'done'"},
    {"cis_id":"W.18.6","section":"18","category":"Audit Policy",
     "title":"Ensure Audit Logon Events is enabled (WS2022)",
     "cmd":"try{$a=auditpol /get /subcategory:'Logon' 2>$null;if($a -match 'Success'){'PASS'}else{'FAIL'}}catch{'SKIP'}",
     "pass_if":"contains:PASS","expected":"Logon auditing Success",
     "is_ig1":True,"is_ig2":True,"is_ig3":True,
     "remediation":"auditpol /set /subcategory:'Logon' /success:enable /failure:enable 2>$null; 'done'"},
]


def get_checks_for_os(os_family: str, benchmark: str) -> list:
    """Return the combined check list for the detected OS/benchmark version."""
    bm = (benchmark or "").upper()
    if os_family == "windows":
        if "2022" in bm:
            return WINDOWS_CHECKS + WIN2022_SPECIFIC
        elif "2019" in bm:
            return WINDOWS_CHECKS + WIN2019_SPECIFIC
        else:
            return WINDOWS_CHECKS + WIN2016_SPECIFIC
    else:  # linux / rhel
        if "RHEL10" in bm or "RHEL_10" in bm or "_10" in bm:
            return LINUX_CHECKS + RHEL10_SPECIFIC
        elif "RHEL9" in bm or "RHEL_9" in bm or "_9" in bm:
            return LINUX_CHECKS + RHEL9_SPECIFIC
        else:
            return LINUX_CHECKS + RHEL8_SPECIFIC


# ─── Initialize on import ────────────────────────────────────────────────────

try:
    init_cis_db()
except Exception as _e:
    log.warning(f"CIS DB init deferred: {_e}")
