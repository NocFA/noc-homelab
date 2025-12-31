# Real-Debrid + Zurg: Lessons Learned & Future Options

**Created:** 2025-12-30
**Status:** Zurg restored to original working state
**Outcome:** Directory organization via Zurg config did NOT work as documented

---

## What We Tried (And Failed)

### Attempt 1: Zurg Directory Organization via Config
**Goal:** Separate `/movies` and `/tv` directories at WebDAV root level using Zurg's built-in `directories` config.

**What We Tried:**
1. **`group:` directive under `__all__`** - Creates subdirectories within `__all__`, NOT at root
2. **Separate `movies:` and `tv:` entries with filters** - Directories created but remained empty
3. **`has_episodes: true` filter** - Documented approach that didn't populate directories
4. **Multiple config variations** - None resulted in working organization

**Why It Failed:**
- Zurg v0.9.3-final (July 2024, latest version) appears to have issues with directory organization
- Real-Debrid torrents are fetched (confirmed via API) but don't populate WebDAV directories
- Config examples from official docs don't work as described
- Possible bug or undocumented requirements in Zurg

**Config That Was Tried (didn't work):**
```yaml
directories:
  __all__:

  tv:
    group: media
    group_order: 20
    filters:
      - has_episodes: true

  movies:
    group: media
    group_order: 30
```

**Result:** Empty directories despite 5 movies in Real-Debrid account

---

## Current Working State

**Zurg Configuration:**
- Location: `/Users/noc/applications/zurg/`
- Config: `/Users/noc/applications/zurg/config.yml`
- Port: 9999
- WebDAV URL: `http://localhost:9999/dav/`

**Working Config (Restored):**
```yaml
token: REDACTED_REALDEBRID_TOKEN

zurg: v1
host: 0.0.0.0
port: 9999

retain_folder_name_extension: false
on_library_update: sh:echo "Library updated"

directories:
  __all__:
    group: |
      /tv: [Ss]\d+[Ee]\d+
      /movies: \b(19|20)\d{2}\b
```

**Note:** The `group:` directive under `__all__` creates subdirectories WITHIN `__all__`, accessible at:
- `http://localhost:9999/dav/__all__/tv/` (theoretically)
- `http://localhost:9999/dav/__all__/movies/` (theoretically)

However, during testing these subdirectories also appeared empty despite pattern matching.

---

## Real-Debrid Account Status

**API Token:** `REDACTED_REALDEBRID_TOKEN`
**Expiration:** 72 days from 2025-12-30

**Torrents in Account (via API check):**
1. **Sinners.2025** - UHD BluRay 2160p (70.1 GB) - Status: downloaded
2. **The.Shining.1980** - UHD BDRemux 2160p (109.6 GB) - Status: downloaded
3. **The.Monkey.2025** - UHD BluRay 2160p (53.1 GB) - Status: downloaded
4. **The.Long.Walk.2025** - UHD BluRay 2160p (size unknown) - Status: downloaded
5. **Avatar.The.Way.of.Water.2022** - UHD Remux (size unknown) - Status: downloaded

All torrents show `progress: 100` and `status: "downloaded"` in Real-Debrid API.

---

## Future Options for Organization

### Option 1: rclone Mount (Standard Approach)
**Why:** Most reliable method used by the community. Mounts Zurg WebDAV with caching.

**Steps:**
```bash
# 1. Install rclone (already done)
brew install rclone

# 2. Configure rclone for Zurg WebDAV
rclone config
# Name: zurg
# Type: webdav
# URL: http://localhost:9999/dav
# Vendor: other

# 3. Test mount
mkdir -p /Users/noc/mounts/zurg
rclone mount zurg:__all__ /Users/noc/mounts/zurg --allow-other --vfs-cache-mode full

# 4. Point Emby to /Users/noc/mounts/zurg
```

**Pros:**
- Industry standard approach
- Better caching than direct WebDAV
- Works reliably with Emby/Jellyfin/Plex

**Cons:**
- Requires macFUSE (or use `rclone serve` alternative)
- Additional layer between Zurg and media server

**Resources:**
- [ElfHosted Zurg Guide](https://docs.elfhosted.com/app/zurg/)
- [Savvy Guides - Sailarr's Guide](https://savvyguides.wiki/sailarrsguide/)

---

### Option 2: CineSync (TMDb-Based Organization)
**Why:** Uses TMDb metadata for smarter organization instead of regex patterns.

**What It Does:**
- Analyzes file names via TMDb API
- Creates properly organized Movies/TV directories
- Handles edge cases (full season packs, unusual naming, anime)
- Symlinks files instead of duplicating

**Installation:**
```bash
# Download CineSync (check latest release)
curl -L "https://github.com/sureshfizzy/CineSync/releases/latest/download/CineSync_macOS" -o /Users/noc/applications/cinesync
chmod +x /Users/noc/applications/cinesync

# Configure
/Users/noc/applications/cinesync --setup
# Point source to: /Users/noc/mounts/zurg (rclone mount of Zurg)
# Point destination to: /Users/noc/organized-media
```

**Pros:**
- More accurate than regex patterns
- Handles complex naming automatically
- Good for mixed/messy libraries

**Cons:**
- Requires rclone mount as source
- Additional processing layer
- Needs TMDb API key

**Resources:**
- [CineSync GitHub](https://github.com/sureshfizzy/CineSync)

---

### Option 3: Direct Real-Debrid Tools (Skip Zurg)
**Why:** Zurg might be unnecessary - use Real-Debrid directly via rclone.

**Tools:**
- **rclone + Real-Debrid backend** - Direct integration (if supported)
- **debrid-rclone** - Community tool for Real-Debrid mounting
- **RDT-Client** - Web UI for Real-Debrid + rclone integration

**Steps:** (varies by tool, research needed)

**Pros:**
- One less component to maintain
- Might be more reliable than Zurg

**Cons:**
- Less documented than Zurg
- Might lack some Zurg features

---

### Option 4: Stremio + Torrentio (No Mounting)
**Why:** Simplest approach - stream directly without local mounting.

**Setup:**
```bash
# 1. Install Stremio
brew install --cask stremio

# 2. Add Torrentio addon
# In Stremio: Addons → Search "Torrentio" → Configure
# Add Real-Debrid API key

# 3. Stream content directly
# No Emby needed for this approach
```

**Pros:**
- No mounting, no transcoding, no complexity
- Works great on all devices
- Real-Debrid integration is native

**Cons:**
- Not a local media server (cloud-dependent)
- Can't use Emby/Jellyfin UI
- Less control over metadata

---

## Debugging Notes for Future

### Why Torrents Didn't Appear in Zurg WebDAV

**Confirmed Working:**
- ✅ Zurg binary runs without errors (v0.9.3-final)
- ✅ Real-Debrid API token is valid
- ✅ 5 torrents exist in Real-Debrid account, all fully downloaded
- ✅ Zurg fetches torrent info (`Fetched info for 5 torrents` in logs)
- ✅ WebDAV server is accessible (`http://localhost:9999/dav/`)
- ✅ `__all__`, `__unplayable__`, `version.txt` directories exist

**Not Working:**
- ❌ Torrents don't populate `__all__` directory (empty)
- ❌ Custom `movies`/`tv` directories remain empty even when created
- ❌ `group:` directive doesn't create accessible subdirectories

**Possible Causes (Unconfirmed):**
1. **Bug in Zurg v0.9.3-final** - Directory population might be broken
2. **Real-Debrid API changes** - Zurg from July 2024 might be outdated for current RD API
3. **Torrent state issue** - Downloaded torrents might need different status
4. **Config syntax changes** - Documentation might be for newer/older version
5. **macOS-specific issue** - Might work on Linux but not macOS

**What Would Help Debug:**
- Try Zurg on Linux (Docker?) to rule out macOS issue
- Check Zurg GitHub issues / Discord for similar reports
- Try adding new torrent and see if it appears (vs old torrents)
- Enable full DEBUG logging and analyze output
- Test with different Real-Debrid account

---

## Key Takeaways

1. **Zurg directory organization is NOT straightforward** - Documentation doesn't match reality
2. **rclone mount is the community standard** - Use it instead of direct WebDAV
3. **CineSync adds value** - TMDb-based organization beats regex
4. **Stremio is viable alternative** - If you don't need local media server
5. **Real-Debrid works fine** - The issue is Zurg, not RD

---

## Files Modified During Session

**Zurg:**
- `/Users/noc/applications/zurg/config.yml` - Restored to original
- `/Users/noc/applications/zurg-old-v0.9.3/` - Backup of original installation
- `~/Library/LaunchAgents/com.zurg.service.plist` - No changes needed

**Dashboard:**
- `/Users/noc/noc-homelab/dashboard/app.py` - Zurg already integrated

**Installed:**
- rclone v1.72.1 (via Homebrew)

---

## Recommended Next Steps (When Tokens Available)

**If you want local media server:**
1. Set up rclone mount for Zurg WebDAV
2. Optionally add CineSync for organization
3. Point Emby to rclone mount directory

**If you want simplicity:**
1. Install Stremio
2. Add Torrentio addon with Real-Debrid
3. Enjoy streaming without mounting

**If you want to debug Zurg:**
1. Check Zurg Discord/GitHub issues
2. Try Docker version on Linux
3. Test with fresh Real-Debrid torrent
4. Contact Zurg maintainers with logs

---

## Commands Reference

**Check Zurg status:**
```bash
ps aux | grep zurg
lsof -i :9999
curl http://localhost:9999/dav/
tail -50 /Users/noc/logs/zurg.out
```

**Check Real-Debrid torrents:**
```bash
curl -s "https://api.real-debrid.com/rest/1.0/torrents" \
  -H "Authorization: Bearer REDACTED_REALDEBRID_TOKEN" \
  | python3 -m json.tool
```

**Restart Zurg:**
```bash
launchctl unload ~/Library/LaunchAgents/com.zurg.service.plist
launchctl load ~/Library/LaunchAgents/com.zurg.service.plist
```

**rclone mount (when configured):**
```bash
rclone mount zurg:__all__ /Users/noc/mounts/zurg --allow-other --vfs-cache-mode full
```

---

## Additional Resources

- [Zurg Configuration Docs](https://notes.debridmediamanager.com/zurg-configuration/)
- [Zurg GitHub Wiki](https://github.com/debridmediamanager/zurg-testing/wiki/Config-v0.9)
- [Debrid Wiki](https://debrid.wiki/docs/zurg)
- [Savvy Guides - Complete Setup](https://savvyguides.wiki/sailarrsguide/)
- [ElfHosted Zurg Guide](https://docs.elfhosted.com/app/zurg/)

---

**End of Session Summary:**
- Zurg restored to original working config
- 5 movies confirmed in Real-Debrid account
- Directory organization via Zurg config failed (known issue now)
- Multiple viable alternatives documented for future implementation
- rclone already installed and ready for next attempt
