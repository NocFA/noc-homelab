#!/usr/bin/env python3
"""
NOC Homelab Agent

Cross-platform service management agent that exposes an HTTP API
for the central dashboard to query and control services.

Usage:
    python agent.py [--port 8080] [--config config.yaml]
"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from flask import Flask, jsonify, request
import yaml

from platforms import get_platform_handler

app = Flask(__name__)
handler = None
config = {}


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        return {'services': {}}

    with open(config_path, 'r') as f:
        return yaml.safe_load(f) or {'services': {}}


@app.route('/api/agent/health')
def health():
    """Health check endpoint."""
    from datetime import datetime
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })


@app.route('/api/agent/info')
def info():
    """Return machine metadata."""
    platform_info = handler.get_platform_info()
    return jsonify({
        'hostname': platform_info['hostname'],
        'platform': platform_info['platform'],
        'version': '1.0.0',
        'uptime': handler.get_system_uptime(),
        'services_count': len(config.get('services', {}))
    })


@app.route('/api/agent/services')
def services():
    """Return all services managed by this agent."""
    service_list = handler.list_services(config)
    return jsonify({
        'services': [asdict(s) for s in service_list]
    })


@app.route('/api/agent/status')
def status():
    """Return status of all services (lightweight)."""
    result = {}
    for svc_id in config.get('services', {}).keys():
        result[svc_id] = handler.get_service_status(svc_id, config)
    return jsonify(result)


@app.route('/api/agent/service/<action>', methods=['POST'])
def control_service(action):
    """Control a service. Actions: start, stop, restart, logs"""
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

    # Initialize platform handler
    handler = get_platform_handler()
    platform_info = handler.get_platform_info()
    print(f"NOC Homelab Agent starting on {platform_info['platform']}")

    # Load config
    config = load_config(args.config)
    print(f"Loaded {len(config.get('services', {}))} services from {args.config}")

    # Run server
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
