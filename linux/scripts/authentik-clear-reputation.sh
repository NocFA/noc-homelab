#!/bin/bash
# Clears Authentik reputation scores for IPs/users that have successfully logged in.
# Run on a timer so legitimate users aren't penalised for typos.

AUTHENTIK_URL="https://auth.nocfa.net"
ENV_FILE="/home/noc/noc-homelab/services/authentik/.env"

python3 - "$AUTHENTIK_URL" "$ENV_FILE" <<'EOF'
import sys, json, datetime, urllib.request, urllib.error

base_url = sys.argv[1]
env_file = sys.argv[2]

token = next(
    l.split('=', 1)[1].strip()
    for l in open(env_file)
    if l.startswith('AUTHENTIK_BOOTSTRAP_TOKEN=')
)

def api_get(path):
    req = urllib.request.Request(
        f"{base_url}/api/v3/{path}",
        headers={'Authorization': f'Bearer {token}'}
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def api_delete(path):
    req = urllib.request.Request(
        f"{base_url}/api/v3/{path}",
        method='DELETE',
        headers={'Authorization': f'Bearer {token}'}
    )
    urllib.request.urlopen(req)

scores = api_get("policies/reputation/scores/?page_size=100")
if scores['pagination']['count'] == 0:
    sys.exit(0)

logins = api_get("events/events/?action=login&ordering=-created&page_size=100")

now = datetime.datetime.now(datetime.timezone.utc)
cutoff = now - datetime.timedelta(minutes=30)

cleared_ips = set()
cleared_usernames = set()
for event in logins['results']:
    created = datetime.datetime.fromisoformat(event['created'])
    if created < cutoff:
        continue
    ip = event.get('client_ip', '')
    username = event.get('user', {}).get('username', '')
    if ip:
        cleared_ips.add(ip)
    if username and username not in ('', 'AnonymousUser'):
        cleared_usernames.add(username)

for score in scores['results']:
    if score['ip'] in cleared_ips or score['identifier'] in cleared_usernames:
        try:
            api_delete(f"policies/reputation/scores/{score['pk']}/")
            print(f"cleared: ip={score['ip']} identifier={score['identifier']} score={score['score']}")
        except urllib.error.HTTPError as e:
            print(f"error deleting {score['pk']}: {e}", file=sys.stderr)
EOF
