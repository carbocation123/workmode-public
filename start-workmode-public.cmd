@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\one-click-start.ps1" %*

if errorlevel 1 (
  echo.
  echo Workmode Public start failed. See logs\launcher.log for details.
  pause
)

