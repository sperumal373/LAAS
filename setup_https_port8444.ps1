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