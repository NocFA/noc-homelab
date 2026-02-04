from flask import Flask, render_template, jsonify, request, send_from_directory
import subprocess
import socket
import os
import glob
import requests
import time
import json
import re
import shutil

app = Flask(__name__, template_folder='.')

# Cache for public IP
_public_ip_cache = {'ip': None, 'timestamp': 0}
_cache_duration = 300  # 5 minutes

# Batch cache for remote machine data (processes + uptime in one SSH call)
_remote_batch_cache = {}
_remote_batch_ttl = 15  # seconds

# Reachability cache
_reachability_cache = {}
_reachability_ttl = 15  # seconds

# Full API status cache (short TTL to absorb rapid polling)
_api_status_cache = {'data': None, 'timestamp': 0}
_api_status_ttl = 5  # seconds

# Validation functions for settings editor
def validate_port(port):
    """Validate port number (1-65535 or None)"""
    if port is None:
        return None
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise ValueError(f"Invalid port: {port} (must be 1-65535)")
    return port

def validate_service_id(service_id):
    """Validate service ID (lowercase alphanumeric + hyphens only)"""
    if not re.match(r'^[a-z0-9-]+$', service_id):
        raise ValueError(f"Invalid service ID: {service_id} (use lowercase alphanumeric + hyphens only)")
    if len(service_id) > 50:
        raise ValueError(f"Service ID too long: {service_id} (max 50 chars)")
    return service_id

def validate_path(path):
    """Validate file path for security"""
    dangerous = [';', '|', '`', '$(', '&&', '||']
    if any(c in path for c in dangerous):
        raise ValueError(f"Invalid characters in path: {path}")
    # Allow absolute paths, tilde paths, or relative paths
    # (glob patterns with * are OK)
    return path

def save_config_atomic(config_path, data):
    """Save config file atomically with backup"""
    backup = config_path + '.backup'
    if os.path.exists(config_path):
        shutil.copy2(config_path, backup)

    temp = config_path + '.tmp'
    try:
        with open(temp, 'w') as f:
            json.dump(data, f, indent=2)

        # Validate JSON is readable
        with open(temp, 'r') as f:
            json.load(f)

        # Atomic rename
        os.rename(temp, config_path)
        return {'success': True}
    except Exception as e:
        # Restore from backup on error
        if os.path.exists(backup):
            shutil.copy2(backup, config_path)
        if os.path.exists(temp):
            os.remove(temp)
        return {'success': False, 'error': str(e)}

def load_services_config():
    """Load services configuration from services.json"""
    config_path = os.path.join(os.path.dirname(__file__), 'services.json')
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
            return data.get('services', {})
    except FileNotFoundError:
        # File doesn't exist yet - will be created by settings UI
        app.logger.warning("services.json not found, using hardcoded SERVICES")
        return None
    except Exception as e:
        app.logger.error(f"Failed to load services.json: {e}")
        return None

def load_machines_config():
    """Load machines configuration from machines.json"""
    config_path = os.path.join(os.path.dirname(__file__), 'machines.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f).get('machines', [])
    except Exception:
        return []

MACHINES = load_machines_config()

def check_remote_port(hostname, port, timeout=0.5):
    """Check if a port is listening on a remote host (LAN/Tailscale)"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((hostname, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def ssh_command(hostname, ssh_user, command, timeout=10):
    """Execute a command on a remote machine via SSH"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=3', '-o', 'StrictHostKeyChecking=no',
             f'{ssh_user}@{hostname}', command],
            capture_output=True, text=True, timeout=timeout
        )
        return result
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None

def _refresh_remote_batch(machine):
    """Single SSH call to get all process names + uptime from a remote machine"""
    machine_id = machine['id']
    now = time.time()

    cached = _remote_batch_cache.get(machine_id)
    if cached and (now - cached['timestamp']) < _remote_batch_ttl:
        return cached['data']

    hostname = machine['hostname']
    ssh_user = machine.get('ssh_user', 'noc')
    data = {'processes': set(), 'uptime_secs': None}

    if machine.get('platform') == 'windows':
        # One SSH call: comma-separated process names on line 1, uptime seconds on line 2
        result = ssh_command(hostname, ssh_user,
            'powershell -Command "((Get-Process -EA SilentlyContinue).Name | Sort -Unique) -join [char]44; [int]((Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime).TotalSeconds"',
            timeout=8)
        if result and result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            if len(lines) >= 1:
                data['processes'] = set(p.strip().lower() for p in lines[0].split(',') if p.strip())
            if len(lines) >= 2:
                try:
                    data['uptime_secs'] = int(lines[1].strip())
                except ValueError:
                    pass

    _remote_batch_cache[machine_id] = {'data': data, 'timestamp': now}
    return data

