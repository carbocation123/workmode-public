param(
  [ValidateSet("x86", "x64")]
  [string]$OfficePlatform,
  [switch]$NoRelaunch
)

$ErrorActionPreference = "Stop"
$ProgId = "Workmode.WordAddin"
$ClassId = "{9A7BC47D-8D3B-4BF8-A77A-7B84EE755C2B}"
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
  return "x64"
}

function ConvertTo-PowerShellLiteral {
  param([AllowEmptyString()][string]$Value)
  return "'" + $Value.Replace("'", "''") + "'"
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
  $scriptLiteral = ConvertTo-PowerShellLiteral -Value $PSCommandPath
  $platformLiteral = ConvertTo-PowerShellLiteral -Value $Platform
  $command = "& $scriptLiteral -OfficePlatform $platformLiteral -NoRelaunch"
  $encodedCommand = [Convert]::ToBase64String(
    [Text.Encoding]::Unicode.GetBytes($command)
  )
  $arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-EncodedCommand", $encodedCommand
  )
  $process = Start-Process -FilePath $powerShell -ArgumentList $arguments `
    -Wait -PassThru -WindowStyle Hidden
  if ($process.ExitCode -ne 0) {
    throw "Native Word add-in unregistration failed in the Office $Platform registry view."
  }
  return $true
}

$Platform = Resolve-OfficePlatform
if (Relaunch-InOfficeBitness -Platform $Platform) {
  return
}

Remove-Item -LiteralPath "HKCU:\Software\Microsoft\Office\Word\Addins\$ProgId" `
  -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "HKCU:\Software\Classes\$ProgId" `
  -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "HKCU:\Software\Classes\CLSID\$ClassId" `
  -Recurse -Force -ErrorAction SilentlyContinue

$Destination = Join-Path $env:LOCALAPPDATA "WorkmodePublic\word-native-addin"
if (Test-Path -LiteralPath $Destination) {
  $expected = [System.IO.Path]::GetFullPath(
    (Join-Path $env:LOCALAPPDATA "WorkmodePublic\word-native-addin")
  )
  $resolved = (Resolve-Path -LiteralPath $Destination).Path
  if ($resolved -ne $expected) {
    throw "Refusing to remove unexpected native Word add-in path: $resolved"
  }
  Remove-Item -LiteralPath $resolved -Recurse -Force
}

Write-Host "Workmode native Word add-in registration was removed."
