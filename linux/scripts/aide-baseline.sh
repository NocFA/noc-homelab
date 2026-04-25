#!/usr/bin/env bash
# Build (or rebuild) the AIDE baseline database.
#
# Run this:
#   - First time after installing aide
#   - After expected system changes (apt upgrade, configs intentionally edited)
#     when the weekly check has flagged them and you've reviewed the diff
#
# Usage: sudo ./aide-baseline.sh
#
# This is the equivalent of `aideinit` from aide-common, but with logging
# and a sanity check that the homelab exclusions are loaded (otherwise the
# baseline will scan /var/lib/docker, /mnt/zurg, etc. and either hang or
# produce a useless multi-GB database).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$REPO_ROOT/linux/logs"
LOG_FILE="$LOG_DIR/aide-baseline.log"
EXCLUSION_CONF="/etc/aide/aide.conf.d/85_aide_homelab"

mkdir -p "$LOG_DIR"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"; }

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: must run as root (sudo)" >&2
    exit 1
fi

# === Sanity: exclusion file must be present, otherwise the baseline will hang ===
if [[ ! -f "$EXCLUSION_CONF" ]]; then
    log "ERROR: $EXCLUSION_CONF missing — refusing to run"
    log "Symlink it first: sudo ln -sf $REPO_ROOT/linux/services/aide/85_aide_homelab $EXCLUSION_CONF"
    exit 1
fi

# === Kill any stale aideinit/aide --init processes ===
if pgrep -f 'aide.*--init' >/dev/null 2>&1; then
    log "killing stale aide --init processes"
    pkill -9 -f 'aide.*--init' || true
    sleep 2
fi

# === Reset working file ===
rm -f /var/lib/aide/aide.db.new
mkdir -p /var/log/aide

log "building AIDE baseline (this can take 5-15 minutes)"
log "config: /etc/aide/aide.conf"
log "exclusions loaded from: $EXCLUSION_CONF"

START=$SECONDS

# Run aide --init; capture stderr to log file but stream summary to stdout
if ! aide --config=/etc/aide/aide.conf --init \
        > /var/log/aide/aide-baseline.log \
        2> /var/log/aide/aide-baseline.errors; then
    log "ERROR: aide --init failed (rc=$?). Last errors:"
    tail -n 20 /var/log/aide/aide-baseline.errors | tee -a "$LOG_FILE"
    exit 1
fi

ELAPSED=$((SECONDS - START))
log "aide --init completed in ${ELAPSED}s"

if [[ ! -s /var/lib/aide/aide.db.new ]]; then
    log "ERROR: aide.db.new is empty after init — something is wrong"
    exit 1
fi

# === Promote new DB to active baseline ===
mv -f /var/lib/aide/aide.db.new /var/lib/aide/aide.db
chmod 600 /var/lib/aide/aide.db

DB_SIZE=$(stat -c%s /var/lib/aide/aide.db)
log "baseline promoted: /var/lib/aide/aide.db ($DB_SIZE bytes)"
log "next: enable the weekly check via aide-check.timer"
