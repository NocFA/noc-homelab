from flask import Flask, render_template, jsonify, request, send_from_directory
import subprocess
import socket
import os
import glob
import requests
import time
import json

app = Flask(__name__, template_folder='.')

# Cache for public IP
_public_ip_cache = {'ip': None, 'timestamp': 0}
_cache_duration = 300  # 5 minutes

SERVICES = {
    'copyparty': {
        'name': 'Copyparty',
        'launchd': 'com.noc.copyparty',
        'port': 8081,
        'log_paths': ['~/Library/Logs/noc-homelab/copyparty.log', '~/Library/Logs/noc-homelab/copyparty.error.log']
    },
    'maloja': {
        'name': 'Maloja',
        'launchd': 'com.maloja.service',
        'port': 42010,
        'log_paths': ['~/Library/Logs/noc-homelab/maloja.log', '~/Library/Logs/noc-homelab/maloja.error.log', '~/.local/share/maloja/logs/sqldb.log']
    },
    'multi-scrobbler': {
        'name': 'Multi-Scrobbler',
        'launchd': 'com.multiscrobbler.service',
        'port': 9078,
        'log_paths': ['~/Library/Logs/noc-homelab/multi-scrobbler.log', '~/Library/Logs/noc-homelab/multi-scrobbler.error.log']
    },
    'uptime-kuma': {
        'name': 'Uptime Kuma',
        'launchd': 'pm2:uptime-kuma',  # Special marker for PM2
        'port': 3001,
        'log_paths': ['~/.pm2/logs/uptime-kuma-out.log', '~/.pm2/logs/uptime-kuma-error.log']
    },
    'tailscale': {
        'name': 'Tailscale',
        'launchd': 'tailscale',  # Special marker for Tailscale (managed via system)
        'port': None,  # No single port, uses dynamic ports
        'log_paths': ['/var/log/tailscaled.log', '~/Library/Logs/Tailscale/'],
        'webclient_port': 5252
    },
    'teamspeak': {
        'name': 'TeamSpeak',
        'launchd': 'com.noc.teamspeak',
        'port': 9987,  # Voice port (UDP, but we'll check TCP port 10011 for status)
        'status_port': 10011,  # ServerQuery port for status checking
        'log_paths': ['/Users/noc/teamspeak3-server_mac/logs/*_1.log', '~/Library/Logs/noc-homelab/teamspeak.log'],
        'web_ports': [30033, 10080],  # File transfer and WebQuery
        'use_wan_ip': True  # Dynamically fetch WAN IP
    },
    'ts3audiobot': {
        'name': 'TS3AudioBot',
        'launchd': 'docker:ts3audiobot',
        'port': 58913,
        'compose_dir': '/Users/noc/noc-homelab/services/ts3audiobot',
        'log_paths': ['/Users/noc/noc-homelab/services/ts3audiobot/data/logs/*.log'],
        'description': 'TeamSpeak Music Bot'
    },
    'nextcloud': {
        'name': 'Nextcloud',
        'launchd': 'docker:nextcloud',
        'port': 9080,
        'compose_dir': '/Users/noc/noc-homelab/services/nextcloud',
        'log_paths': ['/Users/noc/noc-homelab/services/nextcloud/data/nextcloud.log'],
        'description': 'Cloud Storage & Collaboration'
    },
    'voiceseq': {
        'name': 'VoiceSeq',
        'launchd': 'com.noc.voiceseq',
        'port': 61998,
        'log_paths': ['~/Library/Logs/noc-homelab/voiceseq.log', '~/Library/Logs/noc-homelab/voiceseq.error.log']
    },
    'syncthing': {
        'name': 'Syncthing',
        'launchd': 'homebrew.mxcl.syncthing',
        'port': 8384,
        'log_paths': ['~/Library/Application Support/Syncthing/syncthing.log'],
        'description': 'File Synchronization'
    }
}

def get_public_ip():
    """Get public IP address with caching"""
    global _public_ip_cache

    current_time = time.time()

    # Return cached IP if still valid
    if _public_ip_cache['ip'] and (current_time - _public_ip_cache['timestamp']) < _cache_duration:
        return _public_ip_cache['ip']

    # Fetch new public IP
    try:
        response = requests.get('https://api.ipify.org', timeout=3)
        if response.status_code == 200:
            public_ip = response.text.strip()
            _public_ip_cache['ip'] = public_ip
            _public_ip_cache['timestamp'] = current_time
            return public_ip
    except:
        pass

    # Fallback to cached IP even if expired, or None
    return _public_ip_cache['ip']

