# CaaS — Fix HTTPS Frontend service
$ErrorActionPreference = "Continue"
$FRONTEND_DIR = "C:\caas-dashboard\frontend"
$NSSM = "nssm"

Write-Host "=== Diagnosing CaaS-Frontend-HTTPS ===" -ForegroundColor Cyan

# Check what is using port 443 and 80
Write-Host "`nProcesses on port 443:" -ForegroundColor Yellow
netstat -ano | findstr ":443 "

Write-Host "`nProcesses on port 80:" -ForegroundColor Yellow
netstat -ano | findstr ":80 "

# Check NSSM logs
Write-Host "`nNSSM service details:" -ForegroundColor Yellow
& $NSSM status "CaaS-Frontend-HTTPS"

# Try resume first
Write-Host "`nAttempting resume..." -ForegroundColor Cyan
& $NSSM rotate "CaaS-Frontend-HTTPS"
Start-Sleep 2
& $NSSM status "CaaS-Frontend-HTTPS"

# If still paused, restart
Write-Host "`nRestarting service..." -ForegroundColor Cyan
& $NSSM restart "CaaS-Frontend-HTTPS"
Start-Sleep 4
$status = (& $NSSM status "CaaS-Frontend-HTTPS")
Write-Host "Status: $status"

if ($status -eq "SERVICE_RUNNING") {
    Write-Host "`nSERVICE RUNNING - Test: https://172.17.70.100" -ForegroundColor Green
} else {
    Write-Host "`nStill not running. Checking if port 443 is blocked..." -ForegroundColor Yellow
    
    # Find what PID owns port 443
    $portLine = netstat -ano | findstr ":443 " | Select-Object -First 1
    Write-Host "Port 443 used by: $portLine"
    
    if ($portLine) {
        $pid443 = ($portLine -split '\s+')[-1]
        Write-Host "PID: $pid443"
        Get-Process -Id $pid443 -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Description
        
        Write-Host "`nOptions:" -ForegroundColor Yellow
        Write-Host "  1. Kill the conflicting process: Stop-Process -Id $pid443 -Force"
        Write-Host "  2. OR use port 8443 for frontend too (no conflict)"
        Write-Host ""
        Write-Host "Run this to switch frontend to port 8444 instead of 443:" -ForegroundColor Cyan
        Write-Host "  C:\caas-dashboard\setup_https_port8444.ps1"
    }
    
    # Generate port-8444 fallback script
    $fallback = @'
# Switch CaaS-Frontend-HTTPS to port 8444 (avoids port 443 conflict)
$FRONTEND_DIR = "C:\caas-dashboard\frontend"
$CERT_DIR     = "C:\caas-dashboard\certs"
$NSSM         = "nssm"
$SERVER_IP    = "172.17.70.100"
$NODE_EXE     = (Get-Command node).Source

# Patch https_server.js to use port 8444 instead of 443 and 8080 instead of 80
$js = Get-Content "$FRONTEND_DIR\https_server.js" -Raw
$js = $js -replace "\.listen\(443,",  ".listen(8444,"
$js = $js -replace "\.listen\(80,",   ".listen(8080,"
$js = $js -replace "https://$SERVER_IP", "https://${SERVER_IP}:8444"
$js = $js -replace "https://$SERVER_IP", "https://${SERVER_IP}:8444"
[System.IO.File]::WriteAllText("$FRONTEND_DIR\https_server.js", $js, [System.Text.Encoding]::UTF8)

& $NSSM restart "CaaS-Frontend-HTTPS"
Start-Sleep 4
& $NSSM status  "CaaS-Frontend-HTTPS"

netsh advfirewall firewall add rule name="CaaS HTTPS Frontend 8444" dir=in action=allow protocol=TCP localport=8444 | Out-Null
netsh advfirewall firewall add rule name="CaaS HTTP  Redirect  8080" dir=in action=allow protocol=TCP localport=8080 | Out-Null

Write-Host ""
Write-Host "HTTPS now on: https://${SERVER_IP}:8444" -ForegroundColor Green
Write-Host "HTTP redirect: http://${SERVER_IP}:8080 -> https://${SERVER_IP}:8444"
'@
    [System.IO.File]::WriteAllText("C:\caas-dashboard\setup_https_port8444.ps1", $fallback, [System.Text.Encoding]::UTF8)
    Write-Host "`nFallback script written: C:\caas-dashboard\setup_https_port8444.ps1" -ForegroundColor Cyan
}
