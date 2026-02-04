# Create scheduled task for tray app

Unregister-ScheduledTask -TaskName 'Homelab-Tray' -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute 'pythonw.exe' -Argument 'C:\Users\noc\homelab-win\scripts\homelab-tray.pyw'
$trigger = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME
$trigger.Delay = 'PT15S'  # 15 second delay to let services start first
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName 'Homelab-Tray' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force

Write-Host "Homelab-Tray task created"