def check_port_listening(port):
    """Check if a port is listening using socket"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def check_launchd_service_running(launchd_name):
    """Check if a launchd service is running via launchctl (port-independent)"""
    try:
        result = subprocess.run(['launchctl', 'list', launchd_name],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Service is loaded - check if PID is present in the output
            # Output format is a plist dict with "PID" = <number>; if running
            if '"PID"' in result.stdout:
                return True
        return False
    except:
        return False

def check_service_running(service_key, service):
    """Check if a service is running using the best available method"""
    launchd_name = service.get('launchd', '')

    # PM2 services
    if launchd_name.startswith('pm2:'):
        pm2_name = launchd_name.replace('pm2:', '')
        try:
            result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                pm2_list = json.loads(result.stdout)
                for proc in pm2_list:
                    if proc.get('name') == pm2_name and proc.get('pm2_env', {}).get('status') == 'online':
                        return True
        except:
            pass
        return False

    # Docker services
    if launchd_name.startswith('docker:'):
        container_name = launchd_name.replace('docker:', '')
        try:
            result = subprocess.run(['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Names}}'],
                                  capture_output=True, text=True, timeout=5)
            return container_name in result.stdout
        except:
            pass
        return check_port_listening(service.get('port'))

    # OrbStack VMs
    if launchd_name.startswith('orbstack:'):
        return check_port_listening(service.get('port'))

    # Regular launchd services - check via launchctl first, fallback to port
    if launchd_name and not launchd_name.startswith(('pm2:', 'docker:', 'orbstack:', 'tailscale', 'disabled')):
        if check_launchd_service_running(launchd_name):
            return True
        # Also check homebrew services
        if 'homebrew' in launchd_name:
            try:
                result = subprocess.run(['brew', 'services', 'list'], capture_output=True, text=True, timeout=5)
                service_name = launchd_name.replace('homebrew.mxcl.', '')
                for line in result.stdout.split('\n'):
                    if service_name in line and 'started' in line:
                        return True
            except:
                pass

    # Fallback to port check
    port = service.get('port')
    if port:
        return check_port_listening(port)
    return False

def get_service_log(service_key):
    """Get merged logs from all log files, newest at bottom"""
    service = SERVICES.get(service_key, {})
    log_paths = service.get('log_paths', [])

    # Collect all log files
    log_files = []
    for log_path in log_paths:
        expanded_path = os.path.expanduser(log_path)
        if '*' in expanded_path:
            log_files.extend(glob.glob(expanded_path))
        elif os.path.exists(expanded_path):
            log_files.append(expanded_path)

    if not log_files:
        return "No logs found"

    # Sort files by modification time (oldest first, so newest content is at bottom)
    log_files.sort(key=lambda f: os.path.getmtime(f))

    # Read last N lines from each file, concatenate
    all_lines = []
    lines_per_file = 250

    for log_file in log_files:
        try:
            result = subprocess.run(['tail', '-n', str(lines_per_file), log_file],
                                  capture_output=True, text=True)
            if result.stdout.strip():
                all_lines.append(result.stdout.strip())
        except:
            continue

    if not all_lines:
        return "No logs found"

    return '\n'.join(all_lines)

@app.route('/')
def index():
    services_list = []
    for key, service in SERVICES.items():
        # Special handling for Tailscale
        if key == 'tailscale':
            # Check if Tailscale is running by checking for the process
            import subprocess as sp
            try:
                result = sp.run(['pgrep', '-f', 'Tailscale.app'], capture_output=True)
                is_online = result.returncode == 0

                # Get webclient URL if available
                ts_result = sp.run(['/opt/homebrew/bin/python3', '/Users/noc/noc-homelab/scripts/tailscale_manager.py', 'summary'],
                                  capture_output=True, text=True)
                if ts_result.returncode == 0:
                    import json
                    ts_data = json.loads(ts_result.stdout)
                    webclient_url = ts_data.get('webclient_url', 'http://noc-local:5252')
                else:
                    webclient_url = 'http://noc-local:5252'
            except:
                is_online = False
                webclient_url = 'http://noc-local:5252'

            services_list.append({
                'name': service['name'],
                'port': '5252 (WebClient)',
                'status': 'online' if is_online else 'offline',
                'url': webclient_url,
                'description': 'VPN & Mesh Network'
            })
        # Special handling for TeamSpeak
        elif key == 'teamspeak':
            # Check ServerQuery port for status
            status_port = service.get('status_port', service['port'])
            is_online = check_port_listening(status_port)

            # Dynamically get WAN IP if configured
            if service.get('use_wan_ip'):
                wan_ip = get_public_ip()
                server_address = f"{wan_ip}:{service['port']}" if wan_ip else f"noc-local:{service['port']}"
            else:
                server_address = f"noc-local:{service['port']}"

            services_list.append({
                'name': service['name'],
                'port': f"{service['port']} (Voice)",
                'status': 'online' if is_online else 'offline',
                'url': '/teamspeak',  # Link to admin dashboard
                'description': 'Voice Chat Server'
            })
        # Special handling for OrbStack services (like Coolify)
        elif service.get('launchd', '').startswith('orbstack:'):
            # Port forwarding enabled - check localhost
            is_online = check_port_listening(service['port'])
            services_list.append({
                'name': service['name'],
                'port': service['port'],
                'status': 'online' if is_online else 'offline',
                'url': f"http://noc-local:{service['port']}",
                'description': service.get('description', 'OrbStack VM Service')
            })
        # Special handling for Docker Compose services
        elif service.get('launchd', '').startswith('docker:'):
            is_online = check_port_listening(service['port'])
            service_dict = {
                'name': service['name'],
                'port': service['port'],
                'status': 'online' if is_online else 'offline',
                'url': f"http://noc-local:{service['port']}",
                'description': 'Docker Service'
            }
            services_list.append(service_dict)
        else:
            is_online = check_service_running(key, service)

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

@app.route('/teamspeak')
def teamspeak_admin():
    return render_template('teamspeak.html')

@app.route('/api/status')
def get_status():
    status = {}
    for key, service in SERVICES.items():
        if key == 'tailscale':
            # Check if Tailscale is running
            try:
                result = subprocess.run(['pgrep', '-f', 'Tailscale.app'], capture_output=True)
                status[key] = result.returncode == 0
            except:
                status[key] = False
        elif key == 'teamspeak':
            # Check ServerQuery port for TeamSpeak status
            status_port = service.get('status_port', service['port'])
            status[key] = check_port_listening(status_port)
        else:
            # Use launchctl-based check for all other services
            status[key] = check_service_running(key, service)
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
        # Special case: disabled services
        if launchd_name == 'disabled':
            if action == 'logs':
                logs = get_service_log(service_key_lower)
                return jsonify({'success': True, 'logs': logs})
            else:
                return jsonify({'success': False, 'message': f'{service["name"]} control is disabled (managed via Login Items)'})
        # Special handling for Tailscale
        elif launchd_name == 'tailscale':
            if action == 'logs':
                # Get Tailscale logs using tailscale bugreport or system logs
                try:
                    result = subprocess.run(['log', 'show', '--predicate', 'process == "Tailscale"', '--last', '5m', '--style', 'syslog'],
                                          capture_output=True, text=True, timeout=10)
                    logs = result.stdout if result.stdout else "No recent Tailscale logs found"
                    # Also add Tailscale status
                    status_result = subprocess.run(['/opt/homebrew/bin/python3', '/Users/noc/noc-homelab/scripts/tailscale_manager.py', 'summary'],
                                                  capture_output=True, text=True)
                    if status_result.returncode == 0:
                        logs = f"=== Tailscale Status ===\n{status_result.stdout}\n\n=== System Logs ===\n{logs}"
                except Exception as e:
                    logs = f"Error getting Tailscale logs: {str(e)}"
                return jsonify({'success': True, 'logs': logs})
            elif action == 'start':
                # Tailscale is managed by the system, just open the app
                subprocess.run(['open', '-a', 'Tailscale'], check=True, capture_output=True, text=True)
                return jsonify({'success': True, 'message': 'Tailscale app launched'})
            elif action == 'stop':
                # Can't really stop Tailscale easily, but we can disconnect
                return jsonify({'success': False, 'message': 'Tailscale is a system service and should not be stopped. Use the Tailscale app menu to disconnect if needed.'})
            elif action == 'restart':
                # Restart by quitting and reopening
                subprocess.run(['pkill', '-9', 'Tailscale'], capture_output=True)
                import time
                time.sleep(1)
                subprocess.run(['open', '-a', 'Tailscale'], check=True, capture_output=True, text=True)
                return jsonify({'success': True, 'message': 'Tailscale restarted'})
            else:
                return jsonify({'success': False, 'message': 'Invalid action'}), 400
        # Special handling for OrbStack VMs
        elif launchd_name.startswith('orbstack:'):
            vm_name = service.get('vm_name', launchd_name.replace('orbstack:', ''))
            if action == 'start':
                subprocess.run(['orb', 'start', vm_name],
                             check=True, capture_output=True, text=True)
                return jsonify({'success': True, 'message': f'OrbStack VM {vm_name} started'})
            elif action == 'stop':
                subprocess.run(['orb', 'stop', vm_name],
                             check=True, capture_output=True, text=True)
                return jsonify({'success': True, 'message': f'OrbStack VM {vm_name} stopped'})
            elif action == 'restart':
                subprocess.run(['orb', 'stop', vm_name], capture_output=True, text=True)
                import time
                time.sleep(2)
                subprocess.run(['orb', 'start', vm_name],
                             check=True, capture_output=True, text=True)
                return jsonify({'success': True, 'message': f'OrbStack VM {vm_name} restarted'})
            elif action == 'logs':
                # Get Coolify container logs from inside the VM
                try:
                    result = subprocess.run(['orb', '-m', vm_name, 'sudo', 'docker', 'logs', '--tail', '100', 'coolify'],
                                          capture_output=True, text=True, timeout=15)
                    logs = result.stdout if result.stdout else result.stderr
                    if not logs:
                        logs = "No logs available"
                except Exception as e:
                    logs = f"Error getting logs: {str(e)}"
                return jsonify({'success': True, 'logs': logs})
        # Special handling for Docker Compose services
        elif launchd_name.startswith('docker:'):
            container_name = launchd_name.replace('docker:', '')
            compose_dir = service.get('compose_dir', f'/Users/noc/noc-homelab/services/{container_name}')
            if action == 'start':
                subprocess.run(['docker', 'compose', 'up', '-d'],
                             cwd=compose_dir, check=True, capture_output=True, text=True)
                return jsonify({'success': True, 'message': f'{service["name"]} started'})
            elif action == 'stop':
                subprocess.run(['docker', 'compose', 'down'],
                             cwd=compose_dir, check=True, capture_output=True, text=True)
                return jsonify({'success': True, 'message': f'{service["name"]} stopped'})
            elif action == 'restart':
                subprocess.run(['docker', 'compose', 'restart'],
                             cwd=compose_dir, check=True, capture_output=True, text=True)
                return jsonify({'success': True, 'message': f'{service["name"]} restarted'})
            elif action == 'logs':
                try:
                    result = subprocess.run(['docker', 'logs', '--tail', '100', container_name],
                                          capture_output=True, text=True, timeout=15)
                    logs = result.stdout if result.stdout else result.stderr
                    if not logs:
                        logs = get_service_log(service_key_lower)
                except Exception as e:
                    logs = f"Error getting logs: {str(e)}"
                return jsonify({'success': True, 'logs': logs})
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

@app.route('/api/teamspeak/status')
def teamspeak_status():
    """Get TeamSpeak server status and client list"""
    try:
        # Run teamspeak_manager.py to get status
        result = subprocess.run(['/opt/homebrew/bin/python3', '/Users/noc/noc-homelab/scripts/teamspeak_manager.py', 'status'],
                              capture_output=True, text=True, timeout=20)

        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)

            # Add server address
            wan_ip = get_public_ip()
            ts_service = SERVICES.get('teamspeak', {})
            port = ts_service.get('port', 9987)
            data['server_address'] = f"{wan_ip}:{port}" if wan_ip else f"noc-local:{port}"
            data['uptime_hours'] = round(data.get('uptime', 0) / 3600, 1)

            return jsonify(data)
        else:
            return jsonify({'error': 'Failed to get server status'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teamspeak/kick', methods=['POST'])
def teamspeak_kick():
    """Kick a client from the server"""
    try:
        data = request.get_json()
        clid = data.get('clid')
        reason = data.get('reason', 'Kicked by admin')

        if not clid:
            return jsonify({'success': False, 'error': 'Missing client ID'}), 400

        # Use teamspeak_manager.py kick command
        result = subprocess.run(['/opt/homebrew/bin/python3', '/Users/noc/noc-homelab/scripts/teamspeak_manager.py', 'kick', str(clid), reason],
                              capture_output=True, text=True, timeout=20)

        if result.returncode == 0:
            import json
            response = json.loads(result.stdout)
            return jsonify(response)
        else:
            return jsonify({'success': False, 'error': 'Failed to kick client'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/teamspeak/ban', methods=['POST'])
def teamspeak_ban():
    """Ban a client from the server"""
    try:
        data = request.get_json()
        clid = data.get('clid')
        reason = data.get('reason', 'Banned by admin')
        duration = data.get('duration', 0)  # 0 = permanent

        if not clid:
            return jsonify({'success': False, 'error': 'Missing client ID'}), 400

        # Use teamspeak_manager.py ban command
        result = subprocess.run(['/opt/homebrew/bin/python3', '/Users/noc/noc-homelab/scripts/teamspeak_manager.py', 'ban', str(clid), str(duration), reason],
                              capture_output=True, text=True, timeout=20)

        if result.returncode == 0:
            import json
            response = json.loads(result.stdout)
            return jsonify(response)
        else:
            return jsonify({'success': False, 'error': 'Failed to ban client'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/teamspeak/bans')
def teamspeak_bans():
    """Get list of all bans"""
    try:
        result = subprocess.run(['/opt/homebrew/bin/python3', '/Users/noc/noc-homelab/scripts/teamspeak_manager.py', 'banlist'],
                              capture_output=True, text=True, timeout=20)

        if result.returncode == 0:
            import json
            bans = json.loads(result.stdout)
            return jsonify({'bans': bans})
        else:
            return jsonify({'error': 'Failed to get ban list'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teamspeak/unban', methods=['POST'])
def teamspeak_unban():
    """Remove a ban"""
    try:
        data = request.get_json()
        banid = data.get('banid')

        if not banid:
            return jsonify({'success': False, 'error': 'Missing ban ID'}), 400

        result = subprocess.run(['/opt/homebrew/bin/python3', '/Users/noc/noc-homelab/scripts/teamspeak_manager.py', 'unban', str(banid)],
                              capture_output=True, text=True, timeout=20)

        if result.returncode == 0:
            import json
            response = json.loads(result.stdout)
            return jsonify(response)
        else:
            return jsonify({'success': False, 'error': 'Failed to remove ban'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/teamspeak/channels')
def teamspeak_channels():
    """Get list of channels"""
    try:
        result = subprocess.run(['/opt/homebrew/bin/python3', '/Users/noc/noc-homelab/scripts/teamspeak_manager.py', 'channels'],
                              capture_output=True, text=True, timeout=20)

        if result.returncode == 0:
            import json
            channels = json.loads(result.stdout)
            return jsonify({'channels': channels})
        else:
            return jsonify({'error': 'Failed to get channels'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teamspeak/channel/create', methods=['POST'])
def teamspeak_create_channel():
    """Create a new channel"""
    try:
        data = request.get_json()
        name = data.get('name')
        parent_cid = data.get('parent_cid', 0)

        if not name:
            return jsonify({'success': False, 'error': 'Missing channel name'}), 400

        result = subprocess.run(['/opt/homebrew/bin/python3', '/Users/noc/noc-homelab/scripts/teamspeak_manager.py', 'createchannel', name, str(parent_cid)],
                              capture_output=True, text=True, timeout=20)

        if result.returncode == 0:
            import json
            response = json.loads(result.stdout)
            return jsonify(response)
        else:
            return jsonify({'success': False, 'error': 'Failed to create channel'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/teamspeak/channel/delete', methods=['POST'])
def teamspeak_delete_channel():
    """Delete a channel"""
    try:
        data = request.get_json()
        cid = data.get('cid')

        if not cid:
            return jsonify({'success': False, 'error': 'Missing channel ID'}), 400

        result = subprocess.run(['/opt/homebrew/bin/python3', '/Users/noc/noc-homelab/scripts/teamspeak_manager.py', 'deletechannel', str(cid)],
                              capture_output=True, text=True, timeout=20)

        if result.returncode == 0:
            import json
            response = json.loads(result.stdout)
            return jsonify(response)
        else:
            return jsonify({'success': False, 'error': 'Failed to delete channel'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/teamspeak/channel/rename', methods=['POST'])
def teamspeak_rename_channel():
    """Rename a channel"""
    try:
        data = request.get_json()
        cid = data.get('cid')
        new_name = data.get('name')

        if not cid or not new_name:
            return jsonify({'success': False, 'error': 'Missing channel ID or name'}), 400

        result = subprocess.run(['/opt/homebrew/bin/python3', '/Users/noc/noc-homelab/scripts/teamspeak_manager.py', 'renamechannel', str(cid), new_name],
                              capture_output=True, text=True, timeout=20)

        if result.returncode == 0:
            import json
            response = json.loads(result.stdout)
            return jsonify(response)
        else:
            return jsonify({'success': False, 'error': 'Failed to rename channel'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
