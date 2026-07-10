param(
  [Parameter(Mandatory = $true)]
  [string]$Version,
  [string]$Root
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if ($Version -notmatch '^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$') {
  throw "Version must be SemVer such as 1.2.3 or 1.2.3-beta.1."
}
if (-not $Root) {
  $Root = Split-Path -Parent $PSScriptRoot
}
$Root = [System.IO.Path]::GetFullPath($Root)

$paths = [ordered]@{
  version = Join-Path $Root "VERSION"
  frontendPackage = Join-Path $Root "frontend\package.json"
  frontendLock = Join-Path $Root "frontend\package-lock.json"
  desktopPackage = Join-Path $Root "desktop\package.json"
  desktopLock = Join-Path $Root "desktop\package-lock.json"
  tauri = Join-Path $Root "desktop\src-tauri\tauri.conf.json"
  cargo = Join-Path $Root "desktop\src-tauri\Cargo.toml"
  cargoLock = Join-Path $Root "desktop\src-tauri\Cargo.lock"
}
foreach ($path in $paths.Values) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required version source is missing: $path"
  }
}

function Replace-Required {
  param(
    [string]$Text,
    [string]$Pattern,
    [string]$Label
  )
  $regex = New-Object System.Text.RegularExpressions.Regex(
    $Pattern,
    [System.Text.RegularExpressions.RegexOptions]::Multiline
  )
  if (-not $regex.IsMatch($Text)) {
    throw "Version field was not found in $Label"
  }
  $evaluator = [System.Text.RegularExpressions.MatchEvaluator]{
    param($match)
    $match.Groups[1].Value + $Version + $match.Groups[2].Value
  }
  return $regex.Replace($Text, $evaluator, 1)
}

$updates = [ordered]@{}
$updates[$paths.version] = "$Version`n"

foreach ($path in @($paths.frontendPackage, $paths.desktopPackage)) {
  $text = Get-Content -LiteralPath $path -Encoding UTF8 -Raw
  $updates[$path] = Replace-Required $text '("version"\s*:\s*")[^"]+("\s*,?)' $path
}

foreach ($path in @($paths.frontendLock, $paths.desktopLock)) {
  $text = Get-Content -LiteralPath $path -Encoding UTF8 -Raw
  $text = Replace-Required $text '("version"\s*:\s*")[^"]+("\s*,?)' "$path root"
  $text = Replace-Required $text '(?s)("packages"\s*:\s*\{\s*""\s*:\s*\{.*?"version"\s*:\s*")[^"]+("\s*,?)' "$path package root"
  $updates[$path] = $text
}

$tauri = Get-Content -LiteralPath $paths.tauri -Encoding UTF8 -Raw
$updates[$paths.tauri] = Replace-Required $tauri '("version"\s*:\s*")[^"]+("\s*,?)' $paths.tauri

$cargo = Get-Content -LiteralPath $paths.cargo -Encoding UTF8 -Raw
$updates[$paths.cargo] = Replace-Required $cargo '(?s)(\[package\].*?^version\s*=\s*")[^"]+("\s*$)' $paths.cargo

$cargoLock = Get-Content -LiteralPath $paths.cargoLock -Encoding UTF8 -Raw
$updates[$paths.cargoLock] = Replace-Required $cargoLock '(?s)(\[\[package\]\]\s*\r?\nname\s*=\s*"workmode-public"\s*\r?\nversion\s*=\s*")[^"]+("\s*$)' $paths.cargoLock

foreach ($jsonPath in @($paths.frontendPackage, $paths.desktopPackage, $paths.tauri)) {
  $updates[$jsonPath] | ConvertFrom-Json | Out-Null
}
foreach ($entry in $updates.GetEnumerator()) {
  [System.IO.File]::WriteAllText($entry.Key, $entry.Value, $Utf8NoBom)
}

Write-Host "Synchronized Workmode Public version to $Version across $($updates.Count) files."
