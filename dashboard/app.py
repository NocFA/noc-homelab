from flask import Flask, render_template, jsonify, request, send_from_directory
import subprocess
import socket
import os
import glob

app = Flask(__name__, template_folder='.')

SERVICES = {
    'emby': {
        'name': 'Emby',
        'launchd': 'disabled',  # Emby is managed via Login Items, no control
        'port': 8096,
        'log_paths': ['~/.config/emby-server/logs/embyserver*.txt']
    },
    'copyparty': {
        'name': 'Copyparty',
        'launchd': 'com.noc.copyparty',
        'port': 8081,
        'log_paths': ['~/copyparty.log', '~/logs/copyparty.log']
    },
    'nzbhydra2': {
        'name': 'NZBHydra2',
        'launchd': 'com.noc.nzbhydra2',
        'port': 5076,
        'log_paths': ['~/nzbhydra2/logs/nzbhydra2.log', '~/nzbhydra2/config/logs/nzbhydra2.log']
    },
    'nzbget': {
        'name': 'NZBGet',
        'launchd': 'homebrew.mxcl.nzbget',
        'port': 6789,
        'log_paths': ['~/nzbget/config/nzbget.log']
    },
    'maloja': {
        'name': 'Maloja',
        'launchd': 'com.maloja.service',
        'port': 42010,
        'log_paths': ['~/.local/share/maloja/logs/sqldb.log', '~/.local/share/maloja/logs/dbcache.log', '~/maloja.log']
    },
    'multi-scrobbler': {
        'name': 'Multi-Scrobbler',
        'launchd': 'com.multiscrobbler.service',
        'port': 9078,
        'log_paths': ['~/multi-scrobbler.log', '~/multi-scrobbler.error.log']
    },
    'uptime-kuma': {
        'name': 'Uptime Kuma',
        'launchd': 'pm2:uptime-kuma',  # Special marker for PM2
        'port': 3001,
        'log_paths': ['~/.pm2/logs/uptime-kuma-out.log', '~/.pm2/logs/uptime-kuma-error.log']
    }
}

def check_port_listening(port):
    """Check if a port is listening using socket"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def get_service_log(service_key):
    service = SERVICES.get(service_key, {})
    log_paths = service.get('log_paths', [])
    
    for log_path in log_paths:
        expanded_path = os.path.expanduser(log_path)
        # Handle glob patterns for Emby logs
        if '*' in expanded_path:
            files = glob.glob(expanded_path)
            if files:
                # Get the most recent file
                newest_file = max(files, key=os.path.getmtime)
                try:
                    result = subprocess.run(['tail', '-n', '100', newest_file], 
                                          capture_output=True, text=True)
                    if result.stdout:
                        return result.stdout
                except:
                    continue
        elif os.path.exists(expanded_path):
            try:
                result = subprocess.run(['tail', '-n', '100', expanded_path], 
                                      capture_output=True, text=True)
                if result.stdout:
                    return result.stdout
            except:
                continue
    return "No logs found"

@app.route('/')
def index():
    services_list = []
    for key, service in SERVICES.items():
        is_online = check_port_listening(service['port'])
            
        services_list.append({
            'name': service['name'],
            'port': service['port'],
            'status': 'online' if is_online else 'offline',
            'url': f"http://noc-local:{service['port']}"
        })
    return render_template('template.html', services=services_list)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.svg', mimetype='image/svg+xml')

@app.route('/api/status')
def get_status():
    status = {}
    for key, service in SERVICES.items():
        status[key] = check_port_listening(service['port'])
    return jsonify(status)

@app.route('/api/service/<action>', methods=['POST'])
def control_service(action):
    data = request.get_json()
    service_key = data.get('service')
    
    # Find service by name
    service_key_lower = service_key.lower().replace(' ', '-')
    if service_key_lower not in SERVICES:
        return jsonify({'success': False, 'message': 'Unknown service'}), 400
    
    service = SERVICES[service_key_lower]
    launchd_name = service['launchd']
    
    try:
        # Special case: disabled services (like Emby)
        if launchd_name == 'disabled':
            if action == 'logs':
                logs = get_service_log(service_key_lower)
                return jsonify({'success': True, 'logs': logs})
            else:
                return jsonify({'success': False, 'message': f'{service["name"]} control is disabled (managed via Login Items)'})
        # Special handling for PM2 services
        elif launchd_name.startswith('pm2:'):
            pm2_name = launchd_name.replace('pm2:', '')
            if action == 'start':
                subprocess.run(['pm2', 'start', pm2_name], 
                             check=True, capture_output=True, text=True)
            elif action == 'stop':
                subprocess.run(['pm2', 'stop', pm2_name], 
                             check=True, capture_output=True, text=True)
            elif action == 'restart':
                subprocess.run(['pm2', 'restart', pm2_name], 
                             check=True, capture_output=True, text=True)
            elif action == 'logs':
                logs = get_service_log(service_key_lower)
                return jsonify({'success': True, 'logs': logs})
        # Regular launchd services
        else:
            if action == 'start':
                if 'homebrew' in launchd_name:
                    subprocess.run(['brew', 'services', 'start', launchd_name.replace('homebrew.mxcl.', '')], 
                                 check=True, capture_output=True, text=True)
                else:
                    plist_path = f'/Users/noc/Library/LaunchAgents/{launchd_name}.plist'
                    subprocess.run(['launchctl', 'load', plist_path], 
                                 check=True, capture_output=True, text=True)
            elif action == 'stop':
                if 'homebrew' in launchd_name:
                    subprocess.run(['brew', 'services', 'stop', launchd_name.replace('homebrew.mxcl.', '')], 
                                 check=True, capture_output=True, text=True)
                else:
                    plist_path = f'/Users/noc/Library/LaunchAgents/{launchd_name}.plist'
                    subprocess.run(['launchctl', 'unload', plist_path], 
                                 check=True, capture_output=True, text=True)
            elif action == 'restart':
                if 'homebrew' in launchd_name:
                    subprocess.run(['brew', 'services', 'restart', launchd_name.replace('homebrew.mxcl.', '')], 
                                 check=True, capture_output=True, text=True)
                else:
                    plist_path = f'/Users/noc/Library/LaunchAgents/{launchd_name}.plist'
                    # Try unload first, ignore errors if already unloaded
                    subprocess.run(['launchctl', 'unload', plist_path], 
                                 capture_output=True, text=True)
                    # Then load
                    subprocess.run(['launchctl', 'load', plist_path], 
                                 check=True, capture_output=True, text=True)
            elif action == 'logs':
                logs = get_service_log(service_key_lower)
                return jsonify({'success': True, 'logs': logs})
            else:
                return jsonify({'success': False, 'message': 'Invalid action'}), 400
        
        # Wait a moment for service to change state
        import time
        time.sleep(0.5)  # Reduced from 1 second
        
        return jsonify({'success': True})
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        return jsonify({'success': False, 'message': f'Command failed: {error_msg}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
