$bak = [System.IO.File]::ReadAllText('C:\caas-dashboard\frontend\src\OpenShiftPage.jsx.bak')
$cur = [System.IO.File]::ReadAllText('C:\caas-dashboard\frontend\src\OpenShiftPage.jsx')

$wizStart = $bak.IndexOf('{showVMReq&&(')
$showAddInBak = $bak.IndexOf('      {showAdd&&(')

Write-Host "Bak length: $($bak.Length)"
Write-Host "Wizard start in bak: $wizStart"
Write-Host "showAdd in bak: $showAddInBak"

if ($wizStart -lt 0 -or $showAddInBak -lt 0) {
    Write-Host "ERROR: Could not find markers in bak file"
    exit 1
}

# Extract wizard block from bak (from {showVMReq&&( to just before {showAdd&&()
$wizardBlock = $bak.Substring($wizStart, $showAddInBak - $wizStart)
Write-Host "Wizard block length: $($wizardBlock.Length)"
Write-Host "Wizard first 80 chars: $($wizardBlock.Substring(0,[Math]::Min(80,$wizardBlock.Length)))"
Write-Host "Wizard last 80 chars: $($wizardBlock.Substring([Math]::Max(0,$wizardBlock.Length-80)))"

# Find placeholder in current file and replace it
$placeholder = '      {/* -- VM Request Wizard -- */}'+"`n"+'      {false&&(<div/>)}'

$curIdx = $cur.IndexOf('{/* -- VM Request Wizard -- */}')
Write-Host "Placeholder in cur at: $curIdx"

if ($curIdx -lt 0) {
    Write-Host "ERROR: Could not find placeholder comment in current file"
    exit 1
}

# Find the start of the comment line (go back to find whitespace/newline)
$lineStart = $cur.LastIndexOf("`n", $curIdx) + 1

# Find end of placeholder block - up to the next {showAdd&&(
$showAddInCur = $cur.IndexOf('      {showAdd&&(')
Write-Host "showAdd in cur at: $showAddInCur"

if ($showAddInCur -lt 0) {
    Write-Host "ERROR: Could not find showAdd in current file"
    exit 1
}

# Build new file content
$before = $cur.Substring(0, $lineStart)
$after = $cur.Substring($showAddInCur)
$newContent = $before + '      ' + $wizardBlock + "`n`n      " + $after.TrimStart()

Write-Host "New file length: $($newContent.Length)"

[System.IO.File]::WriteAllText('C:\caas-dashboard\frontend\src\OpenShiftPage.jsx', $newContent, [System.Text.Encoding]::UTF8)
Write-Host "DONE - wizard restored to OpenShiftPage.jsx"
