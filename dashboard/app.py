from flask import Flask, render_template, jsonify, request, send_from_directory
import subprocess
import socket
import os
import glob
import requests
import time
import json
import re
import sys
import shutil
import threading
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from alerts import AlertEngine

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

# Full API status cache (populated by background thread)
_api_status_cache = {'data': None, 'timestamp': 0}
_api_status_ttl = 5  # seconds

# Glances stats cache (longer TTL, refreshed in background)
_glances_cache = {}
_glances_ttl = 30  # seconds

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

def _detect_self_id():
    """Detect which machine this dashboard instance is running on."""
    import platform
    hostname = platform.node().split('.')[0].lower()
    # Common hostname patterns for each machine
    hostname_map = {
        'noc-local': ['noc-local', 'nocs-macbook-pro', 'nocs-mbp'],
        'noc-claw': ['noc-claw', 'mac-mini', 'noc-mac-mini'],
        'noc-tux': ['noc-tux'],
    }
    for machine_id, patterns in hostname_map.items():
        if hostname in patterns or any(p in hostname for p in patterns):
            return machine_id
    # Fallback: check platform
    if sys.platform == 'linux':
        return 'noc-tux'
    return 'noc-local'

def _manager_to_launchd_compat(manager, unit_name):
    """Generate backwards-compatible launchd field from manager + unit_name."""
    if manager == 'launchd':
        return unit_name or ''
    elif manager == 'docker':
        return f'docker:{unit_name}' if unit_name else 'docker:'
    elif manager == 'pm2':
        return f'pm2:{unit_name}' if unit_name else 'pm2:'
    elif manager == 'brew':
        return f'homebrew.mxcl.{unit_name}' if unit_name else ''
    elif manager == 'system-daemon':
        return f'system:{unit_name}' if unit_name else 'system:'
    elif manager == 'system-service':
        return f'system:{unit_name}' if unit_name else 'system:'
    elif manager == 'tailscale':
        return 'tailscale'
    elif manager == 'disabled':
        return 'disabled'
    elif manager in ('systemd', 'systemd-user'):
        return f'systemd:{unit_name}' if unit_name else ''
    return unit_name or ''

