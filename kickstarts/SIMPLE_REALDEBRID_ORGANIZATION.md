# Simple Real-Debrid Organization - Kickstart

**Created:** 2025-12-30
**Platform:** macOS (Darwin 24.5.0)
**Goal:** Keep using Real-Debrid Manager, add automatic movie/TV folder separation for Emby

---

## What This Does

✅ **Keeps your exact workflow:**
- Use Real-Debrid Manager on phone/browser (no change!)
- Search, pick quality (including 4K Dolby Vision), add content
- Same instant playback you love

✅ **Adds automatic organization:**
- Zurg monitors your Real-Debrid account
- Auto-separates movies → `/movies`, TV shows → `/tv`
- Emby scans as separate libraries
- **Problem solved!**

✅ **Minimal setup:**
- Primary: Zurg only (~15 minutes)
- Upgrade option: Add CineSync for better TV handling (~30 minutes more)

---

## Storage Requirements

**Local disk usage:**
- Zurg config/cache: ~50-100MB
- Emby metadata: ~500MB-1GB
- CineSync (if upgraded): ~100-200MB
- **Total: ~1-2GB** (perfect for 1TB disk!)

**Real-Debrid account:**
- Active premium subscription (you already have this!)
- Unlimited streaming from cached content

---

## Primary Setup: Real-Debrid Manager + Zurg

### Overview

**What you keep:**
- Real-Debrid Manager (browser extension, app, or DMM)
- Your mobile/desktop search workflow
- Quality selection (4K, Dolby Vision, Remux, etc.)
- Instant playback for cached torrents

**What Zurg adds:**
- Automatic folder organization (movies vs TV)
- WebDAV endpoint for Emby to access
- No workflow changes needed!

**Total setup time:** ~15 minutes

---

## Installation: Zurg

### Step 1: Get Real-Debrid API Token

```bash
# Open Real-Debrid API page
open https://real-debrid.com/apitoken

# Copy your API token (looks like: ABC123XYZ...)
# Keep this handy for next step
```

### Step 2: Create Zurg Configuration

```bash
# Create directories
mkdir -p ~/zurg/config
mkdir -p ~/zurg/data
mkdir -p ~/zurg/logs

# Create config file
cat > ~/zurg/config/config.yml <<'EOF'
# Zurg Configuration for Real-Debrid Organization

# Your Real-Debrid API token
token: YOUR_REAL_DEBRID_API_TOKEN_HERE

# Directory organization rules
directories:
  # Main organized view
  __all__:
    group: |
      # Movies: Files with year pattern (1900-2099)
      /movies: ^.*\.(mkv|mp4|avi|m4v).*\b(19|20)\d{2}\b

      # TV Shows: Files with S##E## pattern
      /tv: ^.*[Ss]\d+[Ee]\d+.*\.(mkv|mp4|avi|m4v)

      # Catch remaining video files
      /other: ^.*\.(mkv|mp4|avi|m4v)

  # Quality-based organization (optional - uncomment if desired)
  # quality:
  #   group: |
  #     /4K: (?i)(2160p|4k|uhd)
  #     /1080p: (?i)1080p
  #     /720p: (?i)720p

  # Dolby Vision content (optional)
  # dolby:
  #   group: |
  #     /dolby-vision: (?i)(dv|dolby.vision|doVi)

# Enable on-the-fly file repair (better compatibility)
enable_repair: true

# Network settings
network_buffer_size: 512KB

# WebDAV server configuration
serve:
  port: 9999

# Logging
log_level: info
EOF

# Replace YOUR_REAL_DEBRID_API_TOKEN_HERE with your actual token
# Get your token from: https://real-debrid.com/apitoken
echo ""
echo "⚠️  IMPORTANT: Edit ~/zurg/config/config.yml and add your Real-Debrid API token!"
echo ""
```

**Edit the config file:**
```bash
# Open in default editor
open -e ~/zurg/config/config.yml

# Or use nano
nano ~/zurg/config/config.yml

# Replace: YOUR_REAL_DEBRID_API_TOKEN_HERE
# With your actual token from https://real-debrid.com/apitoken
# Save and exit (Ctrl+X, Y, Enter in nano)
```

