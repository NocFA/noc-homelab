# Real-Debrid Streaming Setup (No Local Storage) - Kickstart

**Created:** 2025-12-30
**Platform:** macOS (Darwin 24.5.0)
**Goal:** Stream from Real-Debrid to Emby without local storage, mobile management via Helmarr, proper movie/TV separation

---

## ⚠️ CRITICAL: Streaming vs Downloading

This guide is for **STREAMING from Real-Debrid** (no local file storage). If you want to download files locally, use the other kickstart guide (ARR_STACK_SETUP.md).

**How streaming works:**
1. Content stays on Real-Debrid servers (cloud storage)
2. Zurg creates WebDAV endpoint to access Real-Debrid library
3. macOS mounts WebDAV as network volume
4. Emby scans mounted volume and streams files on-demand
5. **Uses only ~1-2GB local storage** (metadata/cache)

---

## Storage Requirements

**Local disk usage:**
- Zurg config/cache: ~100MB
- Emby metadata/artwork: ~500MB - 1GB
- plex_debrid or Radarr/Sonarr databases: ~100-500MB
- **Total: ~1-2GB** (perfect for 1TB disk!)

**Real-Debrid account:**
- Active premium subscription required
- ~2TB+ of cached content available instantly
- Unlimited streaming bandwidth

---

## Two Setup Options

### Option A: plex_debrid + Overseerr (RECOMMENDED - Simpler)

**Best for:** Users who want simple watchlist-based automation

**Workflow:**
1. Open Helmarr on iPhone → Overseerr
2. Search for movie/TV show
3. Tap "Request"
4. plex_debrid adds to Real-Debrid (instant if cached)
5. Zurg exposes via WebDAV
6. Emby auto-refreshes library
7. Watch within 10-20 seconds

**Pros:**
- ✅ Simpler setup (fewer components)
- ✅ Works with Helmarr (supports Overseerr)
- ✅ Auto-refreshes Emby libraries
- ✅ Fast: 10-20 seconds from request to streaming

