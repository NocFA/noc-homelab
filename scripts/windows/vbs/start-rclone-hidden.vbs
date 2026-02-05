Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "C:\Users\noc\scoop\apps\rclone\1.72.1\rclone.exe mount zurg: Z: --dir-cache-time 10s --vfs-cache-mode full --vfs-cache-max-size 50G --vfs-read-ahead 128M --vfs-read-chunk-size 4M --buffer-size 64M --log-file ""C:\Users\noc\homelab\logs\rclone-mount.log"" --log-level INFO", 0, False
