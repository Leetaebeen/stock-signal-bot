$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PidPath = Join-Path $ProjectRoot "data\worker.pid"
$StdoutLogPath = Join-Path $ProjectRoot "logs\worker.stdout.log"
$StderrLogPath = Join-Path $ProjectRoot "logs\worker.stderr.log"
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Set-Location $ProjectRoot
New-Item -ItemType Directory -Path (Split-Path -Parent $PidPath) -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $StdoutLogPath) -Force | Out-Null

if (Test-Path -LiteralPath $PidPath) {
    $ExistingPid = Get-Content -LiteralPath $PidPath -ErrorAction SilentlyContinue
    if ($ExistingPid) {
        $ExistingProcess = Get-Process -Id ([int]$ExistingPid) -ErrorAction SilentlyContinue
        if ($ExistingProcess) {
            Write-Host "Worker already running. pid=$ExistingPid"
            exit 0
        }
    }
}

$Process = Start-Process `
    -FilePath $PythonPath `
    -ArgumentList "-m", "app.worker" `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $StdoutLogPath `
    -RedirectStandardError $StderrLogPath `
    -WindowStyle Hidden `
    -PassThru

Set-Content -LiteralPath $PidPath -Value $Process.Id
Write-Host "Worker started. pid=$($Process.Id)"
Write-Host "Stdout log: $StdoutLogPath"
Write-Host "Stderr log: $StderrLogPath"
