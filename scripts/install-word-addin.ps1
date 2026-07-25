param(
  [string]$ManifestPath
)

$ErrorActionPreference = "Stop"
$AddinId = "0f621bd7-1e31-47e8-8a9f-7d61fdac8805"
$DeveloperRoot = "HKCU:\Software\Microsoft\Office\16.0\WEF\Developer"
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))

if (-not $ManifestPath) {
  $ManifestPath = Join-Path $Root "frontend\word-addin\manifest.xml"
}
$ManifestPath = [System.IO.Path]::GetFullPath($ManifestPath)
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
  throw "Word add-in manifest was not found: $ManifestPath"
}

$Destination = Join-Path $env:LOCALAPPDATA "WorkmodePublic\word-addin"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$InstalledManifest = Join-Path $Destination "manifest.xml"
Copy-Item -LiteralPath $ManifestPath -Destination $InstalledManifest -Force

New-Item -Path $DeveloperRoot -Force | Out-Null
New-ItemProperty -Path $DeveloperRoot -Name $AddinId -PropertyType String -Value $InstalledManifest -Force | Out-Null
Remove-ItemProperty -LiteralPath $DeveloperRoot -Name "{$AddinId}" -ErrorAction SilentlyContinue
$LegacyKey = Join-Path $DeveloperRoot "OutlookSideloadManifestPath"
if ((Test-Path -LiteralPath $LegacyKey) -and (Get-Item -LiteralPath $LegacyKey).GetValue("") -eq $InstalledManifest) {
  Remove-Item -LiteralPath $LegacyKey -Recurse -Force
}

Write-Host "Workmode Word add-in is sideloaded for the current Windows user."
Write-Host "Keep Workmode running, close every Word window, then reopen Word."
