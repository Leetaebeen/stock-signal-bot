$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PidPath = Join-Path $ProjectRoot "data\worker.pid"
$AppLogPath = Join-Path $ProjectRoot "logs\stock_signal.log"
$StdoutLogPath = Join-Path $ProjectRoot "logs\worker.stdout.log"
$StderrLogPath = Join-Path $ProjectRoot "logs\worker.stderr.log"

if (-not (Test-Path -LiteralPath $PidPath)) {
    Write-Host "Worker status: stopped"
} else {
    $WorkerPid = Get-Content -LiteralPath $PidPath -ErrorAction SilentlyContinue
    $Process = $null
    if ($WorkerPid) {
        $Process = Get-Process -Id ([int]$WorkerPid) -ErrorAction SilentlyContinue
    }
    if ($Process) {
        Write-Host "Worker status: running pid=$WorkerPid"
        Write-Host "Started: $($Process.StartTime)"
    } else {
        Write-Host "Worker status: stale pid=$WorkerPid"
    }
}

if (Test-Path -LiteralPath $AppLogPath) {
    Write-Host ""
    Write-Host "Recent app log:"
    Get-Content -LiteralPath $AppLogPath -Tail 20
}

if (Test-Path -LiteralPath $StdoutLogPath) {
    Write-Host ""
    Write-Host "Recent stdout log:"
    Get-Content -LiteralPath $StdoutLogPath -Tail 20
}

if (Test-Path -LiteralPath $StderrLogPath) {
    Write-Host ""
    Write-Host "Recent stderr log:"
    Get-Content -LiteralPath $StderrLogPath -Tail 20
}
