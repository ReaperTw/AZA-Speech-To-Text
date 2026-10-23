$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path ([System.IO.Path]::GetTempPath()) "AZA-STT-build"
$pythonPath = Join-Path $env:USERPROFILE "AppData\Local\Programs\Python\Python310\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = "python"
}

& $pythonPath -m PyInstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --name AZA-STT `
    --distpath "$projectRoot\dist" `
    --workpath "$buildRoot" `
    --specpath "$buildRoot" `
    --collect-all opencc `
    --collect-all _soundfile_data `
    "$projectRoot\src\groq_dictate.py"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

Write-Output "Built: $projectRoot\dist\AZA-STT.exe"
