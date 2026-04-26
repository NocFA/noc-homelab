#!/usr/bin/env bash
# dns-audit.sh — Nightly Cloudflare DNS audit for IP exposure.
#
# Queries all A/AAAA records in the nocfa.net zone via Cloudflare API.
# Alerts via Discord webhook if any non-whitelisted record exposes the
# home IP in a DIRECT (unproxied) record.
#
# Usage:  dns-audit.sh [--quiet]
#   --quiet   suppress clean-audit stdout (for cron/launchd)
#
# Requires:
#   - configs/cloudflare-api.env  (CF_API_TOKEN)
#   - curl, jq
#
# Webhook URL discovery (first match wins):
#   1. $DISCORD_WEBHOOK_URL env var
#   2. services/gatus/config.yaml  (gatus Discord webhook)
#
# Install (noc-local):
#   ln -sf /Users/noc/noc-homelab/launchagents/com.noc.dns-audit.plist \
#          ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.noc.dns-audit.plist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$HOME/Library/Logs/noc-homelab"
LOG_FILE="$LOG_DIR/dns-audit.log"
QUIET="${1:-}"

mkdir -p "$LOG_DIR" 2>/dev/null || true

log() { echo "$(date -Iseconds) $*" | tee -a "$LOG_FILE"; }

# ── Load Cloudflare credentials ──────────────────────────────────────
CF_ENV="$REPO_DIR/configs/cloudflare-api.env"
if [[ ! -r "$CF_ENV" ]]; then
    log "ERROR: $CF_ENV not found or unreadable"
    exit 1
fi
# shellcheck disable=SC1090
set -a; source "$CF_ENV"; set +a

if [[ -z "${CF_API_TOKEN:-}" ]]; then
    log "ERROR: CF_API_TOKEN not set in $CF_ENV"
    exit 1
fi

# ── Configuration ────────────────────────────────────────────────────
# nocfa.net zone — the only zone where home IP exposure is possible.
# looney.eu and mdsf.net confirmed clean (no home IP records) and
# the CF_API_TOKEN is scoped to nocfa.net only.
ZONE_ID="947dfff2b6a8f142dfa56d3ae9e23cc1"
ZONE_NAME="nocfa.net"

# Home IP and subnet to match against
HOME_IP="84.203.199.55"
HOME_SUBNET="84.203.199."

# Records that are intentionally DIRECT with home IP.
# matrix.nocfa.net must be DIRECT for federation + TURN.
EXCEPTIONS=(
    "matrix.nocfa.net"
)

# ── Resolve Discord webhook ─────────────────────────────────────────
WEBHOOK="${DISCORD_WEBHOOK_URL:-}"
if [[ -z "$WEBHOOK" ]]; then
    GATUS_CFG="$REPO_DIR/services/gatus/config.yaml"
    if [[ -r "$GATUS_CFG" ]]; then
        WEBHOOK=$(grep -oE 'https://discord\.com/api/webhooks/[A-Za-z0-9_/-]+' \
            "$GATUS_CFG" 2>/dev/null | head -1)
    fi
fi

# ── Fetch all DNS records ────────────────────────────────────────────
RECORDS=$(curl -sf "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?per_page=500" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: application/json" 2>/dev/null)

if [[ -z "$RECORDS" ]] || ! echo "$RECORDS" | jq -e '.success' >/dev/null 2>&1; then
    log "ERROR: Cloudflare API call failed"
    exit 1
fi

TOTAL=$(echo "$RECORDS" | jq '.result | length')
log "Fetched $TOTAL DNS records from $ZONE_NAME"

# ── Audit each record ───────────────────────────────────────────────
ALERTS=""
ALERT_COUNT=0
EXCEPTION_HITS=""

while IFS= read -r record; do
    name=$(echo "$record" | jq -r '.name')
    type=$(echo "$record" | jq -r '.type')
    content=$(echo "$record" | jq -r '.content')
    proxied=$(echo "$record" | jq -r '.proxied')

    # Only check A and AAAA records
    [[ "$type" != "A" && "$type" != "AAAA" ]] && continue

    # Check if this is a DIRECT record pointing to home IP (or subnet)
    if [[ "$proxied" == "false" ]] && [[ "$content" == "$HOME_IP" || "$content" == "$HOME_SUBNET"* ]]; then
        # Check exceptions
        is_exception=false
        for exc in "${EXCEPTIONS[@]}"; do
            if [[ "$name" == "$exc" ]]; then
                is_exception=true
                EXCEPTION_HITS+="  $name ($type) -> $content [DIRECT, whitelisted]\n"
                break
            fi
        done

        if [[ "$is_exception" == "false" ]]; then
            ALERTS+="**$name** ($type) -> \`$content\` [DIRECT]\n"
            ((ALERT_COUNT++)) || true
            log "ALERT: $name ($type) -> $content DIRECT — HOME IP EXPOSED"
        fi
    fi
done < <(echo "$RECORDS" | jq -c '.result[]')

# ── Report results ───────────────────────────────────────────────────
if [[ $ALERT_COUNT -gt 0 ]]; then
    log "AUDIT FAILED: $ALERT_COUNT record(s) exposing home IP"

    if [[ -n "$WEBHOOK" ]]; then
        DESCRIPTION="$ALERT_COUNT DNS record(s) in **$ZONE_NAME** expose the home IP without Cloudflare proxy:\n\n$ALERTS\nRun \`scripts/dns-audit.sh\` for details."
        PAYLOAD=$(jq -n \
            --arg title "DNS Audit Alert: Home IP Exposed" \
            --arg desc "$DESCRIPTION" \
            '{embeds: [{title: $title, description: $desc, color: 16711680, timestamp: (now | todate)}]}')
        curl -sf -X POST "$WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "$PAYLOAD" >/dev/null 2>&1 || log "WARNING: Discord webhook delivery failed"
    else
        log "WARNING: No Discord webhook configured — alert not sent"
    fi
    exit 1
else
    MSG="DNS audit clean — $TOTAL records checked, 0 unexpected exposures"
    if [[ -n "$EXCEPTION_HITS" ]]; then
        MSG+=". Known exceptions: $(echo -e "$EXCEPTION_HITS" | grep -c 'whitelisted') record(s)"
    fi
    log "$MSG"
    [[ "$QUIET" != "--quiet" ]] && echo "$MSG"
    exit 0
fi
