param(
    [ValidateSet("start", "stop", "status", "open", "logs", "backup", "restore", "snapshots", "upgrade", "rollback", "install-shortcuts", "uninstall-shortcuts")]
    [string]$Action = "start",
    [string]$Snapshot = ""
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DockerDesktopPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$DesktopShortcutRoot = [Environment]::GetFolderPath("Desktop")
$StartMenuShortcutRoot = Join-Path ([Environment]::GetFolderPath("Programs")) "Project Yggdrasil"

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
    $Port = Get-ProductEnvValue -Name "YGGDRASIL_WEB_PORT" -Default "3000"
    return "http://localhost:$Port"
}

function Ensure-Docker {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }
    if (Test-Path $DockerDesktopPath) {
        Start-Process -FilePath $DockerDesktopPath -WindowStyle Hidden
        Write-Host "Docker Desktop is starting. Re-run this action after Docker reports it is ready."
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
        foreach ($Name in @("Yggdrasil Desktop", "Yggdrasil Tray", "Yggdrasil Status", "Yggdrasil Logs", "Yggdrasil Backup", "Yggdrasil Restore", "Yggdrasil Snapshots", "Yggdrasil Update", "Yggdrasil Upgrade", "Yggdrasil Rollback", "Yggdrasil Stop")) {
            $Path = Join-Path $Root "$Name.lnk"
            if (Test-Path $Path) {
                Remove-Item -LiteralPath $Path
            }
        }
    }
}

switch ($Action) {
    "start" {
        Ensure-Docker
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:up")
        Start-Process (Get-ProductUrl)
    }
    "stop" {
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:down")
    }
    "status" {
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:status")
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:smoke")
    }
    "open" {
        Start-Process (Get-ProductUrl)
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
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:upgrade")
        Start-Process (Get-ProductUrl)
    }
    "rollback" {
        Ensure-Docker
        if ($Snapshot.Trim().Length -eq 0) {
            Invoke-RepoCommand -Command @("corepack", "pnpm", "product:rollback")
        }
        else {
            Invoke-RepoCommand -Command @("corepack", "pnpm", "product:rollback", "--", "--snapshot", $Snapshot)
        }
        Start-Process (Get-ProductUrl)
    }
    "install-shortcuts" {
        New-DesktopShortcut -Name "Yggdrasil Desktop" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" start"
        New-DesktopShortcut -Name "Yggdrasil Tray" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptRoot\Yggdrasil.Tray.ps1`""
        New-DesktopShortcut -Name "Yggdrasil Status" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" status"
        New-DesktopShortcut -Name "Yggdrasil Logs" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" logs"
        New-DesktopShortcut -Name "Yggdrasil Backup" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" backup"
        New-DesktopShortcut -Name "Yggdrasil Restore" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" restore"
        New-DesktopShortcut -Name "Yggdrasil Snapshots" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" snapshots"
        New-DesktopShortcut -Name "Yggdrasil Update" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Update.ps1`" check"
        New-DesktopShortcut -Name "Yggdrasil Upgrade" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" upgrade"
        New-DesktopShortcut -Name "Yggdrasil Rollback" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" rollback"
        New-DesktopShortcut -Name "Yggdrasil Stop" -TargetPath "powershell.exe" -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\Yggdrasil.Desktop.ps1`" stop"
        Write-Host "Yggdrasil shortcuts were installed to Desktop and Start Menu."
    }
    "uninstall-shortcuts" {
        Remove-DesktopShortcuts
        Write-Host "Yggdrasil shortcuts were removed from Desktop and Start Menu."
    }
}
