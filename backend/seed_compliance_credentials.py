"""
seed_compliance_credentials.py
Seed the 4 standard COE credential profiles into compliance_credentials vault.
Run once: .\venv\Scripts\python.exe seed_compliance_credentials.py
"""
import sys, base64, psycopg2, psycopg2.extras
from pathlib import Path

PG = dict(host="127.0.0.1", port=5433, dbname="caas_dashboard",
          user="caas_app", password="CaaS@App2024#")

def obfuscate(plain: str) -> str:
    key = b"CaaS@Cred2026#"
    byt = plain.encode()
    out = bytes(b ^ key[i % len(key)] for i, b in enumerate(byt))
    return base64.b64encode(out).decode()

PROFILES = [
    {"profile_name": "Linux - root (Primary)",     "os_family": "linux",   "port": 22,   "username": "root",             "password": "Wipro@123"},
    {"profile_name": "Linux - root (Secondary)",   "os_family": "linux",   "port": 22,   "username": "root",             "password": "sdxcoe@123"},
    {"profile_name": "Windows - Administrator",    "os_family": "windows", "port": 5985, "username": "Administrator",    "password": "Wipro@123"},
    {"profile_name": "AD - sdxtest\\azurehci (Linux)",   "os_family": "linux",   "port": 22,   "username": "sdxtest\\azurehci","password": "Wipro@123"},
    {"profile_name": "AD - sdxtest\\azurehci (Windows)", "os_family": "windows", "port": 5985, "username": "sdxtest\\azurehci","password": "Wipro@123"},
]

conn = psycopg2.connect(**PG, cursor_factory=psycopg2.extras.RealDictCursor)
cur  = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS compliance_credentials (
        id           SERIAL PRIMARY KEY,
        profile_name TEXT NOT NULL UNIQUE,
        os_family    TEXT NOT NULL DEFAULT 'linux',
        port         INTEGER NOT NULL DEFAULT 22,
        username     TEXT NOT NULL,
        password_enc TEXT NOT NULL,
        created_by   TEXT,
        created_at   TIMESTAMPTZ DEFAULT NOW(),
        updated_at   TIMESTAMPTZ DEFAULT NOW()
    )
""")

for p in PROFILES:
    cur.execute("""
        INSERT INTO compliance_credentials (profile_name, os_family, port, username, password_enc, created_by)
        VALUES (%(profile_name)s, %(os_family)s, %(port)s, %(username)s, %(enc)s, 'system')
        ON CONFLICT (profile_name) DO UPDATE
          SET os_family=EXCLUDED.os_family, port=EXCLUDED.port,
              username=EXCLUDED.username, password_enc=EXCLUDED.password_enc,
              updated_at=NOW()
    """, {**p, "enc": obfuscate(p["password"])})
    print(f"  ✓ {p['profile_name']} ({p['username']} / {p['os_family']} :{p['port']})")

conn.commit()
cur.close()
conn.close()
print(f"\nDone — {len(PROFILES)} credential profiles seeded.")
