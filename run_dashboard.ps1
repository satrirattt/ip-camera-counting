$ErrorActionPreference = "Continue"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ProjectDir "logs"
$LogFile = Join-Path $LogDir ("dashboard_{0}.log" -f (Get-Date -Format "yyyyMMdd"))

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
Set-Location -LiteralPath $ProjectDir
$env:PYTHONIOENCODING = "utf-8"

function Write-Log {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    Write-Log "python not found in PATH"
    exit 1
}

while ($true) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $stdoutLog = Join-Path $LogDir "streamlit_$stamp.out.log"
    $stderrLog = Join-Path $LogDir "streamlit_$stamp.err.log"

    Write-Log "Starting Streamlit dashboard on http://localhost:8501"

    $process = Start-Process `
        -FilePath $python `
        -ArgumentList "-m", "streamlit", "run", "dashboard.py", "--server.port", "8501", "--server.headless", "true" `
        -WorkingDirectory $ProjectDir `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -WindowStyle Hidden `
        -PassThru `
        -Wait

    Write-Log "Streamlit exited with code $($process.ExitCode)"
    Write-Log "Restarting in 5 seconds..."
    Start-Sleep -Seconds 5
}
