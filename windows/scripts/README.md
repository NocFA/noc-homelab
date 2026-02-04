# Windows Scripts

This directory contains PowerShell scripts and batch files for managing the Windows homelab services.

## 🔐 Sensitive Files (Gitignored)

- **library-update.ps1** - Contains real API keys for Emby/Jellyfin
  - Use `library-update.example.ps1` as template
  - Setup script will generate this from the example

## Core Automation Scripts

### library-update.ps1 / library-update.example.ps1
**Purpose**: Called by Zurg's `on_library_update` hook when Real-Debrid content changes

**What it does**:
1. Cleans up stale symlinks (targets that no longer exist in Zurg mount)
2. Runs FileBot to organize and symlink new media
3. Triggers library scans in Emby, Jellyfin, and Plex (if configured)

**Configuration**:
- Copy `library-update.example.ps1` to `library-update.ps1`
- Replace `YOUR_EMBY_API_KEY_HERE` with your actual Emby API key
- Replace `YOUR_JELLYFIN_API_KEY_HERE` with your actual Jellyfin API key
- Set `$PlexToken` if using Plex (get from https://www.plex.tv/claim/)
- Adjust `$FileBotExe` path to match your FileBot installation

**How to get API keys**:
- **Emby**: Dashboard > Advanced > API Keys > New API Key
- **Jellyfin**: Dashboard > Advanced > API Keys > New API Key
- **Plex**: https://www.plex.tv/claim/

### library-update.cmd
**Purpose**: Wrapper that calls `library-update.ps1` from Zurg hook

Simple batch file that executes the PowerShell script with proper execution policy.

### filebot-symlinks.ps1
**Purpose**: One-time FileBot symlink creation script

Run this manually to process all existing media in Zurg mount. The `library-update.ps1` script handles incremental updates.

## Service Management Scripts

### start-services.ps1
**Purpose**: Manually start all homelab services

Triggers all scheduled tasks (Zurg, Rclone, Emby, Jellyfin, Sunshine, etc.)

### install-services.ps1
**Purpose**: Install Windows services using NSSM

Creates Windows services for apps that should run as services (like Gatus).

### setup-tasks.ps1
**Purpose**: Create Windows Scheduled Tasks for homelab services

Creates all `Homelab-*` scheduled tasks used for service management.

### fix-tasks.ps1
**Purpose**: Repair scheduled tasks if they get corrupted

Re-creates scheduled tasks with correct settings.

## Startup and Tray Scripts

### homelab-tray.pyw
**Purpose**: System tray application for quick service control

Python script that adds homelab icon to Windows system tray with menu for starting/stopping services.

**Features**:
- Start/stop individual services
- View service status
- Open service web interfaces
- Launch on Windows startup

### setup-tray-task.ps1
**Purpose**: Configure homelab-tray to run on startup

Creates scheduled task to launch the tray application at logon.

### setup-autostart.ps1
**Purpose**: Configure services to start automatically at boot

Sets up auto-start for critical services (Zurg, Rclone, media servers).

### setup-autologin.ps1
**Purpose**: Configure Windows to auto-login

Needed for services that require user desktop session (like Sunshine for game streaming).

## Mount Scripts

### mount-zurg.bat
**Purpose**: Mount Zurg WebDAV as Z: drive

Creates Windows network drive mapping to Zurg's WebDAV server (usually `http://localhost:9999/dav`).

**Usage**:
```batch
mount-zurg.bat
```

**Note**: The scheduled task `Homelab-RcloneMount` typically handles this automatically.

## Hidden Startup Scripts (VBS)

These VBScript files start services without showing console windows:

### start-zurg-hidden.vbs
Starts Zurg daemon without console window.

### start-rclone-hidden.vbs
Starts rclone mount without console window.

### start-jellyfin-hidden.vbs
Starts Jellyfin server without console window.

**Why VBS?**: PowerShell `-WindowStyle Hidden` doesn't work from scheduled tasks. VBScript's `WScript.Shell Run` with `vbHide` properly hides console windows.

## Setup Order

For a fresh Windows install, run scripts in this order:

1. **install-services.ps1** - Create Windows services (Gatus, etc.)
2. **setup-tasks.ps1** - Create scheduled tasks for all services
3. **mount-zurg.bat** - Mount Zurg WebDAV as Z: drive
4. **setup-autostart.ps1** - Configure auto-start for services
5. **setup-tray-task.ps1** - Install system tray application
6. **setup-autologin.ps1** - (Optional) Configure auto-login
7. **filebot-symlinks.ps1** - Process existing media

Or use the master setup script:

```powershell
.\setup\setup-windows.ps1
```

This will prompt for all API keys and configure everything automatically.

## File Locations

Scripts expect these paths (adjust in scripts if different):

- **Homelab root**: `C:\Users\noc\noc-homelab\windows\`
- **Logs**: `C:\Users\noc\noc-homelab\windows\logs\`
- **Media symlinks**: `C:\Users\noc\noc-homelab\windows\media\`
- **Zurg mount**: `Z:\` (WebDAV mount)
- **Zurg config**: `C:\Users\noc\noc-homelab\windows\services\zurg\config.yml`
- **FileBot**: `C:\Users\noc\Downloads\apps\FileBot_5.2.0-portable\filebot.exe`

## Troubleshooting

### Services won't start
1. Check if tasks exist: `schtasks /query /tn "Homelab-*"`
2. Check task status: `Get-ScheduledTask -TaskName "Homelab-*"`
3. View task history: Task Scheduler GUI > Homelab-* tasks > History tab
4. Re-run `setup-tasks.ps1` to recreate tasks

### Library updates not triggering
1. Check Zurg config has `on_library_update` hook pointing to `library-update.cmd`
2. Check logs: `C:\Users\noc\noc-homelab\windows\logs\library-update.log`
3. Verify API keys in `library-update.ps1` are correct
4. Test manually: `.\library-update.ps1`

### Symlinks not created
1. Ensure running as Administrator (symlinks require elevated privileges)
2. Check FileBot license is activated
3. Verify Zurg mount is accessible at `Z:\`
4. Check FileBot logs in `library-update.log`

### Tray icon not appearing
1. Check if Python is installed: `python --version`
2. Check if task exists: `schtasks /query /tn "Homelab-Tray"`
3. Run manually: `pythonw homelab-tray.pyw`
4. Check for errors: `python homelab-tray.pyw` (with console)

## Security Notes

- **Never commit library-update.ps1** - It contains API keys
- **API keys in Emby/Jellyfin** can be regenerated if exposed
- **Scheduled tasks run as your user** - Use appropriate permissions
- **Auto-login is optional** - Only needed for services requiring desktop session (Sunshine, Parsec)
