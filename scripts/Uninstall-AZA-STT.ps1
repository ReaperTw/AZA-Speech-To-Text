#Requires -Version 5.1
# User uninstall for AZA-STT.
# Double-click Uninstall-AZA-STT.cmd, or:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Uninstall-AZA-STT.ps1
# Preview: add -WhatIf. Skip prompt: add -Force.
# Does not delete this folder or any .git checkout.

[CmdletBinding()]
param(
    [switch]$WhatIf,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot

$dataDir = Join-Path $env:LOCALAPPDATA "AZA-STT"
$startupLnk = Join-Path ([Environment]::GetFolderPath("Startup")) "AZA-STT.lnk"
$tempRoot = [System.IO.Path]::GetTempPath()
$removed = New-Object System.Collections.Generic.List[string]
$missing = New-Object System.Collections.Generic.List[string]
$failed = New-Object System.Collections.Generic.List[string]
$wouldRemove = New-Object System.Collections.Generic.List[string]

function Remove-Target {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        $missing.Add($Path)
        return
    }
    if ($WhatIf) {
        $wouldRemove.Add($Path)
        return
    }
    try {
        Remove-Item -LiteralPath $Path -Recurse -Force
        $removed.Add($Path)
    } catch {
        $failed.Add("$Path :: $($_.Exception.Message)")
    }
}

function Get-KnownTempItems {
    Get-ChildItem -LiteralPath $tempRoot -Force -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like "groq_dictate_*" -or
            $_.Name -like "aza_stt_*"
        }
}

function Get-AzaMeiFolders {
    Get-ChildItem -LiteralPath $tempRoot -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "_MEI*" } |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "AZA-STT.exe") }
}

Write-Output "AZA-STT uninstall"
Write-Output "Settings directory: $dataDir"
Write-Output "Startup shortcut: $startupLnk"
Write-Output ""

if (-not $WhatIf -and -not $Force) {
    $answer = Read-Host "This stops AZA-STT and removes settings, API keys, logs, the startup shortcut, and temporary audio. Continue? (Y/N)"
    if ($answer -notmatch '^[Yy]$') {
        Write-Output "Cancelled."
        exit 0
    }
}

$running = @(Get-Process -Name "AZA-STT" -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) {
    $ids = ($running | ForEach-Object { $_.Id }) -join ", "
    if ($WhatIf) {
        Write-Output "Preview: would stop AZA-STT.exe (PID $ids)"
    } else {
        $running | Stop-Process -Force
        Start-Sleep -Seconds 2
        if (Get-Process -Name "AZA-STT" -ErrorAction SilentlyContinue) {
            $failed.Add("AZA-STT.exe is still running; some files cannot be removed")
        } else {
            Write-Output "Stopped AZA-STT.exe"
        }
    }
} else {
    Write-Output "AZA-STT.exe is not running"
}

Remove-Target -Path $startupLnk
Remove-Target -Path $dataDir
Get-KnownTempItems | ForEach-Object { Remove-Target -Path $_.FullName }
Get-AzaMeiFolders | ForEach-Object { Remove-Target -Path $_.FullName }

foreach ($exeName in @("AZA-STT.exe")) {
    foreach ($exePath in @(
            (Join-Path $projectRoot $exeName),
            (Join-Path $projectRoot "bin\$exeName"),
            (Join-Path $projectRoot "dist\$exeName")
        )) {
        if (Test-Path -LiteralPath $exePath) {
            Remove-Target -Path $exePath
        }
    }
}

Write-Output ""
if ($WhatIf) {
    Write-Output "Preview - would remove:"
    if ($wouldRemove.Count -eq 0) { Write-Output "  (nothing found)" } else { $wouldRemove | ForEach-Object { Write-Output "  $_" } }
} else {
    Write-Output "Removed:"
    if ($removed.Count -eq 0) { Write-Output "  (nothing)" } else { $removed | ForEach-Object { Write-Output "  $_" } }
}

Write-Output ""
Write-Output "Already missing:"
if ($missing.Count -eq 0) { Write-Output "  (all core paths exist)" } else { $missing | ForEach-Object { Write-Output "  $_" } }

if ($failed.Count -gt 0) {
    Write-Output ""
    Write-Output "Failed:"
    $failed | ForEach-Object { Write-Output "  $_" }
}

Write-Output ""
Write-Output "This folder was not removed: $projectRoot"
Write-Output "If this is an extracted ZIP, remove the folder manually after uninstalling."
Write-Output "If you downloaded a standalone exe, find and remove any other AZA-STT.exe copies manually."
Write-Output "Removing local files does not revoke Groq keys. Revoke unused keys at https://console.groq.com/keys."

if ($failed.Count -gt 0) { exit 1 }
