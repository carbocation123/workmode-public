param(
  [string]$OldRoot,
  [switch]$NoStart,
  [switch]$NoPause
)

$ErrorActionPreference = "Stop"

$NewRoot = Split-Path -Parent $PSScriptRoot
$Logs = Join-Path $NewRoot "logs"
$BackupRoot = Join-Path $NewRoot "migration-backups"
$MigrationLog = Join-Path $Logs "migration.log"

New-Item -ItemType Directory -Force $Logs, $BackupRoot | Out-Null

function Write-Step {
  param([string]$Message)
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Write-Host $line -ForegroundColor Cyan
  Add-Content -LiteralPath $MigrationLog -Value $line -Encoding UTF8
}

function Write-Warn {
  param([string]$Message)
  $line = "[{0}] WARN {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Write-Host $line -ForegroundColor Yellow
  Add-Content -LiteralPath $MigrationLog -Value $line -Encoding UTF8
}

function Resolve-ExistingDirectory {
  param([string]$Path)
  if (-not $Path) { return $null }
  $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
  if (-not (Test-Path -LiteralPath $resolved -PathType Container)) {
    throw "Not a directory: $resolved"
  }
  return [System.IO.Path]::GetFullPath($resolved)
}

function Select-OldFolder {
  try {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "Select the OLD Workmode Public folder. It should contain WorkmodePublic.cmd."
    $dialog.ShowNewFolderButton = $false
    $result = $dialog.ShowDialog()
    if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
      return $dialog.SelectedPath
    }
    return $null
  } catch {
    Write-Warn "Folder picker is unavailable. Falling back to manual path input."
    return Read-Host "Enter the full path of the OLD Workmode Public folder"
  }
}

function Assert-InsideRoot {
  param(
    [string]$Child,
    [string]$Root,
    [string]$Label
  )
  $childFull = [System.IO.Path]::GetFullPath($Child)
  $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
  if (-not $childFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "$Label is outside the new package directory. Refusing to operate: $childFull"
  }
}

function Test-WorkmodeRoot {
  param([string]$Root)
  $hasLauncher = Test-Path -LiteralPath (Join-Path $Root "WorkmodePublic.cmd")
  $hasBackend = Test-Path -LiteralPath (Join-Path $Root "app\backend\app\main.py")
  $hasFrontend = Test-Path -LiteralPath (Join-Path $Root "app\frontend-dist\index.html")
  return ($hasLauncher -and $hasBackend -and $hasFrontend)
}

function Stop-OldBackend {
  param([string]$Root)
  $stopScript = Join-Path $Root "scripts\stop-release.ps1"
  if (Test-Path -LiteralPath $stopScript) {
    Write-Step "Stopping old backend."
    & $stopScript
    return
  }

  $pidFile = Join-Path $Root ".run\backend.pid"
  if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Step "No old backend pid record was found."
    return
  }
  $raw = (Get-Content -LiteralPath $pidFile -Encoding UTF8 -Raw).Trim()
  if (-not $raw) { return }
  try {
    $process = Get-Process -Id ([int]$raw) -ErrorAction Stop
    Stop-Process -Id $process.Id -Force
    Write-Step "Stopped old backend PID $($process.Id)."
  } catch {
    Write-Step "Old backend process was not found. Continuing."
  }
}

function Backup-NewPathIfNeeded {
  param(
    [string]$Path,
    [string]$Name
  )
  if (-not (Test-Path -LiteralPath $Path)) { return }
  Assert-InsideRoot -Child $Path -Root $NewRoot -Label $Name
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $backup = Join-Path $BackupRoot "$Name-$stamp"
  Write-Step "Backing up existing $Name in the new package to migration-backups\$Name-$stamp."
  Move-Item -LiteralPath $Path -Destination $backup
}

