param(
    [ValidateSet("install", "uninstall")]
    [string]$Action = "install",
    [string]$RepoRootPath = "",
    [switch]$StartTray,
    [switch]$DeleteLocalData,
    [switch]$ConfirmDeleteLocalData
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallRoot = Join-Path $env:LOCALAPPDATA "ProjectYggdrasil\Desktop"
$LocalAppDataRoot = Join-Path $env:LOCALAPPDATA "ProjectYggdrasil"
$StartMenuRoot = Join-Path ([Environment]::GetFolderPath("Programs")) "Project Yggdrasil"
$StartupRoot = [Environment]::GetFolderPath("Startup")
$UninstallStatePath = Join-Path $LocalAppDataRoot "uninstall-state.json"

function Resolve-InstallRepoRoot {
    if (-not [string]::IsNullOrWhiteSpace($RepoRootPath)) {
        if (-not (Test-Path $RepoRootPath)) {
            throw "RepoRootPath does not exist: $RepoRootPath"
        }
        return (Resolve-Path $RepoRootPath).Path
    }
    if ($env:YGGDRASIL_REPO_ROOT -and (Test-Path $env:YGGDRASIL_REPO_ROOT)) {
        return (Resolve-Path $env:YGGDRASIL_REPO_ROOT).Path
    }
    $Candidate = Join-Path $ScriptRoot "..\..\.."
    if (Test-Path (Join-Path $Candidate "package.json")) {
        return (Resolve-Path $Candidate).Path
    }
    throw "Cannot locate the Project Yggdrasil repository. Run from the repo checkout, set YGGDRASIL_REPO_ROOT, or pass -RepoRootPath."
}

$RepoRoot = Resolve-InstallRepoRoot

function Test-UnderPath {
    param(
        [string]$Path,
        [string]$Parent
    )
    $ResolvedPath = [System.IO.Path]::GetFullPath($Path)
    $ResolvedParent = [System.IO.Path]::GetFullPath($Parent)
    return $ResolvedPath.StartsWith($ResolvedParent, [System.StringComparison]::OrdinalIgnoreCase)
}

function Write-UninstallState {
    param([hashtable]$State)
    $StateRoot = Split-Path -Parent $UninstallStatePath
    if (-not (Test-Path $StateRoot)) {
        New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
    }
    $State.checkedAt = (Get-Date).ToUniversalTime().ToString("o")
    $State | ConvertTo-Json -Depth 8 | Set-Content -Path $UninstallStatePath -Encoding UTF8
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

function Get-PathSummary {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return @{
            path = $Path
            exists = $false
            itemCount = 0
            bytes = 0
        }
    }
    $Items = @(Get-ChildItem -LiteralPath $Path -Force -Recurse -ErrorAction SilentlyContinue)
    $Bytes = 0
    foreach ($Item in $Items) {
        if (-not $Item.PSIsContainer) {
            $Bytes += $Item.Length
        }
    }
    return @{
        path = $Path
        exists = $true
        itemCount = $Items.Count
        bytes = $Bytes
    }
}

function Get-UninstallImpactPreview {
    $StateRoot = Join-Path $RepoRoot ".yggdrasil"
    $BackupRoot = Join-Path $RepoRoot ".yggdrasil-backups"
    $ProductEnv = Join-Path $RepoRoot "infra\product.env"
    return @{
        action = "uninstall"
        installRoot = $InstallRoot
        repoRoot = $RepoRoot
        shortcuts = @(
            (Join-Path $StartMenuRoot "Yggdrasil Tray.lnk"),
            (Join-Path $StartMenuRoot "Yggdrasil Desktop.lnk"),
            (Join-Path $StartMenuRoot "Yggdrasil Update.lnk"),
            (Join-Path $StartupRoot "Yggdrasil Tray.lnk")
        )
        defaultKeepsLocalData = $true
        retainedByDefault = @(
            (Get-PathSummary -Path $StateRoot),
            (Get-PathSummary -Path $BackupRoot),
            (Get-PathSummary -Path $ProductEnv)
        )
        deletedWhenDeleteLocalDataIsConfirmed = @(
            (Get-PathSummary -Path $StateRoot),
            (Get-PathSummary -Path $BackupRoot)
        )
        retainedEvenWhenDeletingLocalData = @($ProductEnv)
    }
}

function Remove-LocalData {
    $Targets = @(
        (Join-Path $RepoRoot ".yggdrasil"),
        (Join-Path $RepoRoot ".yggdrasil-backups")
    )
    foreach ($Target in $Targets) {
        if ((Test-Path $Target) -and (Test-UnderPath -Path $Target -Parent $RepoRoot)) {
            Remove-Item -LiteralPath $Target -Recurse -Force
        }
    }
}

function New-Shortcut {
    param(
        [string]$Path,
        [string]$TargetPath,
        [string]$Arguments,
        [string]$WorkingDirectory
    )
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($Path)
    $Shortcut.TargetPath = $TargetPath
    $Shortcut.Arguments = $Arguments
    $Shortcut.WorkingDirectory = $WorkingDirectory
    $Shortcut.Save()
}

function Install-YggdrasilDesktop {
    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
    Copy-Item -Path (Join-Path $ScriptRoot "*") -Destination $InstallRoot -Recurse -Force
    @{
        repoRoot = [string]$RepoRoot
        installedAt = (Get-Date).ToUniversalTime().ToString("o")
        installRoot = $InstallRoot
        signed = $false
    } | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $InstallRoot "install.json") -Encoding UTF8

    New-Item -ItemType Directory -Path $StartMenuRoot -Force | Out-Null
    $TrayScript = Join-Path $InstallRoot "Yggdrasil.Tray.ps1"
    $DesktopScript = Join-Path $InstallRoot "Yggdrasil.Desktop.ps1"
    $UpdateScript = Join-Path $InstallRoot "Yggdrasil.Update.ps1"
    New-Shortcut -Path (Join-Path $StartMenuRoot "Yggdrasil Tray.lnk") -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$TrayScript`"" -WorkingDirectory $InstallRoot
    New-Shortcut -Path (Join-Path $StartMenuRoot "Yggdrasil Desktop.lnk") -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$DesktopScript`" start" -WorkingDirectory $InstallRoot
    New-Shortcut -Path (Join-Path $StartMenuRoot "Yggdrasil Update.lnk") -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$UpdateScript`" check" -WorkingDirectory $InstallRoot
    New-Shortcut -Path (Join-Path $StartupRoot "Yggdrasil Tray.lnk") -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$TrayScript`"" -WorkingDirectory $InstallRoot
    & (Join-Path $InstallRoot "Yggdrasil.Desktop.ps1") install-shortcuts
    if ($StartTray) {
        Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", $TrayScript)
    }
    Write-Host "Installed Project Yggdrasil desktop preview to $InstallRoot"
}

