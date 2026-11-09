@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
git rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 (
  echo LOI: Thu muc nay khong phai ban clone Git. Hay dung git clone.
  pause
  exit /b 1
)
git diff --quiet --exit-code -- .
if errorlevel 1 goto changed
git diff --cached --quiet --exit-code -- .
if errorlevel 1 goto changed
if exist "%~dp0.runtime\runtime.json" (
  call "%~dp0stop.bat"
  if errorlevel 1 exit /b 1
)
git pull --ff-only
if errorlevel 1 (
  echo.
  echo Chua cap nhat duoc. Git giu nguyen thay doi va lich su tren may.
  pause
  exit /b 1
)
call "%~dp0start.bat"
exit /b %errorlevel%
:changed
echo Ban da sua ma nguon tren may nay. Hay commit hoac tu luu thay doi truoc khi cap nhat.
echo Bo cap nhat khong tu reset, stash, ghi de hay xoa thay doi cua anh.
pause
exit /b 1
