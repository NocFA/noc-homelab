@echo off
REM Zurg rclone mount script - optimized for 4K streaming
REM Run as: mount-zurg.bat

set RCLONE=%USERPROFILE%\scoop\apps\rclone\1.72.1\rclone.exe
set CACHE_DIR=%USERPROFILE%\homelab-win\cache
set LOG_DIR=%USERPROFILE%\homelab-win\logs

REM Create cache directory if not exists
if not exist "%CACHE_DIR%" mkdir "%CACHE_DIR%"

%RCLONE% mount zurg: Z: ^
    --dir-cache-time 10s ^
    --vfs-cache-mode full ^
    --vfs-cache-max-age 24h ^
    --vfs-cache-max-size 50G ^
    --vfs-cache-min-free-space 5G ^
    --vfs-read-ahead 128M ^
    --vfs-read-chunk-size 4M ^
    --vfs-read-chunk-size-limit 64M ^
    --vfs-fast-fingerprint ^
    --buffer-size 64M ^
    --transfers 8 ^
    --checkers 8 ^
    --attr-timeout 1s ^
    --cache-dir "%CACHE_DIR%" ^
    --log-file "%LOG_DIR%\rclone-mount.log" ^
    --log-level INFO ^
    --network-mode ^
    --no-console
