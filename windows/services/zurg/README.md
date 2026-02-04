# Zurg - Real-Debrid WebDAV Server

Zurg is a WebDAV server that mounts your Real-Debrid library as a network drive on Windows.

## What is Zurg?

Zurg transforms Real-Debrid from a download service into a streaming library:
- **Mounts RD library as Z: drive** - Access torrents as if they were local files
- **Automatic organization** - Separates movies and TV shows
- **Library change detection** - Triggers FileBot when new content is added
- **Streaming-optimized** - Buffers content for smooth 4K playback
- **No downloads** - Content streams directly from Real-Debrid

## Quick Start

### 1. Get Real-Debrid API Token
1. Go to https://real-debrid.com/apitoken
2. Copy your API token (32-character string like `CZ2YF3TDUT67...`)

### 2. Configure Zurg
```powershell
# Copy example config
cd C:\Users\noc\noc-homelab\windows\services\zurg
Copy-Item config.example.yml config.yml

# Edit config.yml and replace YOUR_REAL_DEBRID_API_TOKEN_HERE with your token
notepad config.yml
```

### 3. Start Zurg
```powershell
# Via scheduled task (recommended)
schtasks /run /tn "Homelab-Zurg"

# Or manually
.\zurg.exe --config config.yml
```

### 4. Mount WebDAV Drive
```powershell
# Via batch script (recommended)
.\mount-zurg.bat

# Or manually
net use Z: http://localhost:9999/dav
```

### 5. Verify Mount
```powershell
# Check if Z: drive exists
dir Z:\

# You should see:
# - movies/
# - shows/
```

## How It Works

```
Real-Debrid Cloud
        ↓
    Zurg (localhost:9999)
        ↓
    WebDAV Server
        ↓
    Z:\ Drive Mount
        ↓
    FileBot (on_library_update hook)
        ↓
    Symlinks in C:\Users\noc\noc-homelab\windows\media\
        ↓
    Emby/Jellyfin/Plex
```

## Configuration

### Basic Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `token` | Real-Debrid API token | REQUIRED |
| `port` | WebDAV server port | 9999 |
| `check_for_changes_every_secs` | Library update polling interval | 10 |
| `network_buffer_size` | Streaming buffer (bytes) | 131072 (128KB) |

### Directory Organization

Zurg organizes content into directories based on filters:

```yaml
directories:
  shows:
    filters:
      - has_episodes: true   # Matches S01E01 pattern

  movies:
    only_show_the_biggest_file: true   # Hide sample files
    filters:
      - regex: /.*/  # Everything else
```

### Library Update Hook

When RD library changes, Zurg runs this command:

```yaml
on_library_update: cmd /c "C:\Users\noc\noc-homelab\windows\scripts\library-update.cmd"
```

This triggers:
1. FileBot to organize new content into symlinks
2. Emby/Jellyfin library scans
3. Cleanup of stale symlinks

## Scheduled Task

Zurg runs as a Windows Scheduled Task (`Homelab-Zurg`):
- **Trigger**: On system startup
- **User**: noc (requires user session for WebDAV mount)
- **Program**: `C:\Users\noc\noc-homelab\windows\scripts\start-zurg-hidden.vbs`

### Task Management
```powershell
# Start
schtasks /run /tn "Homelab-Zurg"

# Stop
taskkill /IM zurg.exe /F

# Check status
Get-Process zurg
```

## WebDAV Mount

### Mount Options

**Scheduled Task (Recommended)**:
```powershell
schtasks /run /tn "Homelab-RcloneMount"
```

**Manual Mount**:
```powershell
net use Z: http://localhost:9999/dav
```

**Persistent Mount** (survives reboot):
```powershell
net use Z: http://localhost:9999/dav /persistent:yes
```

### Unmount
```powershell
net use Z: /delete
```

### Troubleshooting Mount

If mount fails:

