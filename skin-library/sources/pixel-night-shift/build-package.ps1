$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $source '..\..\..')
& (Join-Path $repoRoot 'scripts\build-skin-library.ps1') -SkinId 'pixel-night-shift'
if ($LASTEXITCODE -ne 0) { throw 'pixel-night-shift signing failed' }
