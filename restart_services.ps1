Restart-Service "CaaS-Frontend" -Force -ErrorAction SilentlyContinue
Restart-Service "CaaS-Frontend-HTTPS" -Force -ErrorAction SilentlyContinue
Restart-Service "CaaS-Backend" -Force -ErrorAction SilentlyContinue
Restart-Service "CaaS-Backend-HTTPS" -Force -ErrorAction SilentlyContinue
Start-Sleep 3
Get-Service | Where-Object { $_.Name -like "CaaS*" } | Select-Object Name, Status
