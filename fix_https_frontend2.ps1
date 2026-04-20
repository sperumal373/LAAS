# CaaS — Fix HTTPS Frontend v3 — no here-strings, no brace issues
$ErrorActionPreference = "Continue"
$FRONTEND_DIR = "C:\caas-dashboard\frontend"
$CERT_DIR     = "C:\caas-dashboard\certs"
$SERVER_IP    = "172.17.70.100"
$NSSM         = "nssm"
$NODE_EXE     = (Get-Command node).Source

Write-Host "=== Fix CaaS-Frontend-HTTPS ===" -ForegroundColor Cyan

# Write https_server.js using Python — avoids ALL PowerShell string/brace issues
$pyPath = "$CERT_DIR\write_server.py"
$keyFwd = $CERT_DIR.Replace("\","/") + "/caas.key"
$crtFwd = $CERT_DIR.Replace("\","/") + "/caas.crt"

$pyLines = [System.Collections.Generic.List[string]]::new()
$pyLines.Add("lines = [")
$pyLines.Add("  `"const https = require('https');`",")
$pyLines.Add("  `"const http  = require('http');`",")
$pyLines.Add("  `"const fs    = require('fs');`",")
$pyLines.Add("  `"const path  = require('path');`",")
$pyLines.Add("  `"`",")
$pyLines.Add("  `"const KEY  = fs.readFileSync('$keyFwd');`",")
$pyLines.Add("  `"const CERT = fs.readFileSync('$crtFwd');`",")
$pyLines.Add("  `"const DIST = path.join(__dirname, 'dist');`",")
$pyLines.Add("  `"`",")
$pyLines.Add("  `"const MIME = {'.html':'text/html','.js':'application/javascript','.css':'text/css','.json':'application/json','.png':'image/png','.ico':'image/x-icon','.svg':'image/svg+xml','.woff2':'font/woff2'};`",")
$pyLines.Add("  `"`",")
$pyLines.Add("  `"function serve(req,res){`",")
$pyLines.Add("  `"  var fp=path.join(DIST,req.url==='/'?'index.html':req.url);`",")
$pyLines.Add("  `"  try{ if(!fs.existsSync(fp)||fs.statSync(fp).isDirectory()) fp=path.join(DIST,'index.html'); } catch(e){ fp=path.join(DIST,'index.html'); }`",")
$pyLines.Add("  `"  res.writeHead(200,{'Content-Type':MIME[path.extname(fp)]||'text/plain'});`",")
$pyLines.Add("  `"  fs.createReadStream(fp).pipe(res);`",")
$pyLines.Add("  `"}`",")
$pyLines.Add("  `"`",")
$pyLines.Add("  `"https.createServer({key:KEY,cert:CERT},serve).listen(443,'0.0.0.0',function(){ console.log('CaaS HTTPS: https://$SERVER_IP'); });`",")
$pyLines.Add("  `"`",")
$pyLines.Add("  `"http.createServer(function(req,res){ res.writeHead(301,{Location:'https://$SERVER_IP'+req.url}); res.end(); }).listen(80,'0.0.0.0',function(){ console.log('HTTP redirect port 80'); });`",")
$pyLines.Add("]")
$pyLines.Add("import sys")
$pyLines.Add("out = r'$FRONTEND_DIR\https_server.js'")
$pyLines.Add("open(out,'w').write('\n'.join(lines))")
$pyLines.Add("print('Written:', out)")

[System.IO.File]::WriteAllLines($pyPath, $pyLines, [System.Text.Encoding]::UTF8)
& "C:\caas-dashboard\backend\venv\Scripts\python.exe" $pyPath
Remove-Item $pyPath -ErrorAction SilentlyContinue

# Test Node directly — capture output
Write-Host "`nTesting Node server directly..." -ForegroundColor Cyan
$outFile = "$CERT_DIR\node_test_out.txt"
$errFile = "$CERT_DIR\node_test_err.txt"
"" | Out-File $outFile
"" | Out-File $errFile
$job = Start-Process $NODE_EXE -ArgumentList "$FRONTEND_DIR\https_server.js" -PassThru -WindowStyle Hidden -RedirectStandardOutput $outFile -RedirectStandardError $errFile
Start-Sleep 4
$job | Stop-Process -ErrorAction SilentlyContinue
Start-Sleep 1

$errText = (Get-Content $errFile -Raw).Trim()
$outText = (Get-Content $outFile -Raw).Trim()
if ($outText) { Write-Host "Node output: $outText" -ForegroundColor Green }
if ($errText) { Write-Host "Node error:  $errText" -ForegroundColor Red }

# Restart service
Write-Host "`nRestarting CaaS-Frontend-HTTPS..." -ForegroundColor Cyan
& $NSSM stop  "CaaS-Frontend-HTTPS"
Start-Sleep 3
& $NSSM start "CaaS-Frontend-HTTPS"
Start-Sleep 4
$status = (& $NSSM status "CaaS-Frontend-HTTPS")
Write-Host "Status: $status"

if ($status -eq "SERVICE_RUNNING") {
    Write-Host "`nSUCCESS - https://$SERVER_IP is live!" -ForegroundColor Green
    exit 0
}

# If still failing — switch to port 8444
Write-Host "`nSwitching to port 8444..." -ForegroundColor Yellow
$jsFile = "$FRONTEND_DIR\https_server.js"
$js = Get-Content $jsFile -Raw
$js = $js.Replace(".listen(443,", ".listen(8444,")
$js = $js.Replace(".listen(80,",  ".listen(8080,")
$js = $js.Replace("https://$SERVER_IP'", "https://${SERVER_IP}:8444'")
[System.IO.File]::WriteAllText($jsFile, $js, [System.Text.Encoding]::UTF8)

& $NSSM stop  "CaaS-Frontend-HTTPS"
Start-Sleep 2
& $NSSM start "CaaS-Frontend-HTTPS"
Start-Sleep 4
$status2 = (& $NSSM status "CaaS-Frontend-HTTPS")
Write-Host "Status on 8444: $status2"

if ($status2 -eq "SERVICE_RUNNING") {
    netsh advfirewall firewall add rule name="CaaS HTTPS 8444" dir=in action=allow protocol=TCP localport=8444 | Out-Null
    netsh advfirewall firewall add rule name="CaaS HTTP  8080" dir=in action=allow protocol=TCP localport=8080 | Out-Null
    Write-Host "`nSUCCESS on port 8444!" -ForegroundColor Green
    Write-Host "Dashboard HTTPS: https://${SERVER_IP}:8444" -ForegroundColor Green
if ($status2 -ne "SERVICE_RUNNING") {
    Write-Host "`nNode error shown above. Run manually to debug:" -ForegroundColor Red
    Write-Host "  node C:\caas-dashboard\frontend\https_server.js"
}
