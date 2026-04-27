#!/usr/bin/env bash
# Render the CrowdSec notification YAMLs from services/crowdsec/notifications/
# (placeholders) into /etc/crowdsec/notifications/ (real values), substituting
# env vars from services/crowdsec/.env.
#
# CrowdSec does NOT expand ${VAR} in notifier YAML at runtime — substitution
# has to happen at deploy time. This script automates that step (was a manual
# `sed` one-liner buried in services/crowdsec/README.md before; manual step
# silently failed for http_triage.yaml between 2026-04-21 and 2026-04-25 —
# log-triage got zero events for 4 days because the env vars were never
# substituted on the host).
#
# Usage: sudo ./deploy-crowdsec-notifications.sh
#
# Idempotent. Safe to re-run after editing notification templates or
# rotating webhook URL / triage token in .env.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC_DIR="$REPO_ROOT/services/crowdsec/notifications"
DST_DIR="/etc/crowdsec/notifications"
ENV_FILE="$REPO_ROOT/services/crowdsec/.env"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"; }
err() { echo "ERROR: $1" >&2; exit 1; }

if [[ $EUID -ne 0 ]]; then
    err "must run as root (sudo)"
fi

[[ -d "$SRC_DIR" ]] || err "source dir missing: $SRC_DIR"
[[ -d "$DST_DIR" ]] || err "destination dir missing: $DST_DIR (install crowdsec first)"
[[ -f "$ENV_FILE" ]] || err ".env missing: $ENV_FILE (copy .env.example and fill in values)"

# === Source .env ===
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

# === Required vars ===
required=(CROWDSEC_DISCORD_WEBHOOK LOG_TRIAGE_URL LOG_TRIAGE_TOKEN)
for v in "${required[@]}"; do
    val="${!v:-}"
    [[ -n "$val" ]] || err "$v is empty in $ENV_FILE"
    [[ "$val" == *CHANGE_ME* ]] && err "$v still has CHANGE_ME placeholder in $ENV_FILE"
done

# === Render each *.yaml in source dir ===
shopt -s nullglob
templates=("$SRC_DIR"/*.yaml)
shopt -u nullglob

[[ ${#templates[@]} -gt 0 ]] || err "no *.yaml templates in $SRC_DIR"

# Stage in a temp dir; only swap into place if every template renders cleanly.
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

for tmpl in "${templates[@]}"; do
    name="$(basename "$tmpl")"
    out="$STAGE_DIR/$name"

    # envsubst would be cleanest, but it's not installed by default on
    # minimal Ubuntu servers. Use a controlled shell-expansion via a
    # heredoc-eval pattern that ONLY expands the three known vars (avoids
    # surprises if a YAML happens to contain $foo bash-syntax).
    awk -v webhook="$CROWDSEC_DISCORD_WEBHOOK" \
        -v triage_url="$LOG_TRIAGE_URL" \
        -v triage_tok="$LOG_TRIAGE_TOKEN" '
        {
            gsub(/\${CROWDSEC_DISCORD_WEBHOOK}/, webhook)
            gsub(/\${LOG_TRIAGE_URL}/, triage_url)
            gsub(/\${LOG_TRIAGE_TOKEN}/, triage_tok)
            print
        }
    ' "$tmpl" > "$out"

    # Sanity: nothing of the form ${...} should remain.
    if grep -qE '\$\{[A-Z_][A-Z0-9_]*\}' "$out"; then
        unsubbed="$(grep -oE '\$\{[A-Z_][A-Z0-9_]*\}' "$out" | sort -u | tr '\n' ' ')"
        err "$name still contains unsubstituted vars: $unsubbed"
    fi
done

# === Install (only after every template rendered cleanly) ===
deployed=0
for staged in "$STAGE_DIR"/*.yaml; do
    name="$(basename "$staged")"
    dst="$DST_DIR/$name"

    # Skip if identical (no changes — quiet exit).
    if [[ -f "$dst" ]] && cmp -s "$staged" "$dst"; then
        log "unchanged: $dst"
        continue
    fi

    install -o root -g root -m 0640 "$staged" "$dst"
    log "deployed: $dst"
    deployed=$((deployed + 1))
done

if [[ $deployed -eq 0 ]]; then
    log "no changes; crowdsec reload not required"
    exit 0
fi

# === Reload crowdsec ===
# `systemctl reload` re-reads notifier configs without dropping the LAPI
# connection (preferred over restart — avoids a brief gap in alert
# processing).
log "reloading crowdsec ($deployed file(s) changed)"
systemctl reload crowdsec
log "done"
