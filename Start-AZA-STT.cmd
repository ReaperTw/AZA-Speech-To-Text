@echo off
cd /d "%~dp0"
set "AZA_STT_EXE=%~dp0AZA-STT.exe"
if not exist "%AZA_STT_EXE%" set "AZA_STT_EXE=%~dp0bin\AZA-STT.exe"
if not exist "%AZA_STT_EXE%" set "AZA_STT_EXE=%~dp0dist\AZA-STT.exe"
if not exist "%AZA_STT_EXE%" (
    echo AZA-STT.exe not found in root, bin\ or dist\.
    echo Run: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1
    pause
    exit /b 1
)
if "%~1"=="" (
    start "" "%AZA_STT_EXE%"
) else (
    start "" /wait "%AZA_STT_EXE%" %*
)
exit /b %errorlevel%