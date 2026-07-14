param(
  [switch]$NoInstall,
  [switch]$NoBrowser,
  [switch]$RebuildFrontend
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Logs = Join-Path $Root "logs"
$Run = Join-Path $Root ".run"
$LauncherLog = Join-Path $Logs "launcher.log"
$BackendPidFile = Join-Path $Run "backend.pid"
$ExpectedLiteratureContractVersion = 3

New-Item -ItemType Directory -Force $Logs, $Run | Out-Null

function Write-Step {
  param([string]$Message)
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Write-Host $line -ForegroundColor Cyan
  Add-Content -Path $LauncherLog -Value $line -Encoding UTF8
}

function Write-Warn {
  param([string]$Message)
  $line = "[{0}] WARN {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Write-Host $line -ForegroundColor Yellow
  Add-Content -Path $LauncherLog -Value $line -Encoding UTF8
}

function Load-DotEnv {
  $envPath = Join-Path $Root ".env"
  $examplePath = Join-Path $Root ".env.example"
  if (-not (Test-Path $envPath) -and (Test-Path $examplePath)) {
    Copy-Item -LiteralPath $examplePath -Destination $envPath
    Write-Warn "Created .env from .env.example. Fill WORKMODE_MODEL_API_KEY for chat."
  }
  if (-not (Test-Path $envPath)) {
    return
  }
  Get-Content -LiteralPath $envPath -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
      return
    }
    $name, $value = $line -split "=", 2
    $name = $name.Trim()
    $value = $value.Trim().Trim('"').Trim("'")
    if ($name) {
      [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
  }
}

function Get-EnvOrDefault {
  param(
    [string]$Name,
    [string]$Default
  )
  $value = [Environment]::GetEnvironmentVariable($Name, "Process")
  if ($value) { return $value }
  return $Default
}

function Normalize-ProcessPathEnvironment {
  # Some launch environments provide both Path and PATH. Windows resolves the
  # names case-insensitively, but Windows PowerShell Start-Process rejects the
  # duplicated environment block before the child process can start.
  $pathValue = [Environment]::GetEnvironmentVariable("Path", "Process")
  if ([string]::IsNullOrWhiteSpace($pathValue)) {
    return
  }
  [Environment]::SetEnvironmentVariable("PATH", $null, "Process")
  [Environment]::SetEnvironmentVariable("Path", $pathValue, "Process")
}

function Invoke-SystemPython {
  param([string[]]$Arguments)
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    & $py.Source -3 @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "py -3 $($Arguments -join ' ') failed with exit code $LASTEXITCODE" }
    return
  }
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    & $python.Source @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "python $($Arguments -join ' ') failed with exit code $LASTEXITCODE" }
    return
  }
  throw "Python was not found. Install Python 3.11+ and retry."
}

