param(
    [ValidateSet("start", "start-app", "stop", "status", "open", "open-apps", "open-settings", "logs", "backup", "restore", "snapshots", "upgrade", "rollback", "install-shortcuts", "uninstall-shortcuts")]
    [string]$Action = "start",
    [string]$Snapshot = "",
    [string]$OpenPath = "",
    [switch]$ConfirmUpgrade,
    [switch]$ConfirmRollback
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DockerDesktopPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$DesktopShortcutRoot = [Environment]::GetFolderPath("Desktop")
$StartMenuShortcutRoot = Join-Path ([Environment]::GetFolderPath("Programs")) "Project Yggdrasil"
$MaintenanceStatePath = Join-Path $ScriptRoot "maintenance-state.json"

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

$RepoRoot = Resolve-RepoRoot

function Invoke-RepoCommand {
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

function Write-MaintenanceState {
    param([hashtable]$State)
    $State.checkedAt = (Get-Date).ToUniversalTime().ToString("o")
    $State | ConvertTo-Json -Depth 8 | Set-Content -Path $MaintenanceStatePath -Encoding UTF8
}

function Request-DesktopConfirmation {
    param(
        [string]$Prompt,
        [string]$Expected
    )
    if ([Console]::IsInputRedirected) {
        throw "Confirmation required. Re-run this action in a visible terminal and type '$Expected'."
    }
    $Answer = Read-Host $Prompt
    if ($Answer -ne $Expected) {
        throw "Action cancelled. Expected confirmation text '$Expected'."
    }
}

function Get-GitVersionSummary {
    Push-Location $RepoRoot
    try {
        $Head = (& git rev-parse --short=12 HEAD 2>$null)
        $Branch = (& git rev-parse --abbrev-ref HEAD 2>$null)
        return @{
            branch = ($Branch | Out-String).Trim()
            version = ($Head | Out-String).Trim()
        }
    }
    finally {
        Pop-Location
    }
}

function Get-BackupSnapshotSummary {
    $BackupRoot = Join-Path $RepoRoot ".yggdrasil-backups"
    if (-not (Test-Path $BackupRoot)) {
        return @{
            backupRoot = $BackupRoot
            latestSnapshot = $null
            availableSnapshots = @()
        }
    }
    $Snapshots = @(Get-ChildItem -LiteralPath $BackupRoot -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 10)
    $LatestSnapshot = $null
    if ($Snapshots.Count -gt 0) {
        $LatestSnapshot = $Snapshots[0].FullName
    }
    return @{
        backupRoot = $BackupRoot
        latestSnapshot = $LatestSnapshot
        availableSnapshots = @($Snapshots | ForEach-Object { $_.FullName })
    }
}

function Get-UpgradeImpactPreview {
    $Version = Get-GitVersionSummary
    return @{
        action = "upgrade"
        currentVersion = $Version.version
        branch = $Version.branch
        willCreateBackup = $true
        willRestartLocalProduct = $true
        affectedAreas = @("applications", "tasks", "settings", "local data volumes")
        recovery = @("If upgrade fails, the previous product data backup remains available.", "Use Restore Latest Backup or Restore Previous Version from the tray after checking diagnostics.")
    }
}

function Get-RollbackImpactPreview {
    $Version = Get-GitVersionSummary
    $Backups = Get-BackupSnapshotSummary
    $RequestedSnapshot = $Snapshot
    if ($Snapshot.Trim().Length -eq 0) {
        $RequestedSnapshot = $Backups.latestSnapshot
    }

    return @{
        action = "rollback"
        currentVersion = $Version.version
        branch = $Version.branch
        requestedSnapshot = $RequestedSnapshot
        backupRoot = $Backups.backupRoot
        availableSnapshots = $Backups.availableSnapshots
        willCreateProtectiveBackup = $true
        willRestartLocalProduct = $true
        affectedAreas = @("applications", "tasks", "settings", "local data volumes")
        recovery = @("If rollback fails, the current version is kept running when possible.", "Open Health and Diagnostics, then restore a listed backup if local data needs recovery.")
    }
}

function Get-ProductEnvPath {
    $ProductEnv = Join-Path $RepoRoot "infra\product.env"
    if (Test-Path $ProductEnv) {
        return $ProductEnv
    }
    return Join-Path $RepoRoot "infra\product.env.template"
}

function Get-ProductEnvValue {
    param(
        [string]$Name,
        [string]$Default
    )
    $EnvPath = Get-ProductEnvPath
    if (Test-Path $EnvPath) {
        foreach ($Line in Get-Content -Path $EnvPath) {
            $Trimmed = $Line.Trim()
            if ($Trimmed.Length -eq 0 -or $Trimmed.StartsWith("#")) {
                continue
            }
            $Parts = $Trimmed.Split("=", 2)
            if ($Parts.Length -eq 2 -and $Parts[0].Trim() -eq $Name) {
                $Value = $Parts[1].Trim()
                if ($Value.Length -gt 0) {
                    return $Value
                }
            }
        }
    }
    return $Default
}

function Get-ProductUrl {
    param([string]$Path = "")
    $Port = Get-ProductEnvValue -Name "YGGDRASIL_WEB_PORT" -Default "3000"
    if ($Path.Trim().Length -gt 0 -and -not $Path.StartsWith("/")) {
        $Path = "/$Path"
    }
    return "http://localhost:$Port$Path"
}

function Ensure-Docker {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }
    if (Test-Path $DockerDesktopPath) {
        Start-Process -FilePath $DockerDesktopPath -WindowStyle Hidden
        Write-Host "Local engine is starting. Try this action again after the status icon reports ready."
        exit 2
    }
    throw "Docker is not available and Docker Desktop was not found at $DockerDesktopPath"
}

function New-DesktopShortcut {
    param(
        [string]$Name,
        [string]$TargetPath,
        [string]$Arguments,
        [string]$WorkingDirectory = $RepoRoot
    )
    $Shell = New-Object -ComObject WScript.Shell
    foreach ($Root in @($DesktopShortcutRoot, $StartMenuShortcutRoot)) {
        if (-not (Test-Path $Root)) {
            New-Item -ItemType Directory -Path $Root | Out-Null
        }
        $Shortcut = $Shell.CreateShortcut((Join-Path $Root "$Name.lnk"))
        $Shortcut.TargetPath = $TargetPath
        $Shortcut.Arguments = $Arguments
        $Shortcut.WorkingDirectory = $WorkingDirectory
        $Shortcut.Save()
    }
}

function Remove-DesktopShortcuts {
    foreach ($Root in @($DesktopShortcutRoot, $StartMenuShortcutRoot)) {
        foreach ($Name in @("Yggdrasil Desktop", "Yggdrasil Start", "Yggdrasil Tray", "Yggdrasil Apps", "Yggdrasil Settings", "Yggdrasil Status", "Yggdrasil Logs", "Yggdrasil Diagnostics", "Yggdrasil Backup", "Yggdrasil Restore", "Yggdrasil Snapshots", "Yggdrasil Update", "Yggdrasil Upgrade", "Yggdrasil Rollback", "Yggdrasil Stop")) {
            $Path = Join-Path $Root "$Name.lnk"
            if (Test-Path $Path) {
                Remove-Item -LiteralPath $Path
            }
        }
        foreach ($Shortcut in Get-InstallDistributionShortcuts) {
            if ($Shortcut.name) {
                $Path = Join-Path $Root "$($Shortcut.name).lnk"
                if (Test-Path $Path) {
                    Remove-Item -LiteralPath $Path
                }
            }
        }
    }
}

function Get-InstallDistributionShortcuts {
    $InstallManifest = Join-Path $ScriptRoot "install.json"
    if (-not (Test-Path $InstallManifest)) {
        return @()
    }
    $Manifest = Get-Content -Raw -Path $InstallManifest | ConvertFrom-Json
    if (-not $Manifest.distributionShortcuts) {
        return @()
    }
    return @($Manifest.distributionShortcuts)
}

switch ($Action) {
    "start" {
        Ensure-Docker
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:up")
        Start-Process (Get-ProductUrl -Path $OpenPath)
    }
    "start-app" {
        Ensure-Docker
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:up")
        if ($OpenPath.Trim().Length -eq 0) {
            $OpenPath = "/applications"
        }
        Start-Process (Get-ProductUrl -Path $OpenPath)
    }
    "stop" {
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:down")
    }
    "status" {
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:status")
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:smoke")
    }
    "open" {
        Start-Process (Get-ProductUrl -Path $OpenPath)
    }
    "open-apps" {
        Start-Process (Get-ProductUrl -Path "/applications")
    }
    "open-settings" {
        Start-Process (Get-ProductUrl -Path "/settings")
    }
    "logs" {
        Start-Process powershell -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-NoExit",
            "-Command",
            "Set-Location `"$RepoRoot`"; corepack pnpm product:logs"
        )
    }
    "backup" {
        Ensure-Docker
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:backup")
    }
    "snapshots" {
        Ensure-Docker
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:snapshots")
    }
    "restore" {
        Ensure-Docker
        if ($Snapshot.Trim().Length -eq 0) {
            Invoke-RepoCommand -Command @("corepack", "pnpm", "product:restore")
        }
        else {
            Invoke-RepoCommand -Command @("corepack", "pnpm", "product:restore", "--", "--snapshot", $Snapshot)
        }
    }
    "upgrade" {
        Ensure-Docker
        $Preview = Get-UpgradeImpactPreview
        $State = @{
            status = "upgrade-preview"
            impactPreview = $Preview
        }
        Write-MaintenanceState -State $State
        Write-Host ($State | ConvertTo-Json -Depth 8)
        if (-not $ConfirmUpgrade) {
            Request-DesktopConfirmation -Prompt "Type UPGRADE YGGDRASIL to create a backup and upgrade the local product" -Expected "UPGRADE YGGDRASIL"
        }
        try {
            Invoke-RepoCommand -Command @("corepack", "pnpm", "product:upgrade")
            Write-MaintenanceState -State @{
                status = "upgrade-succeeded"
                impactPreview = $Preview
            }
            Start-Process (Get-ProductUrl)
        }
        catch {
            Write-MaintenanceState -State @{
                status = "upgrade-failed"
                impactPreview = $Preview
                error = $_.Exception.Message
                recoveryActions = @("Open Health and Diagnostics.", "Use Back Up Local Data / View Backups before retrying.", "Run Restore Latest Backup if local data was affected.")
            }
            throw
        }
    }
    "rollback" {
        Ensure-Docker
        $Preview = Get-RollbackImpactPreview
        $State = @{
            status = "rollback-preview"
            impactPreview = $Preview
        }
        Write-MaintenanceState -State $State
        Write-Host ($State | ConvertTo-Json -Depth 8)
        if (-not $ConfirmRollback) {
            Request-DesktopConfirmation -Prompt "Type RESTORE PREVIOUS VERSION to create a protective backup and continue" -Expected "RESTORE PREVIOUS VERSION"
        }
        try {
            if ($Snapshot.Trim().Length -eq 0) {
                Invoke-RepoCommand -Command @("corepack", "pnpm", "product:rollback")
            }
            else {
                Invoke-RepoCommand -Command @("corepack", "pnpm", "product:rollback", "--", "--snapshot", $Snapshot)
            }
            Write-MaintenanceState -State @{
                status = "rollback-succeeded"
                impactPreview = $Preview
            }
            Start-Process (Get-ProductUrl)
        }
        catch {
            Write-MaintenanceState -State @{
                status = "rollback-failed"
                impactPreview = $Preview
                error = $_.Exception.Message
                recoveryActions = @("Open Health and Diagnostics.", "Keep the current version running if it is still available.", "Use View Backups to choose another restore point.")
            }
            throw
        }
    }
    "install-shortcuts" {
        New-DesktopShortcut -Name "Yggdrasil Start" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" start"
        New-DesktopShortcut -Name "Yggdrasil Tray" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptRoot\Yggdrasil.Tray.ps1`""
        New-DesktopShortcut -Name "Yggdrasil Apps" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" open-apps"
        New-DesktopShortcut -Name "Yggdrasil Settings" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" open-settings"
        New-DesktopShortcut -Name "Yggdrasil Status" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" status"
        New-DesktopShortcut -Name "Yggdrasil Diagnostics" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" logs"
        New-DesktopShortcut -Name "Yggdrasil Backup" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" backup"
        New-DesktopShortcut -Name "Yggdrasil Restore" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" restore"
        New-DesktopShortcut -Name "Yggdrasil Snapshots" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" snapshots"
        New-DesktopShortcut -Name "Yggdrasil Update" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Update.ps1`" check"
        New-DesktopShortcut -Name "Yggdrasil Upgrade" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" upgrade"
        New-DesktopShortcut -Name "Yggdrasil Rollback" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" rollback"
        New-DesktopShortcut -Name "Yggdrasil Stop" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" stop"
        foreach ($Shortcut in Get-InstallDistributionShortcuts) {
            if ($Shortcut.name -and $Shortcut.openPath) {
                New-DesktopShortcut -Name ([string]$Shortcut.name) -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" start-app -OpenPath `"$($Shortcut.openPath)`""
            }
        }
        Write-Host "Yggdrasil shortcuts were installed to Desktop and Start Menu."
    }
    "uninstall-shortcuts" {
        Remove-DesktopShortcuts
        Write-Host "Yggdrasil shortcuts were removed from Desktop and Start Menu."
    }
}
