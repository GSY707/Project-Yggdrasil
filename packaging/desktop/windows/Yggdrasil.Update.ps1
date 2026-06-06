param(
    [ValidateSet("check", "apply", "install-task", "uninstall-task")]
    [string]$Action = "check",
    [string]$Ref = "",
    [switch]$AutoApply
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopScript = Join-Path $ScriptRoot "Yggdrasil.Desktop.ps1"
$StatePath = Join-Path $ScriptRoot "update-state.json"
$TaskName = "Project Yggdrasil Desktop Update Check"

function Resolve-RepoRoot {
    if ($env:YGGDRASIL_REPO_ROOT -and (Test-Path $env:YGGDRASIL_REPO_ROOT)) {
        return (Resolve-Path $env:YGGDRASIL_REPO_ROOT)
    }
    $InstallManifest = Join-Path $ScriptRoot "install.json"
    if (Test-Path $InstallManifest) {
        $Manifest = Get-Content -Raw -Path $InstallManifest | ConvertFrom-Json
        if ($Manifest.repoRoot -and (Test-Path $Manifest.repoRoot)) {
            return (Resolve-Path $Manifest.repoRoot)
        }
    }
    return (Resolve-Path (Join-Path $ScriptRoot "..\..\.."))
}

function Invoke-Git {
    param([string[]]$Arguments)
    Push-Location $RepoRoot
    try {
        $PreviousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $Output = & git @Arguments 2>&1
        }
        finally {
            $ErrorActionPreference = $PreviousErrorActionPreference
        }
        if ($LASTEXITCODE -ne 0) {
            throw "git $($Arguments -join ' ') failed: $Output"
        }
        return ($Output | Out-String).Trim()
    }
    finally {
        Pop-Location
    }
}

function Write-UpdateState {
    param([hashtable]$State)
    $State.checkedAt = (Get-Date).ToUniversalTime().ToString("o")
    $State | ConvertTo-Json -Depth 6 | Set-Content -Path $StatePath -Encoding UTF8
}

function Get-UpdateStatus {
    Invoke-Git -Arguments @("rev-parse", "--is-inside-work-tree") | Out-Null
    $CurrentBranch = Invoke-Git -Arguments @("rev-parse", "--abbrev-ref", "HEAD")
    $CurrentHead = Invoke-Git -Arguments @("rev-parse", "HEAD")
    $TargetRef = $Ref
    if ([string]::IsNullOrWhiteSpace($TargetRef)) {
        try {
            $TargetRef = Invoke-Git -Arguments @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
        }
        catch {
            $TargetRef = "origin/$CurrentBranch"
        }
    }
    Invoke-Git -Arguments @("fetch", "--prune") | Out-Null
    $RemoteHead = Invoke-Git -Arguments @("rev-parse", $TargetRef)
    $Base = Invoke-Git -Arguments @("merge-base", $CurrentHead, $RemoteHead)
    $State = "diverged"
    if ($CurrentHead -eq $RemoteHead) {
        $State = "current"
    }
    elseif ($Base -eq $CurrentHead) {
        $State = "update-available"
    }
    elseif ($Base -eq $RemoteHead) {
        $State = "local-ahead"
    }
    return @{
        status = $State
        branch = $CurrentBranch
        targetRef = $TargetRef
        currentHead = $CurrentHead
        remoteHead = $RemoteHead
    }
}

function Invoke-ProductCommand {
    param([string[]]$Command)
    Push-Location $RepoRoot
    try {
        & $Command[0] @($Command | Select-Object -Skip 1)
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $($Command -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

$RepoRoot = Resolve-RepoRoot

switch ($Action) {
    "check" {
        $Status = Get-UpdateStatus
        Write-UpdateState -State $Status
        $Status | ConvertTo-Json -Depth 6
    }
    "apply" {
        $Status = Get-UpdateStatus
        if ($Status.status -eq "current") {
            Write-UpdateState -State $Status
            $Status | ConvertTo-Json -Depth 6
            return
        }
        if ($Status.status -ne "update-available") {
            Write-UpdateState -State $Status
            throw "Refusing to auto-update because repository status is $($Status.status). Resolve local or divergent commits manually."
        }
        Invoke-ProductCommand -Command @("corepack", "pnpm", "product:backup")
        Invoke-Git -Arguments @("merge", "--ff-only", $Status.remoteHead) | Out-Null
        Invoke-ProductCommand -Command @("corepack", "pnpm", "install")
        Invoke-ProductCommand -Command @("corepack", "pnpm", "product:upgrade")
        $Applied = Get-UpdateStatus
        $Applied.applied = $true
        Write-UpdateState -State $Applied
        $Applied | ConvertTo-Json -Depth 6
    }
    "install-task" {
        $TaskAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptRoot\Yggdrasil.Update.ps1`" check"
        $Triggers = @(
            (New-ScheduledTaskTrigger -AtLogOn),
            (New-ScheduledTaskTrigger -Daily -At 9am)
        )
        Register-ScheduledTask -TaskName $TaskName -Action $TaskAction -Trigger $Triggers -Description "Checks Project Yggdrasil desktop updates and writes update-state.json." -Force | Out-Null
        Write-Host "Installed scheduled update check task: $TaskName"
    }
    "uninstall-task" {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "Removed scheduled update check task: $TaskName"
    }
}
