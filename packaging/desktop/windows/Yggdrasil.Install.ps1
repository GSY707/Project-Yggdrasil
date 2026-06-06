param(
    [ValidateSet("install", "uninstall")]
    [string]$Action = "install",
    [string]$RepoRootPath = "",
    [switch]$StartTray
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallRoot = Join-Path $env:LOCALAPPDATA "ProjectYggdrasil\Desktop"
$StartMenuRoot = Join-Path ([Environment]::GetFolderPath("Programs")) "Project Yggdrasil"
$StartupRoot = [Environment]::GetFolderPath("Startup")

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
    Write-Host "Uninstalled Project Yggdrasil desktop preview."
}

switch ($Action) {
    "install" { Install-YggdrasilDesktop }
    "uninstall" { Uninstall-YggdrasilDesktop }
}
