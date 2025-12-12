#!/usr/bin/env python3
"""
Tailscale Management Script
Provides control and status information for Tailscale
"""

import subprocess
import json
import sys

def run_command(cmd):
    """Run a command and return stdout, stderr, and return code"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1

def get_status():
    """Get Tailscale status in JSON format"""
    stdout, stderr, code = run_command(['tailscale', 'status', '--json'])
    if code == 0:
        return json.loads(stdout)
    return None

def get_prefs():
    """Get Tailscale preferences"""
    stdout, stderr, code = run_command(['tailscale', 'debug', 'prefs'])
    if code == 0:
        return json.loads(stdout)
    return None

def enable_feature(feature):
    """Enable a Tailscale feature"""
    features = {
        'webclient': '--webclient=true',
        'exit-node': '--advertise-exit-node=true',
        'auto-update': '--auto-update=true',
    }

    if feature not in features:
        return False, f"Unknown feature: {feature}"

    stdout, stderr, code = run_command(['tailscale', 'set', features[feature]])
    return code == 0, stderr if code != 0 else stdout

def disable_feature(feature):
    """Disable a Tailscale feature"""
    features = {
        'webclient': '--webclient=false',
        'exit-node': '--advertise-exit-node=false',
    }

    if feature not in features:
        return False, f"Unknown feature: {feature}"

    stdout, stderr, code = run_command(['tailscale', 'set', features[feature]])
    return code == 0, stderr if code != 0 else stdout

def get_web_url():
    """Get the WebClient URL if enabled"""
    prefs = get_prefs()
    if prefs and prefs.get('RunWebClient'):
        status = get_status()
        if status and 'Self' in status:
            self_ip = status['Self']['TailscaleIPs'][0]
            return f"http://{self_ip}:5252"
    return None

def get_exit_node_status():
    """Check if this node is advertising as an exit node"""
    prefs = get_prefs()
    if prefs:
        routes = prefs.get('AdvertiseRoutes', [])
        # Exit nodes advertise 0.0.0.0/0 and ::/0
        if routes and ('0.0.0.0/0' in routes or '::/0' in routes):
            return True
    return False

def get_summary():
    """Get a summary of Tailscale status for the dashboard"""
    status = get_status()
    prefs = get_prefs()

    if not status or not prefs:
        return {
            'connected': False,
            'error': 'Unable to get Tailscale status'
        }

    self_info = status.get('Self', {})

    return {
        'connected': True,
        'hostname': self_info.get('HostName', 'Unknown'),
        'tailscale_ip': self_info.get('TailscaleIPs', ['N/A'])[0],
        'dns_name': self_info.get('DNSName', 'N/A'),
        'online': self_info.get('Online', False),
        'exit_node_enabled': get_exit_node_status(),
        'webclient_enabled': prefs.get('RunWebClient', False),
        'webclient_url': get_web_url(),
        'auto_update_enabled': prefs.get('AutoUpdate', {}).get('Apply', False),
        'version': subprocess.check_output(['tailscale', 'version', '--json'], text=True),
        'peer_count': len([p for p in status.get('Peer', {}).values() if p.get('Online', False)])
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: tailscale_manager.py <command> [args]")
        print("Commands:")
        print("  status - Get full status JSON")
        print("  summary - Get dashboard summary JSON")
        print("  enable <feature> - Enable a feature (webclient, exit-node, auto-update)")
        print("  disable <feature> - Disable a feature (webclient, exit-node)")
        print("  web-url - Get WebClient URL if enabled")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'status':
        status = get_status()
        print(json.dumps(status, indent=2))

    elif command == 'summary':
        summary = get_summary()
        print(json.dumps(summary, indent=2))

    elif command == 'enable' and len(sys.argv) > 2:
        feature = sys.argv[2]
        success, message = enable_feature(feature)
        result = {'success': success, 'message': message}
        print(json.dumps(result))
        sys.exit(0 if success else 1)

    elif command == 'disable' and len(sys.argv) > 2:
        feature = sys.argv[2]
        success, message = disable_feature(feature)
        result = {'success': success, 'message': message}
        print(json.dumps(result))
        sys.exit(0 if success else 1)

    elif command == 'web-url':
        url = get_web_url()
        print(json.dumps({'url': url}))

    else:
        print(json.dumps({'error': 'Unknown command'}))
        sys.exit(1)

if __name__ == '__main__':
    main()
