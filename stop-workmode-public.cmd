@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-workmode-public.ps1" %*

if errorlevel 1 (
  echo.
  echo Workmode Public stop failed.
  pause
)

