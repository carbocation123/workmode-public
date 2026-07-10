param(
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$App = Join-Path $Root "app"
$Backend = Join-Path $App "backend"
$Config = Join-Path $Root "config"
$Data = Join-Path $Root "data"
$Logs = Join-Path $Root "logs"
$Run = Join-Path $Root ".run"
$EnvFile = Join-Path $Config ".env"
$EnvExample = Join-Path $Config ".env.example"
$BackendPidFile = Join-Path $Run "backend.pid"
$LauncherLog = Join-Path $Logs "launcher.log"

New-Item -ItemType Directory -Force $Config, $Data, $Logs, $Run | Out-Null

function Write-Step {
  param([string]$Message)
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Write-Host $line -ForegroundColor Cyan
  Add-Content -LiteralPath $LauncherLog -Value $line -Encoding UTF8
}

function Write-Warn {
  param([string]$Message)
  $line = "[{0}] WARN {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Write-Host $line -ForegroundColor Yellow
  Add-Content -LiteralPath $LauncherLog -Value $line -Encoding UTF8
}

function Load-DotEnv {
  if (-not (Test-Path $EnvFile) -and (Test-Path $EnvExample)) {
    Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
    Write-Warn "Created config\.env from config\.env.example. Fill WORKMODE_MODEL_API_KEY before chat."
  }
  if (-not (Test-Path $EnvFile)) {
    return
  }
  Get-Content -LiteralPath $EnvFile -Encoding UTF8 | ForEach-Object {
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

function Repair-PortableVenv {
  $venv = Join-Path $Root "runtime\backend-venv"
  $base = Join-Path $Root "runtime\python-base"
  $cfg = Join-Path $venv "pyvenv.cfg"
  if (-not (Test-Path $cfg) -or -not (Test-Path (Join-Path $base "python.exe"))) {
    return
  }

  $basePython = Join-Path $base "python.exe"
  $lines = Get-Content -LiteralPath $cfg -Encoding UTF8
  $updated = foreach ($line in $lines) {
    if ($line -match "^\s*home\s*=") {
      "home = $base"
    } elseif ($line -match "^\s*executable\s*=") {
      "executable = $basePython"
    } elseif ($line -match "^\s*command\s*=") {
      "command = $basePython -m venv $venv"
    } else {
      $line
    }
  }
  Set-Content -LiteralPath $cfg -Value $updated -Encoding UTF8
}

function Resolve-Python {
  Repair-PortableVenv
  $venvPython = Join-Path $Root "runtime\backend-venv\Scripts\python.exe"
  if (Test-Path $venvPython) {
    return $venvPython
  }
  $embeddedPython = Join-Path $Root "runtime\python\python.exe"
  if (Test-Path $embeddedPython) {
    return $embeddedPython
  }
  throw "Bundled Python runtime was not found. Rebuild the release package with scripts\build-release.ps1."
}

function Get-RunningProcessFromPidFile {
  if (-not (Test-Path $BackendPidFile)) { return $null }
  $raw = (Get-Content -LiteralPath $BackendPidFile -Encoding UTF8 -Raw).Trim()
  if (-not $raw) { return $null }
  try {
    return Get-Process -Id ([int]$raw) -ErrorAction Stop
  } catch {
    Remove-Item -LiteralPath $BackendPidFile -Force -ErrorAction SilentlyContinue
    return $null
  }
}

function Start-Backend {
  param(
    [string]$Python,
    [string]$HostValue,
    [string]$PortValue
  )
  $running = Get-RunningProcessFromPidFile
  if ($running) {
    Write-Step "Backend already running with PID $($running.Id)"
    return
  }

  if (-not (Test-Path (Join-Path $Backend "app\main.py"))) {
    throw "Backend app is missing under app\backend."
  }
  if (-not (Test-Path (Join-Path $App "frontend-dist\index.html"))) {
    throw "Frontend dist is missing under app\frontend-dist."
  }

  $outLog = Join-Path $Logs "backend.out.log"
  $errLog = Join-Path $Logs "backend.err.log"
  Write-Step "Starting backend on http://$HostValue`:$PortValue"
  $process = Start-Process `
    -FilePath $Python `
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
  for ($i = 0; $i -lt 60; $i++) {
    try {
      $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -eq 200) {
        Write-Step "Backend health check passed"
        return
      }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  throw "Backend did not become healthy. Check logs\backend.err.log."
}

try {
  Set-Content -LiteralPath $LauncherLog -Value "[launcher] Workmode Public release start" -Encoding UTF8

  [Environment]::SetEnvironmentVariable("WORKMODE_ENV_FILE", $EnvFile, "Process")
  Load-DotEnv
  if (-not (Get-EnvOrDefault "WORKMODE_PUBLIC_DATA_DIR" "")) {
    [Environment]::SetEnvironmentVariable("WORKMODE_PUBLIC_DATA_DIR", $Data, "Process")
  }
  if (-not (Get-EnvOrDefault "WORKMODE_STATIC_DIR" "")) {
    [Environment]::SetEnvironmentVariable("WORKMODE_STATIC_DIR", (Join-Path $App "frontend-dist"), "Process")
  }

  $versionFile = Join-Path $App "version.json"
  if ((-not (Get-EnvOrDefault "WORKMODE_APP_VERSION" "")) -and (Test-Path $versionFile)) {
    try {
      $version = (Get-Content -LiteralPath $versionFile -Encoding UTF8 -Raw | ConvertFrom-Json).version
      if ($version) {
        [Environment]::SetEnvironmentVariable("WORKMODE_APP_VERSION", $version, "Process")
      }
    } catch {
      Write-Warn "Could not read app\version.json."
    }
  }

  $hostValue = Get-EnvOrDefault "WORKMODE_HOST" "127.0.0.1"
  $portValue = Get-EnvOrDefault "WORKMODE_PORT" "8765"
  if ($hostValue -ne "127.0.0.1" -and $hostValue -ne "localhost") {
    Write-Warn "WORKMODE_HOST is '$hostValue'. For desktop distribution, prefer 127.0.0.1."
  }
  if (-not (Get-EnvOrDefault "WORKMODE_MODEL_API_KEY" "")) {
    Write-Warn "WORKMODE_MODEL_API_KEY is empty. Configure it in config\.env or the UI settings."
  }

  $python = Resolve-Python
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
