#!/opt/homebrew/bin/python3
"""
Push homelab service status as a static JSON file to the web server.

Run every 60s via LaunchAgent (com.noc.homelab-status-push.plist).

Maintains hourly history locally in ~/.homelab-status-history.json,
writes the full payload to a temp file, and SCPs it to noc-tux.
"""

import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DASHBOARD_URL = 'http://localhost:8080/api/status'
WEBSITES_URL = 'http://localhost:8080/api/websites/list'
HISTORY_FILE = Path.home() / '.homelab-status-history.json'
OUTPUT_FILE = Path.home() / '.homelab-status.json'
SCP_DEST = 'noc@noc-tux:/home/webdev/looney.eu/public_html/homelab-status.json'
HOURS = 24

# Services to expose publicly — map from machine_id -> service entries.
# Each entry is either a string label (single service) or a dict with 'label'
# and 'ids' (consolidated group — online if ALL sub-services are online).
PUBLIC_SERVICES = {
    'noc-local': {
        'dashboard':        'Dashboard',
        'copyparty':        'Copyparty',
        'maloja':           'Maloja',
        'multi-scrobbler':  'Scrobbler',
        'teamspeak-6':      'TeamSpeak',
        'mdsf':             {'label': 'MDSF', 'ids': ['mdsf-crew', 'mdsf-org']},
        'voiceseq':         {'label': 'VoiceSeq', 'ids': ['voiceseq', 'voiceseq-processor']},
        'beads-ui':         'Beads',
        'gatus':            'Gatus',
    },
    'noc-tux': {
        'matrix':           {'label': 'Matrix', 'ids': ['matrix-synapse', 'matrix-coturn', 'matrix-client-element']},
        'authentik':        'Authentik',
        'emby':             'Emby',
        'zurg':             'Zurg',
        'jellyfin':         'Jellyfin',
        'arcane':           'Arcane',
        'gatus':            'Gatus',
        'sunshine':         'Sunshine',
    },
    'noc-claw': {
        'openclaw':         'OpenClaw',
        'ollama':           'Ollama',
        'open-llm-vtuber':  'VTuber',
    },
    'noc-baguette': {
        'rathole':          'Rathole',
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


def fetch_websites():
    try:
        req = urllib.request.Request(WEBSITES_URL, headers={'User-Agent': 'homelab-status-push/1.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            return data.get('sites', {})
    except Exception as e:
        print(f'[push-homelab-status] websites fetch failed: {e}', file=sys.stderr)
        return {}


def transform(raw, websites=None):
    # Inject website all_up status into noc-local so MDSF and similar
    # app-sites (which live under /api/websites/list) can be checked by key.
    if websites:
        noc_local = dict(raw.get('noc-local', {}))
        for site_id, site_data in websites.items():
            noc_local[site_id] = bool(site_data.get('all_up', False))
        raw = dict(raw)
        raw['noc-local'] = noc_local

    machines = []
    for machine_id, services_map in PUBLIC_SERVICES.items():
        raw_machine = raw.get(machine_id, {})
        if machine_id == 'noc-local':
            reachable = True
        else:
            reachable = bool(raw_machine.get('_reachable', False))
        uptime = raw_machine.get('_uptime', '--')
        services = []
        for svc_id, svc_def in services_map.items():
            if isinstance(svc_def, dict):
                label = svc_def['label']
                online = all(bool(raw_machine.get(sid, False)) for sid in svc_def['ids'])
            else:
                label = svc_def
                online = bool(raw_machine.get(svc_id, False))
            services.append({'id': svc_id, 'label': label, 'online': online})
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


def load_history():
    try:
        return json.loads(HISTORY_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_history(history):
    HISTORY_FILE.write_text(json.dumps(history))


def update_history(history, current):
    hour_key = current['updated'][:13]

    bucket = next((b for b in history if b['h'] == hour_key), None)
    if not bucket:
        bucket = {'h': hour_key, 'm': {}}
        history.insert(0, bucket)

    for machine in current.get('machines', []):
        mid = machine['id']
        if mid not in bucket['m']:
            bucket['m'][mid] = {'up': 0, 'down': 0}
        if machine['online']:
            bucket['m'][mid]['up'] += 1
        else:
            bucket['m'][mid]['down'] += 1

    return history[:HOURS]


def scp_upload(filepath):
    result = subprocess.run(
        ['scp', '-q', '-o', 'ConnectTimeout=5', str(filepath), SCP_DEST],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        print(f'[push-homelab-status] scp failed: {result.stderr.strip()}', file=sys.stderr)
        return False
    return True


def copy_to_nocfa():
    result = subprocess.run(
        ['ssh', '-o', 'ConnectTimeout=5', 'noc@noc-tux',
         'sudo cp /home/webdev/looney.eu/public_html/homelab-status.json '
         '/matrix/static-files/public/homelab-status.json'],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        print(f'[push-homelab-status] nocfa copy failed: {result.stderr.strip()}', file=sys.stderr)
        return False
    return True


if __name__ == '__main__':
    raw = fetch_status()
    if raw is None:
        sys.exit(1)

    websites = fetch_websites()
    current = transform(raw, websites)
    history = load_history()
    history = update_history(history, current)
    save_history(history)

    payload = json.dumps({'current': current, 'history': history}, separators=(',', ':'))
    OUTPUT_FILE.write_text(payload)

    if scp_upload(OUTPUT_FILE):
        print('[push-homelab-status] pushed OK via SCP')
        if copy_to_nocfa():
            print('[push-homelab-status] copied to nocfa.net')
    else:
        sys.exit(1)
