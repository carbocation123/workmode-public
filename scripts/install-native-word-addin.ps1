param(
  [string]$AssemblyPath,
  [ValidateSet("x86", "x64")]
  [string]$OfficePlatform,
  [switch]$NoRelaunch
)

$ErrorActionPreference = "Stop"
$ProgId = "Workmode.WordAddin"
$ClassId = "{9A7BC47D-8D3B-4BF8-A77A-7B84EE755C2B}"
$ClassName = "Workmode.WordAddin.Connect"
$ManagedCategory = "{62C8FE65-4EBB-45E7-B440-6E39B2CDBF29}"
$WindowsRoot = [Environment]::GetFolderPath([Environment+SpecialFolder]::Windows)

function Resolve-OfficePlatform {
  if ($OfficePlatform) {
    return $OfficePlatform
  }
  $configuration = Get-ItemProperty `
    -LiteralPath "HKLM:\Software\Microsoft\Office\ClickToRun\Configuration" `
    -ErrorAction SilentlyContinue
  if ($configuration.Platform -eq "x86" -or $configuration.Platform -eq "x64") {
    return $configuration.Platform
  }
  $word = Get-Command WINWORD.EXE -ErrorAction SilentlyContinue
  if ($word -and $word.Source -like "*Program Files (x86)*") {
    return "x86"
  }
  return "x64"
}

function Relaunch-InOfficeBitness {
  param([string]$Platform)
  $isCorrect = ($Platform -eq "x64" -and [Environment]::Is64BitProcess) -or
    ($Platform -eq "x86" -and -not [Environment]::Is64BitProcess)
  if ($isCorrect -or $NoRelaunch) {
    return $false
  }
  $powerShell = if ($Platform -eq "x86") {
    Join-Path $WindowsRoot "SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
  } else {
    Join-Path $WindowsRoot "Sysnative\WindowsPowerShell\v1.0\powershell.exe"
  }
  if (-not (Test-Path -LiteralPath $powerShell)) {
    throw "PowerShell for Office $Platform was not found: $powerShell"
  }
  $arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $PSCommandPath,
    "-AssemblyPath", $AssemblyPath,
    "-OfficePlatform", $Platform,
    "-NoRelaunch"
  )
  $process = Start-Process -FilePath $powerShell -ArgumentList $arguments `
    -Wait -PassThru -WindowStyle Hidden
  if ($process.ExitCode -ne 0) {
    throw "Native Word add-in registration failed in the Office $Platform registry view."
  }
  return $true
}

$Platform = Resolve-OfficePlatform
if (Relaunch-InOfficeBitness -Platform $Platform) {
  return
}

if (-not $AssemblyPath) {
  $AssemblyPath = Join-Path (Split-Path -Parent $PSScriptRoot) `
    "word-addin-native\bin\Workmode.WordAddin.dll"
}
$AssemblyPath = [System.IO.Path]::GetFullPath($AssemblyPath)
if (-not (Test-Path -LiteralPath $AssemblyPath -PathType Leaf)) {
  throw "Native Word add-in assembly was not found: $AssemblyPath"
}

$InstallRoot = Join-Path $env:LOCALAPPDATA "WorkmodePublic\word-native-addin"
$AssemblyHash = (Get-FileHash -LiteralPath $AssemblyPath -Algorithm SHA256).Hash
$VersionDirectory = Join-Path $InstallRoot $AssemblyHash.Substring(0, 12).ToLowerInvariant()
New-Item -ItemType Directory -Force -Path $VersionDirectory | Out-Null
$InstalledAssembly = Join-Path $VersionDirectory "Workmode.WordAddin.dll"
if ($AssemblyPath -ne $InstalledAssembly) {
  Copy-Item -LiteralPath $AssemblyPath -Destination $InstalledAssembly -Force
}

$AssemblyName = [Reflection.AssemblyName]::GetAssemblyName($InstalledAssembly).FullName
$CodeBase = ([Uri]$InstalledAssembly).AbsoluteUri
$ClassesRoot = "HKCU:\Software\Classes"
$ClsidRoot = Join-Path $ClassesRoot "CLSID\$ClassId"
$Inproc = Join-Path $ClsidRoot "InprocServer32"
$VersionedInproc = Join-Path $Inproc "1.0.0.0"
$ProgIdRoot = Join-Path $ClassesRoot $ProgId
$OfficeAddin = "HKCU:\Software\Microsoft\Office\Word\Addins\$ProgId"

New-Item -Path $Inproc -Force | Out-Null
Set-Item -LiteralPath $ClsidRoot -Value "Workmode Word Add-in"
Set-Item -LiteralPath $Inproc -Value "mscoree.dll"
New-ItemProperty -LiteralPath $Inproc -Name "ThreadingModel" -Value "Both" `
  -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $Inproc -Name "Class" -Value $ClassName `
  -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $Inproc -Name "Assembly" -Value $AssemblyName `
  -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $Inproc -Name "RuntimeVersion" -Value "v4.0.30319" `
  -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $Inproc -Name "CodeBase" -Value $CodeBase `
  -PropertyType String -Force | Out-Null
New-Item -Path $VersionedInproc -Force | Out-Null
New-ItemProperty -LiteralPath $VersionedInproc -Name "Class" -Value $ClassName `
  -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $VersionedInproc -Name "Assembly" -Value $AssemblyName `
  -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $VersionedInproc -Name "RuntimeVersion" -Value "v4.0.30319" `
  -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $VersionedInproc -Name "CodeBase" -Value $CodeBase `
  -PropertyType String -Force | Out-Null
New-Item -Path (Join-Path $ClsidRoot "ProgId") -Force | Set-Item -Value $ProgId
New-Item -Path (Join-Path $ClsidRoot "Implemented Categories\$ManagedCategory") `
  -Force | Out-Null
New-Item -Path (Join-Path $ProgIdRoot "CLSID") -Force | Set-Item -Value $ClassId
Set-Item -LiteralPath $ProgIdRoot -Value "Workmode Word Add-in"

New-Item -Path $OfficeAddin -Force | Out-Null
New-ItemProperty -LiteralPath $OfficeAddin -Name "FriendlyName" -Value "Workmode" `
  -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $OfficeAddin -Name "Description" `
  -Value "Workmode 文献引用工具" -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $OfficeAddin -Name "LoadBehavior" -Value 3 `
  -PropertyType DWord -Force | Out-Null

$OfficeJsDeveloper = "HKCU:\Software\Microsoft\Office\16.0\WEF\Developer"
Remove-ItemProperty -LiteralPath $OfficeJsDeveloper `
  -Name "0f621bd7-1e31-47e8-8a9f-7d61fdac8805" -ErrorAction SilentlyContinue

Write-Host "Workmode native Word add-in was registered for Office $Platform."
Write-Host "Close every Word window, then reopen Word."