```powershell
# Check if WebDAV client is enabled
Get-WindowsOptionalFeature -Online -FeatureName WebDAV-Redirector

# Enable if needed
Enable-WindowsOptionalFeature -Online -FeatureName WebDAV-Redirector

# Check if Zurg is running
Get-Process zurg

# Check if port is listening
netstat -an | findstr :9999

# Try accessing via browser
Start http://localhost:9999
```

## Logs

**Zurg logs**: `C:\Users\noc\noc-homelab\windows\logs\zurg.log`

View logs:
```powershell
Get-Content C:\Users\noc\noc-homelab\windows\logs\zurg.log -Tail 50 -Wait
```

## Troubleshooting

### Zurg won't start

**Check token**:
```powershell
# Test token via RD API
curl https://api.real-debrid.com/rest/1.0/user -H "Authorization: Bearer YOUR_TOKEN"
```

**Check port**:
```powershell
# See if something else is using port 9999
netstat -an | findstr :9999
```

**Check config syntax**:
- Copy config to https://www.yamllint.com/
- Fix any syntax errors (indentation, colons, etc.)

### Z: drive is empty

**Check RD has content**:
1. Go to https://real-debrid.com/torrents
2. Add a test torrent
3. Wait 10-60 seconds for Zurg to detect it

**Force refresh**:
```powershell
# Restart Zurg
taskkill /IM zurg.exe /F
schtasks /run /tn "Homelab-Zurg"
```

### Library updates not triggering

**Check hook script**:
```powershell
# Verify script exists
Test-Path C:\Users\noc\noc-homelab\windows\scripts\library-update.cmd

# Run manually
C:\Users\noc\noc-homelab\windows\scripts\library-update.cmd
```

**Check logs**:
```powershell
Get-Content C:\Users\noc\noc-homelab\windows\logs\library-update.log -Tail 50
```

### Streaming is slow/buffering

**Increase buffer**:
```yaml
network_buffer_size: 262144  # 256KB (was 128KB)
```

**Check RD server location**:
- RD automatically selects closest server
- Some locations/ISPs have better RD performance
- Test different times of day

**Check network**:
```powershell
# Test speed to RD
curl -o nul https://real-debrid.com/speedtest/100MB.test
```

## Advanced Configuration

### Custom Directory Filters

Separate 4K content:
```yaml
directories:
  4k_movies:
    group: media
    group_order: 15
    only_show_the_biggest_file: true
    filters:
      - regex: /.*2160p.*/
      - has_episodes: false

  movies:
    group: media
    group_order: 20
    only_show_the_biggest_file: true
    filters:
      - regex: /^(?!.*2160p).*/  # Exclude 4K
```

### Plex Optimization

For Plex users:
```yaml
serve_from_rclone: true  # Better compatibility with Plex
```

### Debug Logging

Enable detailed logs:
```yaml
log_level: debug
```

## Security Notes

- **Token is sensitive** - config.yml is gitignored
- **Regenerate token** if exposed: https://real-debrid.com/apitoken
- **Z: drive is local** - Only accessible from this machine
- **Port 9999** is localhost only (not exposed to network)

## Related Components

- **Rclone Mount**: Mounts Z: with VFS caching (optional, for better Plex support)
- **FileBot**: Organizes new content into proper folder structure
- **library-update.ps1**: Runs FileBot + triggers media server scans
- **Emby/Jellyfin**: Media servers that scan the organized symlinks

## Upgrading Zurg

```powershell
# Download latest from: https://github.com/debridmediamanager/zurg-testing/releases
# Stop current instance
taskkill /IM zurg.exe /F

# Replace zurg.exe
Move-Item zurg.exe zurg.exe.backup
# Download new version to this directory

# Start new version
schtasks /run /tn "Homelab-Zurg"
```

## Resources

- **GitHub**: https://github.com/debridmediamanager/zurg-testing
- **Discord**: https://discord.gg/wDgVdH8vNM (debrid media manager community)
- **Real-Debrid**: https://real-debrid.com/
