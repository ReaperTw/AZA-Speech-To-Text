@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Uninstall-AZA-STT.ps1" %*
echo.
pause
