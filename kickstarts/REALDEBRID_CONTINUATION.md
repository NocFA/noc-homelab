# Real-Debrid Organization - Continuation Kickstart

**Created:** 2025-12-30
**Status:** Zurg v0.9.3 found (OLD VERSION - needs upgrade)
**Next Step:** Install Latest Zurg for Movie/TV Separation

---

## What Happened

1. ✅ Docker Desktop installed successfully
2. ⚠️ Discovered existing Zurg v0.9.3 (July 2024 - OUTDATED)
3. ⚠️ Tried to configure old Zurg - directory organization not working
4. ✅ Real-Debrid API token: `REDACTED_REALDEBRID_TOKEN`
5. ✅ 5 movies already in Real-Debrid account
6. ✅ Zurg added to dashboard

**Problem:** Old Zurg version doesn't support directory organization. Need to install LATEST version.

---

## Current Setup Details

**Existing Zurg (OLD - TO BE REPLACED):**
- Version: v0.9.3-final (July 2024)
- Location: `/Users/noc/applications/zurg/`
- Config: `/Users/noc/applications/zurg/config.yml`
- LaunchAgent: `~/Library/LaunchAgents/com.zurg.service.plist`
- Port: 9999
- Status: Running but NO movie/TV separation

**Files Created:**
- `/Users/noc/zurg/config/config.yml` - New config ready for latest Zurg
- Dashboard entry added to `/Users/noc/noc-homelab/dashboard/app.py`

---

## NEXT STEPS: Install Latest Zurg

Follow these steps to replace old Zurg with latest version that supports movie/TV separation:

### Step 1: Stop Old Zurg

```bash
# Unload LaunchAgent
launchctl unload ~/Library/LaunchAgents/com.zurg.service.plist

# Verify stopped
ps aux | grep zurg | grep -v grep
lsof -i :9999  # Should return nothing
```

### Step 2: Backup Old Installation

```bash
# Backup the old version
mv /Users/noc/applications/zurg /Users/noc/applications/zurg-old-v0.9.3

# Create new directory
mkdir -p /Users/noc/applications/zurg
```

### Step 3: Download Latest Zurg

```bash
cd /Users/noc/applications/zurg

# Download latest Zurg binary for macOS ARM64
# Check latest release: https://github.com/debridmediamanager/zurg-testing/releases/latest
curl -L "https://github.com/debridmediamanager/zurg-testing/releases/latest/download/zurg-darwin-arm64" -o zurg

# Make executable
chmod +x zurg

# Verify downloaded
ls -lh zurg
./zurg --version
```

### Step 4: Install New Config

```bash
# Copy the prepared config
cp /Users/noc/zurg/config/config.yml /Users/noc/applications/zurg/config.yml

# Verify config
cat /Users/noc/applications/zurg/config.yml
```

**Config should contain:**
```yaml
token: REDACTED_REALDEBRID_TOKEN

directories:
  __all__:
    group: |
      /movies: ^.*\.(mkv|mp4|avi|m4v).*\b(19|20)\d{2}\b
      /tv: ^.*[Ss]\d+[Ee]\d+.*\.(mkv|mp4|avi|m4v)
      /other: ^.*\.(mkv|mp4|avi|m4v)

enable_repair: true

serve:
  port: 9999

log_level: info
```

### Step 5: Update LaunchAgent (If Needed)

The existing LaunchAgent at `~/Library/LaunchAgents/com.zurg.service.plist` should work, but verify paths:

```bash
cat ~/Library/LaunchAgents/com.zurg.service.plist
```

Should point to: `/Users/noc/applications/zurg/zurg`

If it points elsewhere, update it:

```bash
# Edit the plist if needed
nano ~/Library/LaunchAgents/com.zurg.service.plist

# Make sure ProgramArguments points to:
# <string>/Users/noc/applications/zurg/zurg</string>

# And WorkingDirectory is:
# <string>/Users/noc/applications/zurg</string>
```

### Step 6: Start New Zurg

```bash
# Load LaunchAgent
launchctl load ~/Library/LaunchAgents/com.zurg.service.plist

# Wait a few seconds
sleep 5

# Check if running
ps aux | grep zurg | grep -v grep

# Check port
lsof -i :9999
```

### Step 7: Verify Movie/TV Directories

```bash
# Test WebDAV endpoint
curl -s http://localhost:9999/dav/ | python3 -c "import sys, xml.etree.ElementTree as ET; root = ET.fromstring(sys.stdin.read()); [print(elem.text) for elem in root.findall('.//{DAV:}href')]"

# You should now see:
# /
# __all__
# movies      <-- NEW!
# tv          <-- NEW!
# other       <-- NEW!
# __unplayable__
# version.txt
```

If you see `/movies` and `/tv` directories - **SUCCESS!** 🎉

If not, check logs:
```bash
tail -50 /Users/noc/logs/zurg.out
```

### Step 8: Mount WebDAV

