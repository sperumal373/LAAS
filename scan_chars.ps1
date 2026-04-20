$lines = Get-Content "C:\caas-dashboard\frontend\src\OpenShiftPage.jsx"
$n = 1
foreach ($line in $lines) {
    if ($line -match '\?\?|ï¿½|â€|Ã|Adding…|Adding\?') {
        Write-Host "${n}: $($line.Trim())"
    }
    $n++
}
Write-Host "---SCAN DONE---"