function Copy-DataDirectory {
  param(
    [string]$OldRoot,
    [string]$NewRoot
  )
  $oldData = Join-Path $OldRoot "data"
  if (-not (Test-Path -LiteralPath $oldData -PathType Container)) {
    Write-Warn "Old package has no data directory. Skipping data migration."
    return
  }
  $newData = Join-Path $NewRoot "data"
  Backup-NewPathIfNeeded -Path $newData -Name "new-data"
  Write-Step "Migrating user data directory."
  Copy-Item -LiteralPath $oldData -Destination $newData -Recurse
}

function Copy-EnvFile {
  param(
    [string]$OldRoot,
    [string]$NewRoot
  )
  $oldEnv = Join-Path $OldRoot "config\.env"
  if (-not (Test-Path -LiteralPath $oldEnv)) {
    $oldEnv = Join-Path $OldRoot ".env"
  }
  if (-not (Test-Path -LiteralPath $oldEnv)) {
    Write-Warn "Old package has no config\.env. The new package will create one from .env.example on first launch."
    return
  }

  $newConfig = Join-Path $NewRoot "config"
  New-Item -ItemType Directory -Force $newConfig | Out-Null
  $newEnv = Join-Path $newConfig ".env"
  if (Test-Path -LiteralPath $newEnv) {
    Backup-NewPathIfNeeded -Path $newEnv -Name "new-env"
  }
  Write-Step "Migrating model config config\.env."
  Copy-Item -LiteralPath $oldEnv -Destination $newEnv -Force
}

function Write-MigrationRecord {
  param(
    [string]$OldRoot,
    [string]$NewRoot
  )
  $record = [ordered]@{
    migrated_at = (Get-Date).ToUniversalTime().ToString("o")
    old_root = $OldRoot
    new_root = $NewRoot
    app = "workmode-public"
  }
  $recordPath = Join-Path $Logs "last-migration.json"
  $record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $recordPath -Encoding UTF8
}

try {
  Set-Content -LiteralPath $MigrationLog -Value "[migration] Workmode Public existing-install upgrade" -Encoding UTF8
  $NewRoot = Resolve-ExistingDirectory $NewRoot

  if (-not $OldRoot) {
    $OldRoot = Select-OldFolder
  }
  if (-not $OldRoot) {
    throw "No old Workmode Public folder was selected."
  }
  $OldRoot = Resolve-ExistingDirectory $OldRoot

  if ($OldRoot.TrimEnd("\", "/") -eq $NewRoot.TrimEnd("\", "/")) {
    throw "Old folder and new folder cannot be the same. Run this script from the new extracted package and choose the old package folder."
  }
  if (-not (Test-WorkmodeRoot $OldRoot)) {
    throw "Selected old folder does not look like Workmode Public: $OldRoot"
  }
  if (-not (Test-WorkmodeRoot $NewRoot)) {
    throw "Current new package directory is incomplete: $NewRoot"
  }

  Write-Step "Old package: $OldRoot"
  Write-Step "New package: $NewRoot"
  Stop-OldBackend -Root $OldRoot
  Copy-EnvFile -OldRoot $OldRoot -NewRoot $NewRoot
  Copy-DataDirectory -OldRoot $OldRoot -NewRoot $NewRoot
  Write-MigrationRecord -OldRoot $OldRoot -NewRoot $NewRoot

  Write-Host ""
  Write-Host "Upgrade migration completed." -ForegroundColor Green
  Write-Host "Please verify the new app, projects, sessions, and API settings first. After verification, you can delete the old folder:"
  Write-Host $OldRoot -ForegroundColor Yellow
  Write-Host ""

  if (-not $NoStart) {
    $startScript = Join-Path $PSScriptRoot "start-release.ps1"
    if (Test-Path -LiteralPath $startScript) {
      Write-Step "Starting the new app."
      & $startScript
    }
  }
} catch {
  Write-Host ""
  Write-Host "Upgrade failed: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "The old folder was not deleted. You can keep using the old version."
  throw
} finally {
  if (-not $NoPause) {
    Write-Host ""
    Read-Host "Press Enter to close this window"
  }
}
