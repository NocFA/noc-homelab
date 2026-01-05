# Sailarr Stack Kickstart

## Pre-Reboot Status (Dec 31, 2025)

### What We Have
- **Zurg**: Running at `/Users/noc/applications/zurg/` on port 9999
- **Real-Debrid Token**: `REDACTED_REALDEBRID_TOKEN`
- **rclone**: Official binary at `/usr/local/bin/rclone` (v1.71.2) - supports FUSE
- **rclone config**: `[realdebrid]` pointing to `http://localhost:9999/http/__all__/`
- **macFUSE**: v5.1.2 installed, needs system extension approval
- **Emby**: Running on port 8096 (keep as-is)

### Current Mount (to be replaced)
```
http://localhost:8081/ on /Users/noc/mounts/realdebrid (webdav)
```
This uses macOS native WebDAV - slow, no caching.

---

## Post-Reboot: Verify macFUSE Works

### Step 1: Test FUSE Mount
```bash
# Create test mount point
mkdir -p /tmp/fuse-test

# Test mount (foreground, Ctrl+C to stop)
/usr/local/bin/rclone mount realdebrid: /tmp/fuse-test --vfs-cache-mode full

# In another terminal, verify:
ls /tmp/fuse-test
```

If you see your Real-Debrid content, FUSE works!

### Step 2: Unmount test
```bash
diskutil unmount /tmp/fuse-test
# or
umount /tmp/fuse-test
```

---

## Sailarr Architecture for This Setup

```
                                    ┌─────────────────┐
                                    │   Overseerr     │ ← Phone requests
                                    │   (port 5055)   │
                                    └────────┬────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
            ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
            │    Radarr     │        │    Sonarr     │        │   Prowlarr    │
            │  (port 7878)  │        │  (port 8989)  │        │  (port 9696)  │
            │    Movies     │        │   TV Shows    │        │   Indexers    │
            └───────┬───────┘        └───────┬───────┘        └───────────────┘
                    │                        │
                    └──────────┬─────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Blackhole Script  │ ← Checks RD cache, creates symlinks
                    └──────────┬──────────┘
                               │
                               ▼
            ┌─────────────────────────────────────┐
            │         /mnt/plex/                  │
            │   ├── Movies/    ← Emby Movies lib  │
            │   └── TV/        ← Emby TV lib      │
            └─────────────────────────────────────┘
                               │
                               ▼ (symlinks point to)
            ┌─────────────────────────────────────┐
            │  /mnt/remote/realdebrid/            │
            │  (rclone FUSE mount of Zurg)        │
            └─────────────────────────────────────┘
                               │
                               ▼
            ┌─────────────────────────────────────┐
            │            Zurg (9999)              │
            │         Real-Debrid API             │
            └─────────────────────────────────────┘
```

---

## Directory Structure to Create

```bash
# Base mount points
sudo mkdir -p /mnt/remote/realdebrid
sudo mkdir -p /mnt/plex/Movies
sudo mkdir -p /mnt/plex/TV
sudo mkdir -p /mnt/symlinks/radarr/completed
sudo mkdir -p /mnt/symlinks/sonarr/completed

# Set ownership
sudo chown -R noc:staff /mnt
```

---

## Services to Deploy

| Service | Port | Purpose | Deploy Via |
|---------|------|---------|------------|
| Zurg | 9999 | RD WebDAV | Already running (native) |
| rclone mount | - | FUSE mount | LaunchAgent |
| Radarr | 7878 | Movie automation | Docker |
| Sonarr | 8989 | TV automation | Docker |
| Prowlarr | 9696 | Indexer management | Docker |
| Overseerr | 5055 | Request UI (mobile) | Docker |
| Blackhole | - | Torrent processor | Docker sidecar |

**Emby stays as-is** on port 8096, just add new library paths.

---

## Zurg Config Update Needed

Current config only has basic directory rules. Need to update for better organization:

```yaml
# /Users/noc/applications/zurg/config.yml
token: REDACTED_REALDEBRID_TOKEN

zurg: v1
host: 0.0.0.0
port: 9999

# Performance tuning
prefetch: true
concurrent_workers: 32
chunk_size: 10M
retain_folder_name_extension: false

on_library_update: |
  echo "Library updated at $(date)"

directories:
  __all__:
    group: |
      /tv: [Ss]\d+[Ee]\d+
      /movies: \b(19|20)\d{2}\b
```

---

## rclone Mount Command (Optimized)

```bash
/usr/local/bin/rclone mount realdebrid: /mnt/remote/realdebrid \
  --allow-other \
  --allow-non-empty \
  --dir-cache-time 10s \
  --vfs-cache-mode full \
  --vfs-cache-max-size 50G \
  --vfs-cache-max-age 24h \
  --vfs-read-ahead 128M \
  --buffer-size 64M \
  --poll-interval 15s \
  --log-file /Users/noc/rclone-mount.log \
  --log-level INFO
```

These flags will dramatically improve playback start time and reduce buffering.

---

## Docker Compose (To Be Created)

Location: `/Users/noc/noc-homelab/docker/sailarr/docker-compose.yml`

Will include:
- Radarr
- Sonarr
- Prowlarr
- Overseerr
- Blackhole script (from Sailarr guide)

---

## Mobile Workflow (End Goal)

1. Open Overseerr on phone (http://noc-local:5055)
2. Search "Movie Name" or "TV Show"
3. Tap "Request" (select 4K if available)
4. Radarr/Sonarr picks it up
5. Blackhole finds cached torrent on RD
6. Symlink created → Emby sees it
7. Ready to play in ~1-2 minutes

---

## Next Steps After Reboot

1. **Verify FUSE works** (test mount command above)
2. **Create directory structure** (`/mnt/...`)
3. **Update Zurg config** for better performance
4. **Create rclone mount LaunchAgent**
5. **Deploy Docker stack** (Radarr, Sonarr, Prowlarr, Overseerr)
6. **Configure Blackhole script**
7. **Add libraries to Emby**
8. **Test end-to-end**

---

## Existing Services (Don't Touch)

These are already working and should remain unchanged:
- Dashboard (8080)
- Emby (8096)
- Tailscale
- TeamSpeak
- NZBHydra2 (5076)
- NZBGet (6789)
- Maloja (42010)
- Multi-Scrobbler (9078)
- Uptime Kuma (3001)
- Coolify (8000)
- copyparty (8081) ← Note: Currently used by rclone WebDAV, will change

---

## Reference Links

- Sailarr Guide: https://savvyguides.wiki/sailarrsguide/
- Zurg: https://github.com/debridmediamanager/zurg-testing
- rclone mount docs: https://rclone.org/commands/rclone_mount/
