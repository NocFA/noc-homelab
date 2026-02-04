# Setup scheduled tasks to run hidden via VBS wrappers

# Stop existing processes
Stop-Process -Name zurg, rclone -Force -ErrorAction SilentlyContinue
Start-Sleep 2

# Remove old tasks
Unregister-ScheduledTask -TaskName 'Homelab-Zurg' -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'Homelab-RcloneMount' -Confirm:$false -ErrorAction SilentlyContinue

# Create Zurg task using VBS wrapper
$zurgAction = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '"C:\Users\noc\homelab-win\scripts\start-zurg-hidden.vbs"'
$zurgTrigger = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME
$zurgSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
$zurgPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName 'Homelab-Zurg' -Action $zurgAction -Trigger $zurgTrigger -Settings $zurgSettings -Principal $zurgPrincipal -Force
Write-Host "Created Homelab-Zurg task"

# Create Rclone task using VBS wrapper (10s delay)
$rcloneAction = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '"C:\Users\noc\homelab-win\scripts\start-rclone-hidden.vbs"'
$rcloneTrigger = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME
$rcloneTrigger.Delay = 'PT10S'
$rcloneSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
$rclonePrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName 'Homelab-RcloneMount' -Action $rcloneAction -Trigger $rcloneTrigger -Settings $rcloneSettings -Principal $rclonePrincipal -Force
Write-Host "Created Homelab-RcloneMount task"

# Start services now
Write-Host "Starting Zurg..."
Start-ScheduledTask -TaskName 'Homelab-Zurg'
Start-Sleep 4

Write-Host "Starting Rclone..."
Start-ScheduledTask -TaskName 'Homelab-RcloneMount'
Start-Sleep 5

# Verify
$zurg = Get-Process zurg -ErrorAction SilentlyContinue
$rclone = Get-Process rclone -ErrorAction SilentlyContinue

Write-Host ""
if ($zurg) { Write-Host "Zurg: RUNNING (PID $($zurg.Id))" -ForegroundColor Green }
else { Write-Host "Zurg: NOT RUNNING" -ForegroundColor Red }

if ($rclone) { Write-Host "Rclone: RUNNING (PID $($rclone.Id))" -ForegroundColor Green }
else { Write-Host "Rclone: NOT RUNNING" -ForegroundColor Red }

# Test Z: drive
if (Test-Path Z:\) {
    Write-Host "Z: drive: MOUNTED" -ForegroundColor Green
} else {
    Write-Host "Z: drive: NOT MOUNTED" -ForegroundColor Red
}