### Step 3: Run Zurg via Docker

```bash
# Ensure Docker Desktop is running
open -a Docker

# Wait for Docker to start (check menu bar icon)
echo "Waiting for Docker to start..."
sleep 10

# Run Zurg container
docker run -d \
  --name zurg \
  -p 9999:9999 \
  -v ~/zurg/config:/app/config \
  -v ~/zurg/data:/app/data \
  -v ~/zurg/logs:/app/logs \
  --restart unless-stopped \
  ghcr.io/debridmediamanager/zurg:latest

# Verify Zurg is running
docker ps | grep zurg

# Check logs
docker logs zurg

# Test WebDAV endpoint
echo ""
echo "Testing Zurg WebDAV endpoint..."
curl -I http://localhost:9999/dav/
echo ""
```

**Expected output:**
```
HTTP/1.1 200 OK
Content-Type: text/html
```

If you see errors, check `docker logs zurg` for details.

---

## Step 4: Mount Zurg WebDAV in macOS

### Method 1: Finder GUI (Simple)

```bash
# 1. Press Cmd+K (or Go → Connect to Server in Finder)
# 2. Enter: http://localhost:9999/dav/
# 3. Click Connect (no authentication needed)
# 4. Volume mounts at /Volumes/dav/

# Verify mount
ls -la /Volumes/dav/

# You should see:
# drwxr-xr-x  movies/
# drwxr-xr-x  tv/
# drwxr-xr-x  other/
# drwxr-xr-x  __all__/  (everything, unorganized)
```

### Method 2: Terminal Mount (Persistent)

```bash
# Create mount point
mkdir -p ~/RealDebrid

# Mount WebDAV
osascript -e 'mount volume "http://localhost:9999/dav/"'

# Create symlinks to home directory for easy access
ln -s /Volumes/dav ~/RealDebrid-Mount

# Verify
ls -la ~/RealDebrid-Mount/
```

### Make Mount Persistent Across Reboots

**Option A: Login Items (Easiest)**
1. System Settings → General → Login Items
2. Click "+" to add
3. Navigate to `/Volumes/dav/` (must be mounted first)
4. Add to login items

**Option B: LaunchAgent (Advanced)**

```bash
cat > ~/Library/LaunchAgents/com.noc.zurg.mount.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.noc.zurg.mount</string>
    <key>ProgramArguments</key>
    <array>
        <string>osascript</string>
        <string>-e</string>
        <string>mount volume "http://localhost:9999/dav/"</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardErrorPath</key>
    <string>/Users/noc/zurg/logs/mount.error.log</string>
    <key>StandardOutPath</key>
    <string>/Users/noc/zurg/logs/mount.log</string>
</dict>
</plist>
EOF

# Load LaunchAgent
launchctl load ~/Library/LaunchAgents/com.noc.zurg.mount.plist
```

---

## Step 5: Configure Emby Libraries

### Add Movie Library

1. Open Emby: http://localhost:8096
2. Settings → Library → Add Media Library
3. Content type: **Movies**
4. Folders → Add folder: `/Volumes/dav/movies`
5. **Important settings:**
   - Enable: Automatically refresh metadata from the internet
   - Enable: Save artwork into media folders (if you want)
   - Real-time monitoring: Enable if supported (may not work over WebDAV)
6. Click OK

### Add TV Show Library

1. Add Media Library
2. Content type: **Shows**
3. Folders → Add folder: `/Volumes/dav/tv`
4. **Important settings:**
   - Season folder pattern: Season %s
   - Episode naming: Default
   - Real-time monitoring: Enable if supported
5. Click OK

### Alternative: Use Symlinks (If WebDAV Issues)

If Emby has trouble with WebDAV directly:

