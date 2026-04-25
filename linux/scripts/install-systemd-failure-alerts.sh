#!/usr/bin/env bash
# Installs systemd OnFailure -> Discord alerting for critical security services.
#
# Drops the notify-discord-failure@.service template into /etc/systemd/system/
# and adds OnFailure= drop-ins for each watched unit.
#
# Idempotent: safe to re-run.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SD_DIR="/etc/systemd/system"

if [[ $EUID -ne 0 ]]; then
    echo "must run as root (sudo)" >&2
    exit 1
fi

# 1. Notification template (shared by all watched units)
install -m 644 "$REPO_ROOT/linux/systemd/notify-discord-failure@.service" \
    "$SD_DIR/notify-discord-failure@.service"

# 2. Per-unit drop-ins. Format: "<unit-name>:<source-conf-name>"
declare -a UNITS=(
    "crowdsec.service:crowdsec-discord-onfailure.conf"
    "crowdsec-firewall-bouncer.service:crowdsec-firewall-bouncer-discord-onfailure.conf"
)

for entry in "${UNITS[@]}"; do
    unit="${entry%%:*}"
    src="${entry##*:}"
    dropin_dir="$SD_DIR/${unit}.d"
    install -d -m 755 "$dropin_dir"
    install -m 644 "$REPO_ROOT/linux/systemd/$src" "$dropin_dir/discord-onfailure.conf"
    echo "installed drop-in: $dropin_dir/discord-onfailure.conf"
done

systemctl daemon-reload
echo "daemon reloaded"

# 3. Verify
for entry in "${UNITS[@]}"; do
    unit="${entry%%:*}"
    on_failure=$(systemctl show -p OnFailure --value "$unit")
    if [[ -z "$on_failure" ]]; then
        echo "WARN: $unit has no OnFailure set" >&2
    else
        echo "OK: $unit -> OnFailure=$on_failure"
    fi
done

echo
echo "To test: sudo systemd-run --unit=test-failure --service-type=oneshot --no-block /bin/false"
echo "Or trigger manually: $REPO_ROOT/linux/scripts/notify-systemd-failure.sh test.service"
