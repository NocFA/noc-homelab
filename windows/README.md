# Windows Homelab - Real-Debrid Media Automation

**The killer feature**: Fully automated media pipeline from Real-Debrid cloud to organized media server libraries.

## 🎬 The Pipeline

```
Real-Debrid Cloud (torrent storage)
        ↓
    Zurg (WebDAV server, localhost:9999)
        ↓
    Rclone Mount (mount Z: with VFS caching)
        ↓
    FileBot (auto-organize on content change)
        ↓
    Symlinks (C:\Users\noc\noc-homelab\windows\media\movies & shows)
        ↓
    Emby/Jellyfin/Plex (scan organized libraries)
        ↓
    Clients (Shield, TV apps, browsers, mobile)
```

**What this means**:
1. Add a torrent to Real-Debrid (via browser, app, or automation)
2. Zurg detects it in ~10 seconds
3. FileBot automatically organizes it into proper folder structure
4. Media server libraries update automatically
5. Start streaming in 4K with no downloads

## ⚡ Quick Start

### Prerequisites
- Windows 10/11
- Real-Debrid Premium account ($3/month)
- FileBot license ($6 lifetime via Microsoft Store)

### One-Command Setup
```powershell
# Clone this repo
git clone https://github.com/NocFA/noc-homelab.git C:\Users\noc\noc-homelab
cd noc-homelab\setup

# Run setup script (prompts for API keys)
.\setup-windows.ps1
```

The setup script will:
1. Prompt for Real-Debrid API token
2. Prompt for Emby/Jellyfin API keys
3. Create all config files from templates
4. Install scheduled tasks
5. Mount Zurg as Z: drive
6. Start all services

### Manual Setup
If you prefer step-by-step control:

1. **Get Real-Debrid API token**: https://real-debrid.com/apitoken
2. **Configure Zurg**:
   ```powershell
   cd windows\services\zurg
   Copy-Item config.example.yml config.yml
   notepad config.yml  # Replace YOUR_REAL_DEBRID_API_TOKEN_HERE
   ```
3. **Configure FileBot script**:
   ```powershell
   cd windows\scripts
   Copy-Item library-update.example.ps1 library-update.ps1
   notepad library-update.ps1  # Add Emby/Jellyfin API keys
   ```
4. **Create scheduled tasks**:
   ```powershell
   cd windows\scheduled-tasks
   Get-ChildItem *.xml | ForEach-Object {
       Register-ScheduledTask -Xml (Get-Content $_.FullName | Out-String) -TaskName $_.BaseName
   }
   ```
5. **Start services**:
   ```powershell
   schtasks /run /tn "Homelab-Zurg"
   Start-Sleep -Seconds 5
   schtasks /run /tn "Homelab-RcloneMount"
   ```

## 📁 Directory Structure

```
C:\Users\noc\noc-homelab\windows\
├── scripts\              # PowerShell automation scripts
│   ├── library-update.ps1         # FileBot + library scan (API keys)
│   ├── library-update.example.ps1 # Template with placeholders
│   ├── filebot-symlinks.ps1       # Manual FileBot runner
│   ├── mount-zurg.bat             # Mount Z: drive
│   ├── homelab-tray.pyw           # System tray app
│   └── [other management scripts]
│
├── services\             # Service configurations
│   └── zurg\
│       ├── config.yml             # Zurg config (gitignored, has RD token)
│       ├── config.example.yml     # Template with placeholders
│       ├── zurg.exe               # Zurg binary
│       └── data\                  # Zurg state (gitignored)
│
├── scheduled-tasks\      # Windows Scheduled Task XML exports
│   ├── Homelab-Zurg.xml           # Start Zurg at boot
│   ├── Homelab-RcloneMount.xml    # Mount Z: at boot
│   ├── Homelab-Emby.xml           # Start Emby
│   ├── Homelab-Jellyfin.xml       # Start Jellyfin
│   └── [other service tasks]
│
├── media\                # FileBot symlink destination
│   ├── movies\
│   │   └── Movie Title (2024)\
│   │       └── Movie Title (2024).mkv -> Z:\movies\...
│   └── shows\
│       └── Show Name\
│           └── Season 01\
│               └── Show Name - S01E01.mkv -> Z:\shows\...
│
├── logs\                 # Service logs (gitignored)
│   ├── zurg.log
│   ├── rclone-mount.log
│   └── library-update.log
│
└── cache\                # Rclone VFS cache (gitignored)
    └── vfs\              # Up to 50GB cached content
```