```bash
# Create local media directories
mkdir -p ~/media/movies
mkdir -p ~/media/tv

# Create symlinks pointing to WebDAV mount
# Note: This requires WebDAV to be mounted first
ln -s /Volumes/dav/movies/* ~/media/movies/ 2>/dev/null || true
ln -s /Volumes/dav/tv/* ~/media/tv/ 2>/dev/null || true

# Point Emby at ~/media/movies and ~/media/tv instead
# You'll need to refresh symlinks when new content is added
```

**Script to refresh symlinks:**
```bash
cat > ~/zurg/refresh-symlinks.sh <<'EOF'
#!/bin/bash
# Refresh symlinks from Zurg mount to local media directories

# Remove old symlinks
find ~/media/movies -type l -delete
find ~/media/tv -type l -delete

# Create new symlinks
ln -s /Volumes/dav/movies/* ~/media/movies/ 2>/dev/null || true
ln -s /Volumes/dav/tv/* ~/media/tv/ 2>/dev/null || true

# Trigger Emby library scan (optional - requires Emby API)
# curl -X POST "http://localhost:8096/Library/Refresh?api_key=YOUR_EMBY_API_KEY"

echo "Symlinks refreshed!"
EOF

chmod +x ~/zurg/refresh-symlinks.sh

# Run manually when you add new content
~/zurg/refresh-symlinks.sh
```

---

## Step 6: Test the Workflow

### Add a Movie via Real-Debrid Manager

1. **On your phone/browser:** Open Real-Debrid Manager
2. **Search:** "Inception 2010"
3. **Pick quality:** 4K Dolby Vision Remux (or whatever you want)
4. **Add to Real-Debrid**

### Wait for Zurg to Organize (~30 seconds)

```bash
# Check if movie appears in organized folder
ls -la /Volumes/dav/movies/ | grep -i inception

# You should see:
# Inception.2010.2160p.UHD.BluRay.REMUX.DV.HDR.TrueHD.Atmos.7.1-FraMeSToR/
```

### Check Emby

1. Open Emby: http://localhost:8096
2. Go to Movies library
3. Click "Scan Library" (or wait for auto-scan if enabled)
4. **Inception should appear!**
5. Click play → streams from Real-Debrid

### Add a TV Show via Real-Debrid Manager

1. **Search:** "Breaking Bad S01E01"
2. **Pick quality:** 1080p BluRay
3. **Add to Real-Debrid**

### Check TV Organization

```bash
# Check if episode appears
ls -la /Volumes/dav/tv/ | grep -i "breaking"

# You should see:
# Breaking.Bad.S01E01.1080p.BluRay.x264/
```

### Check Emby TV Library

1. Go to Shows library
2. Scan library
3. **Breaking Bad should appear**

---

## Dashboard Integration

### Add Zurg to Dashboard

Edit `/Users/noc/noc-homelab/dashboard/app.py`:

```python
# Add to SERVICES dictionary (around line 15-74)

'zurg': {
    'name': 'Zurg',
    'launchd': 'disabled',  # Docker container
    'port': 9999,
    'log_paths': ['~/zurg/logs/*.log', '~/zurg/data/logs/*.log'],
    'description': 'Real-Debrid WebDAV organizer'
}
```

**Restart dashboard:**
```bash
launchctl unload ~/Library/LaunchAgents/com.noc.dashboard.plist
launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist
```

**Access dashboard:**
- http://noc-local:8080
- Zurg should appear with status and controls

---

## Upgrade Option: Add CineSync (Better TV Handling)

