$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Root "frontend"

Set-Location $Frontend

if (-not (Test-Path "node_modules")) {
  Write-Host "Frontend node_modules is missing. Run first:" -ForegroundColor Yellow
  Write-Host "  cd frontend"
  Write-Host "  npm install"
  exit 1
}

npm run dev