## 🔧 Services

### Zurg - Real-Debrid WebDAV Server
**What it does**: Connects to Real-Debrid API and exposes your cloud torrents as a WebDAV server on `localhost:9999`.

**Configuration**: `services/zurg/config.yml`
- Real-Debrid API token
- Directory organization (movies, shows)
- Update polling interval (10 seconds)
- Library update hook → triggers FileBot

**Managed by**: Scheduled Task `Homelab-Zurg`

**Documentation**: [services/zurg/README.md](services/zurg/README.md)

### Rclone Mount - WebDAV to Z: Drive
**What it does**: Mounts Zurg's WebDAV server as Windows drive `Z:` with VFS caching for smooth 4K streaming.

**Key features**:
- Full VFS caching (50GB max)
- 128MB read-ahead buffer
- Chunk dedup for efficient bandwidth
- Auto-reconnect on network issues

**Managed by**: Scheduled Task `Homelab-RcloneMount`

### FileBot - Automatic Media Organization
**What it does**: Runs whenever Zurg detects library changes (new content added, torrents deleted). Organizes media into proper folder structure with symlinks.

**Pattern**:
- **Movies**: `movies/{Movie Title} ({Year})/{Movie Title} ({Year}).mkv`
- **TV Shows**: `shows/{Show Name}/Season {##}/{Show Name} - S##E## - {Episode Title}.mkv`

**Why symlinks?**: Original files stay in Zurg mount (Z:), symlinks go to organized folders. Media servers scan organized folders, playback streams from Zurg.

**Triggered by**: Zurg's `on_library_update` hook → `scripts/library-update.ps1`

### Emby/Jellyfin - Media Servers
**What they do**: Scan the organized symlink directories and provide web/app interfaces for streaming.

**Library paths**:
- Movies: `C:\Users\noc\noc-homelab\windows\media\movies`
- TV Shows: `C:\Users\noc\noc-homelab\windows\media\shows`

**API integration**: `library-update.ps1` triggers library scans via API after FileBot completes.

**Managed by**: Scheduled Tasks `Homelab-Emby` and `Homelab-Jellyfin`

## 🎯 How It Works

### Adding New Content

1. **Add torrent to Real-Debrid**:
   - Via browser: https://real-debrid.com/torrents
   - Via mobile app: Real-Debrid app
   - Via automation: RSS feeds, Sonarr/Radarr, browser extensions

2. **Zurg detects change** (~10 seconds):
   - Polls RD API every 10 seconds
   - Detects new/changed torrents
   - Updates internal file tree
   - Triggers `on_library_update` hook

3. **FileBot organizes**:
   - `library-update.ps1` runs
   - Cleans up stale symlinks (from deleted RD content)
   - Runs FileBot on `Z:\movies` and `Z:\shows`
   - Creates/updates symlinks in `media\movies` and `media\shows`

4. **Media servers scan**:
   - `library-update.ps1` calls Emby/Jellyfin APIs
   - Libraries refresh
   - New content appears in apps/web

5. **Start streaming**:
   - Open Emby/Jellyfin on any device
   - Browse organized library
   - Play in 4K (if source is 4K)

### Removing Content

1. **Delete torrent from Real-Debrid**:
   - Via browser or app

2. **Zurg detects deletion**:
   - File disappears from Z: mount

3. **FileBot cleanup**:
   - Next library update detects broken symlinks
   - Removes stale symlinks
   - Removes empty folders

4. **Media servers update**:
   - Library scan removes missing items

## 🖥️ Management

### Dashboard Control
Access from macOS machine:
```
http://noc-local:8080
```

Dashboard can:
- Start/stop/restart all Windows services via SSH
- View service status and logs
- Check process uptime
- Monitor service ports

