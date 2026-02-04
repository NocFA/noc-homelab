# Fix scheduled tasks to run hidden (no terminal windows)

# Stop existing processes
Stop-Process -Name zurg, rclone -Force -ErrorAction SilentlyContinue
Start-Sleep 2

# Remove old tasks
Unregister-ScheduledTask -TaskName 'Homelab-Zurg' -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'Homelab-RcloneMount' -Confirm:$false -ErrorAction SilentlyContinue

# Create Zurg task (hidden, no window)
$zurgAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-WindowStyle Hidden -Command "& \"C:\Users\noc\homelab-win\services\zurg\zurg.exe\"" *> \"C:\Users\noc\homelab-win\logs\zurg.log\"' -WorkingDirectory 'C:\Users\noc\homelab-win\services\zurg'
$zurgTrigger = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME
$zurgSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$zurgPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName 'Homelab-Zurg' -Action $zurgAction -Trigger $zurgTrigger -Settings $zurgSettings -Principal $zurgPrincipal -Force

# Create Rclone task (hidden, no window, 10s delay after Zurg)
$rcloneArgs = 'mount zurg: Z: --dir-cache-time 10s --vfs-cache-mode full --vfs-cache-max-size 50G --vfs-read-ahead 128M --vfs-read-chunk-size 4M --buffer-size 64M --log-file "C:\Users\noc\homelab-win\logs\rclone-mount.log" --log-level INFO'
$rcloneAction = New-ScheduledTaskAction -Execute 'C:\Users\noc\scoop\apps\rclone\1.72.1\rclone.exe' -Argument $rcloneArgs
$rcloneTrigger = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME
$rcloneTrigger.Delay = 'PT10S'
$rcloneSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$rclonePrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName 'Homelab-RcloneMount' -Action $rcloneAction -Trigger $rcloneTrigger -Settings $rcloneSettings -Principal $rclonePrincipal -Force

Write-Host "Tasks recreated. Starting services..."

# Start Zurg
Start-ScheduledTask -TaskName 'Homelab-Zurg'
Start-Sleep 3

# Start Rclone
Start-ScheduledTask -TaskName 'Homelab-RcloneMount'
Start-Sleep 5

# Verify
$zurgRunning = Get-Process zurg -ErrorAction SilentlyContinue
$rcloneRunning = Get-Process rclone -ErrorAction SilentlyContinue

if ($zurgRunning) { Write-Host "Zurg: RUNNING" } else { Write-Host "Zurg: NOT RUNNING" }
if ($rcloneRunning) { Write-Host "Rclone: RUNNING" } else { Write-Host "Rclone: NOT RUNNING" }
