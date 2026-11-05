$ErrorActionPreference = "Stop"

$TaskName = "IP Camera Counting Dashboard"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $ProjectDir "run_dashboard.ps1"

if (-not (Test-Path -LiteralPath $Runner)) {
    throw "run_dashboard.ps1 not found: $Runner"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Runner`""

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Run the IP camera counting dashboard continuously" `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName

Write-Output "Installed scheduled task: $TaskName"
Write-Output "Dashboard: http://localhost:8501"