### System Tray App (Optional)
`homelab-tray.pyw` adds a system tray icon for quick control:
- Right-click → Start/Stop/Restart services
- Click → Open service web interfaces
- Color indicator: Green = all running, Red = services down

Auto-starts at login via `Homelab-Tray` scheduled task.

### PowerShell Control
```powershell
# Start all services
schtasks /run /tn "Homelab-Zurg"
schtasks /run /tn "Homelab-RcloneMount"
schtasks /run /tn "Homelab-Emby"
schtasks /run /tn "Homelab-Jellyfin"

# Stop services (kill processes)
taskkill /IM zurg.exe /F
taskkill /IM rclone.exe /F
taskkill /IM embyserver.exe /F
taskkill /IM jellyfin.exe /F

# Check status
Get-Process zurg,rclone,embyserver,jellyfin -ErrorAction SilentlyContinue

# View logs
Get-Content C:\Users\noc\noc-homelab\windows\logs\library-update.log -Tail 50 -Wait
```

## 🔍 Troubleshooting

### Zurg won't start
```powershell
# Check if token is valid
curl https://api.real-debrid.com/rest/1.0/user -H "Authorization: Bearer YOUR_TOKEN"

# Check port 9999 is free
netstat -an | findstr :9999

# Check config syntax
Get-Content services\zurg\config.yml

# View logs
Get-Content logs\zurg.log -Tail 50
```

### Z: drive not mounting
```powershell
# Check if Zurg is running
Get-Process zurg

# Check if WebDAV client is enabled
Get-WindowsOptionalFeature -Online -FeatureName WebDAV-Redirector

# Enable if needed
Enable-WindowsOptionalFeature -Online -FeatureName WebDAV-Redirector

# Try manual mount
net use Z: http://localhost:9999/dav

# View mount logs
Get-Content logs\rclone-mount.log -Tail 50
```

### Z: drive is empty
```powershell
# Check if Real-Debrid has content
# Go to: https://real-debrid.com/torrents

# Add a test torrent
# Wait 10-60 seconds

# Force Zurg refresh
taskkill /IM zurg.exe /F
schtasks /run /tn "Homelab-Zurg"
```

### FileBot not organizing
```powershell
# Check if FileBot is installed
Test-Path "C:\Users\noc\Downloads\apps\FileBot_5.2.0-portable\filebot.exe"

# Check if library-update.ps1 has API keys
Get-Content scripts\library-update.ps1 | Select-String -Pattern "ApiKey"

# Run FileBot manually
.\scripts\filebot-symlinks.ps1

# Check logs
Get-Content logs\library-update.log -Tail 100
```

### Emby/Jellyfin not updating
```powershell
# Check if API keys are correct
# Emby: Dashboard > Advanced > API Keys
# Jellyfin: Dashboard > Advanced > API Keys

# Test API manually
Invoke-RestMethod -Method Post -Uri "http://localhost:8096/Library/Refresh?api_key=YOUR_EMBY_KEY"
Invoke-RestMethod -Method Post -Uri "http://localhost:8097/Library/Refresh?api_key=YOUR_JELLYFIN_KEY"

# Check library paths in Emby/Jellyfin point to:
# C:\Users\noc\noc-homelab\windows\media\movies
# C:\Users\noc\noc-homelab\windows\media\shows
```

### Streaming is slow/buffering
```powershell
# Check VFS cache usage
Get-ChildItem cache\vfs -Recurse | Measure-Object -Property Length -Sum

# Increase cache size in rclone mount command:
# --vfs-cache-max-size 100G (was 50G)

# Check Real-Debrid bandwidth
# Go to: https://real-debrid.com/

# Check if selecting optimal RD server
# RD automatically uses closest/fastest server

# Test download speed
curl -o nul https://real-debrid.com/speedtest/100MB.test
```

## 🔐 Security & Best Practices

### Secrets Management
- **NEVER commit files with API keys**:
  - `windows/services/zurg/config.yml`
  - `windows/scripts/library-update.ps1`