If Zurg's TV show handling isn't good enough (e.g., full seasons don't organize properly), upgrade to CineSync.

### Why Upgrade to CineSync?

**Zurg limitations:**
- Basic regex matching (may miss some TV shows)
- No episode tracking across seasons
- Manual Emby scans needed

**CineSync improvements:**
- ✅ Intelligent TV season/episode detection
- ✅ Automatic Emby library notifications
- ✅ Web UI for library management
- ✅ Better handling of multi-season packs
- ✅ Real-time monitoring and instant updates
- ✅ 4K/anime/kids content auto-separation

### Installation: CineSync

```bash
# Create directories
mkdir -p ~/cinesync/config
mkdir -p ~/cinesync/data
mkdir -p ~/media/movies
mkdir -p ~/media/tv

# Run CineSync (keeps Zurg running too!)
docker run -d \
  --name cinesync \
  -p 3005:3005 \
  -e PUID=501 \
  -e PGID=20 \
  -e TZ=America/Los_Angeles \
  -v ~/cinesync/config:/config \
  -v ~/cinesync/data:/data \
  -v /Volumes/dav:/source:ro \
  -v ~/media:/media \
  --restart unless-stopped \
  sureshfizzy/cinesync:latest

# Wait for container to start
sleep 10

# Open CineSync web UI
open http://localhost:3005
```

### Initial CineSync Setup

1. **Go to:** http://localhost:3005
2. **Settings → Source:**
   - Source Type: `Debrid Mount`
   - Source Path: `/source/__all__` (Zurg mount)
   - Scan interval: `300` (5 minutes)
3. **Settings → Destination:**
   - Movies path: `/media/movies`
   - TV Shows path: `/media/tv`
4. **Settings → Debrid:**
   - Provider: `Real-Debrid`
   - API Key: (your Real-Debrid token)
   - Enable repair: Yes
5. **Settings → Media Server:**
   - Type: `Emby`
   - URL: `http://host.docker.internal:8096`
   - API Key: (from Emby → Settings → Advanced → API Keys)
   - Auto-update library: Yes
6. **Save settings**

### Update Emby Libraries (CineSync Mode)

**Change Emby library paths:**
1. Movies library: `/Users/noc/media/movies` (instead of `/Volumes/dav/movies`)
2. TV Shows library: `/Users/noc/media/tv` (instead of `/Volumes/dav/tv`)

**Why?** CineSync creates better organized symlinks in `~/media/` with proper metadata structure.

### Workflow with CineSync

1. **Add content via Real-Debrid Manager** (same as before!)
2. **CineSync automatically:**
   - Detects new content in Zurg mount
   - Identifies if it's movie or TV show (using TMDb)
   - Creates organized symlink in proper folder
   - Notifies Emby to scan just that folder
3. **Watch in Emby** (faster than Zurg, with better organization)

### Add CineSync to Dashboard

```python
# Add to dashboard/app.py SERVICES dict

'cinesync': {
    'name': 'CineSync',
    'launchd': 'disabled',  # Docker container
    'port': 3005,
    'log_paths': ['~/cinesync/config/logs/*.log'],
    'description': 'Intelligent Real-Debrid library organizer'
}
```

---

## Troubleshooting

### Zurg Not Starting

```bash
# Check Docker is running
docker ps

# Check Zurg logs
docker logs zurg

# Common issues:
# 1. API token incorrect
#    - Verify at ~/zurg/config/config.yml
#    - Regenerate at https://real-debrid.com/apitoken

# 2. Port 9999 already in use
lsof -i :9999
# Kill process or change port in config.yml

# 3. Config syntax error
docker logs zurg | grep -i error

# Restart Zurg
docker restart zurg
```

### WebDAV Mount Not Appearing

```bash
# Check if Zurg is responding
curl http://localhost:9999/dav/

# Should return HTML directory listing

# Unmount and remount
umount /Volumes/dav 2>/dev/null
osascript -e 'mount volume "http://localhost:9999/dav/"'

# Verify mount
ls -la /Volumes/dav/

# If mount fails:
# - Check Zurg is running: docker ps | grep zurg
# - Check Zurg logs: docker logs zurg
# - Try rebooting Mac (sometimes WebDAV gets stuck)
```

### Content Not Organizing into Movies/TV

```bash
# Check Zurg is scanning Real-Debrid
docker logs zurg | tail -50

# Check if content appears in __all__ folder
ls -la /Volumes/dav/__all__/

# If files are there but not in /movies or /tv:
# 1. Check regex patterns in ~/zurg/config/config.yml
# 2. File might not match patterns (check filename)
# 3. Restart Zurg to reload config
docker restart zurg

# Test regex pattern manually
# Example filename: Inception.2010.1080p.BluRay.x264.mkv
# Should match: ^.*\.(mkv|mp4|avi|m4v).*\b(19|20)\d{2}\b
# Contains: .mkv and 2010 (year) → goes to /movies

# TV show example: Breaking.Bad.S01E01.1080p.mkv
# Should match: ^.*[Ss]\d+[Ee]\d+.*\.(mkv|mp4|avi|m4v)
# Contains: S01E01 → goes to /tv
```

### Emby Not Seeing Files

**If using direct WebDAV mount:**
```bash
# Check files are visible
ls -la /Volumes/dav/movies/

# Force Emby library scan
# Emby → Dashboard → Libraries → Scan All Libraries

# Check Emby logs
tail -f ~/.config/emby-server/logs/embyserver*.txt

# If issues persist, switch to symlink method (see Step 5)
```

**If using symlinks:**
```bash
# Refresh symlinks
~/zurg/refresh-symlinks.sh

# Verify symlinks exist
ls -la ~/media/movies/
ls -la ~/media/tv/

# Scan Emby library
```

### TV Shows Not Organizing Properly (Full Seasons)

This is where **CineSync upgrade** helps!

**Zurg limitation:**
- Relies on filename patterns
- May not detect season packs properly
- Example: "Breaking.Bad.Season.1.Complete.1080p.BluRay" might not match S##E## pattern

**Solution:**
1. Upgrade to CineSync (see upgrade section above)
2. CineSync uses TMDb metadata instead of just filenames
3. Detects full seasons and organizes episodes properly

**Or manually adjust Zurg config:**
```yaml
# Add to ~/zurg/config/config.yml under /tv: pattern
/tv: ^.*(([Ss]\d+[Ee]\d+)|(Season.\d+)|(Complete)).*\.(mkv|mp4|avi|m4v)

# This adds:
# - S##E## pattern (existing)
# - Season.## pattern (for season packs)
# - Complete pattern (for complete series)
```

### Real-Debrid Content Disappearing

**Real-Debrid deletes inactive torrents after 60 days:**
- Keep content active by accessing it
- Or re-add to Real-Debrid when needed
- Zurg doesn't prevent deletion (it just organizes what's there)

