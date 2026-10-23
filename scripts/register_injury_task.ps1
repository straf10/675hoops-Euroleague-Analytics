# Register the recorder's Task Scheduler jobs for the clone's scripts/record_injuries.ps1 (all UTC,
# fixed and DST-independent):
#   675hoops-injury-recorder: 07:30 and 11:00 daily, so the snapshot lands before daily CI at 07:47.
#   675hoops match-day injuries: -MatchDay every 30 minutes from 10:00 to 21:00. The script decides
#     itself whether to record (120 to 60 minutes before today's first EuroLeague tip-off); other
#     polls exit at once.
# Re-running this script is idempotent: both tasks are replaced (Register-ScheduledTask -Force).
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

# Match-day task: -MatchDay every 30 minutes, 10:00 to 21:00 UTC (11 h repetition from 10:00).
$MatchAction = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`" -RepoRoot `"$RepoRoot`" -MatchDay"

function New-UtcMatchDayTrigger([string]$Start) {
    $t = New-UtcDailyTrigger $Start
    $t.Repetition = (New-ScheduledTaskTrigger -Once -At $Start `
        -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Hours 11)).Repetition
    return $t
}

Register-ScheduledTask `
    -TaskName "675hoops match-day injuries" `
    -Action $MatchAction `
    -Trigger (New-UtcMatchDayTrigger "10:00") `
    -Settings $Settings `
    -Principal $Principal `
    -Force | Out-Null

Write-Host "Registered task 675hoops match-day injuries (-MatchDay every 30 min, 10:00 to 21:00 UTC)."
