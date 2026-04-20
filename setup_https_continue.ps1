# CaaS HTTPS Continue Setup — run as Administrator
$ErrorActionPreference = "Continue"
$BASE         = "C:\caas-dashboard"
$CERT_DIR     = "$BASE\certs"
$BACKEND_DIR  = "$BASE\backend"
$FRONTEND_DIR = "$BASE\frontend"
$UVICORN      = "$BACKEND_DIR\venv\Scripts\uvicorn.exe"
$SERVER_IP    = "172.17.70.100"
$NSSM         = "nssm"

Write-Host "=== CaaS HTTPS Continue ===" -ForegroundColor Cyan

if (!(Test-Path "$BACKEND_DIR\logs")) { New-Item -ItemType Directory -Path "$BACKEND_DIR\logs" | Out-Null }

# ── Backend HTTPS on 8443 ─────────────────────────────────────────────────────
Write-Host "Setting up CaaS-Backend-HTTPS..." -ForegroundColor Cyan
Start-Process nssm -ArgumentList "stop ""CaaS-Backend-HTTPS"""    -Wait -WindowStyle Hidden
Start-Sleep 1
Start-Process nssm -ArgumentList "remove ""CaaS-Backend-HTTPS"" confirm" -Wait -WindowStyle Hidden
Start-Sleep 2

& $NSSM install "CaaS-Backend-HTTPS" $UVICORN
& $NSSM set "CaaS-Backend-HTTPS" AppParameters "main:app --host 0.0.0.0 --port 8443 --ssl-keyfile ""$CERT_DIR\caas.key"" --ssl-certfile ""$CERT_DIR\caas.crt"""
& $NSSM set "CaaS-Backend-HTTPS" AppDirectory  $BACKEND_DIR
& $NSSM set "CaaS-Backend-HTTPS" DisplayName   "CaaS Backend HTTPS"
& $NSSM set "CaaS-Backend-HTTPS" Start         SERVICE_AUTO_START
& $NSSM set "CaaS-Backend-HTTPS" AppStdout     "$BACKEND_DIR\logs\backend_https.log"
& $NSSM set "CaaS-Backend-HTTPS" AppStderr     "$BACKEND_DIR\logs\backend_https_err.log"
& $NSSM start "CaaS-Backend-HTTPS"
Start-Sleep 3
Write-Host "Backend HTTPS status:" -ForegroundColor Cyan
& $NSSM status "CaaS-Backend-HTTPS"

# ── Write Node.js HTTPS server via Python (avoids all PS escaping issues) ─────
Write-Host "Writing https_server.js..." -ForegroundColor Cyan
$pyWrite = "$CERT_DIR\write_node.py"
$pyCode = @"
import os
lines = [
    "const https = require('https');",
    "const http  = require('http');",
    "const fs    = require('fs');",
    "const path  = require('path');",
    "",
    "const KEY  = fs.readFileSync('" + r"$CERT_DIR\caas.key".replace("\\","\\\\") + "');",
    "const CERT = fs.readFileSync('" + r"$CERT_DIR\caas.crt".replace("\\","\\\\") + "');",
    "const DIST = path.join(__dirname, 'dist');",
    "",
    "const MIME = {",
    "  '.html':'text/html','.js':'application/javascript','.css':'text/css',",
    "  '.json':'application/json','.png':'image/png','.ico':'image/x-icon',",
    "  '.svg':'image/svg+xml','.woff2':'font/woff2'",
    "};",
    "",
    "function serve(req,res){",
    "  var fp=path.join(DIST,req.url==='/'?'index.html':req.url);",
    "  try{ if(!fs.existsSync(fp)||fs.statSync(fp).isDirectory()) fp=path.join(DIST,'index.html'); }",
    "  catch(e){ fp=path.join(DIST,'index.html'); }",
    "  res.writeHead(200,{'Content-Type':MIME[path.extname(fp)]||'text/plain'});",
    "  fs.createReadStream(fp).pipe(res);",
    "}",
    "",
    "https.createServer({key:KEY,cert:CERT},serve).listen(443,'0.0.0.0',function(){",
    "  console.log('CaaS HTTPS: https://$SERVER_IP');",
    "});",
    "",
    "http.createServer(function(req,res){",
    "  res.writeHead(301,{Location:'https://$SERVER_IP'+req.url});",
    "  res.end();",
    "}).listen(80,'0.0.0.0',function(){",
    "  console.log('HTTP->HTTPS redirect on port 80');",
    "});",
]
out = r"$FRONTEND_DIR\https_server.js"
with open(out,'w') as f:
    f.write('\n'.join(lines))
print("Written:", out)
"@
[System.IO.File]::WriteAllText($pyWrite, $pyCode, [System.Text.Encoding]::UTF8)
& "$BACKEND_DIR\venv\Scripts\python.exe" $pyWrite
Remove-Item $pyWrite -ErrorAction SilentlyContinue

# ── Frontend HTTPS on 443 ─────────────────────────────────────────────────────
Write-Host "Setting up CaaS-Frontend-HTTPS..." -ForegroundColor Cyan
Start-Process nssm -ArgumentList "stop ""CaaS-Frontend-HTTPS"""    -Wait -WindowStyle Hidden
Start-Sleep 1
Start-Process nssm -ArgumentList "remove ""CaaS-Frontend-HTTPS"" confirm" -Wait -WindowStyle Hidden
Start-Sleep 2

$NODE_EXE = (Get-Command node -ErrorAction SilentlyContinue)
if ($NODE_EXE) { $NODE_EXE = $NODE_EXE.Source } else { $NODE_EXE = "node" }

& $NSSM install "CaaS-Frontend-HTTPS" $NODE_EXE
& $NSSM set "CaaS-Frontend-HTTPS" AppParameters "https_server.js"
& $NSSM set "CaaS-Frontend-HTTPS" AppDirectory  $FRONTEND_DIR
& $NSSM set "CaaS-Frontend-HTTPS" DisplayName   "CaaS Frontend HTTPS"
& $NSSM set "CaaS-Frontend-HTTPS" Start         SERVICE_AUTO_START
& $NSSM start "CaaS-Frontend-HTTPS"
Start-Sleep 3
Write-Host "Frontend HTTPS status:" -ForegroundColor Cyan
& $NSSM status "CaaS-Frontend-HTTPS"

# ── Firewall ──────────────────────────────────────────────────────────────────
Write-Host "Adding firewall rules..." -ForegroundColor Cyan
netsh advfirewall firewall delete rule name="CaaS HTTPS Backend"  | Out-Null
netsh advfirewall firewall delete rule name="CaaS HTTPS Frontend" | Out-Null
netsh advfirewall firewall delete rule name="CaaS HTTP Redirect"  | Out-Null
netsh advfirewall firewall add rule name="CaaS HTTPS Backend"  dir=in action=allow protocol=TCP localport=8443 | Out-Null
netsh advfirewall firewall add rule name="CaaS HTTPS Frontend" dir=in action=allow protocol=TCP localport=443  | Out-Null
netsh advfirewall firewall add rule name="CaaS HTTP Redirect"  dir=in action=allow protocol=TCP localport=80   | Out-Null

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  HTTP  (unchanged): http://${SERVER_IP}:3000"
Write-Host "  HTTPS (new):       https://${SERVER_IP}"
Write-Host ""
Write-Host "  First visit: click Advanced -> Proceed (self-signed cert)" -ForegroundColor Yellow
Write-Host "  To remove warning: run install_cert_trust.ps1 as Admin" -ForegroundColor Yellow
