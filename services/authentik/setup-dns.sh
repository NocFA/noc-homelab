#!/usr/bin/env bash
# One-time: create Cloudflare DNS record for auth.nocfa.net.
# Usage: CF_API_TOKEN=xxx CF_ZONE_ID=yyy ./setup-dns.sh
set -euo pipefail

: "${CF_API_TOKEN:?Set CF_API_TOKEN}"
: "${CF_ZONE_ID:?Set CF_ZONE_ID}"

CF_API="https://api.cloudflare.com/client/v4"
AUTH="Authorization: Bearer $CF_API_TOKEN"

PUBLIC_IP=$(curl -sf https://api.ipify.org)
echo "Public IP: $PUBLIC_IP"

create_record() {
  local type="$1" name="$2" content="$3" proxied="${4:-false}"
  echo -n "Creating $type $name -> $content (proxied=$proxied)... "
  RESP=$(curl -sf -X POST -H "$AUTH" -H "Content-Type: application/json" \
    -d "{\"type\":\"$type\",\"name\":\"$name\",\"content\":\"$content\",\"proxied\":$proxied,\"ttl\":1}" \
    "$CF_API/zones/$CF_ZONE_ID/dns_records")
  SUCCESS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success','false'))")
  if [[ "$SUCCESS" == "True" ]]; then
    echo "OK"
  else
    ERRORS=$(echo "$RESP" | python3 -c "import sys,json; [print(e.get('message','?')) for e in json.load(sys.stdin).get('errors',[])]")
    echo "FAILED: $ERRORS"
  fi
}

create_record A "auth.nocfa.net" "$PUBLIC_IP" false

echo "Done. Verify with: dig +short auth.nocfa.net"
