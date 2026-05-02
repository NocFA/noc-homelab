#!/usr/bin/env bash
# Zurg Stale Content Detector
#
# Compares Real-Debrid API torrent count against what zurg is serving via WebDAV.
# If zurg's __all__ directory is missing items that RD has marked "downloaded",
# the zurg process has gotten stuck and needs a restart.
#
# Runs every 5 minutes via zurg-healthcheck.timer.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ZURG_CONFIG="$REPO_ROOT/linux/services/zurg/config.yml"
LOG_FILE="$REPO_ROOT/linux/logs/zurg-healthcheck.log"
COOLDOWN_FILE="/tmp/zurg-healthcheck-last-restart"
COOLDOWN_SECS=1800   # 30 minutes between forced restarts
STALE_THRESHOLD=2    # tolerate up to 1 in-progress torrent before flagging stale
ZURG_URL="http://localhost:9999"
RD_API="https://api.real-debrid.com/rest/1.0"

# === LOG ROTATION (cap at 512KB) ===
MAX_LOG_SIZE=$((512 * 1024))
if [[ -f "$LOG_FILE" ]] && [[ $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]]; then
    tail -n 300 "$LOG_FILE" > "$LOG_FILE.tmp"
    mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"; }

# === READ RD TOKEN FROM ZURG CONFIG ===
RD_TOKEN=$(grep -E '^token:' "$ZURG_CONFIG" | awk '{print $2}' | tr -d '"' | tr -d "'")
if [[ -z "$RD_TOKEN" ]]; then
    log "ERROR: Could not read RD token from $ZURG_CONFIG"
    exit 1
fi

# === VERIFY ZURG IS REACHABLE ===
if ! curl -sf "$ZURG_URL/dav/" -X PROPFIND -H "Depth: 0" -o /dev/null --max-time 5; then
    log "WARN: Zurg WebDAV not reachable — skipping check (zurg may be starting up)"
    exit 0
fi

# === COUNT RD DOWNLOADED TORRENTS ===
RD_RESPONSE=$(curl -sf \
    -H "Authorization: Bearer $RD_TOKEN" \
    "$RD_API/torrents?limit=2500" \
    --max-time 15 2>/dev/null) || {
    log "WARN: RD API request failed — skipping check"
    exit 0
}

RD_COUNT=$(echo "$RD_RESPONSE" | jq '[.[] | select(.status == "downloaded")] | length' 2>/dev/null || echo -1)
if [[ "$RD_COUNT" -lt 0 ]]; then
    log "WARN: Failed to parse RD API response — skipping check"
    exit 0
fi

# === COUNT ZURG __all__ ENTRIES ===
# PROPFIND depth=1 returns the parent directory + one entry per item.
# Subtract 1 to get the actual torrent count.
PROPFIND_RESPONSE=$(curl -sf \
    -X PROPFIND \
    -H "Depth: 1" \
    "$ZURG_URL/dav/__all__/" \
    --max-time 10 2>/dev/null) || {
    log "WARN: Zurg PROPFIND for __all__ failed — skipping check"
    exit 0
}

RESPONSE_COUNT=$(echo "$PROPFIND_RESPONSE" | grep -o '<d:response>' | wc -l)
ZURG_COUNT=$((RESPONSE_COUNT - 1))

log "RD downloaded: $RD_COUNT | Zurg __all__: $ZURG_COUNT"

# === STALENESS CHECK ===
DIFF=$((RD_COUNT - ZURG_COUNT))
if [[ $DIFF -lt $STALE_THRESHOLD ]]; then
    # In sync (within tolerance)
    exit 0
fi

log "STALE: RD has $DIFF more torrents than zurg is showing"

# === COOLDOWN CHECK ===
if [[ -f "$COOLDOWN_FILE" ]]; then
    LAST_RESTART=$(cat "$COOLDOWN_FILE")
    NOW=$(date +%s)
    ELAPSED=$((NOW - LAST_RESTART))
    if [[ $ELAPSED -lt $COOLDOWN_SECS ]]; then
        REMAINING=$((COOLDOWN_SECS - ELAPSED))
        log "Cooldown active — ${ELAPSED}s since last restart, ${REMAINING}s remaining"
        exit 0
    fi
fi

# === RESTART STACK ===
log "Restarting zurg and rclone-zurg..."
date +%s > "$COOLDOWN_FILE"

# Stop rclone first (it depends on zurg WebDAV being alive)
systemctl --user stop rclone-zurg 2>/dev/null || true
sleep 2
systemctl --user restart zurg
sleep 5
systemctl --user start rclone-zurg

log "Restart complete — counts will re-verify on next 5-minute check"
