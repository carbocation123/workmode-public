param(
  [string]$Version,
  [string]$OutputRoot,
  [string]$RuntimeSource,
  [switch]$NoRuntime,
  [switch]$SkipTests,
  [switch]$SkipFrontendBuild,
  [switch]$NoZip
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$ReleaseScripts = Join-Path $Root "scripts\release"

if (-not $Version) {
  $versionFile = Join-Path $Root "VERSION"
  $Version = if (Test-Path $versionFile) { (Get-Content -LiteralPath $versionFile -Encoding UTF8 -Raw).Trim() } else { "0.1.0" }
}
if (-not $OutputRoot) {
  $OutputRoot = Join-Path $Root "release"
}

$PackageName = "workmode-public-$Version-win-x64"
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$PackageRoot = [System.IO.Path]::GetFullPath((Join-Path $OutputRoot $PackageName))

function Write-Step {
  param([string]$Message)
  Write-Host "[release] $Message" -ForegroundColor Cyan
}

function Assert-Inside {
  param(
    [string]$Child,
    [string]$Parent
  )
  $childFull = [System.IO.Path]::GetFullPath($Child)
  $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
  if (-not $childFull.StartsWith($parentFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to operate outside output root: $childFull"
  }
}

function Resolve-DevPython {
  $venvPython = Join-Path $Backend ".venv\Scripts\python.exe"
  if (Test-Path $venvPython) {
    return $venvPython
  }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    return $py.Source
  }
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    return $python.Source
  }
  throw "Python was not found for build-time tests."
}

function Invoke-DevPython {
  param([string[]]$Arguments)
  $python = Resolve-DevPython
  if ((Split-Path -Leaf $python) -eq "py.exe") {
    & $python -3 @Arguments
  } else {
    & $python @Arguments
  }
  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed: $($Arguments -join ' ')"
  }
}

function Copy-RequiredItem {
  param(
    [string]$Source,
    [string]$Destination,
    [switch]$Recurse
  )
  if (-not (Test-Path $Source)) {
    throw "Required source is missing: $Source"
  }
  if ($Recurse) {
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse
  } else {
    Copy-Item -LiteralPath $Source -Destination $Destination
  }
}

function Detect-PythonBase {
  $venvPython = Join-Path $Backend ".venv\Scripts\python.exe"
  if (-not (Test-Path $venvPython)) {
    throw "backend\.venv is required when -NoRuntime is not set."
  }
  $base = (& $venvPython -c "import sys; print(sys.base_prefix)").Trim()
  if ($LASTEXITCODE -ne 0 -or -not $base) {
    throw "Could not detect Python base runtime from backend\.venv."
  }
  return $base
}

function Write-Cmd {
  param(
    [string]$Path,
    [string]$ScriptName,
    [string]$FailureMessage
  )
  $content = @"
@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\$ScriptName" %*

if errorlevel 1 (
  echo.
  echo $FailureMessage
  pause
)
"@
  Set-Content -LiteralPath $Path -Value $content -Encoding ASCII
}