def get_remote_machine_status(machine):
    """Get status of all services on a remote machine using port checks + cached batch data"""
    hostname = machine['hostname']
    services = machine.get('services', {})
    batch = _refresh_remote_batch(machine)
    results = {}

    for svc_id, svc in services.items():
        port = svc.get('port')
        process_name = svc.get('process_name')

        if port:
            # Port-based check (fast, no SSH needed)
            results[svc_id] = check_remote_port(hostname, port)
        elif process_name:
            # Use cached process list from batch SSH call
            results[svc_id] = process_name.lower() in batch['processes']
        else:
            results[svc_id] = False

    return results

def control_remote_service(machine, svc_id, action):
    """Start/stop/restart a service on a remote machine via SSH"""
    hostname = machine['hostname']
    ssh_user = machine.get('ssh_user', 'noc')
    svc = machine.get('services', {}).get(svc_id)
    if not svc:
        return {'success': False, 'message': 'Unknown service'}

    manager = svc.get('manager', 'process')
    service_name = svc.get('service_name', '')
    task_name = svc.get('task_name', '')
    process_name = svc.get('process_name', '')

    cmd = None

    if manager == 'windows-service':
        if action == 'start':
            cmd = f'sc start {service_name}'
        elif action == 'stop':
            cmd = f'sc stop {service_name}'
        elif action == 'restart':
            cmd = f'sc stop {service_name} & timeout /t 3 /nobreak >nul & sc start {service_name}'

    elif manager == 'scheduled-task':
        # Check if this is a service-backed task (has a Windows service to stop)
        svc_name = svc.get('service_name', '')
        if action == 'start':
            cmd = f'schtasks /run /tn "{task_name}"'
        elif action == 'stop':
            if svc_name:
                cmd = f'net stop {svc_name}'
            elif process_name:
                cmd = f'taskkill /IM {process_name}.exe /F'
            else:
                cmd = f'schtasks /end /tn "{task_name}"'
        elif action == 'restart':
            if svc_name:
                cmd = f'net stop {svc_name} & ping -n 3 127.0.0.1 >nul & schtasks /run /tn "{task_name}"'
            elif process_name:
                cmd = f'taskkill /IM {process_name}.exe /F & ping -n 3 127.0.0.1 >nul & schtasks /run /tn "{task_name}"'

    elif manager == 'process':
        if action == 'start':
            start_cmd = svc.get('start_cmd')
            if start_cmd:
                cmd = f'powershell -Command "{start_cmd}"'
        elif action == 'stop':
            stop_cmd = svc.get('stop_cmd')
            if stop_cmd:
                cmd = f'powershell -Command "{stop_cmd}"'
            elif process_name:
                cmd = f'taskkill /IM {process_name}.exe /F'
        elif action == 'restart':
            stop_cmd = svc.get('stop_cmd')
            start_cmd = svc.get('start_cmd')
            if not stop_cmd and process_name:
                stop_cmd = f'Stop-Process -Name {process_name} -Force -EA SilentlyContinue'
            if stop_cmd and start_cmd:
                cmd = f'powershell -Command "{stop_cmd}; Start-Sleep -Seconds 2; {start_cmd}"'

    if not cmd:
        return {'success': False, 'message': f'No {action} command configured for {svc["name"]}'}

    result = ssh_command(hostname, ssh_user, cmd, timeout=15)
    if result is None:
        return {'success': False, 'message': 'SSH connection timed out'}

    # Invalidate caches so next status check is fresh
    _remote_batch_cache.pop(machine['id'], None)
    _api_status_cache['data'] = None

    if result.returncode == 0:
        return {'success': True, 'message': f'{svc["name"]} {action} successful'}
    else:
        error = result.stderr.strip() or result.stdout.strip() or 'Unknown error'
        return {'success': False, 'message': f'{svc["name"]} {action} failed: {error}'}

