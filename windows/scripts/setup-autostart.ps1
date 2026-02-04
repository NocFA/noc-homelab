# Setup Auto-Start for Homelab Services
# Run once to configure Task Scheduler tasks

$ErrorActionPreference = "Stop"

$HomelabDir = "$env:USERPROFILE\homelab-win"
$PythonExe = "$env:USERPROFILE\AppData\Local\Programs\Python\Python312\pythonw.exe"
$ZurgExe = "$HomelabDir\services\zurg\zurg.exe"
$RcloneExe = "$env:USERPROFILE\scoop\apps\rclone\1.72.1\rclone.exe"
$TrayScript = "$HomelabDir\scripts\homelab-tray.pyw"
$CacheDir = "$HomelabDir\cache"
$LogDir = "$HomelabDir\logs"

# Ensure directories exist
New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Write-Host "Setting up Homelab auto-start..." -ForegroundColor Cyan

# ============================================
# Task 1: Start Zurg at logon
# ============================================
Write-Host "Creating Zurg scheduled task..." -ForegroundColor Yellow

$ZurgAction = New-ScheduledTaskAction -Execute $ZurgExe -WorkingDirectory "$HomelabDir\services\zurg"
$ZurgTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$ZurgSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Remove existing task if present
Unregister-ScheduledTask -TaskName "Homelab-Zurg" -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName "Homelab-Zurg" -Action $ZurgAction -Trigger $ZurgTrigger -Settings $ZurgSettings -Description "Zurg Real-Debrid WebDAV server" | Out-Null

# ============================================
# Task 2: Start Rclone mount (delayed, after Zurg)
# ============================================
Write-Host "Creating Rclone mount scheduled task..." -ForegroundColor Yellow

$RcloneArgs = @(
    "mount", "zurg:", "Z:",
    "--dir-cache-time", "10s",
    "--vfs-cache-mode", "full",
    "--vfs-cache-max-age", "24h",
    "--vfs-cache-max-size", "50G",
    "--vfs-cache-min-free-space", "5G",
    "--vfs-read-ahead", "128M",
    "--vfs-read-chunk-size", "4M",
    "--vfs-read-chunk-size-limit", "64M",
    "--vfs-fast-fingerprint",
    "--buffer-size", "64M",
    "--transfers", "8",
    "--checkers", "8",
    "--attr-timeout", "1s",
    "--cache-dir", $CacheDir,
    "--log-file", "$LogDir\rclone-mount.log",
    "--log-level", "INFO",
    "--network-mode"
) -join " "

$RcloneAction = New-ScheduledTaskAction -Execute $RcloneExe -Argument $RcloneArgs
$RcloneTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# Add 10 second delay to let Zurg start first
$RcloneTrigger.Delay = "PT10S"
$RcloneSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Remove existing task if present
Unregister-ScheduledTask -TaskName "Homelab-RcloneMount" -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName "Homelab-RcloneMount" -Action $RcloneAction -Trigger $RcloneTrigger -Settings $RcloneSettings -Description "Rclone mount for Zurg WebDAV to Z:" | Out-Null

# ============================================
# Task 3: Tray app in Startup folder
# ============================================
Write-Host "Adding tray app to Startup..." -ForegroundColor Yellow

$StartupFolder = [Environment]::GetFolderPath("Startup")
$ShortcutPath = "$StartupFolder\Homelab Tray.lnk"

# Create shortcut
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonExe
$Shortcut.Arguments = "`"$TrayScript`""
$Shortcut.WorkingDirectory = $HomelabDir
$Shortcut.Description = "Homelab System Tray Manager"
$Shortcut.Save()

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Configured:" -ForegroundColor Yellow
Write-Host "  - Homelab-Zurg task: Starts Zurg at logon"
Write-Host "  - Homelab-RcloneMount task: Mounts Z: drive 10s after logon"
Write-Host "  - Startup shortcut: Homelab tray app"
Write-Host ""
Write-Host "To manually start services now, run:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName 'Homelab-Zurg'"
Write-Host "  Start-ScheduledTask -TaskName 'Homelab-RcloneMount'"
Write-Host ""
Write-Host "Or use the tray app: $TrayScript"
