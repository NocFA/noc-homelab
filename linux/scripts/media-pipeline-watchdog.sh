#!/usr/bin/env bash
# Media Pipeline Watchdog
#
# Catches the "soft-dead" failure modes that zurg-healthcheck.sh's
# count-divergence check misses:
#
#   1. Stale FUSE mount: rclone-zurg reports `mountpoint` OK but every
#      stat / readdir hangs.  Detected via timeout-bounded `ls`.
#
#   2. on_library_update hook failing repeatedly: zurg keeps detecting
#      new content but library-update.sh exits 1 every time, so new
#      releases never reach Emby/Jellyfin/Plex.  Detected via
#      journalctl grep over the last $WINDOW_MIN minutes.
#
#   3. zurg-healthcheck.timer itself dead/inactive: this happened on
#      2026-05-02 (timer hadn't fired since 2026-03-27).  No timer =
#      no count check = no auto-restart of stuck zurg.
#
# Discord alert per check, deduped by lockfile to avoid spam during
# a sustained outage.  Runs every 5 min via media-pipeline-watchdog.timer.

set -uo pipefail

REPO_ROOT="/home/noc/noc-homelab"
LOG_FILE="$REPO_ROOT/linux/logs/media-pipeline-watchdog.log"
LOCK_DIR="/tmp/media-pipeline-watchdog"
LOCK_TTL=1800            # 30 min: don't re-alert on same problem within this window
WINDOW_MIN=30            # journal lookback window for hook failures
HOOK_FAIL_THRESHOLD=3    # alert if >= this many hook failures in window
MOUNT_POINT="/mnt/zurg"

mkdir -p "$LOCK_DIR" 2>/dev/null || true

# === LOG ROTATION (cap at 256 KB) ===
MAX_LOG_SIZE=$((256 * 1024))
if [[ -f "$LOG_FILE" ]] && [[ $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]]; then
    tail -n 200 "$LOG_FILE" > "$LOG_FILE.tmp"
    mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"; }

discord_webhook() {
    [[ -n "${DISCORD_WEBHOOK_URL:-}" ]] && { echo "$DISCORD_WEBHOOK_URL"; return; }
    if [[ -r "$REPO_ROOT/services/gatus/config.yaml" ]]; then
        grep -oE 'https://discord\.com/api/webhooks/[A-Za-z0-9_/-]+' \
            "$REPO_ROOT/services/gatus/config.yaml" 2>/dev/null | head -1
    fi
}

# alert <key> <title> <description>
# Dedups via lockfile keyed on $1 with $LOCK_TTL window.
alert() {
    local key="$1" title="$2" desc="$3"
    local lock="$LOCK_DIR/$key.lock"

    if [[ -f "$lock" ]]; then
        local last_fired now
        last_fired=$(stat -c %Y "$lock" 2>/dev/null || echo 0)
        now=$(date +%s)
        if (( now - last_fired < LOCK_TTL )); then
            log "[$key] suppressed (cooldown $((LOCK_TTL - (now - last_fired)))s)"
            return
        fi
    fi
    touch "$lock"

    local hook
    hook="$(discord_webhook)"
    if [[ -z "$hook" ]]; then
        log "[$key] ALERT but no Discord webhook configured: $title"
        return
    fi

    log "[$key] ALERT: $title"
    local body
    body=$(cat <<EOF
{
  "content": "<@139476150786195456>",
  "embeds": [{
    "title": "noc-tux -- ${title}",
    "description": "${desc}",
    "color": 15745372,
    "footer": {"text": "media-pipeline-watchdog -- noc-homelab"}
  }]
}
EOF
)
    curl -fsS -m 10 -H 'Content-Type: application/json' \
        -X POST -d "$body" "$hook" >/dev/null 2>&1 \
        || log "[$key] Discord POST failed"
}

# === CHECK 1: stale FUSE mount ===
if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    if ! timeout 10 ls "$MOUNT_POINT" >/dev/null 2>&1; then
        alert "stale-mount" "rclone-zurg mount is stale" \
            "\`$MOUNT_POINT\` is mounted but reads hang (FUSE deadlock).\nFix: \`systemctl --user restart rclone-zurg\` (run as user noc)."
    fi
else
    alert "no-mount" "rclone-zurg not mounted" \
        "\`$MOUNT_POINT\` is not a mountpoint.\nFix: \`systemctl --user start rclone-zurg\`."
fi

# === CHECK 2: zurg on_library_update hook failures ===
# `--user-unit` not always available on older systemd; use --user instead.
HOOK_FAILS=$(journalctl --user -u zurg.service \
    --since "${WINDOW_MIN} minutes ago" --no-pager -o cat 2>/dev/null \
    | grep -c 'Failed to execute hook on_library_update' \
    || true)

if [[ "$HOOK_FAILS" -ge "$HOOK_FAIL_THRESHOLD" ]]; then
    alert "hook-failing" "zurg on_library_update hook is failing" \
        "\`$HOOK_FAILS\` hook failures in last ${WINDOW_MIN} min.\nNew Real-Debrid content is being detected but FileBot+scan triggers are not running.\nCheck: \`journalctl --user -u zurg.service | grep on_library_update\` and \`tail $REPO_ROOT/linux/logs/library-update.log\`."
fi

# === CHECK 3: zurg-healthcheck.timer is dead ===
# `is-active` for an oneshot timer should be "active" (the timer itself,
# not its triggered service).  Inactive = timer was stopped and the
# stale-content auto-restart safety net is gone.
TIMER_STATE=$(systemctl --user is-active zurg-healthcheck.timer 2>/dev/null || echo "unknown")
if [[ "$TIMER_STATE" != "active" ]]; then
    alert "healthcheck-timer-dead" "zurg-healthcheck.timer is $TIMER_STATE" \
        "The 5-min stale-content detector is not running.\nFix: \`systemctl --user start zurg-healthcheck.timer && systemctl --user enable zurg-healthcheck.timer\`."
fi

# Always exit 0 so the timer doesn't OnFailure-cascade itself.
exit 0