def is_remote_machine_reachable(hostname, timeout=2):
    """Quick check if a remote machine is reachable (cached)"""
    now = time.time()
    cached = _reachability_cache.get(hostname)
    if cached and (now - cached['timestamp']) < _reachability_ttl:
        return cached['reachable']

    reachable = check_remote_port(hostname, 22, timeout)
    _reachability_cache[hostname] = {'reachable': reachable, 'timestamp': now}
    return reachable

def format_uptime(uptime_secs):
    """Format uptime seconds into a human-readable string"""
    days = uptime_secs // 86400
    hours = (uptime_secs % 86400) // 3600
    mins = (uptime_secs % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {mins}m"
    else:
        return f"{mins}m"

def get_system_uptime_secs():
    """Get local system uptime in seconds"""
    try:
        result = subprocess.run(['/usr/sbin/sysctl', '-n', 'kern.boottime'], capture_output=True, text=True)
        if result.returncode == 0:
            match = re.search(r'sec\s*=\s*(\d+)', result.stdout)
            if match:
                boot_time = int(match.group(1))
                return int(time.time()) - boot_time
    except Exception:
        pass
    return None

def get_system_uptime():
    """Get system uptime as a formatted string"""
    secs = get_system_uptime_secs()
    return format_uptime(secs) if secs is not None else "--"

def get_remote_uptime_secs(machine):
    """Get uptime in seconds from the batch cache (no extra SSH call)"""
    batch = _refresh_remote_batch(machine)
    return batch.get('uptime_secs')

# Load services from services.json or fall back to hardcoded config
_loaded_services = load_services_config()

SERVICES = _loaded_services if _loaded_services else {
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
    'gatus': {
        'name': 'Gatus',
        'launchd': 'docker:gatus',
        'port': 3001,
        'compose_dir': '/Users/noc/noc-homelab/services/gatus',
        'log_paths': ['~/Library/Logs/noc-homelab/gatus.log', '~/Library/Logs/noc-homelab/gatus.error.log'],
        'description': 'Status Page & Monitoring'
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
    },
    'beads-ui': {
        'name': 'Beads UI',
        'launchd': 'com.noc.beads-ui',
        'port': 3000,
        'log_paths': ['~/Library/Logs/noc-homelab/beads-ui.log', '~/Library/Logs/noc-homelab/beads-ui.error.log'],
        'description': 'Beads Issue Tracker Dashboard'
    }
}  # End of hardcoded fallback SERVICES

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
    port = service.get('port')
    
    # Special case for Tailscale as it doesn't use a standard port check
    if service_key == 'tailscale':
        try:
            # Check if Tailscale process is running
            result = subprocess.run(['pgrep', '-f', 'Tailscale.app'], capture_output=True)
            return result.returncode == 0
        except:
            return False

    is_process_running = False
    
    # 1. Check process status based on type
    if launchd_name.startswith('pm2:'):
        pm2_name = launchd_name.replace('pm2:', '')
        try:
            result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                pm2_list = json.loads(result.stdout)
                for proc in pm2_list:
                    if proc.get('name') == pm2_name and proc.get('pm2_env', {}).get('status') == 'online':
                        is_process_running = True
                        break
        except:
            pass
    elif launchd_name.startswith('docker:'):
        container_name = launchd_name.replace('docker:', '')
        try:
            result = subprocess.run(['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Names}}'],
                                  capture_output=True, text=True, timeout=5)
            is_process_running = container_name in result.stdout
        except:
            pass
    elif launchd_name.startswith('orbstack:'):
        # OrbStack status - we'll treat it as running if the VM is reachable or just fallback to port
        is_process_running = True
    elif launchd_name and not launchd_name.startswith('disabled'):
        if check_launchd_service_running(launchd_name):
            is_process_running = True
        elif 'homebrew' in launchd_name:
            try:
                result = subprocess.run(['brew', 'services', 'list'], capture_output=True, text=True, timeout=5)
                service_name = launchd_name.replace('homebrew.mxcl.', '')
                for line in result.stdout.split('\n'):
                    if service_name in line and 'started' in line:
                        is_process_running = True
                        break
            except:
                pass
    else:
        # If no process manager defined, assume we just check the port
        is_process_running = True

    # 2. Check port if defined
    if port:
        # Use status_port if defined (e.g. for TeamSpeak)
        check_port = service.get('status_port', port)
        is_port_listening = check_port_listening(check_port)
        
        # Service is online ONLY if process is running AND port is listening
        return is_process_running and is_port_listening
    
    # If no port defined, just return process status
    return is_process_running

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
        is_online = check_service_running(key, service)
        status_str = 'online' if is_online else 'offline'
        
        # Special handling for display metadata
        if key == 'tailscale':
            import subprocess as sp
            webclient_url = 'http://noc-local:5252'
            try:
                # Get webclient URL if available
                ts_result = sp.run(['/opt/homebrew/bin/python3', '/Users/noc/noc-homelab/scripts/tailscale_manager.py', 'summary'],
                                  capture_output=True, text=True)
                if ts_result.returncode == 0:
                    import json
                    ts_data = json.loads(ts_result.stdout)
                    webclient_url = ts_data.get('webclient_url', 'http://noc-local:5252')
            except:
                pass

            services_list.append({
                'name': service['name'],
                'port': '5252 (WebClient)',
                'status': status_str,
                'url': webclient_url,
                'description': 'VPN & Mesh Network',
                'remote': False
            })
        elif key == 'teamspeak':
            # Dynamically get WAN IP if configured
            if service.get('use_wan_ip'):
                wan_ip = get_public_ip()
                server_address = f"{wan_ip}:{service['port']}" if wan_ip else f"noc-local:{service['port']}"
            else:
                server_address = f"noc-local:{service['port']}"

            services_list.append({
                'name': service['name'],
                'port': f"{service['port']} (Voice)",
                'status': status_str,
                'url': '/teamspeak',
                'description': 'Voice Chat Server',
                'remote': False
            })
        else:
            port_display = service.get('port', '--')
            url = f"http://noc-local:{service['port']}" if service.get('port') else "#"
            
            services_list.append({
                'name': service['name'],
                'port': port_display,
                'status': status_str,
                'url': url,
                'description': service.get('description', ''),
                'remote': False
            })
            
    # Build machine groups for template
    local_uptime_secs = get_system_uptime_secs()
    local_uptime = format_uptime(local_uptime_secs) if local_uptime_secs else '--'
    uptime_values = [local_uptime_secs] if local_uptime_secs else []

    machine_groups = [
        {
            'id': 'noc-local',
            'name': 'noc-local',
            'platform': 'macOS',
            'reachable': True,
            'uptime': local_uptime,
            'services': services_list
        }
    ]

    # Add remote machines
    for machine in MACHINES:
        if machine.get('role') == 'agent':
            hostname = machine['hostname']
            reachable = is_remote_machine_reachable(hostname)
            remote_status = get_remote_machine_status(machine) if reachable else {}
            remote_services = []

            for svc_id, svc in machine.get('services', {}).items():
                is_online = remote_status.get(svc_id, False)
                remote_services.append({
                    'name': svc['name'],
                    'port': svc.get('port', '--'),
                    'status': 'online' if is_online else 'offline',
                    'url': svc.get('url', '#'),
                    'description': svc.get('description', ''),
                    'machine': machine['id'],
                    'remote': True
                })

            remote_uptime_secs = get_remote_uptime_secs(machine) if reachable else None
            remote_uptime = format_uptime(remote_uptime_secs) if remote_uptime_secs else '--'
            if remote_uptime_secs:
                uptime_values.append(remote_uptime_secs)

            machine_groups.append({
                'id': machine['id'],
                'name': machine.get('display_name', machine['id']),
                'platform': 'Windows' if machine.get('platform') == 'windows' else machine.get('platform', ''),
                'reachable': reachable,
                'uptime': remote_uptime,
                'services': remote_services
            })

    # Compute average uptime across all nodes
    if uptime_values:
        avg_secs = sum(uptime_values) // len(uptime_values)
        avg_uptime = format_uptime(avg_secs)
    else:
        avg_uptime = '--'

    return render_template('template.html',
                         services=services_list,
                         machine_groups=machine_groups,
                         uptime=avg_uptime)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.svg', mimetype='image/svg+xml')

@app.route('/teamspeak')
def teamspeak_admin():
    return render_template('teamspeak.html')

def _build_status():
    """Build full status dict (cached to absorb rapid polling)"""
    now = time.time()
    if _api_status_cache['data'] and (now - _api_status_cache['timestamp']) < _api_status_ttl:
        return _api_status_cache['data']

    status = {'noc-local': {}}
    for key, service in SERVICES.items():
        status['noc-local'][key] = check_service_running(key, service)

    # Local uptime
    local_uptime_secs = get_system_uptime_secs()
    status['noc-local']['_uptime'] = format_uptime(local_uptime_secs) if local_uptime_secs else '--'
    uptime_values = [local_uptime_secs] if local_uptime_secs else []

    # Include remote machine status
    for machine in MACHINES:
        if machine.get('role') == 'agent':
            machine_id = machine['id']
            reachable = is_remote_machine_reachable(machine['hostname'])
            if reachable:
                status[machine_id] = get_remote_machine_status(machine)
                remote_secs = get_remote_uptime_secs(machine)
                status[machine_id]['_uptime'] = format_uptime(remote_secs) if remote_secs else '--'
                if remote_secs:
                    uptime_values.append(remote_secs)
            else:
                status[machine_id] = {svc_id: False for svc_id in machine.get('services', {})}
                status[machine_id]['_uptime'] = '--'
            status[machine_id]['_reachable'] = reachable

    # Average uptime
    if uptime_values:
        avg_secs = sum(uptime_values) // len(uptime_values)
        status['_avg_uptime'] = format_uptime(avg_secs)
    else:
        status['_avg_uptime'] = '--'

    _api_status_cache['data'] = status
    _api_status_cache['timestamp'] = now
    return status

@app.route('/api/status')
def get_status():
    return jsonify(_build_status())

@app.route('/api/remote/service/<action>', methods=['POST'])
def control_remote_service_api(action):
    """Control a service on a remote machine via SSH"""
    data = request.get_json()
    machine_id = data.get('machine')
    service_name = data.get('service')

    # Find the machine
    machine = None
    for m in MACHINES:
        if m['id'] == machine_id:
            machine = m
            break

    if not machine:
        return jsonify({'success': False, 'message': 'Unknown machine'}), 404

    # Find service by display name
    svc_id = None
    for sid, svc in machine.get('services', {}).items():
        if svc['name'] == service_name:
            svc_id = sid
            break

    if not svc_id:
        return jsonify({'success': False, 'message': 'Unknown service'}), 404

    result = control_remote_service(machine, svc_id, action)
    return jsonify(result)

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

# Settings Editor API Endpoints

@app.route('/settings')
def settings_page():
    """Settings editor page"""
    return render_template('settings.html')

@app.route('/api/settings/config', methods=['GET'])
def get_settings_config():
    """Return full configuration for settings editor"""
    return jsonify({
        'local_services': SERVICES,
        'machines': MACHINES,
        'service_types': ['launchd', 'docker', 'pm2', 'homebrew'],
        'manager_types': ['scheduled-task', 'windows-service', 'process']
    })

@app.route('/api/settings/save/local', methods=['POST'])
def save_local_services():
    """Save local services to services.json"""
    try:
        data = request.get_json()
        services = data.get('services', {})

        # Validate each service
        for svc_id, svc in services.items():
            validate_service_id(svc_id)
            validate_port(svc.get('port'))
            for path in svc.get('log_paths', []):
                validate_path(path)

        # Atomic save
        config_path = os.path.join(os.path.dirname(__file__), 'services.json')
        result = save_config_atomic(config_path, {'version': 1, 'services': services})

        if result['success']:
            return jsonify({'success': True, 'restart_required': True})
        return jsonify(result), 500
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error saving services.json: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings/save/remote', methods=['POST'])
def save_remote_machines():
    """Save machines.json"""
    try:
        data = request.get_json()
        machines = data.get('machines', [])

        # Validate
        for machine in machines:
            for svc in machine.get('services', {}).values():
                validate_port(svc.get('port'))

        config_path = os.path.join(os.path.dirname(__file__), 'machines.json')
        result = save_config_atomic(config_path, {'machines': machines})

        if result['success']:
            return jsonify({'success': True, 'restart_required': True})
        return jsonify(result), 500
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error saving machines.json: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings/restart-dashboard', methods=['POST'])
def restart_dashboard():
    """Exit to trigger LaunchAgent auto-restart"""
    app.logger.info("Dashboard restart requested via settings")

    def shutdown():
        time.sleep(0.5)
        os._exit(0)  # LaunchAgent will restart due to KeepAlive:true

    from threading import Thread
    Thread(target=shutdown).start()

    return jsonify({'success': True, 'message': 'Restarting...'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