**Check Real-Debrid web interface:**
```bash
open https://real-debrid.com/torrents

# Verify content is still in your account
# If deleted, re-add via Real-Debrid Manager
```

### CineSync Not Detecting New Content

```bash
# Check CineSync logs
docker logs cinesync

# Check if Zurg mount is accessible
ls -la /Volumes/dav/__all__/

# Verify CineSync settings
open http://localhost:3005

# Settings → Source:
#   - Source Path must be: /source/__all__
#   - Not /source/movies or /source/tv

# Force manual scan
# CineSync UI → Dashboard → Force Scan

# Check permissions
# CineSync container must read /Volumes/dav (mounted as /source)
```

---

## Performance & Optimization

### Zurg Caching

**Zurg caches Real-Debrid metadata:**
- Cache location: `~/zurg/data/`
- Refresh interval: configurable in config.yml
- Typical cache size: 50-100MB

**Improve performance:**
```yaml
# Edit ~/zurg/config/config.yml

# Increase cache size (if you have lots of content)
cache_size: 1000  # Default: 500

# Adjust scan interval (how often to check Real-Debrid)
scan_interval: 300  # 5 minutes (default)

# Enable compression
enable_compression: true
```

### Emby Streaming Performance

**Direct Play settings:**
1. Emby → Settings → Playback
2. Enable: Direct Play
3. Disable: Transcoding (unless needed for compatibility)
4. Hardware acceleration: Enable (if available)

**Network buffer:**
- Real-Debrid serves files at high speed (up to 500Mbps)
- No buffering needed for most content
- Emby can direct play 4K Remux files smoothly

### Disk Space Monitoring

```bash
# Check local disk usage
du -sh ~/zurg/
du -sh ~/cinesync/
du -sh ~/media/  # Only symlinks, minimal space
du -sh ~/.config/emby-server/

# Typical usage:
# Zurg: 50-100MB
# CineSync: 100-200MB
# Emby metadata: 500MB-1GB
# Media symlinks: <10MB (just pointers)
```

