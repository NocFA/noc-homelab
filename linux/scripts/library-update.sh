#!/usr/bin/env bash
# Library Update Script (Linux)
# Called by Zurg `on_library_update` hook when Real-Debrid content changes.
#
#  1. Cleans stale symlinks under media/
#  2. Runs FileBot to create/update symlinks for movies + shows
#  3. Triggers Emby + Plex library scans
#
# media/configs/media-keys.yaml is plaintext on disk per the project's SOPS
# at-rest workflow (encrypted only in git via pre-commit hook). Reads it
# directly; falls back to `sops -d` only if the on-disk file is encrypted
# (e.g. fresh checkout before the post-merge hook ran).
#
# On any error (FileBot crash, scan endpoint dead, missing keys), keeps
# going through every step it can and POSTs a single Discord alert at the
# end so nothing fails silently.

# NOTE: deliberately NOT using `set -e` -- one failing scan endpoint must
# not block the others, and zurg's hook executor swallows stderr so a
# silent exit-1 turns the pipeline into a black box.
set -uo pipefail

REPO_ROOT="/home/noc/noc-homelab"
MEDIA_ROOT="$REPO_ROOT/media"
MOUNT_POINT="/mnt/zurg"
LOG_FILE="$REPO_ROOT/linux/logs/library-update.log"

# === SINGLE-INSTANCE LOCK + PENDING-RERUN COALESCING ===
# Zurg fires `on_library_update` on every WebDAV change (often 1/sec during
# a release sync) and a single FileBot sweep can take 5-10 minutes.
# Without coalescing, dozens of scripts pile up and race on the same
# directory tree.
#
# Pattern: try to grab a non-blocking flock.  If we can't, set PENDING and
# bail -- the running instance will pick up our changes by re-running once
# its current pass finishes.  Cap re-runs so a stuck FileBot can't loop
# us forever.
LOCK_FILE="/tmp/library-update.lock"
PENDING_FILE="/tmp/library-update.pending"
MAX_RERUNS=2

exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    touch "$PENDING_FILE"
    exit 0
fi
rm -f "$PENDING_FILE"

EMBY_URL="http://localhost:8096"
PLEX_URL="http://localhost:32400"

# UTF-8 locale: FileBot's JVM needs this or unicode filenames
# ("Breaking Bad - S03E01 - No Más.mkv") crash with InvalidPathException.
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

# Age key (used only as a fallback if media-keys.yaml is encrypted on disk).
SOPS_AGE_KEY_FILE="$REPO_ROOT/noc-homelab-beads/homelab.agekey"
export SOPS_AGE_KEY_FILE

ERRORS=()

# === LOG ROTATION (cap at 1 MB) ===
MAX_LOG_SIZE=$((1024 * 1024))
if [[ -f "$LOG_FILE" ]] && [[ $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]]; then
    tail -n 500 "$LOG_FILE" > "$LOG_FILE.tmp"
    mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

