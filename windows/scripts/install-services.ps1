# Install Windows services for Homelab
# Run as Administrator: powershell -ExecutionPolicy Bypass -File install-services.ps1

$ErrorActionPreference = "Stop"

$NssmPath = "$env:USERPROFILE\scoop\apps\nssm\2.24-103\nssm.exe"
$HomelabDir = "$env:USERPROFILE\homelab-win"
$RclonePath = "$env:USERPROFILE\scoop\apps\rclone\1.72.1\rclone.exe"
$ZurgPath = "$HomelabDir\services\zurg\zurg.exe"
$LogDir = "$HomelabDir\logs"
$CacheDir = "$HomelabDir\cache"

# Ensure directories exist
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null

Write-Host "Installing Zurg service..." -ForegroundColor Cyan

# Remove existing service if present
& $NssmPath stop zurg 2>$null
& $NssmPath remove zurg confirm 2>$null

# Install Zurg service
& $NssmPath install zurg $ZurgPath
& $NssmPath set zurg AppDirectory "$HomelabDir\services\zurg"
& $NssmPath set zurg DisplayName "Zurg Real-Debrid WebDAV"
& $NssmPath set zurg Description "Real-Debrid WebDAV server for media streaming"
& $NssmPath set zurg Start SERVICE_AUTO_START
& $NssmPath set zurg AppStdout "$LogDir\zurg-service.log"
& $NssmPath set zurg AppStderr "$LogDir\zurg-service.log"
& $NssmPath set zurg AppRotateFiles 1
& $NssmPath set zurg AppRotateBytes 10485760

Write-Host "Installing Rclone mount service..." -ForegroundColor Cyan

# Remove existing service if present
& $NssmPath stop rclone-zurg 2>$null
& $NssmPath remove rclone-zurg confirm 2>$null

# Rclone mount arguments - optimized for 4K streaming
$RcloneArgs = @(
    "mount",
    "zurg:",
    "Z:",
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
    "--log-file", "$LogDir\rclone-service.log",
    "--log-level", "INFO",
    "--network-mode"
) -join " "

# Install Rclone mount service
& $NssmPath install rclone-zurg $RclonePath $RcloneArgs
& $NssmPath set rclone-zurg DisplayName "Rclone Zurg Mount"
& $NssmPath set rclone-zurg Description "Mounts Zurg WebDAV to Z: drive for Emby"
& $NssmPath set rclone-zurg Start SERVICE_AUTO_START
& $NssmPath set rclone-zurg DependOnService zurg
& $NssmPath set rclone-zurg AppRotateFiles 1
& $NssmPath set rclone-zurg AppRotateBytes 10485760

Write-Host "Starting services..." -ForegroundColor Cyan

# Start services
& $NssmPath start zurg
Start-Sleep -Seconds 3
& $NssmPath start rclone-zurg

Write-Host ""
Write-Host "Services installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Service Status:" -ForegroundColor Yellow
& $NssmPath status zurg
& $NssmPath status rclone-zurg
Write-Host ""
Write-Host "The Z: drive should now be available with your Real-Debrid content."
Write-Host "Add Z:\__all__ as a library path in Emby to access your media."
