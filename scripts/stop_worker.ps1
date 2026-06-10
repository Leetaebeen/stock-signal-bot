$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PidPath = Join-Path $ProjectRoot "data\worker.pid"

if (-not (Test-Path -LiteralPath $PidPath)) {
    Write-Host "Worker pid file not found."
    exit 0
}

$WorkerPid = Get-Content -LiteralPath $PidPath -ErrorAction SilentlyContinue
if (-not $WorkerPid) {
    Remove-Item -LiteralPath $PidPath -Force
    Write-Host "Worker pid file was empty. Removed."
    exit 0
}

$Process = Get-Process -Id ([int]$WorkerPid) -ErrorAction SilentlyContinue
if (-not $Process) {
    Remove-Item -LiteralPath $PidPath -Force
    Write-Host "Worker was not running. Removed stale pid=$WorkerPid."
    exit 0
}

Stop-Process -Id ([int]$WorkerPid)
Remove-Item -LiteralPath $PidPath -Force
Write-Host "Worker stopped. pid=$WorkerPid"