```bash
# Mount via Finder (easiest):
# Press Cmd+K
# Enter: http://localhost:9999/dav/
# Click Connect

# OR via terminal:
osascript -e 'mount volume "http://localhost:9999/dav/"'

# Verify mount
ls -la /Volumes/dav/
# Should show: __all__, movies, tv, other, __unplayable__

# Check movies directory
ls /Volumes/dav/movies/
# Should show your 5 movies organized here
```

### Step 9: Configure Emby

```bash
# Open Emby
open http://localhost:8096
```

**In Emby Dashboard:**

1. **Add Movie Library:**
   - Settings → Library → Add Media Library
   - Content type: **Movies**
   - Display name: **Movies**
   - Folders → Add: `/Volumes/dav/movies`
   - Enable: Automatically refresh metadata from the internet
   - Click OK

2. **Add TV Library:**
   - Add Media Library
   - Content type: **Shows**
   - Display name: **TV Shows**
   - Folders → Add: `/Volumes/dav/tv`
   - Enable: Automatically refresh metadata from the internet
   - Click OK

3. **Scan Libraries:**
   - Dashboard → Libraries → Scan All Libraries
   - Wait for scan to complete
   - Your 5 movies should appear in Movies library!

### Step 10: Test Workflow

Add new content via Real-Debrid Manager to verify organization:

1. On phone/browser: Search for a TV show (e.g., "Breaking Bad S01E01")
2. Add to Real-Debrid
3. Wait 30 seconds
4. Check: `ls /Volumes/dav/tv/` - should see the episode
5. Scan Emby library - should appear in TV Shows

**Setup Complete!** ✅

---

## If Zurg Still Doesn't Organize Properly

**Then and ONLY then, consider CineSync as replacement:**

CineSync uses TMDb metadata instead of regex patterns, so it handles edge cases better:
- Full season packs
- Unusual naming conventions
- Anime with different numbering
- 4K/HDR specific organization

**CineSync replaces Zurg's organization logic** (Zurg still provides the WebDAV mount, CineSync adds smart organization on top).

To add CineSync, see original kickstart: `SIMPLE_REALDEBRID_ORGANIZATION.md` section "Upgrade Option: Add CineSync"

---

## Troubleshooting

### Latest Zurg Won't Start

```bash
# Check logs
tail -100 /Users/noc/logs/zurg.out
tail -100 /Users/noc/logs/zurg.err

# Common issues:
# 1. Config syntax error - validate YAML
# 2. Port 9999 in use - kill old process
# 3. Binary not executable - chmod +x zurg
```

### No /movies or /tv Directories

```bash
# Check Zurg version
/Users/noc/applications/zurg/zurg --version
# Should be v0.10+ or newer

# Check config loaded
tail -50 /Users/noc/logs/zurg.out | grep -i config

# Verify content exists
curl -s http://localhost:9999/dav/__all__/ | head -20

# If __all__ has content but no organized dirs:
# - Config regex patterns might not match your files
# - Try CineSync instead
```

### WebDAV Mount Failed

```bash
# Ensure Zurg is running
curl http://localhost:9999/dav/

# Try manual mount
osascript -e 'mount volume "http://localhost:9999/dav/"'

# If that hangs, use Finder GUI (Cmd+K)
```

---

## Quick Reference

**Zurg Status:**
```bash
ps aux | grep zurg
lsof -i :9999
tail -20 /Users/noc/logs/zurg.out
```

**Check Directories:**
```bash
curl -s http://localhost:9999/dav/ | grep href
ls /Volumes/dav/
```

**Restart Zurg:**
```bash
launchctl unload ~/Library/LaunchAgents/com.zurg.service.plist
launchctl load ~/Library/LaunchAgents/com.zurg.service.plist
```

**Dashboard:**
- http://noc-local:8080 (Zurg status and logs)

**Emby:**
- http://noc-local:8096 (Media libraries)

---

## Files to Reference

- Original kickstart: `kickstarts/SIMPLE_REALDEBRID_ORGANIZATION.md`
- Zurg config: `/Users/noc/applications/zurg/config.yml`
- Prepared config: `/Users/noc/zurg/config/config.yml`
- LaunchAgent: `~/Library/LaunchAgents/com.zurg.service.plist`
- Logs: `/Users/noc/logs/zurg.out` and `.err`
- Dashboard: `/Users/noc/noc-homelab/dashboard/app.py`

---

## Summary for Next Chat

**Say:** "Continue with REALDEBRID_CONTINUATION.md - install latest Zurg to replace v0.9.3"

**Current state:**
- Old Zurg v0.9.3 running (no organization working)
- Real-Debrid token configured
- 5 movies ready to organize
- Dashboard integration done
- Need: Install latest Zurg, verify /movies and /tv directories, mount WebDAV, configure Emby

**Goal:** Movie/TV separation working properly.

---

**Start fresh chat and follow Step 1 above!**
