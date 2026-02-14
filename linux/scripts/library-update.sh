#!/usr/bin/env bash
# Library Update Script (Linux)
# Called by Zurg on_library_update hook when Real-Debrid content changes
# 1. Cleans stale symlinks
# 2. Runs FileBot to create/update symlinks
# 3. Triggers Emby + Jellyfin library scans
#
# No secrets in this file -- API keys read from sops at runtime

set -euo pipefail

REPO_ROOT="/home/noc/noc-homelab"
MEDIA_ROOT="$REPO_ROOT/media"
LOG_FILE="$REPO_ROOT/linux/logs/library-update.log"
MOUNT_POINT="/mnt/zurg"
SOPS_AGE_KEY_FILE="$REPO_ROOT/../noc-homelab-beads/homelab.agekey"
export SOPS_AGE_KEY_FILE

EMBY_URL="http://localhost:8096"
JELLYFIN_URL="http://localhost:8097"

# === LOG ROTATION ===
MAX_LOG_SIZE=$((1024 * 1024))  # 1MB
if [[ -f "$LOG_FILE" ]] && [[ $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]]; then
    tail -n 500 "$LOG_FILE" > "$LOG_FILE.tmp"
    mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

log() {
    local msg
    msg="$(date '+%Y-%m-%d %H:%M:%S') - $1"
    echo "$msg" >> "$LOG_FILE"
    echo "$msg"
}

log "=== Library Update Triggered ==="

# === CLEANUP STALE SYMLINKS ===
stale_count=0
if [[ -d "$MEDIA_ROOT" ]]; then
    while IFS= read -r -d '' link; do
        log "Removing stale symlink: $link"
        rm -f "$link"
        ((stale_count++)) || true
    done < <(find "$MEDIA_ROOT" -xtype l -print0 2>/dev/null)

    # Remove empty directories
    find "$MEDIA_ROOT" -type d -empty -delete 2>/dev/null || true

    if [[ $stale_count -gt 0 ]]; then
        log "Cleaned up $stale_count stale symlink(s)"
    fi
fi

# === WAIT FOR ZURG ===
sleep 5

# === CHECK MOUNT ===
if ! mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    log "ERROR: $MOUNT_POINT is not mounted. Aborting."
    exit 1
fi

# === FILEBOT SYMLINKS ===
mkdir -p "$MEDIA_ROOT/movies" "$MEDIA_ROOT/shows"

log "Running FileBot for movies..."
filebot -rename "$MOUNT_POINT/movies" -r \
    --action symlink \
    --db TheMovieDB \
    -non-strict \
    --format "$MEDIA_ROOT/movies/{n} ({y})/{n} ({y})" \
    --def xattr=false \
    --log warning >> "$LOG_FILE" 2>&1 || log "FileBot movies returned non-zero (may be normal if no new content)"

log "Running FileBot for shows..."
filebot -rename "$MOUNT_POINT/shows" -r \
    --action symlink \
    --db TheTVDB \
    -non-strict \
    --format "$MEDIA_ROOT/shows/{n}/Season {s}/{n} - S{s00}E{e00} - {t}" \
    --def xattr=false \
    --log warning >> "$LOG_FILE" 2>&1 || log "FileBot shows returned non-zero (may be normal if no new content)"

# === READ API KEYS FROM SOPS ===
MEDIA_KEYS=$(sops -d "$REPO_ROOT/configs/media-keys.yaml" 2>/dev/null) || {
    log "ERROR: Failed to decrypt media-keys.yaml"
    exit 1
}

EMBY_API_KEY=$(echo "$MEDIA_KEYS" | grep '^emby_api_key:' | awk '{print $2}')
JELLYFIN_API_KEY=$(echo "$MEDIA_KEYS" | grep '^jellyfin_api_key:' | awk '{print $2}')

# === EMBY SCAN ===
if [[ -n "$EMBY_API_KEY" ]]; then
    log "Triggering Emby library scan..."
    if curl -sf -X POST "$EMBY_URL/Library/Refresh?api_key=$EMBY_API_KEY" >/dev/null 2>&1; then
        log "Emby scan triggered successfully"
    else
        log "Emby scan failed (is Emby running?)"
    fi
else
    log "Emby API key not found - skipping"
fi

# === JELLYFIN SCAN ===
if [[ -n "$JELLYFIN_API_KEY" ]]; then
    log "Triggering Jellyfin library scan..."
    if curl -sf -X POST "$JELLYFIN_URL/Library/Refresh?api_key=$JELLYFIN_API_KEY" >/dev/null 2>&1; then
        log "Jellyfin scan triggered successfully"
    else
        log "Jellyfin scan failed (is Jellyfin running?)"
    fi
else
    log "Jellyfin API key not found - skipping"
fi

log "=== Library Update Complete ==="
