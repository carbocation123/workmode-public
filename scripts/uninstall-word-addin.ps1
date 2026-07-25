$ErrorActionPreference = "Stop"
$AddinId = "0f621bd7-1e31-47e8-8a9f-7d61fdac8805"
$DeveloperRoot = "HKCU:\Software\Microsoft\Office\16.0\WEF\Developer"
$Destination = Join-Path $env:LOCALAPPDATA "WorkmodePublic\word-addin"

if (Test-Path -LiteralPath $DeveloperRoot) {
  Remove-ItemProperty -LiteralPath $DeveloperRoot -Name $AddinId -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath (Join-Path $DeveloperRoot $AddinId) -Recurse -Force -ErrorAction SilentlyContinue
  $LegacyKey = Join-Path $DeveloperRoot "OutlookSideloadManifestPath"
  if ((Test-Path -LiteralPath $LegacyKey) -and (Get-Item -LiteralPath $LegacyKey).GetValue("") -eq (Join-Path $Destination "manifest.xml")) {
    Remove-Item -LiteralPath $LegacyKey -Recurse -Force
  }
}

if (Test-Path -LiteralPath $Destination) {
  Remove-Item -LiteralPath $Destination -Recurse -Force
}

Write-Host "Workmode Word add-in registration was removed."
Write-Host "Close every Word window and reopen Word to refresh the ribbon."
