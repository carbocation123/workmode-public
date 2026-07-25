param(
  [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$SourceRoot = Join-Path $Root "word-addin-native"
$WindowsRoot = [Environment]::GetFolderPath([Environment+SpecialFolder]::Windows)
if (-not $OutputDirectory) {
  $OutputDirectory = Join-Path $SourceRoot "bin"
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$Csc = Join-Path $WindowsRoot "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $Csc)) {
  $Csc = Join-Path $WindowsRoot "Microsoft.NET\Framework\v4.0.30319\csc.exe"
}
if (-not (Test-Path -LiteralPath $Csc)) {
  throw ".NET Framework C# compiler was not found."
}

$Office = Get-ChildItem (Join-Path $WindowsRoot "assembly\GAC_MSIL\office") `
  -Recurse -Filter "OFFICE.DLL" -ErrorAction SilentlyContinue |
  Sort-Object FullName -Descending |
  Select-Object -First 1
$Extensibility = Get-ChildItem (Join-Path $WindowsRoot "assembly\GAC\Extensibility") `
  -Recurse -Filter "extensibility.dll" -ErrorAction SilentlyContinue |
  Sort-Object FullName -Descending |
  Select-Object -First 1
if (-not $Office -or -not $Extensibility) {
  throw "Microsoft Office primary interop assemblies were not found."
}

$Output = Join-Path $OutputDirectory "Workmode.WordAddin.dll"
$Arguments = @(
  "/nologo",
  "/target:library",
  "/platform:anycpu",
  "/optimize+",
  "/out:$Output",
  "/resource:$(Join-Path $SourceRoot 'Ribbon.xml'),Workmode.WordAddin.Ribbon.xml",
  "/reference:System.dll",
  "/reference:System.Core.dll",
  "/reference:System.Drawing.dll",
  "/reference:System.Windows.Forms.dll",
  "/reference:System.Web.Extensions.dll",
  "/reference:$($Office.FullName)",
  "/reference:$($Extensibility.FullName)",
  (Join-Path $SourceRoot "WorkmodeWordAddin.cs"),
  (Join-Path $SourceRoot "CitationDialog.cs")
)

& $Csc $Arguments
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Output)) {
  throw "Native Word add-in compilation failed."
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "install-native-word-addin.ps1") `
  -Destination (Join-Path $OutputDirectory "install-native-word-addin.ps1") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "uninstall-native-word-addin.ps1") `
  -Destination (Join-Path $OutputDirectory "uninstall-native-word-addin.ps1") -Force

Write-Host "Native Word add-in built: $Output"