---

## Maintenance

### Update Zurg

```bash
# Pull latest image
docker pull ghcr.io/debridmediamanager/zurg:latest

# Stop and remove old container
docker stop zurg
docker rm zurg

# Run new container (same command as installation)
docker run -d \
  --name zurg \
  -p 9999:9999 \
  -v ~/zurg/config:/app/config \
  -v ~/zurg/data:/app/data \
  -v ~/zurg/logs:/app/logs \
  --restart unless-stopped \
  ghcr.io/debridmediamanager/zurg:latest

# Verify
docker logs zurg
```

### Update CineSync

```bash
# Pull latest image
docker pull sureshfizzy/cinesync:latest

# Stop and remove old container
docker stop cinesync
docker rm cinesync

# Run new container (same command as installation)
docker run -d \
  --name cinesync \
  -p 3005:3005 \
  -e PUID=501 \
  -e PGID=20 \
  -e TZ=America/Los_Angeles \
  -v ~/cinesync/config:/config \
  -v ~/cinesync/data:/data \
  -v /Volumes/dav:/source:ro \
  -v ~/media:/media \
  --restart unless-stopped \
  sureshfizzy/cinesync:latest
```

### Backup Configurations

```bash
# Create backup script
cat > ~/zurg/backup-configs.sh <<'EOF'
#!/bin/bash
# Backup Zurg and CineSync configs to homelab repo

REPO_DIR="/Users/noc/noc-homelab"

# Create backup directories
mkdir -p "$REPO_DIR/configs/zurg"
mkdir -p "$REPO_DIR/configs/cinesync"

# Backup Zurg config
cp ~/zurg/config/config.yml "$REPO_DIR/configs/zurg/"

# Backup CineSync config (if exists)
if [ -d ~/cinesync/config ]; then
    cp -r ~/cinesync/config/* "$REPO_DIR/configs/cinesync/"
fi

# Commit to git
cd "$REPO_DIR"
git add configs/zurg/ configs/cinesync/
git commit -m "Backup Zurg/CineSync configs - $(date +%Y-%m-%d)"

echo "✅ Configs backed up!"
EOF

chmod +x ~/zurg/backup-configs.sh

# Run backup
~/zurg/backup-configs.sh
```

### Monitor Real-Debrid Usage

```bash
# Check Real-Debrid account status
open https://real-debrid.com/

# View active torrents
open https://real-debrid.com/torrents

# Check API usage (if concerned)
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
  https://api.real-debrid.com/rest/1.0/user | jq
```

---

## Security

### API Keys

**Real-Debrid API Token:**
- Stored in: `~/zurg/config/config.yml`
- **Never commit to git!** (already in .gitignore)
- Regenerate if compromised: https://real-debrid.com/apitoken

**Emby API Key:**
- Stored in: `~/cinesync/config/` (if using CineSync)
- Create separate keys for different services
- Emby → Settings → Advanced → API Keys

### Network Access

**Services accessible only on LAN:**
- Zurg WebDAV: http://localhost:9999 (via Tailscale as noc-local)
- CineSync UI: http://localhost:3005 (via Tailscale)
- Emby: http://noc-local:8096 (existing setup)

**Remote access:**
- Use Tailscale (already configured)
- Don't expose ports to internet
- Real-Debrid Manager works from anywhere (uses RD servers)

### gitignore Configuration

Ensure these are in `/Users/noc/noc-homelab/.gitignore`:

```gitignore
# Zurg
zurg/data/
zurg/logs/
configs/zurg/config.yml

# CineSync
cinesync/data/
cinesync/config/

# API tokens
**/config.yml
**/*API_KEY*
**/*TOKEN*
```

---

## Comparison: Zurg vs CineSync

