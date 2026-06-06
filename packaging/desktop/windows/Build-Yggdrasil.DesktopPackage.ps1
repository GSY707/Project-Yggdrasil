$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptRoot "..\..\..")
$DistRoot = Join-Path $RepoRoot "dist\desktop"
$PackageRoot = Join-Path $DistRoot "yggdrasil-desktop-preview"
$ZipPath = Join-Path $DistRoot "yggdrasil-desktop-preview.zip"

if (Test-Path $PackageRoot) {
    Remove-Item -LiteralPath $PackageRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageRoot -Force | Out-Null
Copy-Item -Path (Join-Path $ScriptRoot "*") -Destination $PackageRoot -Recurse -Force
@{
    name = "Project Yggdrasil Desktop Preview"
    signed = $false
    builtAt = (Get-Date).ToUniversalTime().ToString("o")
    install = "Run Yggdrasil Installer.cmd from a repo checkout, or run powershell -File Yggdrasil.Install.ps1 -RepoRootPath <repo> when installing from the ZIP."
    uninstall = "Run Yggdrasil Uninstaller.cmd."
} | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $PackageRoot "package-manifest.json") -Encoding UTF8

if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path (Join-Path $PackageRoot "*") -DestinationPath $ZipPath -Force
Write-Host "Built unsigned desktop package: $ZipPath"
