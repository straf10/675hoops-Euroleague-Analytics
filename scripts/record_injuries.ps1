# Record the BasketNews injury report from a dedicated clone and push when the log changes.
# Run via Task Scheduler (see register_injury_task.ps1). Use -WhatIf to print steps only.
param(
    [string]$RepoRoot = "C:\Python\675hoops-recorder",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$AttemptLog = Join-Path $env:LOCALAPPDATA "675hoops\injury_attempts.log"
$Mart = Join-Path $RepoRoot "data\marts\eurohoops.duckdb"
$UtcNow = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")

function Write-Attempt([string]$Status, [int]$Rows, [string]$Sha) {
    $line = "$UtcNow`t$Status`t$Rows`t$Sha"
    if ($WhatIf) {
        Write-Host "[WhatIf] append attempt log: $line"
        return
    }
    $dir = Split-Path $AttemptLog -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    Add-Content -Path $AttemptLog -Value $line -Encoding utf8
}

function Invoke-Step([string]$Label, [scriptblock]$Action) {
    if ($WhatIf) {
        Write-Host "[WhatIf] $Label"
        return
    }
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit $LASTEXITCODE)" }
}

if (-not (Test-Path $RepoRoot)) {
    throw "Repo root not found: $RepoRoot (clone main here first)"
}

Push-Location $RepoRoot
try {
    Invoke-Step "git pull --ff-only" { git pull --ff-only origin main }

    $martStale = -not (Test-Path $Mart) -or (
        (Get-Item $Mart).LastWriteTimeUtc -lt [DateTime]::UtcNow.AddDays(-7)
    )
    if ($martStale) {
        Invoke-Step "ingest --current-only" { uv run --no-dev eurohoops ingest --current-only }
        Invoke-Step "build" { uv run --no-dev eurohoops build }
    }

    if ($WhatIf) {
        Write-Host "[WhatIf] uv run --no-dev eurohoops injuries"
        Write-Attempt "whatif" 0 ""
        exit 0
    }

    $out = uv run --no-dev eurohoops injuries 2>&1 | Out-String
    Write-Host $out.TrimEnd()
    $rows = 0
    if ($out -match "(\d+) rows") { $rows = [int]$Matches[1] }

    if ($out -match "injuries: appended") {
        git add injuries/
        $stamp = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mmZ")
        git commit -m "Injury snapshot $stamp"
        $pushed = $false
        foreach ($attempt in 1..2) {
            git push origin HEAD:main
            if ($LASTEXITCODE -eq 0) { $pushed = $true; break }
            if ($attempt -eq 1) {
                if (-not (git pull --rebase origin main)) {
                    git rebase --abort 2>$null
                    Write-Attempt "push_conflict" $rows ""
                    throw "push failed after rebase conflict; merge by hand"
                }
            }
        }
        if (-not $pushed) {
            Write-Attempt "push_failed" $rows ""
            throw "git push failed"
        }
        $sha = (git rev-parse --short HEAD).Trim()
        Write-Attempt "appended" $rows $sha
        exit 0
    }

    if ($out -match "injuries: unchanged") {
        Write-Attempt "unchanged" $rows ""
        exit 0
    }

    Write-Attempt "failed" 0 ""
    exit 1
}
finally {
    Pop-Location
}
