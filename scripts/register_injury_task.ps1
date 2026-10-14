# Register a twice-daily Task Scheduler job for scripts/record_injuries.ps1.
param(
    [string]$RepoRoot = "C:\Python\675hoops-recorder"
)

$Script = Join-Path $PSScriptRoot "record_injuries.ps1"
if (-not (Test-Path $Script)) {
    throw "Missing $Script"
}

Write-Host @"
One-time setup (if the recorder clone does not exist yet):
  git clone https://github.com/straf10/675hoops-Euroleague-Analytics.git $RepoRoot
  cd $RepoRoot
  uv sync
"@

$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`" -RepoRoot `"$RepoRoot`""

$Triggers = @(
    (New-ScheduledTaskTrigger -Daily -At "11:00"),
    (New-ScheduledTaskTrigger -Daily -At "14:00")
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

Write-Host "Registered task 675hoops-injury-recorder (11:00 and 14:00 local, StartWhenAvailable)."
