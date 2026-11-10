@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
rem Explicitly select an already installed official CPython 3.12 x64.
rem This does not install Python or change Windows Application Control policy.
rem Run once, then use start.bat or the existing Desktop shortcut as usual.
set "STUDIO_SYSTEM_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not "%~1"=="" set "STUDIO_SYSTEM_PYTHON=%~1"
if not "%~2"=="" (
  echo Cach dung: setup-system-python.bat [duong-dan-python.exe]
  pause
  exit /b 2
)
if not exist "%~dp0bootstrap.ps1" (
  echo LOI: Thieu bootstrap.ps1. Hay tai day du repository.
  pause
  exit /b 1
)
if not exist "%STUDIO_SYSTEM_PYTHON%" (
  echo LOI: Chua co CPython 3.12 x64 tai duong dan da chon.
  echo "%STUDIO_SYSTEM_PYTHON%"
  echo Hay nho quan tri vien cung cap bo Python duoc phep chay tren may.
  pause
  exit /b 1
)
echo Thiet lap Studio bang CPython he thong da cai.
echo Giu nguyen moi truong app\.venv hien co.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" -SystemPython "%STUDIO_SYSTEM_PYTHON%"
set "STUDIO_EXIT=%errorlevel%"
if not "%STUDIO_EXIT%"=="0" (
  echo.
  echo Studio chua mo duoc. Xem thong bao o tren.
  pause
)
exit /b %STUDIO_EXIT%