**Cons:**
- ❌ Less granular control than Radarr/Sonarr
- ❌ Watchlist-based (can't browse indexers directly)

### Option B: Radarr/Sonarr + RDT-Client (Advanced)

**Best for:** Users who want maximum control and indexer browsing

**Workflow:**
1. Open Helmarr on iPhone → Radarr/Sonarr
2. Search for movie/TV show (via indexers)
3. Tap "Add" with quality profile
4. Radarr/Sonarr → RDT-Client → Real-Debrid
5. RDT-Client creates symlinks on mount
6. Emby scans symlinked folders
7. Watch within minutes

**Pros:**
- ✅ Maximum control (quality profiles, custom formats)
- ✅ Direct indexer access via NZBHydra2/Prowlarr
- ✅ Granular movie/TV separation
- ✅ Can use Usenet as fallback

**Cons:**
- ❌ More complex setup
- ❌ RDT-Client symlinks can be finicky on macOS
- ❌ More components to manage

---

## macOS Compatibility Note

⚠️ **Avoid macFUSE/rclone mount on macOS:**
- macFUSE requires kernel extension (being deprecated)
- Requires "Reduced Security" settings
- Reported as flaky on M1/M2 Macs
- Frequent disconnection issues

✅ **Use native macOS WebDAV mounting instead:**
- Finder → Connect to Server → `http://localhost:9999/dav/`
- No kernel extension needed
- No security setting changes
- Built-in macOS functionality

---

## Option A Setup: plex_debrid + Overseerr

### Components & Ports

| Component | Port | Purpose |
|-----------|------|---------|
| Zurg | 9999 | WebDAV server for Real-Debrid |
| plex_debrid | 5000 | Automation engine |
| Overseerr | 5055 | Request interface |
| Emby | 8096 | Media server (existing) |
| Dashboard | 8080 | Service control (existing) |

### Installation Steps

#### 1. Install Zurg (Real-Debrid WebDAV Server)

```bash
# Create directory
mkdir -p ~/zurg/config
mkdir -p ~/zurg/data

# Create config file
cat > ~/zurg/config/config.yml <<'EOF'
# Zurg configuration
token: YOUR_REAL_DEBRID_API_TOKEN_HERE

# Directories
directories:
  __all__:
    group: |
      /movies: ^.*\.(mkv|mp4|avi).*\b(19|20)\d{2}\b
      /tv: ^.*[Ss]\d+[Ee]\d+.*\.(mkv|mp4|avi)

# Enable on-the-fly repacking (better compatibility)
enable_repair: true

# WebDAV server settings
serve:
  port: 9999
EOF

# Get Real-Debrid API token
echo "Get your API token from: https://real-debrid.com/apitoken"
echo "Then edit ~/zurg/config/config.yml and replace YOUR_REAL_DEBRID_API_TOKEN_HERE"
```

**Run Zurg:**
```bash
docker run -d \
  --name zurg \
  -p 9999:9999 \
  -v ~/zurg/config:/app/config \
  -v ~/zurg/data:/app/data \
  --restart unless-stopped \
  ghcr.io/debridmediamanager/zurg:latest
```

**Verify Zurg:**
```bash
curl http://localhost:9999/dav/
# Should return WebDAV directory listing
```

#### 2. Mount Zurg WebDAV in macOS Finder

```bash
# Method 1: Finder GUI
# 1. Press Cmd+K (or Go → Connect to Server)
# 2. Enter: http://localhost:9999/dav/
# 3. Click Connect (no authentication needed)
# 4. Volume mounts at /Volumes/dav/

# Method 2: Terminal (persistent mount)
mkdir -p /Users/noc/RealDebrid
osascript -e 'mount volume "http://localhost:9999/dav/"'

# Verify mount
ls -la /Volumes/dav/
# Should see: movies/, tv/, __all__/
```

**Make mount persistent across reboots:**
```bash
# Add to Login Items
# System Settings → General → Login Items → Add /Volumes/dav/
# Or use launchd (advanced)
```

#### 3. Install plex_debrid

```bash
# Create directory
mkdir -p ~/plex_debrid/config

# Create config file
cat > ~/plex_debrid/config/config.json <<'EOF'
{
  "DEBRID_PROVIDER": "realdebrid",
  "REAL_DEBRID_API_KEY": "YOUR_API_KEY_HERE",

  "AUTO_UPDATE_INTERVAL": 300,
  "AUTO_DELETE_OLD": false,

  "EMBY_URL": "http://localhost:8096",
  "EMBY_API_KEY": "YOUR_EMBY_API_KEY_HERE",
  "EMBY_REFRESH_LIBRARY": true,

  "JELLYSEERR_URL": "http://localhost:5055",
  "JELLYSEERR_API_KEY": "YOUR_JELLYSEERR_API_KEY_HERE",

  "MOUNT_TORRENTS_PATH": "/zurg",
  "RCLONE_MOUNT_PATH": "/zurg"
}
EOF

# Run plex_debrid
docker run -d \
  --name plex_debrid \
  -p 5000:5000 \
  -v ~/plex_debrid/config:/config \
  -v /Volumes/dav:/zurg:ro \
  --restart unless-stopped \
  ghcr.io/itstoggle/plex_debrid:latest
```

**Note:** Get Emby API key from:
- Emby → Settings → Advanced → API Keys → Create New

#### 4. Install Overseerr (Request Interface)

```bash
# Install via Homebrew
brew install --cask overseerr

# Or via Docker
docker run -d \
  --name overseerr \
  -p 5055:5055 \
  -v ~/overseerr/config:/app/config \
  --restart unless-stopped \
  sctx/overseerr:latest
```

**Initial Setup:**
1. Go to http://localhost:5055
2. Sign in with Emby account
3. Settings → Services → Enable "Jellyfin/Emby"
4. Enter Emby URL and API key
5. Settings → General → Copy API key (for plex_debrid config)

#### 5. Configure Helmarr (iOS App)

**Install from App Store:**
- Search "Helmarr" and install

**Add Overseerr:**
1. Open Helmarr → Add Instance → Overseerr
2. Primary Host: `http://noc-local:5055`
3. API Key: (from Overseerr settings)
4. Test connection → Save

**Add Emby (for playback):**
1. Add Instance → Emby
2. Host: `http://noc-local:8096`
3. Username/Password: (your Emby credentials)
4. Test → Save

#### 6. Configure Emby Libraries

**Add Movie Library:**
1. Emby → Settings → Library → Add Library
2. Content Type: Movies
3. Folders: `/Volumes/dav/movies`
4. Enable: Real-time monitoring (if supported over WebDAV)

**Add TV Library:**
1. Add Library → TV Shows
2. Folders: `/Volumes/dav/tv`
3. Enable: Real-time monitoring

**Alternatively (if WebDAV causes issues):**
Create symlinks to local directory:
```bash
mkdir -p ~/media/movies ~/media/tv
ln -s /Volumes/dav/movies/* ~/media/movies/
ln -s /Volumes/dav/tv/* ~/media/tv/

# Point Emby at ~/media/movies and ~/media/tv
```

---

## Option B Setup: Radarr/Sonarr + RDT-Client

### Components & Ports

| Component | Port | Purpose |
|-----------|------|---------|
| Zurg | 9999 | WebDAV server for Real-Debrid |
| Radarr | 7878 | Movie automation |
| Sonarr | 8989 | TV automation |
| Prowlarr | 9696 | Indexer manager |
| RDT-Client | 6500 | Real-Debrid proxy |
| NZBHydra2 | 5076 | Usenet indexer (existing) |
| NZBGet | 6789 | Usenet downloader (existing) |
| Emby | 8096 | Media server (existing) |

### Installation Steps

**Follow steps 1-2 from Option A** (Install Zurg and mount WebDAV)

#### 3. Install *ARR Stack

```bash
# Install via Homebrew
brew install --cask radarr
brew install --cask sonarr
brew install --cask prowlarr

# Verify
open http://localhost:7878  # Radarr
open http://localhost:8989  # Sonarr
open http://localhost:9696  # Prowlarr
```

#### 4. Install RDT-Client

```bash
mkdir -p ~/rdt-client/config
mkdir -p ~/media/movies
mkdir -p ~/media/tv

docker run -d \
  --name rdt-client \
  -p 6500:6500 \
  -v ~/rdt-client/config:/data/db \
  -v /Volumes/dav:/mnt/realdebrid:ro \
  -v ~/media:/media \
  --restart unless-stopped \
  rogerfar/rdtclient:latest
```

**Configure RDT-Client:**
1. Go to http://localhost:6500
2. Settings → Provider → Real-Debrid
3. Enter API key (from https://real-debrid.com/apitoken)
4. Settings → Download Client:
   - Select "Symlink Downloader"
   - rclone Mount Path: `/mnt/realdebrid/__all__`
   - Mapped Path: `/mnt/realdebrid/__all__`
   - Download Path: `/media`
5. Save settings

#### 5. Configure Radarr (Movies)

**Settings → Media Management:**
- Root Folder: `/Users/noc/media/movies`
- Rename Movies: Yes

**Settings → Download Clients:**
- Add → qBittorrent (RDT-Client)
- Host: `localhost`
- Port: `6500`
- Category: `radarr`

**Settings → Indexers:**
- Add → Newznab (NZBHydra2)
- URL: `http://localhost:5076`
- API Key: (from NZBHydra2)

#### 6. Configure Sonarr (TV Shows)

**Settings → Media Management:**
- Root Folder: `/Users/noc/media/tv`
- Rename Episodes: Yes

**Settings → Download Clients:**
- Add → qBittorrent (RDT-Client)
- Host: `localhost`
- Port: `6500`
- Category: `sonarr`

**Settings → Indexers:**
- Add → Newznab (NZBHydra2)

#### 7. Configure Prowlarr (Indexer Manager)

**Add Indexers:**
- Add torrent indexers (1337x, RARBG, etc.)

**Sync to Apps:**
- Settings → Apps → Add Radarr
- Settings → Apps → Add Sonarr

#### 8. Configure Helmarr

**Add Radarr:**
1. Helmarr → Add Instance → Radarr
2. Host: `http://noc-local:7878`
3. API Key: (from Radarr settings)

**Add Sonarr:**
1. Add Instance → Sonarr
2. Host: `http://noc-local:8989`
3. API Key: (from Sonarr settings)

#### 9. Configure Emby Libraries

**Add libraries pointing to:**
- Movies: `/Users/noc/media/movies` (symlinks created by RDT-Client)
- TV: `/Users/noc/media/tv`

---

## Dashboard Integration

### Add Services to Dashboard

Edit `/Users/noc/noc-homelab/dashboard/app.py`:

**For Option A:**
```python
'zurg': {
    'name': 'Zurg',
    'launchd': 'disabled',  # Docker container
    'port': 9999,
    'log_paths': ['~/zurg/data/logs/*.log']
},
'plex-debrid': {
    'name': 'plex_debrid',
    'launchd': 'disabled',
    'port': 5000,
    'log_paths': ['~/plex_debrid/logs/*.log']
},
'overseerr': {
    'name': 'Overseerr',
    'launchd': 'homebrew.mxcl.overseerr',  # If Homebrew
    'port': 5055,
    'log_paths': ['~/overseerr/config/logs/*.log']
}
```

**For Option B:**
```python
'zurg': {
    'name': 'Zurg',
    'launchd': 'disabled',
    'port': 9999,
    'log_paths': ['~/zurg/data/logs/*.log']
},
'radarr': {
    'name': 'Radarr',
    'launchd': 'homebrew.mxcl.radarr',
    'port': 7878,
    'log_paths': ['~/Library/Logs/Radarr/*.txt']
},
'sonarr': {
    'name': 'Sonarr',
    'launchd': 'homebrew.mxcl.sonarr',
    'port': 8989,
    'log_paths': ['~/Library/Logs/Sonarr/*.txt']
},
'prowlarr': {
    'name': 'Prowlarr',
    'launchd': 'homebrew.mxcl.prowlarr',
    'port': 9696,
    'log_paths': ['~/Library/Logs/Prowlarr/*.txt']
},
'rdt-client': {
    'name': 'RDT-Client',
    'launchd': 'disabled',
    'port': 6500,
    'log_paths': ['~/rdt-client/config/logs/*.log']
}
```

**Restart dashboard:**
```bash
launchctl unload ~/Library/LaunchAgents/com.noc.dashboard.plist
launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist
```

---

## Usage Workflow

### Option A (plex_debrid + Overseerr):

1. **Open Helmarr on iPhone**
2. **Tap Overseerr tab**
3. **Search "Inception"**
4. **Tap "Request"**
5. **plex_debrid automatically:**
   - Checks if cached on Real-Debrid (instant!)
   - Adds to Real-Debrid if not cached
   - Monitors Zurg mount for completion
   - Refreshes Emby library
6. **Watch in Emby within 10-20 seconds**

### Option B (Radarr/Sonarr):

1. **Open Helmarr on iPhone**
2. **Tap Radarr or Sonarr tab**
3. **Search "Inception" or "Breaking Bad"**
4. **Select quality profile**
5. **Tap "Add"**
6. **Radarr/Sonarr automatically:**
   - Search indexers (NZBHydra2 + Prowlarr)
   - Send torrent to RDT-Client
   - RDT-Client adds to Real-Debrid
   - RDT-Client creates symlink in ~/media
7. **Emby scans symlink**
8. **Watch within minutes**

---

## Troubleshooting

### Zurg Not Accessible

```bash
# Check Docker container
docker ps | grep zurg
docker logs zurg

# Restart Zurg
docker restart zurg

# Test WebDAV
curl http://localhost:9999/dav/
```

### WebDAV Mount Not Appearing

```bash
# Check if mounted
ls -la /Volumes/dav/

# Remount
osascript -e 'mount volume "http://localhost:9999/dav/"'

# Check Zurg config
cat ~/zurg/config/config.yml
```

### Emby Can't See Files

**If using direct WebDAV mount:**
- Some WebDAV limitations exist with real-time monitoring
- Try manual library scan

**Switch to symlink approach:**
```bash
mkdir -p ~/media/movies ~/media/tv
ln -s /Volumes/dav/movies/* ~/media/movies/
ln -s /Volumes/dav/tv/* ~/media/tv/

# Point Emby at ~/media instead of /Volumes/dav
```

### Real-Debrid Content Not Appearing

**Check Real-Debrid account:**
```bash
# Visit Real-Debrid web interface
open https://real-debrid.com/torrents

# Verify content is there
# Check API key is correct in Zurg config
```

**Verify Zurg sees content:**
```bash
curl http://localhost:9999/dav/ | grep -i "movie-name"
```

### RDT-Client Symlinks Not Creating (Option B)

**Check paths:**
```bash
# Verify mount is accessible
ls -la /Volumes/dav/__all__/

# Check RDT-Client config
# Settings → Download Client → Symlink Downloader
# rclone Mount Path must match actual mount
```

**Common issues:**
- Path mismatch between Zurg mount and RDT-Client config
- Permissions on ~/media directory
- WebDAV mount disconnected

### plex_debrid Not Adding Content (Option A)

**Check logs:**
```bash
docker logs plex_debrid
```

**Verify config:**
```bash
cat ~/plex_debrid/config/config.json
# Ensure API keys are correct
# Ensure mount path matches: /zurg
```

**Test Overseerr connection:**
```bash
curl http://localhost:5055/api/v1/status
```

---

## Performance & Optimization

### Streaming Quality

**Real-Debrid serves files at:**
- Up to 500 Mbps download speed
- No transcoding needed for most content
- Direct play recommended in Emby

**Emby playback settings:**
- Enable Direct Play
- Disable transcoding (use original file)
- Hardware acceleration (if available)

### Storage Monitoring

**Check local disk usage:**
```bash
# Zurg cache
du -sh ~/zurg/

# Emby metadata
du -sh ~/.config/emby-server/

# plex_debrid or *arr databases
du -sh ~/plex_debrid ~/Library/Application\ Support/Radarr ~/Library/Application\ Support/Sonarr
```

**Typical usage:**
- Zurg: 50-100MB
- Emby metadata: 500MB - 1GB (grows with library size)
- plex_debrid: 50-100MB
- Radarr/Sonarr: 100-500MB each

### Real-Debrid Account Limits

**Fair use policy:**
- No specific bandwidth limit
- Don't abuse (excessive downloads may trigger review)
- Cached torrents are instant and don't count against limits

**Storage:**
- Torrents auto-delete after 60 days of inactivity
- Keep watchlist/library active to prevent deletion

---

## Security

### API Keys

**Real-Debrid API Key:**
- Keep private (full account access)
- Regenerate if compromised: https://real-debrid.com/apitoken
- Never commit to git

**Emby API Key:**
- Store securely (1Password recommended)
- Create separate keys for different services

### Network Access

**Local only (default):**
- Services accessible on LAN via Tailscale
- Overseerr/Radarr/Sonarr protected by Tailscale ACLs

**Remote access:**
- Use Tailscale for secure remote access
- Don't expose ports directly to internet
- Helmarr uses multi-network (LAN + Tailscale)

---

## Backup & Maintenance

### Backup Configurations

```bash
# Create backup directory
mkdir -p ~/noc-homelab/configs/zurg
mkdir -p ~/noc-homelab/configs/plex_debrid
mkdir -p ~/noc-homelab/configs/overseerr

# Backup configs
cp ~/zurg/config/config.yml ~/noc-homelab/configs/zurg/
cp ~/plex_debrid/config/config.json ~/noc-homelab/configs/plex_debrid/
cp ~/overseerr/config/settings.json ~/noc-homelab/configs/overseerr/

# For Option B
cp ~/Library/Application\ Support/Radarr/config.xml ~/noc-homelab/configs/radarr/
cp ~/Library/Application\ Support/Sonarr/config.xml ~/noc-homelab/configs/sonarr/

# Commit to git
cd ~/noc-homelab
git add configs/
git commit -m "Backup Real-Debrid streaming configs"
```

### Update Services

```bash
# Update Zurg
docker pull ghcr.io/debridmediamanager/zurg:latest
docker stop zurg && docker rm zurg
# Re-run docker run command

# Update plex_debrid
docker pull ghcr.io/itstoggle/plex_debrid:latest
docker stop plex_debrid && docker rm plex_debrid
# Re-run docker run command

# Update RDT-Client
docker pull rogerfar/rdtclient:latest
docker stop rdt-client && docker rm rdt-client
# Re-run docker run command

# Update Homebrew apps
brew upgrade --cask radarr sonarr prowlarr overseerr
```

---

## Comparison: Option A vs Option B

| Feature | Option A (plex_debrid) | Option B (Radarr/Sonarr) |
|---------|------------------------|--------------------------|
| Setup Complexity | ⭐⭐ (Simple) | ⭐⭐⭐⭐ (Complex) |
| Mobile Interface | Helmarr → Overseerr | Helmarr → Radarr/Sonarr |
| Search Method | Watchlist/request | Indexer browsing |
| Quality Control | Basic | Advanced (profiles) |
| Content Discovery | Overseerr trending | Indexer search |
| Speed to Watch | 10-20 seconds | 1-5 minutes |
| Usenet Support | No | Yes (via NZBGet) |
| Granular Control | Low | High |
| Component Count | 3 (Zurg, plex_debrid, Overseerr) | 6 (Zurg, Radarr, Sonarr, Prowlarr, RDT-Client, NZBHydra2) |
| Maintenance | Low | Medium |
| Best For | Simple watchlist workflow | Power users wanting control |

---

## Recommended: Option A (plex_debrid + Overseerr)

**For your use case:**
- ✅ 1TB disk (streaming saves space)
- ✅ Mobile workflow (Helmarr + Overseerr)
- ✅ Instant playback (Real-Debrid cached content)
- ✅ Simple maintenance
- ✅ macOS native WebDAV (no macFUSE)

**Start with Option A**, and if you need more control later, migrate to Option B.

---

## Reference Links

**Official Documentation:**
- [Zurg GitHub](https://github.com/debridmediamanager/zurg-testing)
- [plex_debrid GitHub](https://github.com/itsToggle/plex_debrid)
- [Overseerr Docs](https://docs.overseerr.dev)
- [RDT-Client GitHub](https://github.com/rogerfar/rdt-client)
- [Helmarr Website](https://helmarr.app)

**Community Guides:**
- [ElfHosted: Emby + Real-Debrid Streaming](https://docs.elfhosted.com/guides/media/emby-realdebrid-aars/)
- [Savvy Guides: Plex + Real-Debrid](https://savvyguides.wiki/sailarrsguide/)
- [Zurg Configuration Guide](https://notes.debridmediamanager.com/zurg-configuration/)

**Alternative Debrid Services:**
- [Premiumize](https://www.premiumize.me) - More expensive, more features
- [AllDebrid](https://alldebrid.com) - Cheaper alternative
- [TorBox](https://torbox.app) - New service with free tier

---

## Setup Complete! 🎉

**Option A Setup Time:** ~30 minutes
**Option B Setup Time:** ~1-2 hours

**You now have:**
- ✅ Unlimited streaming from Real-Debrid
- ✅ Mobile search/add via Helmarr
- ✅ Separate movie/TV libraries in Emby
- ✅ ~1-2GB disk usage (perfect for 1TB Mac!)
- ✅ 10-second watchlist-to-streaming workflow

**Next Steps:**
1. Install Helmarr on iPhone
2. Add first movie/TV show
3. Watch it stream instantly from Real-Debrid
4. Enjoy unlimited content with minimal storage!

---

**Questions or Issues?**
- Check Troubleshooting section
- Review component logs via dashboard
- Search GitHub issues for specific services
- Ask in r/realdebrid, r/overseerr subreddits
