$ErrorActionPreference = "Stop"
$DemoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $DemoRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$BackendPython = Join-Path $BackendRoot ".venv\Scripts\python.exe"
$BackendProcess = $null
$RequiredLiteratureContractVersion = 1

function Get-WorkmodeHealth {
  param([int]$Port)
  try {
    return Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
  }
  catch {
    return $null
  }
}

function Test-CompatibleWorkmodeBackend {
  param($Health)
  return [bool](
    $Health `
    -and $Health.status -eq "ok" `
    -and [int]($Health.literature_project_contract_version) -ge $RequiredLiteratureContractVersion
  )
}

function Test-PortAvailable {
  param([int]$Port)
  $listener = $null
  try {
    $listener = [System.Net.Sockets.TcpListener]::new(
      [System.Net.IPAddress]::Loopback,
      $Port
    )
    $listener.Start()
    return $true
  }
  catch {
    return $false
  }
  finally {
    if ($listener) { $listener.Stop() }
  }
}

function Find-AvailablePort {
  param([int]$StartPort)
  foreach ($port in $StartPort..($StartPort + 50)) {
    if (Test-PortAvailable -Port $port) { return $port }
  }
  throw "No available loopback port found from $StartPort."
}

function Get-OrCreate-LiteratureProject {
  param([int]$Port)
  $apiRoot = "http://127.0.0.1:$Port/api"
  $projects = Invoke-RestMethod -Uri "$apiRoot/work/projects" -TimeoutSec 5
  $existing = @($projects.projects) | Where-Object { $_.project_type -eq "literature-library" } | Select-Object -First 1
  if ($existing) { return $existing }

  $projectRoot = Join-Path $RepoRoot ".run\literature-project-dev"
  $body = @{
    name = "Literature development library"
    root_path = $projectRoot
  } | ConvertTo-Json
  $created = Invoke-RestMethod `
    -Uri "$apiRoot/work/literature-projects" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body `
    -TimeoutSec 10
  return $created.project
}

try {
  $BackendPort = 8765
  $health = Get-WorkmodeHealth -Port $BackendPort
  if (-not (Test-CompatibleWorkmodeBackend -Health $health)) {
    if (-not (Test-Path -LiteralPath $BackendPython)) {
      throw "Backend environment is missing: $BackendPython"
    }
    if ($health) {
      Write-Warning "Port 8765 is running an incompatible Workmode backend. Starting this repository backend on another port."
    }
    $BackendPort = Find-AvailablePort -StartPort 8766
    $env:PYTHONPATH = $BackendRoot
    $BackendProcess = Start-Process -FilePath $BackendPython `
      -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") `
      -WorkingDirectory $BackendRoot -WindowStyle Hidden -PassThru
    $deadline = (Get-Date).AddSeconds(20)
    while (-not (Test-CompatibleWorkmodeBackend -Health (Get-WorkmodeHealth -Port $BackendPort))) {
      if ($BackendProcess.HasExited) { throw "Workmode backend exited during startup." }
      if ((Get-Date) -ge $deadline) { throw "Workmode backend did not become ready within 20 seconds." }
      Start-Sleep -Milliseconds 400
    }
  }

  $project = Get-OrCreate-LiteratureProject -Port $BackendPort
  $FrontendPort = Find-AvailablePort -StartPort 5176
  $env:VITE_WORKMODE_API_BASE = "http://127.0.0.1:$BackendPort/api"
  $env:VITE_LITERATURE_PROJECT_SLUG = $project.slug
  Write-Host "Workmode backend: $env:VITE_WORKMODE_API_BASE"
  Write-Host "Literature project: $($project.name) [$($project.slug)]"
  Write-Host "Literature frontend: http://127.0.0.1:$FrontendPort/"
  Start-Process "http://127.0.0.1:$FrontendPort/"
  Push-Location $DemoRoot
  try {
    & npm run dev -- --port $FrontendPort --strictPort
    if ($LASTEXITCODE -ne 0) { throw "Literature frontend failed with exit code $LASTEXITCODE." }
  }
  finally {
    Pop-Location
  }
}
finally {
  if ($BackendProcess -and -not $BackendProcess.HasExited) {
    Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
  }
}