function Write-VersionFile {
  param(
    [string]$Path,
    [string]$RuntimeKind
  )
  $payload = [ordered]@{
    app = "workmode-public"
    version = $Version
    platform = "win-x64"
    built_at = (Get-Date).ToUniversalTime().ToString("o")
    runtime = $RuntimeKind
  }
  $payload | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Copy-Runtime {
  $runtimeRoot = Join-Path $PackageRoot "runtime"
  New-Item -ItemType Directory -Force $runtimeRoot | Out-Null

  $venvSource = Join-Path $Backend ".venv"
  if (-not (Test-Path (Join-Path $venvSource "Scripts\python.exe"))) {
    throw "backend\.venv with installed dependencies is required for a runtime bundle."
  }

  Write-Step "Copying backend virtual environment."
  Copy-Item -LiteralPath $venvSource -Destination (Join-Path $runtimeRoot "backend-venv") -Recurse

  $baseSource = if ($RuntimeSource) { $RuntimeSource } else { Detect-PythonBase }
  $baseSource = [System.IO.Path]::GetFullPath($baseSource)
  if (-not (Test-Path (Join-Path $baseSource "python.exe"))) {
    throw "Python runtime source must contain python.exe: $baseSource"
  }
  Write-Step "Copying Python base runtime from $baseSource."
  Copy-Item -LiteralPath $baseSource -Destination (Join-Path $runtimeRoot "python-base") -Recurse

  return @{
    kind = "python-base-plus-venv"
    source = $baseSource
  }
}

New-Item -ItemType Directory -Force $OutputRoot | Out-Null
Assert-Inside -Child $PackageRoot -Parent $OutputRoot
if (Test-Path $PackageRoot) {
  Write-Step "Removing previous package directory."
  Remove-Item -LiteralPath $PackageRoot -Recurse -Force
}

if (-not $SkipTests) {
  Write-Step "Running backend tests."
  Push-Location $Backend
  try {
    Invoke-DevPython -Arguments @("-m", "unittest", "discover", "tests")
  } finally {
    Pop-Location
  }
}

if (-not $SkipFrontendBuild) {
  Write-Step "Building frontend."
  $npm = Get-Command npm -ErrorAction SilentlyContinue
  if (-not $npm) {
    throw "npm was not found. Install Node.js on the build machine or pass -SkipFrontendBuild after building dist."
  }
  Push-Location $Frontend
  try {
    & $npm.Source run build
    if ($LASTEXITCODE -ne 0) {
      throw "npm run build failed"
    }
  } finally {
    Pop-Location
  }
}

$distIndex = Join-Path $Frontend "dist\index.html"
if (-not (Test-Path $distIndex)) {
  throw "frontend\dist is missing. Build the frontend first."
}

Write-Step "Creating package layout."
New-Item -ItemType Directory -Force `
  (Join-Path $PackageRoot "app\backend"), `
  (Join-Path $PackageRoot "config"), `
  (Join-Path $PackageRoot "data"), `
  (Join-Path $PackageRoot "logs"), `
  (Join-Path $PackageRoot "scripts") | Out-Null

Copy-RequiredItem -Source (Join-Path $Backend "app") -Destination (Join-Path $PackageRoot "app\backend\app") -Recurse
Copy-RequiredItem -Source (Join-Path $Backend "requirements.txt") -Destination (Join-Path $PackageRoot "app\backend\requirements.txt")
Copy-RequiredItem -Source (Join-Path $Frontend "dist") -Destination (Join-Path $PackageRoot "app\frontend-dist") -Recurse
Copy-RequiredItem -Source (Join-Path $Root ".env.example") -Destination (Join-Path $PackageRoot "config\.env.example")
Copy-RequiredItem -Source (Join-Path $Root "README.md") -Destination (Join-Path $PackageRoot "README.md")
Copy-RequiredItem -Source (Join-Path $Root "docs") -Destination (Join-Path $PackageRoot "docs") -Recurse
Copy-RequiredItem -Source (Join-Path $ReleaseScripts "start-release.ps1") -Destination (Join-Path $PackageRoot "scripts\start-release.ps1")
Copy-RequiredItem -Source (Join-Path $ReleaseScripts "stop-release.ps1") -Destination (Join-Path $PackageRoot "scripts\stop-release.ps1")
Copy-RequiredItem -Source (Join-Path $ReleaseScripts "update-release.ps1") -Destination (Join-Path $PackageRoot "scripts\update-release.ps1")
Copy-RequiredItem -Source (Join-Path $ReleaseScripts "upgrade-existing.ps1") -Destination (Join-Path $PackageRoot "scripts\upgrade-existing.ps1")

Set-Content -LiteralPath (Join-Path $PackageRoot "VERSION") -Value $Version -Encoding UTF8
Write-Cmd -Path (Join-Path $PackageRoot "WorkmodePublic.cmd") -ScriptName "start-release.ps1" -FailureMessage "Workmode Public start failed. See logs\launcher.log for details."
Write-Cmd -Path (Join-Path $PackageRoot "StopWorkmodePublic.cmd") -ScriptName "stop-release.ps1" -FailureMessage "Workmode Public stop failed."
Write-Cmd -Path (Join-Path $PackageRoot "UpdateWorkmodePublic.cmd") -ScriptName "update-release.ps1" -FailureMessage "Workmode Public update failed. See logs\updater.log for details."
$ChineseUpgradeName = (-join ([char[]]@(0x5347, 0x7EA7, 0x5DF2, 0x6709, 0x7248, 0x672C))) + ".cmd"
Write-Cmd -Path (Join-Path $PackageRoot $ChineseUpgradeName) -ScriptName "upgrade-existing.ps1" -FailureMessage "Workmode Public upgrade failed. See logs\migration.log for details."
Write-Cmd -Path (Join-Path $PackageRoot "UpgradeExistingWorkmode.cmd") -ScriptName "upgrade-existing.ps1" -FailureMessage "Workmode Public upgrade failed. See logs\migration.log for details."

$runtimeInfo = if ($NoRuntime) {
  @{ kind = "none"; source = "" }
} else {
  Copy-Runtime
}
Write-VersionFile -Path (Join-Path $PackageRoot "app\version.json") -RuntimeKind $runtimeInfo.kind

if (-not $NoZip) {
  $zipPath = Join-Path $OutputRoot "$PackageName.zip"
  if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
  }
  Write-Step "Creating zip archive."
  Compress-Archive -LiteralPath $PackageRoot -DestinationPath $zipPath -Force
  $sha = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  Set-Content -LiteralPath "$zipPath.sha256" -Value "$sha  $PackageName.zip" -Encoding UTF8

  $manifest = [ordered]@{
    app = "workmode-public"
    version = $Version
    channel = "stable"
    platform = "win-x64"
    url = "https://example.com/releases/$PackageName.zip"
    sha256 = $sha
    notes = "Replace url with the real release download URL before publishing."
  }
  $manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $OutputRoot "manifest-$Version.json") -Encoding UTF8
}

Write-Step "Release package ready: $PackageRoot"
