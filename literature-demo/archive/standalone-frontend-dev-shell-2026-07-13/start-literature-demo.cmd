@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-literature-demo.ps1"
if errorlevel 1 pause
