#!/usr/bin/env pwsh
# safe_shutdown.ps1 — 向 Yggdrasil worker 发送安全关闭信号
# Usage: .\scripts\safe_shutdown.ps1 [-ProcessName yggdrasil-worker] [-WaitSeconds 30]
param(
    [string]$ProcessName = "python",
    [string]$ScriptFilter = "yggdrasil_worker",
    [int]$WaitSeconds = 30
)

$targets = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -like "*$ScriptFilter*" -or
    (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine -like "*$ScriptFilter*"
}

if ($null -eq $targets -or $targets.Count -eq 0) {
    Write-Host "No matching worker process found for filter '$ScriptFilter'."
    exit 0
}

foreach ($proc in $targets) {
    Write-Host "Sending CTRL_C_EVENT to PID $($proc.Id) ($($proc.ProcessName))..."
    # On Windows, use taskkill /PID /T to send SIGTERM equivalent
    & taskkill /PID $proc.Id /T
}

Write-Host "Waiting up to ${WaitSeconds}s for worker to save checkpoint..."
$deadline = (Get-Date).AddSeconds($WaitSeconds)
foreach ($proc in $targets) {
    while ((Get-Date) -lt $deadline -and -not $proc.HasExited) {
        Start-Sleep -Milliseconds 500
        $proc.Refresh()
    }
    if ($proc.HasExited) {
        Write-Host "Worker PID $($proc.Id) exited cleanly."
    } else {
        Write-Warning "Worker PID $($proc.Id) did not exit within ${WaitSeconds}s."
    }
}
