param(
    [string]$Distribution = "local-preview",
    [string]$Version = "",
    [switch]$SkipArchive,
    [switch]$Sign
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptRoot "..\..\..")
$DistributionPath = Join-Path $RepoRoot "packaging\distributions\$Distribution.json"
if (-not (Test-Path $DistributionPath)) {
    throw "Distribution manifest not found: $DistributionPath"
}

$Manifest = Get-Content -Raw -Path $DistributionPath | ConvertFrom-Json
$ReleaseVersion = $Version
if ([string]::IsNullOrWhiteSpace($ReleaseVersion)) {
    $ReleaseVersion = [string]$Manifest.version
}
if ([string]::IsNullOrWhiteSpace($ReleaseVersion)) {
    throw "Release version is required. Set distribution version or pass -Version."
}

$DistRoot = Join-Path $RepoRoot "dist\releases"
$PackageName = "project-yggdrasil-$($Manifest.distributionId)-$ReleaseVersion"
$StageRoot = Join-Path $DistRoot $PackageName
$ZipPath = Join-Path $DistRoot "$PackageName.zip"
$ChecksumPath = Join-Path $DistRoot "$PackageName.sha256"

if (Test-Path $StageRoot) {
    Remove-Item -LiteralPath $StageRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $StageRoot -Force | Out-Null

function Copy-RepoPath {
    param([string]$RelativePath)
    $Source = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path $Source)) {
        throw "Release package source path missing: $RelativePath"
    }
    $Destination = Join-Path $StageRoot $RelativePath
    $Parent = Split-Path -Parent $Destination
    if (-not (Test-Path $Parent)) {
        New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

$BasePaths = @(
    "adapters",
    "applications\base-template",
    "apps\web\app",
    "apps\web\lib",
    "apps\web\public",
    "apps\web\.eslintrc.json",
    "apps\web\next-env.d.ts",
    "apps\web\next.config.ts",
    "apps\web\package.json",
    "apps\web\tsconfig.json",
    "docs",
    "infra",
    "migrations",
    "modules",
    "packages",
    "packaging",
    "scripts",
    "services",
    ".dockerignore",
    ".env.example",
    "alembic.ini",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "pyproject.toml",
    "pyrightconfig.json",
    "pytest.ini",
    "README.md",
    "README.en.md",
    "tsconfig.base.json",
    "uv.lock"
)

foreach ($RelativePath in $BasePaths) {
    Copy-RepoPath -RelativePath $RelativePath
}

foreach ($AppPath in @($Manifest.includedApplications)) {
    Copy-RepoPath -RelativePath ([string]$AppPath)
}

$ReleaseManifest = [ordered]@{
    schemaVersion = 1
    packageName = $PackageName
    distributionId = $Manifest.distributionId
    displayName = $Manifest.displayName
    version = $ReleaseVersion
    releaseChannel = $Manifest.releaseChannel
    updatePolicy = $Manifest.updatePolicy
    defaultAppId = $Manifest.defaultAppId
    includedApplications = @($Manifest.includedApplications)
    shortcutTargets = @($Manifest.shortcutTargets)
    docker = $Manifest.docker
    signing = @{
        requested = [bool]$Sign
        signed = $false
        status = "reserved"
        note = "Code signing is intentionally reserved until a Windows code signing certificate is available."
    }
    builtAt = (Get-Date).ToUniversalTime().ToString("o")
    install = "Run packaging\\desktop\\windows\\Yggdrasil Installer.cmd from the unpacked release package."
    publish = @{
        channel = "GitHub Releases"
        checksumFile = "$PackageName.sha256"
        archiveFile = "$PackageName.zip"
    }
}
$ReleaseManifest | ConvertTo-Json -Depth 10 | Set-Content -Path (Join-Path $StageRoot "release-manifest.json") -Encoding UTF8

if ($Sign) {
    Write-Warning "Signing was requested, but no certificate is configured. The package is built unsigned and marked signed=false."
}

if (-not $SkipArchive) {
    if (Test-Path $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive -Path (Join-Path $StageRoot "*") -DestinationPath $ZipPath -Force
    $Stream = [System.IO.File]::OpenRead($ZipPath)
    try {
        $Sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            $HashBytes = $Sha256.ComputeHash($Stream)
        }
        finally {
            $Sha256.Dispose()
        }
    }
    finally {
        $Stream.Dispose()
    }
    $HashText = ([System.BitConverter]::ToString($HashBytes)).Replace("-", "").ToLowerInvariant()
    "$HashText  $(Split-Path -Leaf $ZipPath)" | Set-Content -Path $ChecksumPath -Encoding ASCII
}

Write-Host "Built release package staging directory: $StageRoot"
if (-not $SkipArchive) {
    Write-Host "Built release package archive: $ZipPath"
    Write-Host "Wrote SHA256 checksum: $ChecksumPath"
}
