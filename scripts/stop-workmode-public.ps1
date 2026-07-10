$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Run = Join-Path $Root ".run"
$Logs = Join-Path $Root "logs"
$BackendPidFile = Join-Path $Run "backend.pid"

New-Item -ItemType Directory -Force $Logs | Out-Null

function Stop-PidFile {
  param(
    [string]$Name,
    [string]$PidFile
  )
  if (-not (Test-Path $PidFile)) {
    Write-Host "$Name is not running."
    return
  }
  $raw = (Get-Content -LiteralPath $PidFile -Encoding UTF8 -Raw).Trim()
  if (-not $raw) {
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "$Name pid file was empty."
    return
  }
  try {
    $process = Get-Process -Id ([int]$raw) -ErrorAction Stop
    Stop-Process -Id $process.Id -Force
    Write-Host "Stopped $Name with PID $($process.Id)."
  } catch {
    Write-Host "$Name process was not found."
  } finally {
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
  }
}

Stop-PidFile -Name "Workmode Public backend" -PidFile $BackendPidFile

