#!/usr/bin/env bash
# Deploy Seafile CE (self-hosted file sync). LAN-only; no DNS / Caddy vhost.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found." >&2
  echo "This service ships with a pre-populated .env. Restore it before running deploy." >&2
  exit 1
fi

# Preflight: warn on low free space (Seafile object store + ingest can balloon to several hundred GB).
FREE_KB=$(df -k . | awk 'NR==2 {print $4}')
FREE_GB=$(( FREE_KB / 1024 / 1024 ))
if (( FREE_GB < 500 )); then
  echo "WARNING: only ${FREE_GB} GB free on the volume hosting $SCRIPT_DIR." >&2
  echo "         Seafile ingest can require 500 GB+ headroom. Consider freeing space before bulk uploads." >&2
fi

docker compose up -d

# Read a couple of values back from .env for the summary banner.
# shellcheck disable=SC1090
set +u
source "$ENV_FILE"
set -u

ADMIN_EMAIL="${SEAFILE_ADMIN_EMAIL:-(unset)}"
HOSTNAME="${SEAFILE_SERVER_HOSTNAME:-(unset)}"
PORT="${SEAFILE_PORT:-8000}"

# If SEAFILE_SERVER_HOSTNAME already includes a port (recommended to dodge the
# SERVICE_URL trap), use it as-is; otherwise append SEAFILE_PORT for the banner.
case "$HOSTNAME" in
  *:*) URL="http://${HOSTNAME}" ;;
  *)   URL="http://${HOSTNAME}:${PORT}" ;;
esac

echo ""
echo "Seafile is starting."
echo "  Web UI:       ${URL}"
echo "  Admin login:  ${ADMIN_EMAIL}  (password in $ENV_FILE)"
echo ""
echo "SERVICE_URL gotcha reminder (seafile-mc 11.0):"
echo "  The container entrypoint builds SERVICE_URL from"
echo "      \$SEAFILE_SERVER_PROTOCOL://\$SEAFILE_SERVER_HOSTNAME"
echo "  and IGNORES SEAFILE_PORT. If SEAFILE_SERVER_HOSTNAME does NOT contain"
echo "  a port suffix, file uploads/downloads will fail because Seafile assumes"
echo "  port 80."
echo ""
case "$HOSTNAME" in
  *:*)
    echo "  Current .env has SEAFILE_SERVER_HOSTNAME=${HOSTNAME} (port-suffixed) — OK."
    ;;
  *)
    echo "  Current .env has SEAFILE_SERVER_HOSTNAME=${HOSTNAME} — NOT port-suffixed."
    echo "  Fix ONE of the following:"
    echo "    A) Edit .env so SEAFILE_SERVER_HOSTNAME=${HOSTNAME}:${PORT}, then"
    echo "         docker compose down && docker compose up -d"
    echo "    B) Patch data/seafile/conf/seahub_settings.py:"
    echo "         SERVICE_URL      = '${URL}'"
    echo "         FILE_SERVER_ROOT = '${URL}/seafhttp'"
    echo "       then  docker compose restart seafile"
    ;;
esac
echo ""
