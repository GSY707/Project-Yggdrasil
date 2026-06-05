param(
    [ValidateSet("start", "stop", "status", "open", "logs", "backup", "restore")]
    [string]$Action = "start",
    [string]$Snapshot = ""
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptRoot "..\..\..")
$DockerDesktopPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$ProductUrl = "http://localhost:3000"

function Invoke-RepoCommand {
    param([string[]]$Command)
    Push-Location $RepoRoot
    try {
        & $Command[0] @($Command | Select-Object -Skip 1)
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE: $($Command -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

function Ensure-Docker {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }
    if (Test-Path $DockerDesktopPath) {
        Start-Process -FilePath $DockerDesktopPath
        Write-Host "Docker Desktop is starting. Re-run this action after Docker reports it is ready."
        exit 2
    }
    throw "Docker is not available and Docker Desktop was not found at $DockerDesktopPath"
}

switch ($Action) {
    "start" {
        Ensure-Docker
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:up")
        Start-Process $ProductUrl
    }
    "stop" {
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:down")
    }
    "status" {
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:status")
        Invoke-RepoCommand -Command @("corepack", "pnpm", "product:smoke")
    }
    "open" {
        Start-Process $ProductUrl
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
    "restore" {
        Ensure-Docker
        if ($Snapshot.Trim().Length -eq 0) {
            Invoke-RepoCommand -Command @("corepack", "pnpm", "product:restore")
        }
        else {
            Invoke-RepoCommand -Command @("corepack", "pnpm", "product:restore", "--", "--snapshot", $Snapshot)
        }
    }
}
