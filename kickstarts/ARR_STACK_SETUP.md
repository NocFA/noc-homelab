# *ARR Stack + Real-Debrid + Helmarr Setup Kickstart

**Created:** 2025-12-30
**Platform:** macOS (Darwin 24.5.0)
**Goal:** Set up Radarr/Sonarr with Real-Debrid + Usenet, manageable via Helmarr iOS app, with proper movie/TV separation for Emby

---

## Overview

This setup provides:
- **Helmarr iOS app** - Mobile interface to search and add content
- **Radarr** - Automated movie downloads (to `/movies`)
- **Sonarr** - Automated TV downloads (to `/tv`)
- **RDT-Client** - Real-Debrid integration (instant cached torrents)
- **NZBGet** - Usenet downloads (already configured)
- **NZBHydra2** - Usenet indexer aggregation (already configured)
- **Prowlarr** - Torrent indexer management (optional but recommended)
- **Dispatcharr** - IPTV/Live TV management (separate project)

**Workflow:** Search on iPhone → Add via Helmarr → Auto-download via Radarr/Sonarr → Separate folders → Emby scans as different libraries

---

## System Requirements

✅ **macOS Compatibility:**
- macOS 11+ (Big Sur or newer)
- Your system: Darwin 24.5.0 ✓
- Homebrew installed ✓
- Docker Desktop (for RDT-Client)

✅ **Storage:**
- Separate directories for movies and TV shows
- Sufficient space for downloads (recommend 500GB+)

✅ **Network:**
- Real-Debrid account with active subscription
- Usenet provider (for NZBGet, if using Usenet)

✅ **Mobile:**
- Helmarr iOS app (App Store)
- Note: Requires iOS 18+ (some sources mention iOS 26 beta, verify current version)

---

## Port Assignments

| Service | Port | Status | Access |
|---------|------|--------|--------|
| Radarr | 7878 | New | http://noc-local:7878 |
| Sonarr | 8989 | New | http://noc-local:8989 |
| Prowlarr | 9696 | New | http://noc-local:9696 |
| RDT-Client | 6500 | New | http://noc-local:6500 |
| Dispatcharr | 9191 | New | http://noc-local:9191 |
| NZBGet | 6789 | Existing | http://noc-local:6789 |
| NZBHydra2 | 5076 | Existing | http://noc-local:5076 |
| Emby | 8096 | Existing | http://noc-local:8096 |
| Dashboard | 8080 | Existing | http://noc-local:8080 |

---

## Installation Steps

### 1. Install Core *ARR Apps via Homebrew

```bash
# Install Radarr (movies)
brew install --cask radarr

# Install Sonarr (TV shows)
brew install --cask sonarr

# Install Prowlarr (indexer manager - optional but recommended)
brew install --cask prowlarr
```

**Verification:**
```bash
# Check if services are running
open http://localhost:7878  # Radarr
open http://localhost:8989  # Sonarr
open http://localhost:9696  # Prowlarr
```

### 2. Install RDT-Client via Docker

**Install Docker Desktop:**
```bash
brew install --cask docker
# Open Docker Desktop and wait for it to start
```

**Run RDT-Client:**
```bash
# Create config directory
mkdir -p ~/rdt-client/config
mkdir -p ~/rdt-client/downloads

# Run RDT-Client container
docker run -d \
  --name rdt-client \
  -e PUID=501 \
  -e PGID=20 \
  -p 6500:6500 \
  -v ~/rdt-client/config:/data/db \
  -v ~/rdt-client/downloads:/data/downloads \
  --restart unless-stopped \
  rogerfar/rdtclient:latest
```

**Verification:**
```bash
docker ps | grep rdt-client
open http://localhost:6500
```