function Uninstall-YggdrasilDesktop {
    $LocalAppData = Join-Path $env:LOCALAPPDATA "ProjectYggdrasil"
    $Preview = Get-UninstallImpactPreview
    $State = @{
        status = "uninstall-preview"
        impactPreview = $Preview
        deleteLocalDataRequested = [bool]$DeleteLocalData
    }
    Write-UninstallState -State $State
    Write-Host ($State | ConvertTo-Json -Depth 8)
    if ($DeleteLocalData -and -not $ConfirmDeleteLocalData) {
        Request-DesktopConfirmation -Prompt "Type DELETE LOCAL DATA to remove local state and backups after uninstalling" -Expected "DELETE LOCAL DATA"
    }
    try {
    if (Test-Path $InstallRoot) {
        & (Join-Path $InstallRoot "Yggdrasil.Desktop.ps1") uninstall-shortcuts
    }
    foreach ($Shortcut in @(
        (Join-Path $StartMenuRoot "Yggdrasil Tray.lnk"),
        (Join-Path $StartMenuRoot "Yggdrasil Desktop.lnk"),
        (Join-Path $StartMenuRoot "Yggdrasil Update.lnk"),
        (Join-Path $StartupRoot "Yggdrasil Tray.lnk")
    )) {
        if (Test-Path $Shortcut) {
            Remove-Item -LiteralPath $Shortcut
        }
    }
    if ((Test-Path $InstallRoot) -and (Test-UnderPath -Path $InstallRoot -Parent $LocalAppData)) {
        Remove-Item -LiteralPath $InstallRoot -Recurse -Force
    }
    if (Test-Path $StartMenuRoot) {
        $Remaining = Get-ChildItem -LiteralPath $StartMenuRoot -Force
        if (-not $Remaining) {
            Remove-Item -LiteralPath $StartMenuRoot -Force
        }
    }
        if ($DeleteLocalData) {
            Remove-LocalData
        }
        Write-UninstallState -State @{
            status = "uninstall-succeeded"
            impactPreview = $Preview
            localDataDeleted = [bool]$DeleteLocalData
        }
        if ($DeleteLocalData) {
            Write-Host "Uninstalled Project Yggdrasil desktop preview and deleted confirmed local data."
        }
        else {
            Write-Host "Uninstalled Project Yggdrasil desktop preview. Local data was kept."
        }
    }
    catch {
        Write-UninstallState -State @{
            status = "uninstall-failed"
            impactPreview = $Preview
            localDataDeleteRequested = [bool]$DeleteLocalData
            error = $_.Exception.Message
            recoveryActions = @("Re-run uninstall after closing tray windows.", "If local data was not requested for deletion, it remains in the repository data folders.", "Open the install folder and inspect uninstall-state.json for the failed step.")
        }
        throw
    }
}

switch ($Action) {
    "install" { Install-YggdrasilDesktop }
    "uninstall" { Uninstall-YggdrasilDesktop }
}
