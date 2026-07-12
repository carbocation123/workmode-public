param(
  [string[]]$SkinId,
  [string]$SourceRoot,
  [string]$PackageRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$PrivateLibraryRoot = Join-Path $Root "local-reference\reward-skin-library"
if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
  $SourceRoot = Join-Path $PrivateLibraryRoot "sources"
} elseif (-not [System.IO.Path]::IsPathRooted($SourceRoot)) {
  $SourceRoot = Join-Path $Root $SourceRoot
}
if ([string]::IsNullOrWhiteSpace($PackageRoot)) {
  $PackageRoot = Join-Path $PrivateLibraryRoot "packages"
} elseif (-not [System.IO.Path]::IsPathRooted($PackageRoot)) {
  $PackageRoot = Join-Path $Root $PackageRoot
}
$SourceRoot = [System.IO.Path]::GetFullPath($SourceRoot)
$PackageRoot = [System.IO.Path]::GetFullPath($PackageRoot)
$Signer = Join-Path $Root "scripts\official-skin.mjs"

function Assert-Inside {
  param([string]$Child, [string]$Parent)
  $childFull = [System.IO.Path]::GetFullPath($Child)
  $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
  if (-not $childFull.StartsWith($parentFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing path outside the skin source: $childFull"
  }
  return $childFull
}

if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
  throw "Private skin source directory is missing: $SourceRoot. Restore the ignored local reward library or pass -SourceRoot explicitly."
}
if (-not (Test-Path -LiteralPath $Signer -PathType Leaf)) {
  throw "Skin signer is missing: $Signer"
}
New-Item -ItemType Directory -Force -Path $PackageRoot | Out-Null

$sources = if ($SkinId -and $SkinId.Count -gt 0) {
  foreach ($id in $SkinId) {
    $path = Assert-Inside -Child (Join-Path $SourceRoot $id) -Parent $SourceRoot
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
      throw "Unknown skin source: $id"
    }
    Get-Item -LiteralPath $path
  }
} else {
  Get-ChildItem -LiteralPath $SourceRoot -Directory | Sort-Object Name
}

foreach ($source in $sources) {
  $manifestPath = Join-Path $source.FullName "manifest.json"
  $layoutPath = Join-Path $source.FullName "layout.css"
  $visualPath = Join-Path $source.FullName "visual.css"
  foreach ($required in @($manifestPath, $layoutPath, $visualPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
      throw "Skin source is missing a required file: $required"
    }
  }

  $manifest = Get-Content -LiteralPath $manifestPath -Encoding UTF8 -Raw | ConvertFrom-Json
  $staging = Join-Path ([System.IO.Path]::GetTempPath()) ("workmode-skin-sign-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $staging | Out-Null
  try {
    Copy-Item -LiteralPath $manifestPath -Destination $staging
    Copy-Item -LiteralPath $layoutPath -Destination $staging
    Copy-Item -LiteralPath $visualPath -Destination $staging

    $license = Join-Path $source.FullName "LICENSE.txt"
    if (Test-Path -LiteralPath $license -PathType Leaf) {
      Copy-Item -LiteralPath $license -Destination $staging
    }

    foreach ($asset in @($manifest.assets)) {
      $relativePath = [string]$asset.path
      if (-not $relativePath -or [System.IO.Path]::IsPathRooted($relativePath) -or $relativePath.Contains("\") -or $relativePath.Split("/").Contains("..")) {
        throw "Unsafe asset path in $($source.Name): $relativePath"
      }
      $sourceAsset = Assert-Inside -Child (Join-Path $source.FullName ($relativePath.Replace("/", "\"))) -Parent $source.FullName
      if (-not (Test-Path -LiteralPath $sourceAsset -PathType Leaf)) {
        throw "Declared skin asset is missing: $sourceAsset"
      }
      $targetAsset = Join-Path $staging ($relativePath.Replace("/", "\"))
      New-Item -ItemType Directory -Force -Path (Split-Path -Parent $targetAsset) | Out-Null
      Copy-Item -LiteralPath $sourceAsset -Destination $targetAsset
    }

    $output = Join-Path $PackageRoot ($source.Name + ".workmode-skin")
    & node $Signer sign $staging $output
    if ($LASTEXITCODE -ne 0) {
      throw "Skin signing failed: $($source.Name)"
    }
  } finally {
    if (Test-Path -LiteralPath $staging) {
      Remove-Item -LiteralPath $staging -Recurse -Force
    }
  }
}

Get-ChildItem -LiteralPath $PackageRoot -File -Filter "*.workmode-skin" |
  Sort-Object Name |
  Select-Object Name, Length, LastWriteTime
