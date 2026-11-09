@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist "%~dp0bootstrap.ps1" (
  echo LOI: Thieu bootstrap.ps1.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" -Stop
set "STUDIO_EXIT=%errorlevel%"
if not "%STUDIO_EXIT%"=="0" pause
exit /b %STUDIO_EXIT%
