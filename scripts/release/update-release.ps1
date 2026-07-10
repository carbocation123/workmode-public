param(
  [string]$PackagePath,
  [string]$ManifestUrl,
  [string]$Sha256,
  [string]$Channel = "stable",
  [switch]$NoRestart
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Logs = Join-Path $Root "logs"
$Backups = Join-Path $Root "backups"
$CurrentApp = Join-Path $Root "app"
$UpdaterLog = Join-Path $Logs "updater.log"

New-Item -ItemType Directory -Force $Logs, $Backups | Out-Null

function Write-Step {
  param([string]$Message)
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Write-Host $line -ForegroundColor Cyan
  Add-Content -LiteralPath $UpdaterLog -Value $line -Encoding UTF8
}

function Get-Sha256 {
  param([string]$Path)
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Resolve-ManifestPackage {
  param([string]$Url)
  $manifestPath = Join-Path $TempRoot "manifest.json"
  Write-Step "Downloading update manifest: $Url"
  Invoke-WebRequest -Uri $Url -OutFile $manifestPath -UseBasicParsing
  $manifest = Get-Content -LiteralPath $manifestPath -Encoding UTF8 -Raw | ConvertFrom-Json
  if ($manifest.channel -and $manifest.channel -ne $Channel) {
    throw "Manifest channel '$($manifest.channel)' does not match requested channel '$Channel'."
  }
  $downloadUrl = $manifest.url
  if (-not $downloadUrl) {
    throw "Manifest does not contain a package url."
  }
  $script:Sha256 = if ($manifest.sha256) { [string]$manifest.sha256 } else { $script:Sha256 }
  $downloadPath = Join-Path $TempRoot "update.zip"
  Write-Step "Downloading update package."
  Invoke-WebRequest -Uri $downloadUrl -OutFile $downloadPath -UseBasicParsing
  return $downloadPath
}

function Find-PackageRoot {
  param([string]$Expanded)
  $candidates = @($Expanded)
  $candidates += Get-ChildItem -LiteralPath $Expanded -Directory | Select-Object -ExpandProperty FullName
  foreach ($candidate in $candidates) {
    $backendMain = Join-Path $candidate "app\backend\app\main.py"
    $frontendIndex = Join-Path $candidate "app\frontend-dist\index.html"
    if ((Test-Path $backendMain) -and (Test-Path $frontendIndex)) {
      return $candidate
    }
  }
  throw "Update package is invalid: app\backend and app\frontend-dist were not found."
}

function Copy-OptionalReleaseFiles {
  param([string]$PackageRoot)
  $envExample = Join-Path $PackageRoot "config\.env.example"
  if (Test-Path $envExample) {
    Copy-Item -LiteralPath $envExample -Destination (Join-Path $Root "config\.env.example") -Force
  }
  foreach ($name in @("README.md", "VERSION")) {
    $source = Join-Path $PackageRoot $name
    if (Test-Path $source) {
      Copy-Item -LiteralPath $source -Destination (Join-Path $Root $name) -Force
    }
  }
  $sourceDocs = Join-Path $PackageRoot "docs"
  if (Test-Path $sourceDocs) {
    $targetDocs = Join-Path $Root "docs"
    if (Test-Path $targetDocs) {
      Remove-Item -LiteralPath $targetDocs -Recurse -Force
    }
    Copy-Item -LiteralPath $sourceDocs -Destination $targetDocs -Recurse
  }
}

$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("workmode-public-update-" + [guid]::NewGuid().ToString("N"))
$backupApp = $null

try {
  Set-Content -LiteralPath $UpdaterLog -Value "[updater] Workmode Public update" -Encoding UTF8
  New-Item -ItemType Directory -Force $TempRoot | Out-Null

  if ($ManifestUrl) {
    $PackagePath = Resolve-ManifestPackage -Url $ManifestUrl
  }
  if (-not $PackagePath) {
    throw "Provide -PackagePath or -ManifestUrl."
  }

  $resolvedPackage = (Resolve-Path -LiteralPath $PackagePath).Path
  if ($Sha256) {
    $actual = Get-Sha256 -Path $resolvedPackage
    if ($actual -ne $Sha256.ToLowerInvariant()) {
      throw "SHA256 mismatch. Expected $Sha256, got $actual."
    }
    Write-Step "SHA256 verification passed."
  }

  $expanded = Join-Path $TempRoot "expanded"
  New-Item -ItemType Directory -Force $expanded | Out-Null
  Write-Step "Expanding update package."
  Expand-Archive -LiteralPath $resolvedPackage -DestinationPath $expanded -Force
  $packageRoot = Find-PackageRoot -Expanded $expanded

  $stopScript = Join-Path $PSScriptRoot "stop-release.ps1"
  if (Test-Path $stopScript) {
    & $stopScript
  }

  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  if (Test-Path $CurrentApp) {
    $backupApp = Join-Path $Backups "app-$stamp"
    Write-Step "Backing up current app to backups\app-$stamp."
    Move-Item -LiteralPath $CurrentApp -Destination $backupApp
  }

  try {
    Write-Step "Installing new app files."
    Copy-Item -LiteralPath (Join-Path $packageRoot "app") -Destination $CurrentApp -Recurse
    Copy-OptionalReleaseFiles -PackageRoot $packageRoot
  } catch {
    if ($backupApp -and (Test-Path $backupApp) -and -not (Test-Path $CurrentApp)) {
      Move-Item -LiteralPath $backupApp -Destination $CurrentApp
    }
    throw
  }

  Write-Step "Update installed successfully."
  if (-not $NoRestart) {
    $startScript = Join-Path $PSScriptRoot "start-release.ps1"
    if (Test-Path $startScript) {
      & $startScript -NoBrowser
    }
  }
} finally {
  if (Test-Path $TempRoot) {
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}
