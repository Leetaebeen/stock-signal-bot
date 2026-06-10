$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "Starting Stock Signal Bot worker. Press Ctrl+C to stop."
& ".\.venv\Scripts\python.exe" -m app.worker
