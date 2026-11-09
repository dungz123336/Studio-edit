@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist "%~dp0bootstrap.ps1" (
  echo LOI: Hay tai day du repository, thieu bootstrap.ps1.
  pause
  exit /b 1
)
set "STUDIO_OPTION="
if "%~1"=="" goto launch
if /i "%~1"=="--check" set "STUDIO_OPTION=-Check"
if /i "%~1"=="--no-browser" set "STUDIO_OPTION=-NoBrowser"
if not defined STUDIO_OPTION (
  echo Cach dung: start.bat [--check ^| --no-browser]
  pause
  exit /b 2
)
:launch
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" %STUDIO_OPTION%
set "STUDIO_EXIT=%errorlevel%"
if not "%STUDIO_EXIT%"=="0" (
  echo.
  echo Studio chua mo duoc. Xem thong bao o tren.
  pause
)
exit /b %STUDIO_EXIT%
