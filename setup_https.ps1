# ============================================================================
# CaaS Dashboard — HTTPS Setup Script (fixed)
# Adds HTTPS backend on port 8443 + HTTPS frontend on port 443
# HTTP (8000 / 3000) is NEVER touched — HTTPS is purely additive
# Run as Administrator on 172.17.70.100
# ============================================================================

$ErrorActionPreference = "Stop"
$BASE         = "C:\caas-dashboard"
$CERT_DIR     = "$BASE\certs"
$BACKEND_DIR  = "$BASE\backend"
$FRONTEND_DIR = "$BASE\frontend"
$UVICORN      = "$BACKEND_DIR\venv\Scripts\uvicorn.exe"
$VENV_PYTHON  = "$BACKEND_DIR\venv\Scripts\python.exe"
$SERVER_IP    = "172.17.70.100"
$NSSM         = "nssm"

Write-Host "=== CaaS HTTPS Setup ===" -ForegroundColor Cyan

# Step 1: Create directories
if (!(Test-Path $CERT_DIR))             { New-Item -ItemType Directory -Path $CERT_DIR | Out-Null }
if (!(Test-Path "$BACKEND_DIR\logs"))   { New-Item -ItemType Directory -Path "$BACKEND_DIR\logs" | Out-Null }

# Step 2: Generate self-signed certificate via PowerShell built-in
Write-Host "`nGenerating self-signed certificate..." -ForegroundColor Cyan

$cert = New-SelfSignedCertificate `
    -DnsName "caas-dashboard","localhost",$SERVER_IP `
    -CertStoreLocation "cert:\LocalMachine\My" `
    -NotAfter (Get-Date).AddYears(10) `
    -KeyAlgorithm RSA -KeyLength 2048 `
    -FriendlyName "CaaS Dashboard SSL" `
    -KeyExportPolicy Exportable

Write-Host "Certificate thumbprint: $($cert.Thumbprint)" -ForegroundColor Green

# Export PFX
$pfxPass = ConvertTo-SecureString -String "CaasTemp2024!" -Force -AsPlainText
$pfxPath = "$CERT_DIR\caas.pfx"
Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $pfxPass | Out-Null

# Write Python conversion script to temp file (avoids all heredoc/escaping issues)
$pyScript = "$CERT_DIR\convert_cert.py"
$pyContent = @"
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
from cryptography.hazmat.primitives import serialization
import sys

pfx_path  = r"$pfxPath"
key_path  = r"$CERT_DIR\caas.key"
crt_path  = r"$CERT_DIR\caas.crt"
password  = b"CaasTemp2024!"

with open(pfx_path, "rb") as f:
    data = f.read()

pk, cert, _ = load_key_and_certificates(data, password)

with open(key_path, "wb") as f:
    f.write(pk.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))

with open(crt_path, "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

print("OK: PEM files written to", key_path, "and", crt_path)
"@

[System.IO.File]::WriteAllText($pyScript, $pyContent, [System.Text.Encoding]::UTF8)

Write-Host "Running PFX -> PEM conversion..." -ForegroundColor Cyan
& $VENV_PYTHON $pyScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing cryptography package..." -ForegroundColor Yellow
    & "$BACKEND_DIR\venv\Scripts\pip.exe" install cryptography --quiet
    & $VENV_PYTHON $pyScript
}

if (!(Test-Path "$CERT_DIR\caas.crt")) {
    Write-Host "ERROR: PEM conversion failed. See output above." -ForegroundColor Red
    exit 1
}
Write-Host "Certificate PEM files ready." -ForegroundColor Green

# Cleanup temp files
Remove-Item $pyScript -ErrorAction SilentlyContinue
Remove-Item $pfxPath  -ErrorAction SilentlyContinue

# Step 3: HTTPS Backend NSSM service on port 8443
Write-Host "`nConfiguring CaaS-Backend-HTTPS (port 8443)..." -ForegroundColor Cyan

& $NSSM stop   "CaaS-Backend-HTTPS" 2>$null
& $NSSM remove "CaaS-Backend-HTTPS" confirm 2>$null
Start-Sleep -Seconds 2

$uvArgs = "main:app --host 0.0.0.0 --port 8443 --ssl-keyfile `"$CERT_DIR\caas.key`" --ssl-certfile `"$CERT_DIR\caas.crt`""
& $NSSM install "CaaS-Backend-HTTPS" $UVICORN
& $NSSM set "CaaS-Backend-HTTPS" AppParameters  $uvArgs
& $NSSM set "CaaS-Backend-HTTPS" AppDirectory   $BACKEND_DIR
& $NSSM set "CaaS-Backend-HTTPS" DisplayName    "CaaS Backend HTTPS"
& $NSSM set "CaaS-Backend-HTTPS" Start          SERVICE_AUTO_START
& $NSSM set "CaaS-Backend-HTTPS" AppStdout      "$BACKEND_DIR\logs\backend_https.log"
& $NSSM set "CaaS-Backend-HTTPS" AppStderr      "$BACKEND_DIR\logs\backend_https_err.log"
& $NSSM start "CaaS-Backend-HTTPS"
Write-Host "CaaS-Backend-HTTPS started." -ForegroundColor Green

