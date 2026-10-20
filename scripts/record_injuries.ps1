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
$logged = $false
$rows = 0
$stage = "recover"
$refreshTag = ""

function Write-Attempt([string]$Status, [int]$Rows, [string]$Sha) {
    $script:logged = $true
    $line = "$UtcNow`t$Status$script:refreshTag`t$Rows`t$Sha"
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
    Write-Attempt "no_repo" 0 ""
    throw "Repo root not found: $RepoRoot (clone main here first)"
}

Push-Location $RepoRoot
try {
    # Recover an injury commit left unpushed by an earlier failed run, so pull --ff-only can work again.
    if ($WhatIf) {
        Write-Host "[WhatIf] git fetch origin main"
        Write-Host "[WhatIf] if local commits ahead of origin/main: git pull --rebase origin main; git push origin HEAD:main"
    } else {
        git fetch origin main
        if ($LASTEXITCODE -ne 0) { throw "git fetch failed (exit $LASTEXITCODE)" }
        $revOut = git rev-list --count origin/main..HEAD
        if ($LASTEXITCODE -ne 0) { throw "git rev-list failed (exit $LASTEXITCODE)" }
        $ahead = [int]("$revOut".Trim())
        if ($ahead -gt 0) {
            Write-Host "Recovering $ahead unpushed local commit(s)"
            git pull --rebase origin main
            if ($LASTEXITCODE -ne 0) {
                $pullExit = $LASTEXITCODE
                # Abort succeeds only if a rebase is in progress (a conflict); else the pull itself failed.
                git rebase --abort
                if ($LASTEXITCODE -eq 0) {
                    Write-Attempt "stuck" $rows ""
                    throw "local commits conflict with origin; resolve by hand in $RepoRoot"
                }
                throw "git pull --rebase failed (exit $pullExit)"
            }
            git push origin HEAD:main
            if ($LASTEXITCODE -ne 0) { throw "recovery push failed (exit $LASTEXITCODE)" }
        }
    }

    $stage = "pull"
    Invoke-Step "git pull --ff-only" { git pull --ff-only origin main }

    $martStale = -not (Test-Path $Mart) -or (
        (Get-Item $Mart).LastWriteTimeUtc -lt [DateTime]::UtcNow.AddDays(-7)
    )
    if ($martStale) {
        # A failed refresh is not fatal when a mart exists: record the injuries from the old one.
        try {
            $stage = "ingest"
            Invoke-Step "ingest --current-only" { uv run --no-dev eurohoops ingest --current-only }
            $stage = "build"
            Invoke-Step "build" { uv run --no-dev eurohoops build }
        }
        catch {
            if (-not (Test-Path $Mart)) { throw }
            Write-Warning "stale-mart refresh failed at ${stage}: $($_.Exception.Message); using the existing mart"
            $refreshTag = "+refresh_$($stage)_failed"
        }
    }

    if ($WhatIf) {
        Write-Host "[WhatIf] uv run --no-dev eurohoops injuries"
        Write-Attempt "whatif" 0 ""
        exit 0
    }

    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = (uv run --no-dev eurohoops injuries 2>&1 | ForEach-Object { "$_" }) -join "`n"
    $ErrorActionPreference = $prev
    Write-Host $out.TrimEnd()
    if ($out -match "(\d+) rows") { $rows = [int]$Matches[1] }

    if ($out -match "injuries: appended") {
        $stage = "commit"
        git add injuries/
        $stamp = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mmZ")
        git commit -m "Injury snapshot $stamp"
        $stage = "push"
        $pushed = $false
        foreach ($attempt in 1..2) {
            git push origin HEAD:main
            if ($LASTEXITCODE -eq 0) { $pushed = $true; break }
            if ($attempt -eq 1) {
                git pull --rebase origin main
                if ($LASTEXITCODE -ne 0) {
                    git rebase --abort
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
catch {
    # Log stages that threw before their own Write-Attempt; rethrow so Task Scheduler sees the failure.
    if (-not $logged) {
        $status = "error"
        if ($stage -in @("recover", "pull", "ingest", "build")) { $status = "$($stage)_failed" }
        Write-Attempt $status $rows ""
    }
    throw
}
finally {
    Pop-Location
}