log() {
    local msg
    msg="$(date '+%Y-%m-%d %H:%M:%S') - $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

err() {
    log "ERROR: $1"
    ERRORS+=("$1")
}

# === DISCORD ALERT (only fired if ERRORS not empty at exit) ===
discord_webhook() {
    # Reuse the same gatus webhook the notify-systemd-failure.sh script does.
    if [[ -n "${DISCORD_WEBHOOK_URL:-}" ]]; then
        echo "$DISCORD_WEBHOOK_URL"; return
    fi
    if [[ -r "$REPO_ROOT/services/gatus/config.yaml" ]]; then
        grep -oE 'https://discord\.com/api/webhooks/[A-Za-z0-9_/-]+' \
            "$REPO_ROOT/services/gatus/config.yaml" 2>/dev/null | head -1
    fi
}

post_discord_failure() {
    local hook err_count body
    hook="$(discord_webhook)"
    [[ -z "$hook" ]] && { logger -t library-update "no discord webhook, skipping alert"; return; }

    err_count="${#ERRORS[@]}"
    local err_list=""
    for e in "${ERRORS[@]}"; do
        err_list+="- ${e}\n"
    done

    body=$(cat <<EOF
{
  "content": "<@139476150786195456>",
  "embeds": [{
    "title": "noc-tux -- library-update.sh degraded",
    "description": "**${err_count} error(s) during zurg \`on_library_update\` hook**:\n${err_list}\nNew content may not appear in Emby/Plex until next manual scan.",
    "color": 15745372,
    "footer": {"text": "library-update.sh -- noc-homelab"}
  }]
}
EOF
)
    curl -fsS -m 10 -H 'Content-Type: application/json' \
        -X POST -d "$body" "$hook" >/dev/null 2>&1 \
        || logger -t library-update "Discord webhook POST failed"
}

trap 'rc=$?; if [[ ${#ERRORS[@]} -gt 0 ]]; then post_discord_failure; fi; exit $rc' EXIT

RERUN_COUNT="${LIBRARY_UPDATE_RERUN_COUNT:-0}"
log "=== Library Update Triggered (rerun=$RERUN_COUNT) ==="

# === CLEANUP STALE SYMLINKS ===
stale_count=0
if [[ -d "$MEDIA_ROOT" ]]; then
    while IFS= read -r -d '' link; do
        rm -f "$link"
        ((stale_count++)) || true
    done < <(find "$MEDIA_ROOT" -xtype l -print0 2>/dev/null)

    find "$MEDIA_ROOT" -type d -empty -delete 2>/dev/null || true

    if [[ $stale_count -gt 0 ]]; then
        log "Cleaned up $stale_count stale symlink(s)"
    fi
fi

# === WAIT FOR ZURG TO SETTLE AFTER RD CHANGE ===
sleep 5

# === MOUNT SANITY: stat-check -- not just mountpoint ===
# A dead rclone FUSE mount can still report `mountpoint -q` OK but every
# read hangs.  An ls + stat catches the common stale-mount failure mode.
if ! mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    err "$MOUNT_POINT is not a mountpoint"
elif ! timeout 10 ls "$MOUNT_POINT" >/dev/null 2>&1; then
    err "$MOUNT_POINT is mounted but unreadable (stale FUSE)"
fi

# Bail out of the FileBot+scan steps if mount is unhealthy -- there's
# nothing useful we can do until rclone is restarted.
if [[ ${#ERRORS[@]} -gt 0 ]]; then
    log "Aborting FileBot+scan steps: mount is unhealthy"
    exit 1
fi

# === FILEBOT SYMLINKS ===
mkdir -p "$MEDIA_ROOT/movies" "$MEDIA_ROOT/shows"

run_filebot() {
    local label="$1"; shift
    log "Running FileBot for $label..."
    if ! filebot "$@" >> "$LOG_FILE" 2>&1; then
        # FileBot exits non-zero when there are zero new matches OR a real
        # crash. Treat it as soft-fail unless the log shows a Java stack
        # trace -- in which case we want to know about it.
        if tail -n 30 "$LOG_FILE" | grep -q 'java\.[a-z.]\+Exception'; then
            err "FileBot $label crashed (Java exception, see log)"
        else
            log "FileBot $label returned non-zero (likely no new content)"
        fi
    fi
}

run_filebot "movies" \
    -rename "$MOUNT_POINT/movies" -r \
    --action symlink \
    --db TheMovieDB \
    -non-strict \
    --format "$MEDIA_ROOT/movies/{n} ({y})/{n} ({y})" \
    --def xattr=false \
    --log warning

run_filebot "shows" \
    -rename "$MOUNT_POINT/shows" -r \
    --action symlink \
    --db TheTVDB \
    -non-strict \
    --format "$MEDIA_ROOT/shows/{n}/Season {s}/{n} - S{s00}E{e00} - {t}" \
    --def xattr=false \
    --log warning

# === LOAD API KEYS ===
# media-keys.yaml is plaintext at rest per the project's SOPS workflow.
# Only fall back to `sops -d` if the file looks encrypted.
KEYS_FILE="$REPO_ROOT/configs/media-keys.yaml"
if [[ ! -r "$KEYS_FILE" ]]; then
    err "media-keys.yaml not readable at $KEYS_FILE"
    MEDIA_KEYS=""
elif head -1 "$KEYS_FILE" | grep -q '^sops:\|ENC\['; then
    log "media-keys.yaml is encrypted, decrypting via sops..."
    if ! MEDIA_KEYS=$(sops -d "$KEYS_FILE" 2>/dev/null); then
        err "sops decryption of media-keys.yaml failed"
        MEDIA_KEYS=""
    fi
else
    MEDIA_KEYS=$(cat "$KEYS_FILE")
fi

extract() { echo "$MEDIA_KEYS" | grep "^$1:" | head -1 | awk '{print $2}'; }
EMBY_API_KEY=$(extract emby_api_key)
PLEX_TOKEN=$(extract plex_token)

# === MEDIA SERVER SCANS ===
# All three independent: a failure in one must NOT short-circuit the others.
trigger_scan() {
    local label="$1" url="$2"
    if curl -fsS -m 10 -X POST "$url" -o /dev/null 2>&1; then
        log "$label scan triggered"
    else
        err "$label scan failed (server down or wrong key?)"
    fi
}

if [[ -n "$EMBY_API_KEY" ]]; then
    trigger_scan "Emby" "$EMBY_URL/Library/Refresh?api_key=$EMBY_API_KEY"
else
    err "Emby API key not found"
fi

if [[ -n "$PLEX_TOKEN" ]]; then
    # Plex uses GET, not POST, for library refresh
    if curl -fsS -m 10 "$PLEX_URL/library/sections/all/refresh?X-Plex-Token=$PLEX_TOKEN" -o /dev/null 2>&1; then
        log "Plex scan triggered"
    else
        err "Plex scan failed (server down or wrong token?)"
    fi
else
    err "Plex token not found"
fi

if [[ ${#ERRORS[@]} -eq 0 ]]; then
    log "=== Library Update Complete (all OK) ==="
else
    log "=== Library Update Complete (${#ERRORS[@]} error(s)) ==="
fi

# === COALESCED RE-RUN ===
# If zurg fired more hook calls during this run, the dropped instances
# touched $PENDING_FILE.  Catch up with one more pass so we don't miss
# a final-second change.  Capped at $MAX_RERUNS to bound runtime.
if [[ -f "$PENDING_FILE" && "$RERUN_COUNT" -lt "$MAX_RERUNS" ]]; then
    rm -f "$PENDING_FILE"
    log "Pending changes detected -- re-running (#$((RERUN_COUNT + 1)))"
    flock -u 200
    LIBRARY_UPDATE_RERUN_COUNT=$((RERUN_COUNT + 1)) exec "$0" "$@"
fi
