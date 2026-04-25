#!/usr/bin/env bash
# Sends a Discord webhook embed when a critical systemd unit fails.
#
# Wired up via systemd template `notify-discord-failure@.service` and an
# `OnFailure=notify-discord-failure@%n.service` directive on each watched unit.
#
# Usage:  notify-systemd-failure.sh <unit-name>
#   e.g.  notify-systemd-failure.sh crowdsec-firewall-bouncer.service
#
# Webhook URL discovery (first match wins):
#   1. $DISCORD_WEBHOOK_URL env var
#   2. /etc/crowdsec/notifications/http_discord.yaml  (existing CrowdSec webhook)
#   3. /home/noc/noc-homelab/services/gatus/config.yaml  (gatus webhook)
#
# Deduplication: a 60s lockfile per unit prevents a flapping service from
# spamming the channel.  systemd's own RestartSec=10 + StartLimitBurst=5
# already provides upstream rate limiting, this is belt-and-braces.

set -u

UNIT="${1:-unknown.service}"
HOSTNAME_SHORT="$(hostname -s 2>/dev/null || echo unknown)"
LOCK_DIR="/run/notify-systemd-failure"
LOCK_FILE="${LOCK_DIR}/${UNIT}.lock"
LOCK_TTL=60  # seconds

mkdir -p "$LOCK_DIR" 2>/dev/null || true

# Dedup check
if [[ -f "$LOCK_FILE" ]]; then
    last_fired=$(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0)
    now=$(date +%s)
    if (( now - last_fired < LOCK_TTL )); then
        exit 0
    fi
fi
touch "$LOCK_FILE"

# Resolve webhook URL
WEBHOOK="${DISCORD_WEBHOOK_URL:-}"
if [[ -z "$WEBHOOK" && -r /etc/crowdsec/notifications/http_discord.yaml ]]; then
    WEBHOOK=$(awk '/^url:/ {print $2; exit}' /etc/crowdsec/notifications/http_discord.yaml 2>/dev/null)
fi
if [[ -z "$WEBHOOK" && -r /home/noc/noc-homelab/services/gatus/config.yaml ]]; then
    WEBHOOK=$(grep -oE 'https://discord\.com/api/webhooks/[A-Za-z0-9_/-]+' \
        /home/noc/noc-homelab/services/gatus/config.yaml 2>/dev/null | head -1)
fi
if [[ -z "$WEBHOOK" ]]; then
    logger -t notify-systemd-failure "no webhook URL configured, dropping alert for $UNIT"
    exit 0
fi

# Gather diagnostics
ACTIVE_STATE=$(systemctl show -p ActiveState --value "$UNIT" 2>/dev/null)
SUB_STATE=$(systemctl show -p SubState --value "$UNIT" 2>/dev/null)
RESULT=$(systemctl show -p Result --value "$UNIT" 2>/dev/null)
N_RESTARTS=$(systemctl show -p NRestarts --value "$UNIT" 2>/dev/null)
EXEC_STATUS=$(systemctl show -p ExecMainStatus --value "$UNIT" 2>/dev/null)

# Last 12 lines of journal for the failed unit (panic backtraces fit in here)
LOG_TAIL=$(journalctl -u "$UNIT" -n 12 --no-pager -o cat 2>/dev/null \
    | tail -c 1500 \
    | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/    /g' \
    | awk 'BEGIN{ORS="\\n"} {print}')

# Build payload (single-line jq-style escaping done above)
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
TITLE="${HOSTNAME_SHORT} -- ${UNIT} FAILED"

DESCRIPTION="**Result:** ${RESULT:-unknown} | **Restarts:** ${N_RESTARTS:-?} | **Exit:** ${EXEC_STATUS:-?}\\n**State:** ${ACTIVE_STATE:-?} (${SUB_STATE:-?})\\n\\n**Recent log:**\\n\`\`\`\\n${LOG_TAIL}\\n\`\`\`"

# Discord limits embed description to 4096 chars; truncate just in case
if (( ${#DESCRIPTION} > 3900 )); then
    DESCRIPTION="${DESCRIPTION:0:3900}..."
fi

PAYLOAD=$(cat <<EOF
{
  "content": "<@139476150786195456>",
  "embeds": [{
    "title": "${TITLE}",
    "description": "${DESCRIPTION}",
    "color": 15745372,
    "timestamp": "${TIMESTAMP}",
    "footer": {"text": "systemd OnFailure -- noc-homelab"}
  }]
}
EOF
)

# Post (with 10s timeout, fail silently to journal)
RESPONSE=$(curl -fsS -m 10 -H 'Content-Type: application/json' \
    -X POST -d "$PAYLOAD" "$WEBHOOK" 2>&1) || {
    logger -t notify-systemd-failure "Discord webhook failed for $UNIT: $RESPONSE"
    exit 1
}

logger -t notify-systemd-failure "alert sent for $UNIT (Result=$RESULT, NRestarts=$N_RESTARTS)"
exit 0