**Initial Setup:**
1. Go to http://localhost:6500
2. Settings → Provider → Select "Real-Debrid"
3. Enter your Real-Debrid API key (get from https://real-debrid.com/apitoken)
4. Settings → Download Client → Choose downloader (default: Bezzad is fine)
5. Save settings

### 3. Install Dispatcharr (Optional - for IPTV)

```bash
# Via Docker
docker run -d \
  --name dispatcharr \
  -p 9191:9191 \
  -v ~/dispatcharr/config:/config \
  --restart unless-stopped \
  dispatcharr/dispatcharr:latest
```

**Access:** http://localhost:9191

---

## Configuration

### 4. Configure Download Paths

**Create directory structure:**
```bash
# Create media directories
mkdir -p ~/media/movies
mkdir -p ~/media/tv

# Create download directories
mkdir -p ~/downloads/complete/radarr
mkdir -p ~/downloads/complete/sonarr
mkdir -p ~/downloads/incomplete
```

**Set permissions:**
```bash
chmod -R 755 ~/media
chmod -R 755 ~/downloads
```

### 5. Configure Radarr (Movies)

**Access:** http://localhost:7878

**Settings → Media Management:**
- Root Folder: `/Users/noc/media/movies`
- Rename Movies: Yes
- Replace Illegal Characters: Yes

**Settings → Download Clients:**

**Add RDT-Client (for torrents):**
- Name: `RDT-Client`
- Protocol: Torrent
- Client: qBittorrent
- Host: `localhost`
- Port: `6500`
- Username: (from RDT-Client settings)
- Password: (from RDT-Client settings)
- Category: `radarr`
- Priority: 1

**Add NZBGet (for Usenet):**
- Name: `NZBGet`
- Host: `localhost`
- Port: `6789`
- Username: (from NZBGet config)
- Password: (from NZBGet config)
- Category: `radarr`
- Priority: 2 (use Usenet as fallback)

**Settings → Indexers:**
- Add NZBHydra2 as Newznab indexer:
  - Name: `NZBHydra2`
  - URL: `http://localhost:5076`
  - API Key: (from NZBHydra2 settings)

**If using Prowlarr:** Skip manual indexer setup, let Prowlarr sync them.

### 6. Configure Sonarr (TV Shows)

**Access:** http://localhost:8989

**Settings → Media Management:**
- Root Folder: `/Users/noc/media/tv`
- Rename Episodes: Yes
- Episode Title Required: Season Folder

**Settings → Download Clients:**

**Add RDT-Client (for torrents):**
- Name: `RDT-Client`
- Protocol: Torrent
- Client: qBittorrent
- Host: `localhost`
- Port: `6500`
- Username: (from RDT-Client settings)
- Password: (from RDT-Client settings)
- Category: `sonarr`
- Priority: 1

**Add NZBGet (for Usenet):**
- Name: `NZBGet`
- Host: `localhost`
- Port: `6789`
- Username: (from NZBGet config)
- Password: (from NZBGet config)
- Category: `sonarr`
- Priority: 2

**Settings → Indexers:**
- Add NZBHydra2 as Newznab indexer:
  - Name: `NZBHydra2`
  - URL: `http://localhost:5076`
  - API Key: (from NZBHydra2 settings)

### 7. Configure Prowlarr (Indexer Manager - Optional)

**Access:** http://localhost:9696

**Settings → Indexers:**
- Add torrent indexers (1337x, RARBG, YTS, etc.)
- Configure each with search capabilities

**Settings → Apps:**
- Add Radarr:
  - Prowlarr Server: `http://localhost:9696`
  - Radarr Server: `http://localhost:7878`
  - API Key: (from Radarr Settings → General)
  - Sync Level: Full Sync

- Add Sonarr:
  - Prowlarr Server: `http://localhost:9696`
  - Sonarr Server: `http://localhost:8989`
  - API Key: (from Sonarr Settings → General)
  - Sync Level: Full Sync

**Prowlarr will automatically sync all indexers to Radarr and Sonarr.**

### 8. Configure Helmarr iOS App

**Install from App Store:**
- Search "Helmarr" and install

**Add Radarr:**
1. Open Helmarr → Add Instance → Radarr
2. Primary Host: `http://noc-local:7878` (or your Mac's IP)
3. API Key: (from Radarr Settings → General)
4. Test connection → Save

**Add Sonarr:**
1. Add Instance → Sonarr
2. Primary Host: `http://noc-local:8989`
3. API Key: (from Sonarr Settings → General)
4. Test connection → Save

**Add NZBGet:**
1. Add Instance → NZBGet
2. Host: `http://noc-local:6789`
3. Username/Password: (from NZBGet)
4. Test → Save

**Optional: Add Overseerr/Jellyseerr if you want a dedicated request interface**

### 9. Configure Emby Libraries

**Access:** http://localhost:8096

**Add Movie Library:**
- Library Type: Movies
- Folders: `/Users/noc/media/movies`
- Enable: Real-time monitoring

**Add TV Library:**
- Library Type: TV Shows
- Folders: `/Users/noc/media/tv`
- Enable: Real-time monitoring

**This ensures movies and TV shows are in separate Emby libraries.**

---

## Dashboard Integration

### 10. Add Services to Dashboard

Edit `/Users/noc/noc-homelab/dashboard/app.py` and add to `SERVICES` dict:

```python
'radarr': {
    'name': 'Radarr',
    'launchd': 'homebrew.mxcl.radarr',  # Homebrew services
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
    'launchd': 'disabled',  # Docker container, no launchd control
    'port': 6500,
    'log_paths': ['~/rdt-client/config/logs/*.log']
},
'dispatcharr': {
    'name': 'Dispatcharr',
    'launchd': 'disabled',  # Docker container
    'port': 9191,
    'log_paths': ['~/dispatcharr/config/logs/*.log']
}
```

**Restart dashboard:**
```bash
launchctl unload ~/Library/LaunchAgents/com.noc.dashboard.plist
launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist
```

### 11. Create LaunchAgents (Optional - for auto-start)

Homebrew services should handle this, but if needed:

```bash
# Start services via Homebrew
brew services start radarr
brew services start sonarr
brew services start prowlarr
```

**For Docker containers to auto-start:**
- Ensure `--restart unless-stopped` flag is set (already in commands above)
- Docker Desktop → Settings → General → "Start Docker Desktop when you log in"

---

## Usage Workflow

### Mobile Workflow (Primary):

1. **Open Helmarr on iPhone**
2. **Search for content:**
   - Tap Radarr tab → Search → "Inception"
   - Or tap Sonarr tab → Search → "Breaking Bad"
3. **Add to library:**
   - Select quality profile
   - Tap "Add"
4. **Automatic process:**
   - Radarr/Sonarr search indexers (NZBHydra2 + Prowlarr)
   - If torrent found: Sends to RDT-Client → Real-Debrid (instant if cached)
   - If Usenet found: Sends to NZBGet → Downloads
   - File moves to `/movies` or `/tv`
   - Emby auto-scans and adds to library
5. **Watch in Emby within minutes**

### Desktop Workflow:

1. Go to http://noc-local:7878 (Radarr) or http://noc-local:8989 (Sonarr)
2. Add Movie/TV Show
3. Same automatic process

---

## Troubleshooting

### Radarr/Sonarr Can't Connect to RDT-Client

**Check Docker container:**
```bash
docker ps | grep rdt-client
docker logs rdt-client
```

**Restart container:**
```bash
docker restart rdt-client
```

**Verify port:**
```bash
lsof -i :6500
```

### RDT-Client Not Downloading from Real-Debrid

**Check API key:**
- Go to http://localhost:6500/settings
- Verify Real-Debrid API key is correct
- Test connection

**Check Real-Debrid account:**
- Ensure subscription is active
- Check if torrent is cached (instant) or needs download

### Files Not Appearing in Emby

**Check file paths:**
```bash
ls -la ~/media/movies
ls -la ~/media/tv
```

**Force Emby scan:**
- Emby Dashboard → Libraries → Scan All Libraries

**Check permissions:**
```bash
chmod -R 755 ~/media
```

### Helmarr Can't Connect

**Ensure services are accessible:**
```bash
# From another device on network
curl http://noc-local:7878/api/v3/system/status
curl http://noc-local:8989/api/v3/system/status
```

**Check Tailscale:**
```bash
tailscale status
```

**Enable authentication:**
- Radarr/Sonarr Settings → General → Authentication: Forms (Basic)
- Set username/password
- Use these credentials in Helmarr

### Homebrew Services Not Starting

**Check status:**
```bash
brew services list
```

**Restart services:**
```bash
brew services restart radarr
brew services restart sonarr
brew services restart prowlarr
```

**Check logs:**
```bash
tail -f ~/Library/Logs/Radarr/radarr.txt
tail -f ~/Library/Logs/Sonarr/sonarr.txt
```

---

## Advanced Configuration

### Quality Profiles

**Radarr → Settings → Profiles:**
- Create profile "1080p Preferred"
- Allowed: 720p, 1080p, 2160p
- Preferred: 1080p
- Minimum: 720p

**Sonarr → Settings → Profiles:**
- Similar setup for TV shows

### Auto-Organization

**Radarr → Settings → Media Management:**
- Enable: Rename Movies
- Format: `{Movie Title} ({Release Year}) - {Quality Full}`

**Sonarr → Settings → Media Management:**
- Enable: Rename Episodes
- Format: `{Series Title} - S{season:00}E{episode:00} - {Episode Title}`

### Metadata & Artwork

**Enable in both Radarr and Sonarr:**
- Settings → Metadata → Emby (Legacy)
- Write metadata files
- Download artwork

---

## macOS Compatibility Notes

✅ **Confirmed Working:**
- Radarr, Sonarr, Prowlarr (Homebrew casks)
- RDT-Client (Docker)
- Helmarr (native macOS app)
- NZBGet (already working)

⚠️ **Considerations:**
- Docker Desktop must be running for RDT-Client
- M1/M2 Macs: Use ARM-compatible Docker images (latest versions support this)
- macOS sleep: May interrupt downloads (disable sleep or use caffeinate)

**Prevent sleep during downloads:**
```bash
# Add to ~/.zshrc or run manually
alias keepawake='caffeinate -s'
```

---

## Maintenance

### Update Services

```bash
# Update Homebrew apps
brew upgrade --cask radarr sonarr prowlarr

# Update Docker containers
docker pull rogerfar/rdtclient:latest
docker stop rdt-client
docker rm rdt-client
# Re-run docker run command from installation

docker pull dispatcharr/dispatcharr:latest
docker stop dispatcharr
docker rm dispatcharr
# Re-run docker run command
```

### Backup Configurations

```bash
# Backup to repo
cp ~/Library/Application\ Support/Radarr/config.xml ~/noc-homelab/configs/radarr/
cp ~/Library/Application\ Support/Sonarr/config.xml ~/noc-homelab/configs/sonarr/
cp ~/Library/Application\ Support/Prowlarr/config.xml ~/noc-homelab/configs/prowlarr/
cp -r ~/rdt-client/config ~/noc-homelab/configs/rdt-client/

# Commit to git
cd ~/noc-homelab
git add configs/
git commit -m "Backup *arr stack configs"
```

### Monitor Disk Usage

```bash
# Check media directory size
du -sh ~/media/movies
du -sh ~/media/tv

# Check download directory
du -sh ~/downloads

# Clean completed downloads (if needed)
rm -rf ~/downloads/complete/*
```

---

## Security Notes

**API Keys:**
- Radarr, Sonarr, Prowlarr API keys are sensitive
- Store in 1Password or similar
- Never commit to git

**Real-Debrid API Key:**
- Keep private (access to your RD account)
- Regenerate if compromised: https://real-debrid.com/apitoken

**Network Access:**
- Services accessible on LAN via Tailscale (noc-local)
- Do NOT expose ports to internet directly
- Use Tailscale for remote access

**Helmarr Multi-Network:**
- Configure primary (LAN) and fallback (Tailscale) hosts
- Helmarr auto-switches based on network

---

## Reference Links

**Official Documentation:**
- [Radarr Wiki](https://wiki.servarr.com/radarr)
- [Sonarr Wiki](https://wiki.servarr.com/sonarr)
- [Prowlarr Wiki](https://wiki.servarr.com/prowlarr)
- [RDT-Client GitHub](https://github.com/rogerfar/rdt-client)
- [Helmarr Website](https://helmarr.app)
- [Dispatcharr GitHub](https://github.com/Dispatcharr/Dispatcharr)

**Community Guides:**
- [Savvy Guides: Plex + Real-Debrid](https://savvyguides.wiki/sailarrsguide/)
- [ElfHosted: Jellyfin + Real-Debrid](https://docs.elfhosted.com/guides/media/stream-from-real-debrid-with-jellyfin-radarr-sonarr-prowlarr/)
- [Zurg Documentation](https://savvyguides.wiki/zurg/)

**Homebrew Formulae:**
- [Radarr Cask](https://formulae.brew.sh/cask/radarr)
- [Sonarr Cask](https://formulae.brew.sh/cask/sonarr)
- [Prowlarr Cask](https://formulae.brew.sh/cask/prowlarr)

---

## Support

**If you encounter issues:**
1. Check this kickstart guide's Troubleshooting section
2. Check service logs via dashboard or terminal
3. Search official wikis and GitHub issues
4. Ask in r/radarr, r/sonarr, r/usenet subreddits

---

**Setup Complete!** 🎉

You now have a fully automated media stack with mobile management via Helmarr, proper movie/TV separation for Emby, and dual download sources (Real-Debrid + Usenet).

**Next Steps:**
- Install Helmarr on iPhone
- Add your first movie via Radarr
- Add your first TV show via Sonarr
- Watch it appear in Emby within minutes

Enjoy your new setup!