| Feature | Zurg Only | Zurg + CineSync |
|---------|-----------|-----------------|
| Setup Time | 15 mins | 45 mins total |
| Complexity | ⭐ Simple | ⭐⭐ Medium |
| TV Season Handling | Basic (regex) | Advanced (metadata) |
| Web UI | ❌ | ✅ |
| Emby Auto-Notify | ❌ (manual scan) | ✅ |
| Storage Used | ~50MB | ~250MB |
| Quality Detection | Filename only | Metadata + filename |
| Episode Tracking | ❌ | ✅ |
| Best For | Movies + simple TV | Complex TV seasons |

---

## Your Workflow (Final)

### With Zurg Only:

1. **On phone:** Open Real-Debrid Manager
2. **Search:** "Dune 2021 4K Dolby Vision"
3. **Add:** Pick best quality torrent
4. **Wait:** ~30 seconds for Zurg to organize
5. **Emby:** Manual scan or auto-scan (if enabled)
6. **Watch:** Stream from Real-Debrid instantly!

**Storage used:** ~1-2GB total
**Quality:** Your choice (4K DV, Remux, whatever you pick!)
**Separation:** Movies and TV in different Emby libraries ✅

### With Zurg + CineSync (Upgraded):

1. **On phone:** Open Real-Debrid Manager (same!)
2. **Search:** "Breaking Bad Season 1 Complete"
3. **Add:** Full season pack
4. **Wait:** ~1 minute for CineSync to process
5. **Emby:** Auto-scans automatically (CineSync notifies)
6. **Watch:** All episodes organized properly!

**Storage used:** ~2GB total
**Better:** TV season/episode organization
**Faster:** Emby updates automatically

---

## Next Steps

### Start with Zurg:

1. Install Docker Desktop (if not already)
2. Follow "Installation: Zurg" section
3. Mount WebDAV in Finder
4. Configure Emby libraries
5. Test with one movie and one TV episode
6. **If it works for you → DONE!** 🎉

### Upgrade to CineSync if needed:

- TV seasons not organizing well? → Add CineSync
- Want web UI for library management? → Add CineSync
- Want automatic Emby notifications? → Add CineSync

**Both can run together!** Zurg provides the WebDAV mount, CineSync adds intelligence on top.

---

## Reference Links

**Zurg:**
- [Zurg GitHub](https://github.com/debridmediamanager/zurg-testing)
- [Zurg Organization Guide](https://github.com/debridmediamanager/zurg-testing/wiki/Organizing-Your-Torrents-Made-Easy)
- [Zurg Configuration](https://notes.debridmediamanager.com/zurg-configuration/)

**CineSync:**
- [CineSync GitHub](https://github.com/sureshfizzy/CineSync)
- [CineSync Installation](https://github.com/sureshfizzy/CineSync/wiki/Installation)
- [CineSync Features](https://deepwiki.com/debridmediamanager/debrid-media-manager/1.1-features-and-capabilities)

**Real-Debrid:**
- [API Token](https://real-debrid.com/apitoken)
- [Torrent Management](https://real-debrid.com/torrents)

**Community:**
- [Savvy Guides: Plex + Real-Debrid](https://savvyguides.wiki/sailarrsguide/)
- [ElfHosted: Zurg with Emby](https://docs.elfhosted.com/app/zurg/)
- [Debrid Media Manager Notes](https://notes.debridmediamanager.com/)

---

## Support

**If you encounter issues:**
1. Check Troubleshooting section above
2. Check Docker logs: `docker logs zurg` or `docker logs cinesync`
3. Verify Real-Debrid account is active
4. Search GitHub issues for specific errors
5. Ask in r/realdebrid or r/emby subreddits

---

**Setup Complete!** 🎉

**You now have:**
- ✅ Your exact Real-Debrid Manager workflow (unchanged!)
- ✅ Automatic movie/TV separation
- ✅ Streaming from Real-Debrid (no local storage!)
- ✅ ~1-2GB disk usage (perfect for 1TB Mac!)
- ✅ Upgrade path to CineSync if needed

**Enjoy unlimited streaming with organized libraries!**

---

**Start a new chat with:**
*"Use the SIMPLE_REALDEBRID_ORGANIZATION.md kickstart guide to set up Zurg"*
