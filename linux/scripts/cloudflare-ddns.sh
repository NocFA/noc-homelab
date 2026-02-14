#!/usr/bin/env bash
# Cloudflare DDNS updater for nocfa.net and matrix.nocfa.net
# Runs via systemd timer every 5 minutes.
set -euo pipefail

CONFIG="/home/noc/noc-homelab/configs/cloudflare-ddns.sops.env"
SOPS_AGE_KEY_FILE="/home/noc/noc-homelab/noc-homelab-beads/homelab.agekey"
export SOPS_AGE_KEY_FILE

# Decrypt config
eval "$(sops -d "$CONFIG")"

# CF_API_TOKEN, CF_ZONE_ID must be set after sourcing config
: "${CF_API_TOKEN:?CF_API_TOKEN not set}"
: "${CF_ZONE_ID:?CF_ZONE_ID not set}"

# Records to update (name -> record ID, populated on first run)
RECORDS=("nocfa.net" "matrix.nocfa.net")

CF_API="https://api.cloudflare.com/client/v4"
AUTH_HEADER="Authorization: Bearer $CF_API_TOKEN"

# Get current public IP
CURRENT_IP=$(curl -sf https://api.ipify.org || curl -sf https://ifconfig.me)
if [[ -z "$CURRENT_IP" ]]; then
  echo "ERROR: Could not determine public IP" >&2
  exit 1
fi

for RECORD_NAME in "${RECORDS[@]}"; do
  # Get record ID and current value
  RESPONSE=$(curl -sf -H "$AUTH_HEADER" \
    "$CF_API/zones/$CF_ZONE_ID/dns_records?type=A&name=$RECORD_NAME")

  RECORD_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; r=json.load(sys.stdin)['result']; print(r[0]['id'] if r else '')")
  RECORD_IP=$(echo "$RESPONSE" | python3 -c "import sys,json; r=json.load(sys.stdin)['result']; print(r[0]['content'] if r else '')")

  if [[ -z "$RECORD_ID" ]]; then
    echo "WARNING: No A record found for $RECORD_NAME, skipping" >&2
    continue
  fi

  if [[ "$RECORD_IP" == "$CURRENT_IP" ]]; then
    echo "$RECORD_NAME already points to $CURRENT_IP"
    continue
  fi

  # Update the record
  curl -sf -X PATCH -H "$AUTH_HEADER" -H "Content-Type: application/json" \
    -d "{\"content\":\"$CURRENT_IP\"}" \
    "$CF_API/zones/$CF_ZONE_ID/dns_records/$RECORD_ID" > /dev/null

  echo "$RECORD_NAME updated: $RECORD_IP -> $CURRENT_IP"
done