def load_machines_config():
    """Load machines configuration from machines.json"""
    config_path = os.path.join(os.path.dirname(__file__), 'machines.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f).get('machines', [])
    except Exception:
        return []

def load_services_config():
    """Load local services from machines.json (self machine) with fallback to services.json."""
    config_path = os.path.join(os.path.dirname(__file__), 'machines.json')
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
        machines = data.get('machines', [])
        self_id = _detect_self_id()
        for m in machines:
            if m['id'] == self_id:
                services = m.get('services', {})
                # Generate backwards-compatible launchd field
                for svc in services.values():
                    if 'launchd' not in svc:
                        manager = svc.get('manager', '')
                        unit_name = svc.get('unit_name', '')
                        svc['launchd'] = _manager_to_launchd_compat(manager, unit_name)
                return services
    except Exception as e:
        app.logger.error(f"Failed to load services from machines.json: {e}")

    # Fallback to services.json
    try:
        svc_path = os.path.join(os.path.dirname(__file__), 'services.json')
        with open(svc_path, 'r') as f:
            return json.load(f).get('services', {})
    except Exception:
        return {}

def get_authentik_config():
    """Load authentik config section from machines.json"""
    config_path = os.path.join(os.path.dirname(__file__), 'machines.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f).get('authentik', {})
    except Exception:
        return {}

SELF_MACHINE_ID = _detect_self_id()
_ALL_MACHINES = load_machines_config()
MACHINES = [m for m in _ALL_MACHINES if m['id'] != SELF_MACHINE_ID]
SELF_MACHINE = next((m for m in _ALL_MACHINES if m['id'] == SELF_MACHINE_ID), {})

# Initialize alert engine with Glances hosts from all machines
_alert_glances_hosts = {
    'noc-local': {'host': 'localhost', 'port': 61999},
}
for _m in MACHINES:
    if _m.get('role') == 'agent':
        _alert_glances_hosts[_m['id']] = {'host': _m['hostname'], 'port': 61999}

_discord_webhook = None
try:
    import yaml
    _gatus_cfg_path = os.path.join(os.path.dirname(__file__), '..', 'services', 'gatus', 'config.yaml')
    if os.path.exists(_gatus_cfg_path):
        with open(_gatus_cfg_path) as _f:
            _gatus_cfg = yaml.safe_load(_f)
        _discord_webhook = _gatus_cfg.get('alerting', {}).get('discord', {}).get('webhook-url')
except Exception:
    pass

alert_engine = AlertEngine(
    discord_webhook_url=_discord_webhook,
    glances_hosts=_alert_glances_hosts,
)

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

def _query_agent_api(hostname, agent_port, endpoint, method='GET', json_data=None, timeout=5):
    """Query a remote machine's agent API"""
    url = f'http://{hostname}:{agent_port}{endpoint}'
    try:
        if method == 'GET':
            resp = requests.get(url, timeout=timeout)
        else:
            resp = requests.post(url, json=json_data, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

def _refresh_remote_batch(machine):
    """Get service status + uptime from a remote machine (agent API or SSH)"""
    machine_id = machine['id']
    now = time.time()

    cached = _remote_batch_cache.get(machine_id)
    if cached and (now - cached['timestamp']) < _remote_batch_ttl:
        return cached['data']

    hostname = machine['hostname']
    ssh_user = machine.get('ssh_user', 'noc')
    data = {'processes': set(), 'uptime_secs': None, 'agent_status': None}

    if machine.get('role') == 'agent':
        agent_port = machine.get('agent_port', 8080)
        # Query agent API for service status
        status = _query_agent_api(hostname, agent_port, '/api/agent/status')
        if status is not None:
            data['agent_status'] = status
        # Query agent API for uptime
        info = _query_agent_api(hostname, agent_port, '/api/agent/info')
        if info and 'uptime' in info:
            data['uptime_secs'] = info['uptime']

    elif machine.get('platform') == 'windows':
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
    """Get status of all services on a remote machine"""
    hostname = machine['hostname']
    services = machine.get('services', {})
    batch = _refresh_remote_batch(machine)
    results = {}

    # Agent machines: use agent API response directly
    if machine.get('role') == 'agent' and batch.get('agent_status') is not None:
        agent_status = batch['agent_status']
        for svc_id in services:
            results[svc_id] = agent_status.get(svc_id, False)
        return results

    # Fallback: port checks + process list (Windows / non-agent machines)
    for svc_id, svc in services.items():
        port = svc.get('port')
        process_name = svc.get('process_name')

        if port:
            results[svc_id] = check_remote_port(hostname, port)
        elif process_name:
            results[svc_id] = process_name.lower() in batch['processes']
        else:
            results[svc_id] = False

    return results

def control_remote_service(machine, svc_id, action):
    """Start/stop/restart a service on a remote machine"""
    svc = machine.get('services', {}).get(svc_id)
    if not svc:
        return {'success': False, 'message': 'Unknown service'}

    # Agent machines: forward to agent API
    if machine.get('role') == 'agent':
        hostname = machine['hostname']
        agent_port = machine.get('agent_port', 8080)
        result = _query_agent_api(
            hostname, agent_port,
            f'/api/agent/service/{action}',
            method='POST',
            json_data={'service': svc_id},
            timeout=15
        )
        # Invalidate caches
        _remote_batch_cache.pop(machine['id'], None)
        _api_status_cache['data'] = None

        if result is None:
            return {'success': False, 'message': f'Agent unreachable on {hostname}:{agent_port}'}
        return result

    # Windows machines: SSH commands
    hostname = machine['hostname']
    ssh_user = machine.get('ssh_user', 'noc')
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

    # Invalidate caches
    _remote_batch_cache.pop(machine['id'], None)
    _api_status_cache['data'] = None

    if result.returncode == 0:
        return {'success': True, 'message': f'{svc["name"]} {action} successful'}
    else:
        error = result.stderr.strip() or result.stdout.strip() or 'Unknown error'
        return {'success': False, 'message': f'{svc["name"]} {action} failed: {error}'}

def is_remote_machine_reachable(hostname, port=22, timeout=2):
    """Quick check if a remote machine is reachable (cached)"""
    now = time.time()
    cache_key = f'{hostname}:{port}'
    cached = _reachability_cache.get(cache_key)
    if cached and (now - cached['timestamp']) < _reachability_ttl:
        return cached['reachable']

    reachable = check_remote_port(hostname, port, timeout)
    _reachability_cache[cache_key] = {'reachable': reachable, 'timestamp': now}
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
    """Get local system uptime in seconds (cross-platform)"""
    try:
        if sys.platform == 'darwin':
            result = subprocess.run(['/usr/sbin/sysctl', '-n', 'kern.boottime'], capture_output=True, text=True)
            if result.returncode == 0:
                match = re.search(r'sec\s*=\s*(\d+)', result.stdout)
                if match:
                    boot_time = int(match.group(1))
                    return int(time.time()) - boot_time
        elif sys.platform == 'linux':
            with open('/proc/uptime') as f:
                return int(float(f.read().split()[0]))
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

def get_glances_stats(host, port=61999, timeout=5):
    """Fetch memory, battery, and temperature stats from Glances API v4"""
    try:
        base = f'http://{host}:{port}/api/4'

        mem_response = requests.get(f'{base}/mem', timeout=timeout)
        mem_data = mem_response.json() if mem_response.status_code == 200 else {}

        sensor_response = requests.get(f'{base}/sensors', timeout=timeout)
        sensor_data = sensor_response.json() if sensor_response.status_code == 200 else []

        battery_percent = None
        temp_c = None
        if isinstance(sensor_data, list):
            core_temps = []
            for sensor in sensor_data:
                stype = sensor.get('type', '')
                val = sensor.get('value')
                if val is None:
                    continue
                if stype == 'battery':
                    battery_percent = val
                elif stype == 'temperature_core':
                    label = sensor.get('label', '')
                    # Prefer package-level sensor as the canonical CPU temp
                    if 'package' in label.lower():
                        temp_c = val
                    elif 'core' in label.lower():
                        core_temps.append(val)
            # Fall back to max core temp if no package sensor found
            if temp_c is None and core_temps:
                temp_c = max(core_temps)

        return {
            'memory_percent': mem_data.get('percent'),
            'battery_percent': battery_percent,
            'temp_c': temp_c
        }
    except Exception:
        return {'memory_percent': None, 'battery_percent': None, 'temp_c': None}

def get_glances_stats_cached(host, port=61999):
    """Get Glances stats with caching (30s TTL)"""
    now = time.time()
    cached = _glances_cache.get(host)
    if cached and (now - cached['timestamp']) < _glances_ttl:
        return cached['data']
    data = get_glances_stats(host, port)
    _glances_cache[host] = {'data': data, 'timestamp': now}
    return data

# Load services from services.json or fall back to hardcoded config
_loaded_services = load_services_config()
SERVICES = _loaded_services if _loaded_services else {}

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
    """Check if a launchd service is loaded (and potentially running)"""
    try:
        result = subprocess.run(['launchctl', 'list', launchd_name],
                              capture_output=True, text=True, timeout=5)
        # returncode 0 means the service is loaded in launchd
        return result.returncode == 0
    except:
        return False

def check_systemd_service_running(unit_name, user=False):
    """Check if a systemd service is active"""
    try:
        cmd = ['systemctl']
        if user:
            cmd.append('--user')
        cmd.extend(['is-active', '--quiet', unit_name])
        result = subprocess.run(cmd, capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False

def check_service_running(service_key, service):
    """Check if a service is running using the best available method"""
    manager = service.get('manager', '')
    unit_name = service.get('unit_name', '')
    launchd_name = service.get('launchd', '')
    port = service.get('port')

    # Special case for Tailscale
    if manager == 'tailscale' or service_key == 'tailscale':
        try:
            if sys.platform == 'darwin':
                result = subprocess.run(['pgrep', '-f', 'Tailscale.app'], capture_output=True)
            else:
                result = subprocess.run(['systemctl', 'is-active', '--quiet', 'tailscaled'], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False

    is_process_running = False

    # 1. Check process status based on manager type
    if manager == 'systemd':
        is_process_running = check_systemd_service_running(unit_name, user=False)
    elif manager == 'systemd-user':
        is_process_running = check_systemd_service_running(unit_name, user=True)
    elif manager == 'system-service':
        # System service (e.g. nxserver) — rely on port check
        if sys.platform == 'linux':
            is_process_running = check_systemd_service_running(unit_name, user=False)
        else:
            is_process_running = True
    elif manager == 'pm2' or launchd_name.startswith('pm2:'):
        pm2_name = unit_name or launchd_name.replace('pm2:', '')
        try:
            result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                pm2_list = json.loads(result.stdout)
                for proc in pm2_list:
                    if proc.get('name') == pm2_name and proc.get('pm2_env', {}).get('status') == 'online':
                        is_process_running = True
                        break
        except Exception:
            pass
    elif manager == 'docker' or launchd_name.startswith('docker:'):
        container_name = unit_name or launchd_name.replace('docker:', '')
        try:
            result = subprocess.run(['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Names}}'],
                                  capture_output=True, text=True, timeout=5)
            is_process_running = container_name in result.stdout
        except Exception:
            pass
    elif manager == 'brew' or (launchd_name and 'homebrew' in launchd_name):
        brew_name = unit_name or launchd_name.replace('homebrew.mxcl.', '')
        if check_launchd_service_running(launchd_name or f'homebrew.mxcl.{unit_name}'):
            is_process_running = True
        else:
            try:
                result = subprocess.run(['brew', 'services', 'list'], capture_output=True, text=True, timeout=5)
                for line in result.stdout.split('\n'):
                    if brew_name in line and 'started' in line:
                        is_process_running = True
                        break
            except Exception:
                pass
    elif manager == 'system-daemon' or launchd_name.startswith('system:'):
        is_process_running = True
    elif manager == 'disabled' or launchd_name.startswith('disabled'):
        is_process_running = False
    elif manager == 'launchd' or (launchd_name and not launchd_name.startswith('disabled')):
        ld_name = unit_name or launchd_name
        if ld_name and check_launchd_service_running(ld_name):
            is_process_running = True
    elif launchd_name.startswith('orbstack:'):
        is_process_running = True
    else:
        is_process_running = True

    # 2. Check port if defined
    if port:
        check_port = service.get('status_port', port)
        is_port_listening = check_port_listening(check_port)
        return is_process_running and is_port_listening

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
    # Use cached status from background thread (instant, no blocking)
    status_data = _build_status()
    local_status = status_data.get(SELF_MACHINE_ID, {})

    services_list = []
    for key, service in SERVICES.items():
        is_online = local_status.get(key, False)
        status_str = 'online' if is_online else 'offline'

        if key == 'tailscale':
            services_list.append({
                'key': key,
                'name': service['name'],
                'port': '5252 (WebClient)',
                'status': status_str,
                'url': 'http://noc-local:5252',
                'description': 'VPN & Mesh Network',
                'remote': False
            })
        elif key == 'teamspeak':
            services_list.append({
                'key': key,
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
                'key': key,
                'name': service['name'],
                'port': port_display,
                'status': status_str,
                'url': url,
                'description': service.get('description', ''),
                'remote': False
            })

    # Build machine groups from cached data
    local_uptime = local_status.get('_uptime', '--')
    local_glances = get_glances_stats_cached('localhost')

    self_platform = {'darwin': 'macOS', 'linux': 'Linux', 'windows': 'Windows'}.get(SELF_MACHINE.get('platform', sys.platform), sys.platform)
    machine_groups = [
        {
            'id': SELF_MACHINE_ID,
            'name': SELF_MACHINE.get('display_name', SELF_MACHINE_ID),
            'platform': self_platform,
            'reachable': True,
            'uptime': local_uptime,
            'services': services_list,
            'memory_percent': local_glances['memory_percent'],
            'battery_percent': local_glances['battery_percent'],
            'temp_c': local_glances.get('temp_c')
        }
    ]

    # Add remote machines from cached data
    for machine in MACHINES:
        if machine.get('role') == 'agent':
            machine_id = machine['id']
            machine_data = status_data.get(machine_id, {})
            reachable = machine_data.get('_reachable', False)
            remote_services = []

            for svc_id, svc in machine.get('services', {}).items():
                is_online = machine_data.get(svc_id, False)
                remote_services.append({
                    'key': svc_id,
                    'name': svc['name'],
                    'port': svc.get('port', '--'),
                    'status': 'online' if is_online else 'offline',
                    'url': svc.get('url', '#'),
                    'description': svc.get('description', ''),
                    'machine': machine['id'],
                    'remote': True
                })

            remote_uptime = machine_data.get('_uptime', '--')
            remote_glances = get_glances_stats_cached(machine['hostname']) if reachable else {'memory_percent': None, 'battery_percent': None, 'temp_c': None}

            machine_groups.append({
                'id': machine['id'],
                'name': machine.get('display_name', machine['id']),
                'platform': {'windows': 'Windows', 'linux': 'Linux', 'darwin': 'macOS'}.get(machine.get('platform', ''), machine.get('platform', '')),
                'reachable': reachable,
                'uptime': remote_uptime,
                'services': remote_services,
                'memory_percent': remote_glances['memory_percent'],
                'battery_percent': remote_glances['battery_percent'],
                'temp_c': remote_glances.get('temp_c')
            })

    avg_uptime = status_data.get('_avg_uptime', '--')

    return render_template('template.html',
                         services=services_list,
                         machine_groups=machine_groups,
                         uptime=avg_uptime,
                         self_machine_id=SELF_MACHINE_ID)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.svg', mimetype='image/svg+xml')

@app.route('/teamspeak')
def teamspeak_admin():
    return render_template('teamspeak.html')

def _check_all_local_services_parallel():
    """Check all local services in parallel using thread pool"""
    results = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(check_service_running, key, svc): key
                   for key, svc in SERVICES.items()}
        for future in as_completed(futures, timeout=15):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception:
                results[key] = False
    return results

def _update_status_cache():
    """Full status update — runs in background thread or on first request"""
    try:
        status = {SELF_MACHINE_ID: _check_all_local_services_parallel()}

        # Local uptime
        local_uptime_secs = get_system_uptime_secs()
        status[SELF_MACHINE_ID]['_uptime'] = format_uptime(local_uptime_secs) if local_uptime_secs else '--'
        uptime_values = [local_uptime_secs] if local_uptime_secs else []

        # Remote machines
        for machine in MACHINES:
            if machine.get('role') == 'agent':
                machine_id = machine['id']
                # For agent machines, check reachability via agent port
                check_port = machine.get('agent_port', 22)
                reachable = is_remote_machine_reachable(machine['hostname'], check_port)
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

        # Refresh Glances caches while we're at it
        get_glances_stats_cached('localhost')
        for machine in MACHINES:
            if machine.get('role') == 'agent':
                hostname = machine['hostname']
                check_port = machine.get('agent_port', 22)
                if is_remote_machine_reachable(hostname, check_port):
                    get_glances_stats_cached(hostname)

        _api_status_cache['data'] = status
        _api_status_cache['timestamp'] = time.time()
    except Exception as e:
        app.logger.error(f"Status update failed: {e}")

def _bg_status_loop():
    """Background thread that keeps status cache fresh"""
    while True:
        _update_status_cache()
        try:
            alert_engine.check_all()
        except Exception as e:
            app.logger.error(f"Alert check failed: {e}")
        time.sleep(10)

def _build_status():
    """Return cached status (populated by background thread)"""
    if _api_status_cache['data'] is None:
        # First request before background thread has populated cache
        _update_status_cache()
    return _api_status_cache['data'] or {}

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
        # System LaunchDaemons (require root, can only view logs)
        elif launchd_name.startswith('system:'):
            if action == 'logs':
                logs = get_service_log(service_key_lower)
                return jsonify({'success': True, 'logs': logs})
            else:
                return jsonify({'success': False, 'message': f'{service["name"]} is a system daemon (requires root to control)'})
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
                subprocess.run(['docker', 'compose', 'start'],
                             cwd=compose_dir, check=True, capture_output=True, text=True)
                return jsonify({'success': True, 'message': f'{service["name"]} started'})
            elif action == 'stop':
                subprocess.run(['docker', 'compose', 'stop'],
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
        # Systemd services (Linux)
        elif service.get('manager') in ('systemd', 'systemd-user'):
            user_flag = ['--user'] if service['manager'] == 'systemd-user' else []
            svc_unit = service.get('unit_name', '')
            if action == 'logs':
                try:
                    cmd = ['journalctl'] + user_flag + ['-u', svc_unit, '-n', '250', '--no-pager']
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    logs = result.stdout or 'No logs available'
                except Exception as e:
                    logs = f"Error getting logs: {str(e)}"
                return jsonify({'success': True, 'logs': logs})
            elif action in ('start', 'stop', 'restart'):
                cmd = ['systemctl'] + user_flag + [action, svc_unit]
                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            else:
                return jsonify({'success': False, 'message': 'Invalid action'}), 400
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

# Alert API Endpoints

@app.route('/alerts')
def alerts_page():
    """Alert history page"""
    return render_template('alerts.html')

@app.route('/api/alerts')
def get_alerts():
    """Return alert history and active count"""
    limit = request.args.get('limit', 50, type=int)
    return jsonify({
        'alerts': alert_engine.get_history(limit),
        'active_count': alert_engine.get_active_count(),
        'active': alert_engine.get_active_alerts(),
    })

@app.route('/api/alerts/active')
def get_active_alerts():
    """Return just the active alert count (lightweight, for header badge)"""
    return jsonify({
        'count': alert_engine.get_active_count(),
    })

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

# Invitation management routes

@app.route('/invites')
def invites_page():
    return render_template('invites.html')

@app.route('/api/invites')
def list_invites():
    """List active invitations from Authentik"""
    cfg = get_authentik_config()
    if not cfg.get('api_token'):
        return jsonify({'error': 'Authentik not configured'}), 500
    try:
        resp = requests.get(
            f"{cfg['api_url']}/api/v3/stages/invitation/invitations/",
            headers={'Authorization': f"Bearer {cfg['api_token']}"},
            timeout=10
        )
        if resp.status_code != 200:
            return jsonify({'error': f'Authentik API error: {resp.status_code}'}), 502
        data = resp.json()
        invites = []
        for inv in data.get('results', []):
            invites.append({
                'pk': inv['pk'],
                'name': inv.get('name', ''),
                'link': f"{cfg['api_url']}/if/flow/{cfg.get('enrollment_flow_slug', 'enrollment-invitation')}/?itoken={inv['pk']}",
                'created': inv.get('created', ''),
                'expires': inv.get('expires', None),
                'single_use': inv.get('single_use', False),
            })
        return jsonify({'invites': invites})
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 502

@app.route('/api/invites/create', methods=['POST'])
def create_invite():
    """Create a new invitation in Authentik"""
    cfg = get_authentik_config()
    if not cfg.get('api_token'):
        return jsonify({'error': 'Authentik not configured'}), 500
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    expiry_days = data.get('expiry_days', 7)
    single_use = data.get('single_use', True)

    payload = {
        'name': name,
        'single_use': single_use,
    }
    if expiry_days and expiry_days > 0:
        from datetime import datetime, timedelta, timezone
        expires = datetime.now(timezone.utc) + timedelta(days=expiry_days)
        payload['expires'] = expires.isoformat()

    # Get the enrollment flow PK
    flow_slug = cfg.get('enrollment_flow_slug', 'enrollment-invitation')
    try:
        flow_resp = requests.get(
            f"{cfg['api_url']}/api/v3/flows/instances/?slug={flow_slug}",
            headers={'Authorization': f"Bearer {cfg['api_token']}"},
            timeout=10
        )
        if flow_resp.status_code == 200:
            results = flow_resp.json().get('results', [])
            if results:
                payload['flow'] = results[0]['pk']

        resp = requests.post(
            f"{cfg['api_url']}/api/v3/stages/invitation/invitations/",
            headers={
                'Authorization': f"Bearer {cfg['api_token']}",
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=10
        )
        if resp.status_code in (200, 201):
            inv = resp.json()
            return jsonify({
                'success': True,
                'invite': {
                    'pk': inv['pk'],
                    'name': inv.get('name', ''),
                    'link': f"{cfg['api_url']}/if/flow/{flow_slug}/?itoken={inv['pk']}",
                }
            })
        else:
            error = resp.text
            try:
                error = resp.json()
            except Exception:
                pass
            return jsonify({'error': f'Authentik API error: {error}'}), 502
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 502

@app.route('/api/invites/<pk>', methods=['DELETE'])
def delete_invite(pk):
    """Delete/revoke an invitation"""
    cfg = get_authentik_config()
    if not cfg.get('api_token'):
        return jsonify({'error': 'Authentik not configured'}), 500
    try:
        resp = requests.delete(
            f"{cfg['api_url']}/api/v3/stages/invitation/invitations/{pk}/",
            headers={'Authorization': f"Bearer {cfg['api_token']}"},
            timeout=10
        )
        if resp.status_code == 204:
            return jsonify({'success': True})
        else:
            return jsonify({'error': f'Authentik API error: {resp.status_code}'}), 502
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 502

# --- Website Manager ---
NOC_TUX_SITES_JSON = '/home/noc/websites/sites.json'
NOC_TUX_CADDYFILE = '/home/noc/websites/Caddyfile'
NOC_TUX_ACCESS_LOG = '/home/noc/websites/logs/access.log'

# Local app sites (managed via LaunchAgents on noc-local)
LOCAL_APP_SITES = {
    'mdsf-crew': {
        'type': 'app', 'domain': 'crew.nocfa.net', 'aliases': [], 'host': 'noc-local',
        'components': [
            {'id': 'com.noc.mdsf-crew-api',    'name': 'API',    'role': 'api',      'type': 'launchctl', 'log': '/Users/noc/Library/Logs/noc-homelab/mdsf-crew-api.log'},
            {'id': 'com.noc.mdsf-crew-web',    'name': 'Web',    'role': 'frontend', 'type': 'launchctl', 'log': '/Users/noc/Library/Logs/noc-homelab/mdsf-crew-web.log'},
            {'id': 'com.noc.mdsf-crew-tunnel', 'name': 'Tunnel', 'role': 'tunnel',   'type': 'launchctl', 'log': '/Users/noc/Library/Logs/noc-homelab/mdsf-crew-tunnel.log'},
        ]
    },
    'mdsf-org': {
        'type': 'app', 'domain': 'mdsf.nocfa.net', 'aliases': [], 'host': 'noc-local',
        'components': [
            {'id': 'com.noc.mdsf-org',        'name': 'Site',   'role': 'frontend', 'type': 'launchctl', 'log': '/Users/noc/Library/Logs/noc-homelab/mdsf-org.log'},
            {'id': 'com.noc.mdsf-org-tunnel', 'name': 'Tunnel', 'role': 'tunnel',   'type': 'launchctl', 'log': '/Users/noc/Library/Logs/noc-homelab/mdsf-org-tunnel.log'},
        ]
    },
    'pelican': {
        'type': 'app', 'domain': 'games.nocfa.net', 'aliases': [], 'host': 'mixed',
        'components': [
            {'id': 'com.noc.games-tunnel', 'name': 'Tunnel', 'role': 'tunnel',  'type': 'launchctl',    'log': '/Users/noc/Library/Logs/noc-homelab/games-tunnel.log'},
            {'id': 'wings',                'name': 'Wings',  'role': 'backend', 'type': 'tux-systemd',  'unit': 'wings'},
            {'id': 'pelican-queue',        'name': 'Queue',  'role': 'worker',  'type': 'tux-systemd',  'unit': 'pelican-queue'},
        ]
    },
}

# Remote app sites on noc-tux (docker-managed)
REMOTE_APP_SITES = {
    'animated-album-covers': {
        'type': 'app', 'domain': 'api.nocfa.net', 'aliases': [], 'host': 'noc-tux',
        'compose_dir': '/home/noc/animated-album-covers',
        'components': [
            {'id': 'musicpresence-animated-album-covers-http-1',  'name': 'HTTP',  'role': 'web',       'type': 'docker'},
            {'id': 'musicpresence-animated-album-covers-video-1', 'name': 'Video', 'role': 'processor', 'type': 'docker'},
            {'id': 'musicpresence-animated-album-covers-redis-1', 'name': 'Redis', 'role': 'cache',     'type': 'docker'},
        ]
    },
}

# Remote app sites on noc-claw (launchd-managed)
CLAW_APP_SITES = {
    'open-llm-vtuber': {
        'type': 'app', 'domain': 'noc-claw:12394', 'aliases': [], 'host': 'noc-claw',
        'components': [
            {'id': 'com.noc.open-llm-vtuber', 'name': 'VTuber Server', 'role': 'backend', 'type': 'launchctl'},
            {'id': 'com.noc.vtuber-caddy',    'name': 'HTTPS Proxy',   'role': 'proxy',   'type': 'launchctl'},
        ]
    },
}

def _websites_ssh(cmd, timeout=10):
    return ssh_command('noc-tux', 'noc', cmd, timeout=timeout)

def _local_launchctl_running(label):
    """Check if a local LaunchAgent is running."""
    try:
        result = subprocess.run(['launchctl', 'list', label], capture_output=True, text=True, timeout=3)
        return result.returncode == 0 and '"PID"' in result.stdout
    except Exception:
        return False

def _remote_docker_running(container_name):
    """Check if a docker container is running on noc-tux."""
    r = _websites_ssh(f'docker inspect --format "{{{{.State.Running}}}}" {container_name} 2>/dev/null', timeout=6)
    return r is not None and r.stdout.strip() == 'true'

def _claw_launchctl_running(label):
    """Check if a LaunchAgent is running on noc-claw."""
    r = ssh_command('noc-claw', 'noc', f'launchctl list {label} 2>/dev/null', timeout=6)
    return r is not None and r.returncode == 0 and '"PID"' in r.stdout

def _tux_systemd_running(unit):
    """Check if a system-level (not user) systemd service is running on noc-tux."""
    r = ssh_command('noc-tux', 'noc', f'systemctl is-active {unit} 2>/dev/null', timeout=6)
    return r is not None and r.stdout.strip() == 'active'

@app.route('/websites')
def websites_page():
    return render_template('websites.html')

@app.route('/api/websites/list')
def websites_list():
    all_sites = {}

    # 1. Local app sites (mdsf-crew, mdsf-org, pelican) — check via launchctl or tux-systemd
    for sid, site in LOCAL_APP_SITES.items():
        s = dict(site)
        components = []
        all_up = True
        for comp in site['components']:
            comp_type = comp.get('type', 'launchctl')
            if comp_type == 'tux-systemd':
                running = _tux_systemd_running(comp['unit'])
            else:
                running = _local_launchctl_running(comp['id'])
            if not running:
                all_up = False
            components.append({**comp, 'running': running})
        s['components'] = components
        s['all_up'] = all_up
        all_sites[sid] = s

    # 2. Remote app sites (animated-album-covers) — check via docker on noc-tux
    for sid, site in REMOTE_APP_SITES.items():
        s = dict(site)
        components = []
        all_up = True
        for comp in site['components']:
            running = _remote_docker_running(comp['id'])
            if not running:
                all_up = False
            components.append({**comp, 'running': running})
        s['components'] = components
        s['all_up'] = all_up
        all_sites[sid] = s

    # 2b. Remote app sites on noc-claw — check via launchctl over SSH
    for sid, site in CLAW_APP_SITES.items():
        s = dict(site)
        components = []
        all_up = True
        for comp in site['components']:
            running = _claw_launchctl_running(comp['id'])
            if not running:
                all_up = False
            components.append({**comp, 'running': running})
        s['components'] = components
        s['all_up'] = all_up
        all_sites[sid] = s

    # 3. Static sites from noc-tux sites.json
    r = _websites_ssh(f"cat {NOC_TUX_SITES_JSON} 2>/dev/null || echo '{{}}'")
    caddy_running = False
    if r:
        try:
            sites_data = json.loads(r.stdout.strip()) if r.stdout.strip() else {}
            checks = ['systemctl --user is-active caddy-websites 2>/dev/null']
            for sid in sites_data:
                checks.append(f"echo {sid}:$(systemctl --user is-active cloudflared-{sid} 2>/dev/null)")
            status_r = _websites_ssh('; '.join(checks), timeout=8)
            tunnel_status = {}
            if status_r and status_r.stdout:
                lines = status_r.stdout.strip().split('\n')
                if lines:
                    caddy_running = lines[0].strip() == 'active'
                for line in lines[1:]:
                    if ':' in line:
                        sid2, _, state = line.partition(':')
                        tunnel_status[sid2.strip()] = state.strip() == 'active'
            for sid, s in sites_data.items():
                s = dict(s)
                s['tunnel_running'] = tunnel_status.get(sid, False)
                s['caddy_responding'] = caddy_running
                all_sites[sid] = s
        except json.JSONDecodeError:
            pass

    return jsonify({'sites': all_sites, 'caddy_running': caddy_running})

@app.route('/api/websites/<site_id>/tunnel/<action>', methods=['POST'])
def websites_tunnel_action(site_id, action):
    if action not in ('start', 'stop', 'restart'):
        return jsonify({'error': 'Invalid action'}), 400
    if not re.match(r'^[a-zA-Z0-9-]+$', site_id):
        return jsonify({'error': 'Invalid site ID'}), 400
    r = _websites_ssh(f'systemctl --user {action} cloudflared-{site_id}', timeout=12)
    if not r:
        return jsonify({'error': 'Cannot reach noc-tux'}), 503
    if r.returncode == 0:
        return jsonify({'success': True})
    return jsonify({'error': r.stderr.strip() or f'Failed to {action} tunnel'}), 500

@app.route('/api/websites/<site_id>/logs')
def websites_site_logs(site_id):
    # Handle LOCAL_APP_SITES (e.g. pelican, mdsf-crew) — tail local log files per component
    if site_id in LOCAL_APP_SITES:
        site = LOCAL_APP_SITES[site_id]
        lines = []
        for comp in site.get('components', []):
            log_path = comp.get('log', '')
            if not log_path:
                continue
            log_path = os.path.expanduser(log_path)
            if comp.get('type') == 'tux-systemd':
                r = ssh_command('noc-tux', 'noc', f'journalctl -u {comp["unit"]} -n 50 --no-pager 2>/dev/null', timeout=8)
                if r and r.stdout.strip():
                    lines.append(f'--- {comp["name"]} ---')
                    lines.extend(r.stdout.strip().splitlines()[-50:])
            elif os.path.exists(log_path):
                try:
                    with open(log_path) as f:
                        tail = f.readlines()[-50:]
                    if tail:
                        lines.append(f'--- {comp["name"]} ---')
                        lines.extend(l.rstrip() for l in tail)
                except Exception:
                    pass
        return jsonify({'logs': '\n'.join(lines) if lines else 'No logs available.'})

    r = _websites_ssh(f"cat {NOC_TUX_SITES_JSON} 2>/dev/null || echo '{{}}'")
    if not r:
        return jsonify({'logs': 'Cannot reach noc-tux'})
    try:
        sites_data = json.loads(r.stdout.strip()) if r.stdout.strip() else {}
    except json.JSONDecodeError:
        return jsonify({'logs': 'Failed to parse sites.json'})
    site = sites_data.get(site_id)
    if not site:
        return jsonify({'logs': f'Site {site_id} not found'})
    all_domains = set([site.get('domain', '')] + site.get('aliases', []))
    log_r = _websites_ssh(f"tail -n 300 {NOC_TUX_ACCESS_LOG} 2>/dev/null", timeout=8)
    if not log_r:
        return jsonify({'logs': 'Cannot reach noc-tux'})
    lines = []
    for line in log_r.stdout.strip().split('\n'):
        if not line:
            continue
        try:
            entry = json.loads(line)
            req = entry.get('request', {})
            if req.get('host', '') not in all_domains:
                continue
            ts = entry.get('ts', 0)
            dt = time.strftime('%m/%d %H:%M:%S', time.localtime(ts))
            headers = req.get('headers', {})
            ip = (headers.get('Cf-Connecting-Ip') or [req.get('remote_ip', '-')])[0]
            cc = (headers.get('Cf-Ipcountry') or ['-'])[0]
            method = req.get('method', '-')
            uri = req.get('uri', '-')[:60]
            status = entry.get('status', '-')
            lines.append(f"{dt}  {ip:<15}  {cc:<3}  {method:<6}  {uri:<60}  {status}")
        except Exception:
            pass
    return jsonify({'logs': '\n'.join(lines[-100:]) if lines else 'No log entries for this site.'})

@app.route('/api/websites/add', methods=['POST'])
def websites_add():
    data = request.get_json() or {}
    domain = data.get('domain', '').strip()
    aliases = [a.strip() for a in data.get('aliases', []) if a.strip()]
    root = data.get('root', '').strip()
    if not domain or not root:
        return jsonify({'error': 'Domain and root are required'}), 400
    site_id = re.sub(r'[^a-z0-9]', '-', domain.lower()).strip('-')

    payload_b64 = base64.b64encode(json.dumps({
        'site_id': site_id, 'domain': domain, 'aliases': aliases, 'root': root,
        'sites_json': NOC_TUX_SITES_JSON, 'caddyfile': NOC_TUX_CADDYFILE
    }).encode()).decode()
    script_b64 = base64.b64encode(b"""
import json, base64, sys
d = json.loads(base64.b64decode(sys.argv[1]))
sid, domain, aliases, root = d['site_id'], d['domain'], d['aliases'], d['root']
sites_path, caddy_path = d['sites_json'], d['caddyfile']
with open(sites_path) as f: sites = json.load(f)
if sid in sites:
    print('ERROR:already_exists'); exit(1)
sites[sid] = {'domain': domain, 'aliases': aliases, 'root': root, 'enabled': True}
with open(sites_path, 'w') as f: json.dump(sites, f, indent=2)
all_hosts = ' '.join([domain] + aliases)
block = f'    @{sid} host {all_hosts}\\n    handle @{sid} {{\\n        root * {root}\\n        file_server\\n    }}\\n\\n'
with open(caddy_path) as f: c = f.read()
c = c.replace('    # Fallback', block + '    # Fallback')
with open(caddy_path, 'w') as f: f.write(c)
print('OK')
""").decode()

    r = _websites_ssh(f"echo {script_b64} | base64 -d | python3 - {payload_b64}", timeout=12)
    if not r:
        return jsonify({'error': 'Cannot reach noc-tux'}), 503
    if 'ERROR:already_exists' in (r.stdout or ''):
        return jsonify({'error': f'Site {site_id} already exists'}), 400
    if r.returncode != 0 or 'OK' not in (r.stdout or ''):
        return jsonify({'error': r.stderr.strip() or 'Failed to add site'}), 500
    _websites_ssh('systemctl --user reload caddy-websites', timeout=10)
    return jsonify({'success': True})

@app.route('/api/websites/<site_id>/remove', methods=['POST'])
def websites_remove(site_id):
    if not re.match(r'^[a-zA-Z0-9-]+$', site_id):
        return jsonify({'error': 'Invalid site ID'}), 400
    _websites_ssh(f'systemctl --user stop cloudflared-{site_id} 2>/dev/null || true', timeout=8)

    payload_b64 = base64.b64encode(json.dumps({
        'site_id': site_id, 'sites_json': NOC_TUX_SITES_JSON, 'caddyfile': NOC_TUX_CADDYFILE
    }).encode()).decode()
    script_b64 = base64.b64encode(b"""
import json, re, base64, sys
d = json.loads(base64.b64decode(sys.argv[1]))
sid, sites_path, caddy_path = d['site_id'], d['sites_json'], d['caddyfile']
with open(sites_path) as f: sites = json.load(f)
if sid not in sites:
    print('ERROR:not_found'); exit(1)
del sites[sid]
with open(sites_path, 'w') as f: json.dump(sites, f, indent=2)
with open(caddy_path) as f: c = f.read()
c = re.sub(r'\\s+@' + re.escape(sid) + r' host[^\\n]*\\n\\s+handle @' + re.escape(sid) + r' \\{[^}]*\\}\\n?', '\\n', c, flags=re.DOTALL)
with open(caddy_path, 'w') as f: f.write(c)
print('OK')
""").decode()

    r = _websites_ssh(f"echo {script_b64} | base64 -d | python3 - {payload_b64}", timeout=12)
    if not r:
        return jsonify({'error': 'Cannot reach noc-tux'}), 503
    if 'ERROR:not_found' in (r.stdout or ''):
        return jsonify({'error': f'Site {site_id} not found'}), 404
    if r.returncode != 0:
        return jsonify({'error': r.stderr.strip() or 'Failed to remove site'}), 500
    _websites_ssh('systemctl --user reload caddy-websites', timeout=10)
    return jsonify({'success': True})

@app.route('/api/websites/<site_id>/component/<comp_id>/<action>', methods=['POST', 'GET'])
def websites_component_action(site_id, comp_id, action):
    if not re.match(r'^[a-zA-Z0-9._-]+$', site_id) or not re.match(r'^[a-zA-Z0-9._-]+$', comp_id):
        return jsonify({'error': 'Invalid ID'}), 400

    # Find the component definition to know its type and host
    site = LOCAL_APP_SITES.get(site_id) or REMOTE_APP_SITES.get(site_id)
    comp_def = None
    if site:
        for c in site.get('components', []):
            if c['id'] == comp_id:
                comp_def = c
                break

    comp_type = comp_def.get('type') if comp_def else 'docker'
    host = site.get('host') if site else 'noc-tux'

    # --- TUX SYSTEMD (system-level, not user) ---
    if comp_type == 'tux-systemd':
        unit = comp_def.get('unit', comp_id) if comp_def else comp_id
        if action == 'logs':
            r = ssh_command('noc-tux', 'noc', f'sudo journalctl -u {unit} -n 100 --no-pager 2>&1', timeout=12)
            if not r:
                return jsonify({'logs': 'Cannot reach noc-tux'})
            return jsonify({'logs': r.stdout or 'No logs available'})
        if action in ('start', 'stop', 'restart'):
            r = ssh_command('noc-tux', 'noc', f'sudo systemctl {action} {unit}', timeout=15)
            if not r:
                return jsonify({'error': 'Cannot reach noc-tux'}), 503
            if r.returncode == 0:
                return jsonify({'success': True})
            return jsonify({'error': r.stderr.strip() or f'Failed to {action} {unit}'}), 500
        return jsonify({'error': 'Invalid action'}), 400

    # --- LOCAL LAUNCHCTL ---
    if host == 'noc-local' or comp_type == 'launchctl':
        plist = f'/Users/noc/Library/LaunchAgents/{comp_id}.plist'
        if action == 'logs':
            log_file = comp_def.get('log') if comp_def else f'/Users/noc/Library/Logs/noc-homelab/{comp_id}.log'
            try:
                result = subprocess.run(['tail', '-n', '100', log_file], capture_output=True, text=True, timeout=5)
                return jsonify({'logs': result.stdout or 'No logs available'})
            except Exception as e:
                return jsonify({'logs': f'Error reading logs: {e}'})
        if action == 'start':
            subprocess.run(['launchctl', 'load', plist], capture_output=True, timeout=5)
            return jsonify({'success': True})
        if action == 'stop':
            subprocess.run(['launchctl', 'unload', plist], capture_output=True, timeout=5)
            return jsonify({'success': True})
        if action == 'restart':
            subprocess.run(['launchctl', 'unload', plist], capture_output=True, timeout=5)
            time.sleep(0.5)
            subprocess.run(['launchctl', 'load', plist], capture_output=True, timeout=5)
            return jsonify({'success': True})
        return jsonify({'error': 'Invalid action'}), 400

    # --- REMOTE DOCKER (noc-tux) ---
    if action == 'logs':
        r = _websites_ssh(f'docker logs --tail 100 {comp_id} 2>&1', timeout=12)
        if not r:
            return jsonify({'error': 'Cannot reach noc-tux'})
        return jsonify({'logs': r.stdout or 'No logs available'})
    if action in ('start', 'stop', 'restart'):
        r = _websites_ssh(f'docker {action} {comp_id}', timeout=15)
        if not r:
            return jsonify({'error': 'Cannot reach noc-tux'}), 503
        if r.returncode == 0:
            return jsonify({'success': True})
        return jsonify({'error': r.stderr.strip() or f'Failed to {action} {comp_id}'}), 500
    return jsonify({'error': 'Invalid action'}), 400

# --- Pelican Panel ---

@app.route('/api/pelican/component/<component_id>/<action>', methods=['POST'])
def pelican_component_action(component_id, action):
    """Start/stop/restart a Pelican component (tunnel on noc-local, wings/queue on noc-tux)."""
    if action not in ('start', 'stop', 'restart'):
        return jsonify({'error': 'Invalid action'}), 400
    if not re.match(r'^[a-zA-Z0-9._-]+$', component_id):
        return jsonify({'error': 'Invalid component ID'}), 400

    if component_id == 'com.noc.games-tunnel':
        # LaunchAgent on noc-local
        plist = f'/Users/noc/Library/LaunchAgents/{component_id}.plist'
        try:
            if action == 'start':
                subprocess.run(['launchctl', 'load', plist], capture_output=True, timeout=5)
            elif action == 'stop':
                subprocess.run(['launchctl', 'unload', plist], capture_output=True, timeout=5)
            elif action == 'restart':
                subprocess.run(['launchctl', 'unload', plist], capture_output=True, timeout=5)
                time.sleep(0.5)
                subprocess.run(['launchctl', 'load', plist], capture_output=True, timeout=5)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif component_id in ('wings', 'pelican-queue'):
        # systemd system service on noc-tux
        r = ssh_command('noc-tux', 'noc', f'sudo systemctl {action} {component_id}', timeout=15)
        if not r:
            return jsonify({'error': 'Cannot reach noc-tux'}), 503
        if r.returncode == 0:
            return jsonify({'success': True})
        return jsonify({'error': r.stderr.strip() or f'Failed to {action} {component_id}'}), 500

    else:
        return jsonify({'error': f'Unknown component: {component_id}'}), 404


@app.route('/api/pelican/maintenance', methods=['GET'])
def pelican_maintenance_status():
    """Check if Pelican maintenance mode is active."""
    r = ssh_command('noc-tux', 'noc', 'test -f /var/www/pelican/storage/framework/down && echo active || echo inactive', timeout=8)
    if not r:
        return jsonify({'error': 'Cannot reach noc-tux'}), 503
    active = r.stdout.strip() == 'active'
    return jsonify({'maintenance': active})


@app.route('/api/pelican/maintenance/<action>', methods=['POST'])
def pelican_maintenance_action(action):
    """Enable or disable Pelican maintenance mode."""
    if action not in ('on', 'off'):
        return jsonify({'error': 'Invalid action (use on or off)'}), 400

    if action == 'on':
        cmd = 'sudo php /var/www/pelican/artisan down'
    else:
        cmd = 'sudo php /var/www/pelican/artisan up'

    r = ssh_command('noc-tux', 'noc', cmd, timeout=20)
    if not r:
        return jsonify({'error': 'Cannot reach noc-tux'}), 503
    if r.returncode == 0:
        return jsonify({'success': True, 'maintenance': action == 'on'})
    return jsonify({'error': r.stderr.strip() or r.stdout.strip() or f'Failed to turn maintenance {action}'}), 500


# Screen lock management (macOS only)

@app.route('/api/screenlock', methods=['GET'])
def screenlock_status():
    """Get current screen lock status"""
    try:
        ask = subprocess.run(
            ['defaults', 'read', 'com.apple.screensaver', 'askForPassword'],
            capture_output=True, text=True, timeout=5
        )
        enabled = ask.stdout.strip() == '1'

        idle = subprocess.run(
            ['defaults', '-currentHost', 'read', 'com.apple.screensaver', 'idleTime'],
            capture_output=True, text=True, timeout=5
        )
        timeout_secs = int(idle.stdout.strip()) if idle.returncode == 0 and idle.stdout.strip().isdigit() else 0

        return jsonify({
            'enabled': enabled,
            'timeout_minutes': timeout_secs // 60
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/screenlock', methods=['POST'])
def screenlock_toggle():
    """Toggle screen lock on/off"""
    data = request.get_json() or {}
    action = data.get('action', 'toggle')

    try:
        if action in ('enable', 'disable', 'toggle'):
            if action == 'toggle':
                ask = subprocess.run(
                    ['defaults', 'read', 'com.apple.screensaver', 'askForPassword'],
                    capture_output=True, text=True, timeout=5
                )
                action = 'disable' if ask.stdout.strip() == '1' else 'enable'

            if action == 'enable':
                subprocess.run(['defaults', 'write', 'com.apple.screensaver', 'askForPassword', '-bool', 'true'], timeout=5)
                subprocess.run(['defaults', 'write', 'com.apple.screensaver', 'askForPasswordDelay', '-int', '0'], timeout=5)
                subprocess.run(['defaults', '-currentHost', 'write', 'com.apple.screensaver', 'idleTime', '-int', '3600'], timeout=5)
                return jsonify({'success': True, 'enabled': True, 'timeout_minutes': 60})
            else:
                subprocess.run(['defaults', 'write', 'com.apple.screensaver', 'askForPassword', '-bool', 'false'], timeout=5)
                return jsonify({'success': True, 'enabled': False})
        else:
            return jsonify({'error': f'Invalid action: {action}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Start background status updater thread
_status_thread = threading.Thread(target=_bg_status_loop, daemon=True)
_status_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
