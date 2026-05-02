#!/usr/bin/env bash
#
# cf-crowdsec-sync — push CrowdSec ban decisions into a Cloudflare WAF
# Custom Rule on the looney.eu zone. The rule blocks listed source IPs at
# CF's edge before they ever reach the cloudflared tunnel + caddy.
#
# This is the free fallback for the paid Cloudflare Worker bouncer:
# CrowdSec LAPI -> jq -> Cloudflare Rulesets API PATCH.
#
# Reads CF_API_TOKEN, CF_ZONE_ID, CF_RULESET_ID, CF_RULE_ID, MAX_IPS from
# /etc/cf-crowdsec-sync.env (deploy.sh installs it).
set -euo pipefail

env_file="${CF_CROWDSEC_SYNC_ENV:-/etc/cf-crowdsec-sync.env}"
if [[ -r "$env_file" ]]; then
    # shellcheck disable=SC1090
    set -a; . "$env_file"; set +a
fi

: "${CF_API_TOKEN:?CF_API_TOKEN missing — populate $env_file}"
: "${CF_ZONE_ID:?CF_ZONE_ID missing}"
: "${CF_RULESET_ID:?CF_RULESET_ID missing}"
: "${CF_RULE_ID:?CF_RULE_ID missing}"
: "${CF_RULE_HOST:=love.looney.eu}"
: "${MAX_IPS:=200}"

api="https://api.cloudflare.com/client/v4"

# Pull active ban decisions and keep IP-scope only. cscli needs sudo to read
# /etc/crowdsec/config.yaml; the systemd unit runs as root for this reason.
mapfile -t ips < <(
    cscli decisions list -o json 2>/dev/null \
    | jq -r '
        (. // [])
        | map(.decisions // [])
        | flatten
        | map(select(.type == "ban"
                     and (.scope|ascii_downcase) == "ip"
                     and .value
                     and (.value | test("^(\\d{1,3}\\.){3}\\d{1,3}(/\\d{1,2})?$"))))
        | map(.value)
        | unique
        | .[]
    '
)

count=${#ips[@]}

# Cloudflare expressions are capped at ~4 KB. Each IPv4 + space ≈ 16 bytes;
# 200 IPs ≈ 3.2 KB. Trim from the head if we somehow exceed the cap so the
# newest bans always make it into the rule.
if (( count > MAX_IPS )); then
    ips=("${ips[@]:0:$MAX_IPS}")
    count=$MAX_IPS
fi

# An empty `ip.src in {}` is rejected by CF's expression parser. Use
# TEST-NET-1 as a placeholder so the rule remains valid but matches nothing.
if (( count == 0 )); then
    ips=("192.0.2.1")
fi

ip_set="${ips[*]}"
expression="(http.host eq \"${CF_RULE_HOST}\") and (ip.src in {${ip_set}})"

response=$(
    curl -sS -X PATCH \
        "${api}/zones/${CF_ZONE_ID}/rulesets/${CF_RULESET_ID}/rules/${CF_RULE_ID}" \
        -H "Authorization: Bearer ${CF_API_TOKEN}" \
        -H "Content-Type: application/json" \
        --data-binary @- <<EOF
{
  "description": "lovelang: crowdsec ban (synced)",
  "action": "block",
  "expression": $(printf '%s' "$expression" | jq -Rs .),
  "enabled": true
}
EOF
)

if printf '%s' "$response" | jq -e '.success' >/dev/null; then
    printf '%s synced %d IP(s) to CF rule %s\n' \
        "$(date -u +%FT%TZ)" "$count" "$CF_RULE_ID"
else
    printf '%s sync FAILED: %s\n' \
        "$(date -u +%FT%TZ)" "$(printf '%s' "$response" | jq -c '.errors')" >&2
    exit 1
fi
