$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

Set-Location $Root

if (Test-Path ".env") {
  Get-Content ".env" | ForEach-Object {
    if ($_ -match "^\s*#" -or $_ -notmatch "=") { return }
    $name, $value = $_ -split "=", 2
    if ($name.Trim()) {
      [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), "Process")
    }
  }
}

if (-not (Test-Path $Python)) {
  Write-Host "Backend virtualenv is missing. Create it with:" -ForegroundColor Yellow
  Write-Host "  cd backend"
  Write-Host "  python -m venv .venv"
  Write-Host "  .\.venv\Scripts\python -m pip install -r requirements.txt"
  exit 1
}

Set-Location $Backend
$HostValue = $env:WORKMODE_HOST
if (-not $HostValue) { $HostValue = "127.0.0.1" }
$PortValue = $env:WORKMODE_PORT
if (-not $PortValue) { $PortValue = "8765" }

& $Python -m uvicorn app.main:app --host $HostValue --port $PortValue