- **Use .example templates** with placeholders
- **Rotate keys if exposed**:
  - Real-Debrid: https://real-debrid.com/apitoken
  - Emby/Jellyfin: Regenerate in Dashboard > API Keys

### Backups
The setup script does NOT backup:
- VFS cache (`cache/vfs/`) - This is temporary streaming cache
- Zurg data (`services/zurg/data/`) - Rebuilt from RD on restart
- Logs (`logs/`) - Rotated automatically

You SHOULD backup:
- `services/zurg/config.yml` (has RD token)
- `scripts/library-update.ps1` (has API keys)
- Media server configs (Emby/Jellyfin AppData)

### Updates
```powershell
# Update Zurg
# Download latest: https://github.com/debridmediamanager/zurg-testing/releases
taskkill /IM zurg.exe /F
Move-Item services\zurg\zurg.exe services\zurg\zurg.exe.backup
# Copy new zurg.exe to services\zurg\
schtasks /run /tn "Homelab-Zurg"

# Update FileBot
# Download latest: https://www.filebot.net/
# Update $FileBotExe path in library-update.ps1

# Update this repo
git pull origin main
# Review changes to .example files
# Regenerate configs if needed
```

## 📊 Performance Optimization

### For 4K REMUX Streaming
```powershell
# Zurg config tweaks
network_buffer_size: 262144  # 256KB (was 128KB)

# Rclone mount tweaks
--vfs-read-ahead 256M        # 256MB (was 128MB)
--buffer-size 128M           # 128MB (was 64MB)
--vfs-cache-max-size 100G    # 100GB (was 50GB)
```

### For Lower-End Hardware
```powershell
# Reduce memory usage
--vfs-cache-max-size 20G     # 20GB (was 50GB)
--vfs-read-ahead 64M         # 64MB (was 128MB)
--buffer-size 32M            # 32MB (was 64MB)
```

### For Multiple Concurrent Streams
```powershell
# Increase cache and buffer
--vfs-cache-max-size 100G
--vfs-cache-max-age 168h     # Keep cache for 7 days
--transfers 16               # Allow 16 concurrent transfers (was 4)
```

## 🌐 Network Access

Services are accessible via Tailscale mesh network:
- **This machine**: `noc-winlocal`
- **macOS server**: `noc-local`
- **Dashboard**: http://noc-local:8080

From any Tailscale device:
- Emby: http://noc-winlocal:8096
- Jellyfin: http://noc-winlocal:8097
- Zurg: http://noc-winlocal:9999 (API only)

## 📚 Documentation

- **Scripts**: [scripts/README.md](scripts/README.md)
- **Zurg**: [services/zurg/README.md](services/zurg/README.md)
- **Scheduled Tasks**: [scheduled-tasks/README.md](scheduled-tasks/README.md)
- **Main README**: [../../README.md](../../README.md)
- **Deployment Guide**: [../../docs/deployment.md](../../docs/deployment.md)

## 🆘 Getting Help

1. **Check logs**: All services log to `logs/`
2. **Check process status**: `Get-Process zurg,rclone,embyserver,jellyfin`
3. **Check scheduled tasks**: `Get-ScheduledTask -TaskName "Homelab-*"`
4. **Check dashboard**: http://noc-local:8080
5. **Review this README and sub-READMEs**

## 🎉 Success Criteria

You know it's working when:
1. ✅ Z: drive shows `movies/` and `shows/` directories
2. ✅ Adding torrent to RD appears in Z: within 10-60 seconds
3. ✅ FileBot creates organized symlinks in `media/movies` and `media/shows`
4. ✅ Emby/Jellyfin shows new content after library scan
5. ✅ 4K content streams smoothly without buffering
6. ✅ Dashboard shows all services as "Running"

## 🚀 Next Steps

- **Add automation**: Integrate Sonarr/Radarr for automatic downloads
- **Add Plex**: Configure Plex libraries alongside Emby/Jellyfin
- **Optimize for your content**: Adjust FileBot patterns for anime, 4K, etc.
- **Monitor usage**: Set up alerts for RD bandwidth limits
- **Expand storage**: Point old media to NAS while keeping new content on RD
