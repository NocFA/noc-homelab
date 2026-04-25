#!/usr/bin/env bash
# Weekly AIDE FIM check
#
# Runs `aide --check` against the baseline at /var/lib/aide/aide.db,
# captures the report, and notifies Discord if there are any
# Added/Removed/Changed entries.
#
# - Exits 0 if no changes detected.
# - Exits 1 if changes detected (but does NOT auto-update the baseline —
#   operator reviews the diff and runs aide-baseline.sh to re-bake).
# - Exits 2 on script/aide errors (missing baseline, etc.).
#
# Triggered by aide-check.timer (Sunday 03:00).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WEBHOOK_ENV="$REPO_ROOT/configs/discord-webhooks.env"
LOG_DIR="$REPO_ROOT/linux/logs"
LOG_FILE="$LOG_DIR/aide-check.log"
REPORT_DIR="/var/log/aide"
TS="$(date '+%Y%m%d-%H%M%S')"
REPORT_FILE="$REPORT_DIR/aide-check-$TS.report"
HOSTNAME="$(hostname -s)"

mkdir -p "$LOG_DIR"

# === LOG ROTATION (cap at 512KB) ===
MAX_LOG_SIZE=$((512 * 1024))
if [[ -f "$LOG_FILE" ]] && [[ $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]]; then
    tail -n 300 "$LOG_FILE" > "$LOG_FILE.tmp"
    mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"; }

# === LOAD WEBHOOK (optional — script still runs without it, just no notify) ===
if [[ -r "$WEBHOOK_ENV" ]]; then
    # shellcheck source=/dev/null
    source "$WEBHOOK_ENV"
fi

notify() {
    local title="$1"
    local body="$2"
    local color="${3:-15158332}"  # red

    if [[ -z "${DISCORD_WEBHOOK_HOMELAB:-}" ]]; then
        log "no Discord webhook configured — skipping notification"
        return
    fi

    # Discord embed description has a 4096-char limit; truncate body if needed.
    if [[ ${#body} -gt 3800 ]]; then
        body="${body:0:3800}"$'\n\n...(truncated; see full report)'
    fi

    # Build payload via jq for proper escaping.
    local payload
    payload=$(jq -nc \
        --arg title "$title" \
        --arg desc "$body" \
        --arg footer "AIDE FIM | $HOSTNAME" \
        --argjson color "$color" \
        '{embeds:[{title:$title, description:$desc, color:$color, footer:{text:$footer}}]}')

    if curl -sf -X POST -H 'Content-Type: application/json' \
        --data "$payload" "$DISCORD_WEBHOOK_HOMELAB" -o /dev/null; then
        log "notification sent to Discord"
    else
        log "WARN: Discord notification failed"
    fi
}

# === PRECONDITION: baseline must exist ===
if [[ ! -f /var/lib/aide/aide.db ]]; then
    log "ERROR: no baseline at /var/lib/aide/aide.db — run aide-baseline.sh first"
    notify "🚨 AIDE FIM check failed" "No baseline database found at /var/lib/aide/aide.db on $HOSTNAME. Run aide-baseline.sh to create one."
    exit 2
fi

mkdir -p "$REPORT_DIR"

log "starting aide --check (baseline: $(stat -c '%y' /var/lib/aide/aide.db))"

# `aide --check` exit code is a bitfield:
#   0  = no diffs
#   1  = new files
#   2  = removed files
#   4  = changed files
#   (combinations sum the bits)
#   higher bits = errors
# So 0 = clean, 1-7 = changes, >=8 = error.
RC=0
aide --config=/etc/aide/aide.conf --check > "$REPORT_FILE" 2>&1 || RC=$?

log "aide exited with code $RC"

if [[ $RC -eq 0 ]]; then
    log "no changes detected — clean"
    # Don't notify on clean weekly run (cron-style — silent success).
    # Trim old reports (keep last 12 weeks).
    find "$REPORT_DIR" -maxdepth 1 -name 'aide-check-*.report' -mtime +90 -delete 2>/dev/null || true
    exit 0
fi

if [[ $RC -ge 8 ]]; then
    log "ERROR: aide reported a runtime error (rc=$RC)"
    tail_excerpt="$(tail -n 30 "$REPORT_FILE")"
    notify "🚨 AIDE FIM error on $HOSTNAME (rc=$RC)" "\`\`\`$tail_excerpt\`\`\`"
    exit 2
fi

# === CHANGES DETECTED — build summary + notify ===
# AIDE report has a "Summary" section with counts and a "details" section
# listing each changed file. Pull both.
summary="$(awk '/^Summary:/,/^---/' "$REPORT_FILE" | head -n 30)"
if [[ -z "$summary" ]]; then
    # Older aide format — grab the first ~50 lines after header
    summary="$(grep -A 25 -m1 -E 'Number of (entries|files)' "$REPORT_FILE" 2>/dev/null | head -n 30)"
fi

# Top-level changed paths (limit to 25 to keep notification readable)
paths="$(grep -E '^(added|removed|changed):' "$REPORT_FILE" 2>/dev/null \
    | head -n 25 \
    || grep -E '^(f |d |l ).*(>|<|=)' "$REPORT_FILE" 2>/dev/null | head -n 25)"

body=$(cat <<EOF
**AIDE detected changes on $HOSTNAME** (rc=$RC)

Report: \`$REPORT_FILE\`
Baseline: \`$(stat -c '%y' /var/lib/aide/aide.db | cut -d. -f1)\`

\`\`\`
$summary
\`\`\`

**First changed paths:**
\`\`\`
$paths
\`\`\`

Review the full report on $HOSTNAME, then re-baseline with:
\`sudo $REPO_ROOT/linux/scripts/aide-baseline.sh\`
EOF
)

log "changes detected — notifying"
notify "AIDE FIM: changes on $HOSTNAME" "$body" 16753920  # orange

# Trim old reports (keep last 12 weeks).
find "$REPORT_DIR" -maxdepth 1 -name 'aide-check-*.report' -mtime +90 -delete 2>/dev/null || true

exit 1
