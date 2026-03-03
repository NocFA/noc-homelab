#!/opt/homebrew/bin/python3
"""
Push homelab service status to Cloudflare Worker KV for public display on looney.eu/homelab.html

Run every 60s via LaunchAgent (com.noc.homelab-status-push.plist).

Required env var: HOMELAB_STATUS_PUSH_SECRET
Worker URL: configured via HOMELAB_STATUS_WORKER_URL (set in LaunchAgent plist EnvironmentVariables)
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

DASHBOARD_URL = 'http://localhost:8080/api/status'
WORKER_URL = os.environ.get('HOMELAB_STATUS_WORKER_URL', 'CHANGE_ME_WORKER_URL')
PUSH_SECRET = os.environ.get('HOMELAB_STATUS_PUSH_SECRET', '')

# Services to expose publicly — map from machine_id -> { service_id: display_label }
PUBLIC_SERVICES = {
    'noc-local': {
        'dashboard':        'Dashboard',
        'copyparty':        'Copyparty',
        'maloja':           'Maloja',
        'multi-scrobbler':  'Scrobbler',
        'syncthing':        'Syncthing',
        'teamspeak':        'TeamSpeak',
    },
    'noc-tux': {
        'gatus':            'Gatus',
        'caddy-websites':   'Web',
    },
    'noc-claw': {
        'homelab-agent':    'Agent',
    },
}


def fetch_status():
    try:
        req = urllib.request.Request(DASHBOARD_URL, headers={'User-Agent': 'homelab-status-push/1.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f'[push-homelab-status] fetch failed: {e}', file=sys.stderr)
        return None


def transform(raw):
    machines = []
    for machine_id, services_map in PUBLIC_SERVICES.items():
        raw_machine = raw.get(machine_id, {})
        # noc-local is always reachable (we're running on it); others have _reachable flag
        if machine_id == 'noc-local':
            reachable = True
        else:
            reachable = bool(raw_machine.get('_reachable', False))
        uptime = raw_machine.get('_uptime', '--')
        services = []
        for svc_id, svc_label in services_map.items():
            online = bool(raw_machine.get(svc_id, False))
            services.append({'id': svc_id, 'label': svc_label, 'online': online})
        machines.append({
            'id': machine_id,
            'label': machine_id,
            'online': reachable,
            'uptime': uptime,
            'services': services,
        })
    return {
        'updated': datetime.now(timezone.utc).isoformat(),
        'machines': machines,
    }


def push(data):
    if not PUSH_SECRET:
        print('[push-homelab-status] HOMELAB_STATUS_PUSH_SECRET not set', file=sys.stderr)
        sys.exit(1)
    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(
        f'{WORKER_URL}/push',
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'X-Auth-Token': PUSH_SECRET,
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status


if __name__ == '__main__':
    raw = fetch_status()
    if raw is None:
        sys.exit(1)
    data = transform(raw)
    status = push(data)
    print(f'[push-homelab-status] pushed OK (HTTP {status})')
