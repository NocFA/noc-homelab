# Start all homelab services
# Run as Administrator

$ErrorActionPreference = "Stop"
$HomelabDir = "$env:USERPROFILE\homelab-win"
$LogDir = "$HomelabDir\logs"
$CacheDir = "$HomelabDir\cache"

# Ensure directories exist
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null

# Check if Zurg is running
$zurgProcess = Get-Process -Name "zurg" -ErrorAction SilentlyContinue
if (-not $zurgProcess) {
    Write-Host "Starting Zurg..."
    Start-Process -FilePath "$HomelabDir\services\zurg\zurg.exe" -WorkingDirectory "$HomelabDir\services\zurg" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

# Check if mount exists
$mountExists = Test-Path "Z:\"
if (-not $mountExists) {
    Write-Host "Starting rclone mount..."
    $rclone = "$env:USERPROFILE\scoop\apps\rclone\1.72.1\rclone.exe"

    $rcloneArgs = @(
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
    )

    Start-Process -FilePath $rclone -ArgumentList $rcloneArgs -WindowStyle Hidden
}

Write-Host "Services started."