# Step 4: HTTPS Frontend Node.js server on port 443
Write-Host "`nConfiguring CaaS-Frontend-HTTPS (port 443)..." -ForegroundColor Cyan

$nodeServerPath = "$FRONTEND_DIR\https_server.js"
$nodeContent = @"
const https = require('https');
const http  = require('http');
const fs    = require('fs');
const path  = require('path');

const KEY  = fs.readFileSync(String.raw``$CERT_DIR\caas.key``);
const CERT = fs.readFileSync(String.raw``$CERT_DIR\caas.crt``);
const DIST = path.join(__dirname, 'dist');

const MIME = {
  '.html': 'text/html',
  '.js':   'application/javascript',
  '.css':  'text/css',
  '.json': 'application/json',
  '.png':  'image/png',
  '.ico':  'image/x-icon',
  '.svg':  'image/svg+xml',
  '.woff2':'font/woff2'
};

function serve(req, res) {
  var fp = path.join(DIST, req.url === '/' ? 'index.html' : req.url);
  if (!fs.existsSync(fp) || fs.statSync(fp).isDirectory()) {
    fp = path.join(DIST, 'index.html');
  }
  var ext = path.extname(fp);
  res.writeHead(200, { 'Content-Type': MIME[ext] || 'text/plain' });
  fs.createReadStream(fp).pipe(res);
}

https.createServer({ key: KEY, cert: CERT }, serve).listen(443, '0.0.0.0', function() {
  console.log('CaaS HTTPS frontend running: https://$SERVER_IP');
});

http.createServer(function(req, res) {
  res.writeHead(301, { Location: 'https://$SERVER_IP' + req.url });
  res.end();
}).listen(80, '0.0.0.0', function() {
  console.log('HTTP redirect active on port 80');
});
"@

[System.IO.File]::WriteAllText($nodeServerPath, $nodeContent, [System.Text.Encoding]::UTF8)

$NODE_EXE = "node"
$nodePath = (Get-Command node -ErrorAction SilentlyContinue)
if ($nodePath) { $NODE_EXE = $nodePath.Source }

& $NSSM stop   "CaaS-Frontend-HTTPS" 2>$null
& $NSSM remove "CaaS-Frontend-HTTPS" confirm 2>$null
Start-Sleep -Seconds 2

& $NSSM install "CaaS-Frontend-HTTPS" $NODE_EXE
& $NSSM set "CaaS-Frontend-HTTPS" AppParameters  "https_server.js"
& $NSSM set "CaaS-Frontend-HTTPS" AppDirectory   $FRONTEND_DIR
& $NSSM set "CaaS-Frontend-HTTPS" DisplayName    "CaaS Frontend HTTPS"
& $NSSM set "CaaS-Frontend-HTTPS" Start          SERVICE_AUTO_START
& $NSSM start "CaaS-Frontend-HTTPS"
Write-Host "CaaS-Frontend-HTTPS started." -ForegroundColor Green

# Step 5: Firewall rules
Write-Host "`nAdding firewall rules..." -ForegroundColor Cyan
netsh advfirewall firewall delete rule name="CaaS HTTPS Backend"  | Out-Null
netsh advfirewall firewall delete rule name="CaaS HTTPS Frontend" | Out-Null
netsh advfirewall firewall delete rule name="CaaS HTTP Redirect"  | Out-Null
netsh advfirewall firewall add rule name="CaaS HTTPS Backend"  dir=in action=allow protocol=TCP localport=8443 | Out-Null
netsh advfirewall firewall add rule name="CaaS HTTPS Frontend" dir=in action=allow protocol=TCP localport=443  | Out-Null
netsh advfirewall firewall add rule name="CaaS HTTP Redirect"  dir=in action=allow protocol=TCP localport=80   | Out-Null
Write-Host "Firewall rules set for ports 80, 443, 8443." -ForegroundColor Green

# Step 6: Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  HTTPS Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  HTTP  (unchanged) : http://${SERVER_IP}:3000"
Write-Host "  HTTPS (new)       : https://${SERVER_IP}"
Write-Host ""
Write-Host "  NOTE: Browser will show a security warning on first visit." -ForegroundColor Yellow
Write-Host "  Click Advanced -> Proceed to continue." -ForegroundColor Yellow
Write-Host "  Run install_cert_trust.ps1 as Admin to suppress this permanently." -ForegroundColor Yellow
