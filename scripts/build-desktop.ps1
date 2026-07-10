param(
  [string]$Version,
  [string]$RuntimeSource,
  [string]$UpdateEndpoint = "https://github.com/carbocation123/workmode-public/releases/latest/download/latest.json",
  [string]$ArtifactBaseUrl,
  [string]$ReleaseNotes = "Workmode Public desktop release",
  [switch]$SkipTests,
  [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"

$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Desktop = Join-Path $Root "desktop"
$TauriRoot = Join-Path $Desktop "src-tauri"
$Resources = Join-Path $TauriRoot "resources"
$ReleaseRoot = Join-Path $Root "release"
$RunRoot = Join-Path $Root ".run"
$SecretRoot = Join-Path $Root ".release-secrets"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if (-not $Version) {
  $Version = (Get-Content -LiteralPath (Join-Path $Root "VERSION") -Encoding UTF8 -Raw).Trim()
}
if (-not $ArtifactBaseUrl) {
  $ArtifactBaseUrl = "https://github.com/carbocation123/workmode-public/releases/download/v$Version"
}

$OutputRoot = [System.IO.Path]::GetFullPath((Join-Path $ReleaseRoot "desktop-$Version"))

function Write-Step {
  param([string]$Message)
  Write-Host "[desktop-release] $Message" -ForegroundColor Cyan
}

function Assert-Inside {
  param(
    [string]$Child,
    [string]$Parent
  )
  $childFull = [System.IO.Path]::GetFullPath($Child)
  $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
  if (-not $childFull.StartsWith($parentFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to operate outside the expected root: $childFull"
  }
}

function Write-Utf8Json {
  param(
    [string]$Path,
    [object]$Value,
    [int]$Depth = 8
  )
  $json = $Value | ConvertTo-Json -Depth $Depth
  [System.IO.File]::WriteAllText($Path, $json, $Utf8NoBom)
}

function Resolve-Cargo {
  $cargo = Get-Command cargo -ErrorAction SilentlyContinue
  if ($cargo) {
    return $cargo.Source
  }
  $rustupCargo = Join-Path $env:USERPROFILE ".cargo\bin\cargo.exe"
  if (Test-Path $rustupCargo) {
    return $rustupCargo
  }
  throw "Rust/Cargo was not found on the build machine."
}

function Resolve-Python {
  $venvPython = Join-Path $Backend ".venv\Scripts\python.exe"
  if (Test-Path $venvPython) {
    return $venvPython
  }
  throw "backend\.venv is missing. Create it and install backend requirements before packaging."
}

function Resolve-PythonBase {
  if ($RuntimeSource) {
    $base = [System.IO.Path]::GetFullPath($RuntimeSource)
  } else {
    $python = Resolve-Python
    $base = (& $python -c "import sys; print(sys.base_prefix)").Trim()
    if ($LASTEXITCODE -ne 0) {
      throw "Could not detect the Python base runtime."
    }
  }
  if (-not (Test-Path (Join-Path $base "pythonw.exe"))) {
    throw "Python runtime source must contain pythonw.exe: $base"
  }
  return $base
}

function Assert-VersionConsistency {
  $tauri = Get-Content -LiteralPath (Join-Path $TauriRoot "tauri.conf.json") -Encoding UTF8 -Raw | ConvertFrom-Json
  $frontendPackage = Get-Content -LiteralPath (Join-Path $Frontend "package.json") -Encoding UTF8 -Raw | ConvertFrom-Json
  $frontendLockText = Get-Content -LiteralPath (Join-Path $Frontend "package-lock.json") -Encoding UTF8 -Raw
  $desktopPackage = Get-Content -LiteralPath (Join-Path $Desktop "package.json") -Encoding UTF8 -Raw | ConvertFrom-Json
  $desktopLockText = Get-Content -LiteralPath (Join-Path $Desktop "package-lock.json") -Encoding UTF8 -Raw
  $cargoText = Get-Content -LiteralPath (Join-Path $TauriRoot "Cargo.toml") -Encoding UTF8 -Raw
  $cargoLockText = Get-Content -LiteralPath (Join-Path $TauriRoot "Cargo.lock") -Encoding UTF8 -Raw
  $cargoMatch = [regex]::Match($cargoText, '(?ms)\[package\].*?^version\s*=\s*"([^"]+)"')
  $cargoLockMatch = [regex]::Match($cargoLockText, '(?ms)\[\[package\]\]\s*\r?\nname\s*=\s*"workmode-public"\s*\r?\nversion\s*=\s*"([^"]+)"')
  if (-not $cargoMatch.Success -or -not $cargoLockMatch.Success) {
    throw "Could not read the Workmode Public Cargo version."
  }
  $frontendLockVersion = [regex]::Match($frontendLockText, '"version"\s*:\s*"([^"]+)"').Groups[1].Value
  $frontendLockRoot = [regex]::Match($frontendLockText, '(?s)"packages"\s*:\s*\{\s*""\s*:\s*\{.*?"version"\s*:\s*"([^"]+)"').Groups[1].Value
  $desktopLockVersion = [regex]::Match($desktopLockText, '"version"\s*:\s*"([^"]+)"').Groups[1].Value
  $desktopLockRoot = [regex]::Match($desktopLockText, '(?s)"packages"\s*:\s*\{\s*""\s*:\s*\{.*?"version"\s*:\s*"([^"]+)"').Groups[1].Value
  foreach ($entry in @(
      @{ Name = "tauri.conf.json"; Value = $tauri.version },
      @{ Name = "frontend/package.json"; Value = $frontendPackage.version },
      @{ Name = "frontend/package-lock.json"; Value = $frontendLockVersion },
      @{ Name = "frontend/package-lock.json packages root"; Value = $frontendLockRoot },
      @{ Name = "desktop/package.json"; Value = $desktopPackage.version },
      @{ Name = "desktop/package-lock.json"; Value = $desktopLockVersion },
      @{ Name = "desktop/package-lock.json packages root"; Value = $desktopLockRoot },
      @{ Name = "desktop/src-tauri/Cargo.toml"; Value = $cargoMatch.Groups[1].Value },
      @{ Name = "desktop/src-tauri/Cargo.lock"; Value = $cargoLockMatch.Groups[1].Value }
    )) {
    if ($entry.Value -ne $Version) {
      throw "Version mismatch: $($entry.Name) is $($entry.Value), VERSION is $Version."
    }
  }
}

function Reset-Directory {
  param(
    [string]$Path,
    [string]$AllowedParent
  )
  Assert-Inside -Child $Path -Parent $AllowedParent
  if (Test-Path $Path) {
    Remove-Item -LiteralPath $Path -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Stage-Resources {
  $started = Get-Date
  $pythonBase = Resolve-PythonBase
  $venvSitePackages = Join-Path $Backend ".venv\Lib\site-packages"
  if (-not (Test-Path $venvSitePackages)) {
    throw "Backend virtualenv site-packages is missing: $venvSitePackages"
  }

  Write-Step "Staging backend and bundled Python runtime."
  Reset-Directory -Path $Resources -AllowedParent $TauriRoot
  New-Item -ItemType File -Force -Path (Join-Path $Resources ".gitkeep") | Out-Null

  $backendTarget = Join-Path $Resources "backend"
  $configTarget = Join-Path $Resources "config"
  $pythonTarget = Join-Path $Resources "runtime\python-base"
  $venvLibTarget = Join-Path $Resources "runtime\backend-venv\Lib"
  New-Item -ItemType Directory -Force -Path $backendTarget, $configTarget, $pythonTarget, $venvLibTarget | Out-Null

  Copy-Item -LiteralPath (Join-Path $Backend "app") -Destination $backendTarget -Recurse
  Copy-Item -LiteralPath (Join-Path $Root ".env.example") -Destination (Join-Path $configTarget ".env.example")
  Get-ChildItem -LiteralPath $pythonBase -Force | Copy-Item -Destination $pythonTarget -Recurse -Force
  Copy-Item -LiteralPath $venvSitePackages -Destination $venvLibTarget -Recurse

  $baseSitePackages = Join-Path $pythonTarget "Lib\site-packages"
  if (Test-Path $baseSitePackages) {
    Assert-Inside -Child $baseSitePackages -Parent $Resources
    Remove-Item -LiteralPath $baseSitePackages -Recurse -Force
  }
  Get-ChildItem -LiteralPath $Resources -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    Assert-Inside -Child $_.FullName -Parent $Resources
    Remove-Item -LiteralPath $_.FullName -Recurse -Force
  }

  foreach ($required in @(
      (Join-Path $Resources "backend\app\main.py"),
      (Join-Path $Resources "runtime\python-base\pythonw.exe"),
      (Join-Path $Resources "runtime\backend-venv\Lib\site-packages\uvicorn"),
      (Join-Path $Resources "config\.env.example")
    )) {
    if (-not (Test-Path $required)) {
      throw "Staged desktop resource is missing: $required"
    }
  }
  Write-Step ("Resource staging completed in {0:N1}s." -f ((Get-Date) - $started).TotalSeconds)
}

function Invoke-Checks {
  if ($SkipTests) {
    return
  }
  $python = Resolve-Python
  $cargo = Resolve-Cargo

  $backendStarted = Get-Date
  Write-Step "Running backend tests."
  Push-Location $Backend
  try {
    & $python -m unittest discover tests
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }
  } finally {
    Pop-Location
  }
  Write-Step ("Backend tests completed in {0:N1}s." -f ((Get-Date) - $backendStarted).TotalSeconds)

  $rustStarted = Get-Date
  Write-Step "Running desktop Rust tests in release profile."
  Push-Location $TauriRoot
  try {
    & $cargo test --release
    if ($LASTEXITCODE -ne 0) { throw "Desktop Rust tests failed." }
  } finally {
    Pop-Location
  }
  Write-Step ("Rust release-profile tests completed in {0:N1}s." -f ((Get-Date) - $rustStarted).TotalSeconds)
}

function Invoke-TauriBuild {
  $started = Get-Date
  $tauri = Join-Path $Desktop "node_modules\.bin\tauri.cmd"
  if (-not (Test-Path $tauri)) {
    throw "Desktop npm dependencies are missing. Run npm install in desktop/."
  }
  $privateKey = Join-Path $SecretRoot "workmode-public-updater.key"
  $passwordFile = Join-Path $SecretRoot "updater-password.txt"
  if (-not (Test-Path $privateKey) -or -not (Test-Path $passwordFile)) {
    throw "Updater signing key is missing from .release-secrets."
  }

  New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
  $overridePath = Join-Path $RunRoot "tauri-release-$Version.json"
  Write-Utf8Json -Path $overridePath -Value ([ordered]@{
      version = $Version
      plugins = [ordered]@{
        updater = [ordered]@{
          endpoints = @($UpdateEndpoint)
        }
      }
    })

  Write-Step "Building signed NSIS installer."
  $cargoDir = Split-Path -Parent (Resolve-Cargo)
  $previousPath = $env:PATH
  $previousKey = $env:TAURI_SIGNING_PRIVATE_KEY
  $previousPassword = $env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD
  try {
    $env:PATH = $cargoDir + [System.IO.Path]::PathSeparator + $env:PATH
    $env:TAURI_SIGNING_PRIVATE_KEY = $privateKey
    $env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = (Get-Content -LiteralPath $passwordFile -Encoding UTF8 -Raw).Trim()
    Push-Location $Desktop
    try {
      & $tauri build --bundles nsis --config $overridePath
      if ($LASTEXITCODE -ne 0) { throw "Tauri desktop build failed." }
    } finally {
      Pop-Location
    }
  } finally {
    $env:PATH = $previousPath
    if ($null -eq $previousKey) { Remove-Item Env:TAURI_SIGNING_PRIVATE_KEY -ErrorAction SilentlyContinue } else { $env:TAURI_SIGNING_PRIVATE_KEY = $previousKey }
    if ($null -eq $previousPassword) { Remove-Item Env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD -ErrorAction SilentlyContinue } else { $env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = $previousPassword }
  }
  Write-Step ("Signed NSIS build completed in {0:N1}s." -f ((Get-Date) - $started).TotalSeconds)
}

function Publish-Artifacts {
  $started = Get-Date
  $bundleRoot = Join-Path $TauriRoot "target\release\bundle\nsis"
  if (-not (Test-Path $bundleRoot)) {
    throw "NSIS bundle output is missing: $bundleRoot"
  }
  Reset-Directory -Path $OutputRoot -AllowedParent $ReleaseRoot

  $setup = Get-ChildItem -LiteralPath $bundleRoot -File -Filter "*-setup.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  $signature = Get-ChildItem -LiteralPath $bundleRoot -File -Filter "*.sig" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $setup -or -not $signature) {
    throw "Signed NSIS setup artifacts were not produced."
  }
  $updaterArtifactPath = $signature.FullName.Substring(0, $signature.FullName.Length - 4)
  if (-not (Test-Path $updaterArtifactPath)) {
    throw "Updater artifact referenced by signature is missing: $updaterArtifactPath"
  }
  $updaterArtifact = Get-Item -LiteralPath $updaterArtifactPath

  $publishedSetupName = "workmode-public-$Version-windows-x86_64-setup.exe"
  $publishedArtifactName = if ($updaterArtifact.Extension -eq ".exe") {
    $publishedSetupName
  } else {
    "workmode-public-$Version-windows-x86_64$($updaterArtifact.Extension)"
  }
  $publishedSignatureName = "$publishedArtifactName.sig"
  Copy-Item -LiteralPath $setup.FullName -Destination (Join-Path $OutputRoot $publishedSetupName)
  if ($updaterArtifact.FullName -ne $setup.FullName) {
    Copy-Item -LiteralPath $updaterArtifact.FullName -Destination (Join-Path $OutputRoot $publishedArtifactName)
  }
  Copy-Item -LiteralPath $signature.FullName -Destination (Join-Path $OutputRoot $publishedSignatureName)

  $publishedArtifact = Join-Path $OutputRoot $publishedArtifactName
  $publishedSignature = Join-Path $OutputRoot $publishedSignatureName
  $signatureText = (Get-Content -LiteralPath $publishedSignature -Encoding UTF8 -Raw).Trim()
  $artifactUrl = $ArtifactBaseUrl.TrimEnd("/") + "/" + $publishedArtifactName
  $feed = [ordered]@{
    version = $Version
    notes = $ReleaseNotes
    pub_date = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    platforms = [ordered]@{
      "windows-x86_64" = [ordered]@{
        signature = $signatureText
        url = $artifactUrl
      }
    }
  }
  Write-Utf8Json -Path (Join-Path $OutputRoot "latest.json") -Value $feed

  $hashLines = Get-ChildItem -LiteralPath $OutputRoot -File | Where-Object { $_.Extension -in @(".exe", ".zip") } | ForEach-Object {
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $($_.Name)"
  }
  [System.IO.File]::WriteAllLines((Join-Path $OutputRoot "SHA256SUMS.txt"), [string[]]$hashLines, $Utf8NoBom)

  if (Get-ChildItem -LiteralPath $OutputRoot -Recurse -Force | Where-Object { $_.Name -in @("workmode-public-updater.key", "updater-password.txt") }) {
    throw "Release output contains a private signing secret."
  }
  Write-Step ("Artifact publication completed in {0:N1}s." -f ((Get-Date) - $started).TotalSeconds)
  Write-Step "Desktop release ready: $OutputRoot"
}

Assert-VersionConsistency
if ($ValidateOnly) {
  Write-Step "Version sources are consistent at $Version."
  return
}
Invoke-Checks
Stage-Resources
Invoke-TauriBuild
Publish-Artifacts
