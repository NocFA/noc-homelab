import argparse
import json
import os
import platform
import sys
from dataclasses import asdict
from flask import Flask, jsonify, request
import yaml

from platforms import get_platform_handler

app = Flask(__name__)
handler = None
config = {}


def _current_hostname() -> str:
    """Return the local hostname, stripped of any FQDN suffix.

    `platform.node()` may return something like `noc-tux.tail6aa1bb.ts.net`
    on Tailscale machines; the canonical config keys are bare hostnames.
    """
    name = platform.node() or ''
    return name.split('.', 1)[0]


def load_config(config_path: str) -> dict:
    """Load agent config and produce a host-scoped legacy-shaped dict.

    The on-disk schema (v2, introduced 2026-05-02) is a single canonical
    file listing every service across the homelab, each tagged with a
    `host:` field, plus a top-level `hosts:` map of per-machine metadata.

    The rest of the agent (route handlers, platform handlers) still
    expects the legacy shape:

        {
          'machine': {'id': ..., 'display_name': ..., 'role': ...},
          'services': {svc_id: {...}, ...},
        }

    so this function detects the current hostname, filters the v2 list,
    and reshapes it back to the legacy dict.  v1 files (no `version:`
    key, top-level `machine:` block) are returned as-is.
    """
    if not os.path.exists(config_path):
        return {'services': {}}
    with open(config_path, 'r') as f:
        raw = yaml.safe_load(f) or {}

    # Legacy v1: keep behaviour identical.
    if raw.get('version') is None and 'hosts' not in raw:
        if 'services' not in raw:
            raw['services'] = {}
        return raw

    hostname = _current_hostname()
    hosts = raw.get('hosts') or {}
    if hostname not in hosts:
        raise RuntimeError(
            f"agent/config.yaml has no entry for host {hostname!r}; "
            f"add it under `hosts:` (known: {sorted(hosts)})"
        )
    host_meta = hosts[hostname] or {}

    services_dict = {}
    for svc in raw.get('services') or []:
        if not isinstance(svc, dict):
            continue
        if svc.get('host') != hostname:
            continue
        svc_id = svc.get('id')
        if not svc_id:
            continue
        # Strip the routing fields; everything else passes through to
        # the platform handlers verbatim.
        cleaned = {k: v for k, v in svc.items() if k not in ('host', 'id')}
        services_dict[svc_id] = cleaned

    return {
        'machine': {
            'id': host_meta.get('id', hostname),
            'display_name': host_meta.get('display_name', hostname),
            'role': host_meta.get('role', 'agent'),
        },
        'services': services_dict,
    }


@app.route('/api/agent/health')
def health():
    from datetime import datetime
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })


@app.route('/api/agent/info')
def info():
    platform_info = handler.get_platform_info()
    return jsonify({
        'hostname': platform_info['hostname'],
        'platform': platform_info['platform'],
        'version': '1.0.0',
        'uptime': handler.get_system_uptime(),
        'services_count': len(config.get('services', {}))
    })


@app.route('/api/agent/machine')
def machine():
    return jsonify(config.get('machine', {}))


@app.route('/api/agent/services')
def services():
    service_list = handler.list_services(config)
    return jsonify({
        'services': [asdict(s) for s in service_list]
    })


@app.route('/api/agent/status')
def status():
    result = {}
    for svc_id in config.get('services', {}).keys():
        result[svc_id] = handler.get_service_status(svc_id, config)
    return jsonify(result)


@app.route('/api/agent/service/<action>', methods=['POST'])
def control_service(action):
    data = request.get_json() or {}
    service_id = data.get('service')
    if not service_id:
        return jsonify({'success': False, 'error': 'Missing service ID'}), 400
    if service_id not in config.get('services', {}):
        return jsonify({'success': False, 'error': 'Unknown service'}), 404
    try:
        if action == 'start':
            success = handler.start_service(service_id, config)
            return jsonify({'success': success, 'message': 'Service started' if success else 'Failed to start'})
        elif action == 'stop':
            success = handler.stop_service(service_id, config)
            return jsonify({'success': success, 'message': 'Service stopped' if success else 'Failed to stop'})
        elif action == 'restart':
            success = handler.restart_service(service_id, config)
            return jsonify({'success': success, 'message': 'Service restarted' if success else 'Failed to restart'})
        elif action == 'logs':
            lines = data.get('lines', 100)
            logs = handler.get_service_logs(service_id, config, lines)
            return jsonify({'success': True, 'logs': logs})
        else:
            return jsonify({'success': False, 'error': f'Unknown action: {action}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def main():
    global handler, config
    parser = argparse.ArgumentParser(description='NOC Homelab Agent')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    args = parser.parse_args()
    handler = get_platform_handler()
    config = load_config(args.config)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