function Test-PythonInterpreter {
  param([string]$Path)
  if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return $false
  }
  try {
    & $Path -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function Ensure-Backend {
  $venvRoot = Join-Path $Backend ".venv"
  $venvPython = Join-Path $venvRoot "Scripts\python.exe"
  if ((Test-Path -LiteralPath $venvRoot) -and -not (Test-PythonInterpreter -Path $venvPython)) {
    if ($NoInstall) { throw "Backend virtualenv is broken and -NoInstall was set." }
    $resolvedRoot = [IO.Path]::GetFullPath($Root)
    $resolvedVenv = [IO.Path]::GetFullPath($venvRoot)
    $expectedVenv = [IO.Path]::GetFullPath((Join-Path $Root "backend\.venv"))
    $rootPrefix = $resolvedRoot.TrimEnd('\') + '\'
    if (
      -not $resolvedVenv.Equals($expectedVenv, [StringComparison]::OrdinalIgnoreCase) -or
      -not $resolvedVenv.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)
    ) {
      throw "Refusing to remove unexpected virtualenv path: $resolvedVenv"
    }
    Write-Warn "Backend virtualenv is not executable; rebuilding it."
    Remove-Item -LiteralPath $resolvedVenv -Recurse -Force
  }
  if (-not (Test-Path $venvPython)) {
    if ($NoInstall) { throw "Backend virtualenv is missing and -NoInstall was set." }
    Write-Step "Creating backend virtualenv"
    Invoke-SystemPython -Arguments @("-m", "venv", $venvRoot)
  }
  if (-not (Test-PythonInterpreter -Path $venvPython)) {
    throw "Backend Python is not executable after virtualenv setup: $venvPython"
  }

  $requirements = Join-Path $Backend "requirements.txt"
  $stamp = Join-Path $Backend ".venv\.requirements.sha256"
  $hash = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash
  $installedHash = if (Test-Path $stamp) { (Get-Content -LiteralPath $stamp -Encoding UTF8 -Raw).Trim() } else { "" }

  if ($hash -ne $installedHash) {
    if ($NoInstall) { throw "Backend dependencies are not installed and -NoInstall was set." }
    Write-Step "Installing backend dependencies"
    & $venvPython -m pip install --upgrade pip | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
    & $venvPython -m pip install -r $requirements | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    Set-Content -LiteralPath $stamp -Value $hash -Encoding UTF8
  }
  return $venvPython
}

function Ensure-Frontend {
  $npm = Get-Command npm -ErrorAction SilentlyContinue
  if (-not $npm) {
    throw "npm was not found. Install Node.js 20+ and retry."
  }

  $nodeModules = Join-Path $Frontend "node_modules"
  $packageJson = Join-Path $Frontend "package.json"
  $packageStamp = Join-Path $nodeModules ".package.sha256"
  $packageHash = (Get-FileHash -LiteralPath $packageJson -Algorithm SHA256).Hash
  $installedHash = if (Test-Path $packageStamp) { (Get-Content -LiteralPath $packageStamp -Encoding UTF8 -Raw).Trim() } else { "" }

  if ((-not (Test-Path $nodeModules)) -or $packageHash -ne $installedHash) {
    if ($NoInstall) { throw "Frontend dependencies are not installed and -NoInstall was set." }
    Write-Step "Installing frontend dependencies"
    Push-Location $Frontend
    try {
      & $npm.Source install
      if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    } finally {
      Pop-Location
    }
    Set-Content -LiteralPath $packageStamp -Value $packageHash -Encoding UTF8
  }

  $distIndex = Join-Path $Frontend "dist\index.html"
  $sourceAchievementStamp = Join-Path $Frontend "dist\.source-achievements"
  if ($RebuildFrontend -or -not (Test-Path $distIndex) -or -not (Test-Path $sourceAchievementStamp)) {
    Write-Step "Building frontend"
    Push-Location $Frontend
    $previousSourceAchievements = $env:VITE_WORKMODE_SOURCE_ACHIEVEMENTS
    try {
      $env:VITE_WORKMODE_SOURCE_ACHIEVEMENTS = "1"
      & $npm.Source run build
      if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
      Set-Content -LiteralPath $sourceAchievementStamp -Value "source-only achievements enabled" -Encoding UTF8
    } finally {
      $env:VITE_WORKMODE_SOURCE_ACHIEVEMENTS = $previousSourceAchievements
      Pop-Location
    }
  }
}

function Get-RunningProcessFromPidFile {
  param([string]$PidFile)
  if (-not (Test-Path $PidFile)) { return $null }
  $raw = (Get-Content -LiteralPath $PidFile -Encoding UTF8 -Raw).Trim()
  if (-not $raw) { return $null }
  try {
    return Get-Process -Id ([int]$raw) -ErrorAction Stop
  } catch {
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    return $null
  }
}

function Start-Backend {
  param(
    [string]$Python,
    [string]$HostValue,
    [string]$PortValue
  )
  $running = Get-RunningProcessFromPidFile $BackendPidFile
  if ($running) {
    Write-Step "Backend already running with PID $($running.Id)"
    return
  }

  if (-not (Test-PythonInterpreter -Path $Python)) {
    throw "Backend Python is not executable: $Python"
  }
  $resolvedPython = (Resolve-Path -LiteralPath $Python).Path

  $outLog = Join-Path $Logs "backend.out.log"
  $errLog = Join-Path $Logs "backend.err.log"
  Write-Step "Starting backend with $resolvedPython on http://$HostValue`:$PortValue"
  $process = Start-Process `
    -FilePath $resolvedPython `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", $HostValue, "--port", $PortValue) `
    -WorkingDirectory $Backend `
    -WindowStyle Hidden `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -PassThru
  Set-Content -LiteralPath $BackendPidFile -Value $process.Id -Encoding UTF8
}

function Wait-Backend {
  param(
    [string]$HostValue,
    [string]$PortValue
  )
  $healthHost = if ($HostValue -eq "0.0.0.0") { "127.0.0.1" } else { $HostValue }
  $healthUrl = "http://$healthHost`:$PortValue/api/health"
  $incompatiblePrefix = "incompatible Workmode backend"
  for ($i = 0; $i -lt 60; $i++) {
    try {
      $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -eq 200) {
        try {
          $health = $response.Content | ConvertFrom-Json
        } catch {
          throw "$incompatiblePrefix is already using $healthHost`:$PortValue (invalid health response)."
        }
        $contractVersion = [int]($health.literature_project_contract_version)
        if ($health.app -ne "workmode-public" -or $contractVersion -ne $ExpectedLiteratureContractVersion) {
          throw "$incompatiblePrefix is already using $healthHost`:$PortValue (literature contract $contractVersion; expected $ExpectedLiteratureContractVersion). Stop the old source backend and retry."
        }
        Write-Step "Backend health check passed"
        return
      }
    } catch {
      if ($_.Exception.Message.StartsWith($incompatiblePrefix)) {
        throw
      }
      Start-Sleep -Milliseconds 500
    }
  }
  throw "Backend did not become healthy. Check logs\backend.err.log."
}

try {
  Set-Content -LiteralPath $LauncherLog -Value "[launcher] Workmode Public start" -Encoding UTF8
  Load-DotEnv
  Normalize-ProcessPathEnvironment

  $hostValue = Get-EnvOrDefault "WORKMODE_HOST" "127.0.0.1"
  $portValue = Get-EnvOrDefault "WORKMODE_PORT" "8765"
  if ($hostValue -ne "127.0.0.1" -and $hostValue -ne "localhost") {
    Write-Warn "WORKMODE_HOST is '$hostValue'. For distribution, prefer 127.0.0.1."
  }
  if (-not (Get-EnvOrDefault "WORKMODE_MODEL_API_KEY" "")) {
    Write-Warn "WORKMODE_MODEL_API_KEY is empty. The UI can start, but chat will fail until configured."
  }

  $python = Ensure-Backend
  Ensure-Frontend
  Start-Backend -Python $python -HostValue $hostValue -PortValue $portValue
  Wait-Backend -HostValue $hostValue -PortValue $portValue

  $browserHost = if ($hostValue -eq "0.0.0.0") { "127.0.0.1" } else { $hostValue }
  $appUrl = "http://$browserHost`:$portValue"
  Write-Step "Workmode Public is ready: $appUrl"
  if (-not $NoBrowser) {
    Start-Process $appUrl
  }
} catch {
  Write-Warn ($_.Exception.Message)
  throw
}
