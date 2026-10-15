# Register a twice-daily Task Scheduler job for the recorder clone's scripts/record_injuries.ps1.
# Runs at 07:30 and 11:00 UTC (fixed, DST-independent) so the snapshot lands before daily CI at 08:00 UTC.
param(
    [string]$RepoRoot = "C:\Python\675hoops-recorder"
)

$Script = Join-Path $RepoRoot "scripts\record_injuries.ps1"
if (-not (Test-Path $Script)) {
    throw "Missing $Script. Clone the recorder first (see one-time setup below)."
}

Write-Host @"
One-time setup (if the recorder clone does not exist yet):
  git clone https://github.com/straf10/675hoops-Euroleague-Analytics.git $RepoRoot
  cd $RepoRoot
  uv sync
"@

$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`" -RepoRoot `"$RepoRoot`""

# Daily trigger pinned to a UTC wall time via a Z-suffixed StartBoundary.
function New-UtcDailyTrigger([string]$Time) {
    $t = New-ScheduledTaskTrigger -Daily -At $Time
    $t.StartBoundary = "2026-01-01T$($Time):00Z"
    return $t
}

$Triggers = @(
    (New-UtcDailyTrigger "07:30"),
    (New-UtcDailyTrigger "11:00")
)

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask `
    -TaskName "675hoops-injury-recorder" `
    -Action $Action `
    -Trigger $Triggers `
    -Settings $Settings `
    -Principal $Principal `
    -Force | Out-Null

Write-Host "Registered task 675hoops-injury-recorder (07:30 and 11:00 UTC, StartWhenAvailable)."
