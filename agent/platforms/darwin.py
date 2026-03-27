import subprocess
import platform
import time
import re
import os
import glob
import json
from typing import Dict, List
from .base import PlatformHandler, ServiceInfo


class DarwinHandler(PlatformHandler):
    """macOS-specific service handler."""

    def get_platform_info(self) -> Dict:
        return {
            "platform": "darwin",
            "version": platform.mac_ver()[0],
            "arch": platform.machine(),
            "hostname": platform.node()
        }

    def get_system_uptime(self) -> int:
        try:
            result = subprocess.run(
                ['/usr/sbin/sysctl', '-n', 'kern.boottime'],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                match = re.search(r'sec\s*=\s*(\d+)', result.stdout)
                if match:
                    boot_time = int(match.group(1))
                    return int(time.time()) - boot_time
        except Exception:
            pass
        return 0

    def list_services(self, config: Dict) -> List[ServiceInfo]:
        services = []
        for svc_id, svc_config in config.get('services', {}).items():
            status = 'online' if self.get_service_status(svc_id, config) else 'offline'
            services.append(ServiceInfo(
                id=svc_id,
                name=svc_config.get('name', svc_id),
                type=self._get_service_type(svc_config),
                port=svc_config.get('port'),
                status=status,
                description=svc_config.get('description', ''),
                url=svc_config.get('url')
            ))
        return services

    def _get_service_type(self, svc_config: Dict) -> str:
        launchd = svc_config.get('launchd', '')
        if launchd.startswith('docker:'):
            return 'docker'
        elif launchd.startswith('pm2:'):
            return 'pm2'
        elif launchd.startswith('homebrew'):
            return 'homebrew'
        else:
            return 'launchd'

    def get_service_status(self, service_id: str, config: Dict) -> bool:
        svc_config = config.get('services', {}).get(service_id, {})
        launchd = svc_config.get('launchd', '')
        port = svc_config.get('port')

        is_running = False

        # Check process status based on type
        if launchd.startswith('docker:'):
            container = launchd.replace('docker:', '')
            is_running = self._check_docker_container(container)
        elif launchd.startswith('pm2:'):
            pm2_name = launchd.replace('pm2:', '')
            is_running = self._check_pm2_process(pm2_name)
        elif launchd.startswith('homebrew'):
            service_name = launchd.replace('homebrew.mxcl.', '')
            is_running = self._check_homebrew_service(service_name)
        elif launchd:
            is_running = self._check_launchd_service(launchd)
        else:
            # If no launchd/docker/pm2 specified, assume running if port check passes
            is_running = True

        # Also check port if defined
        if port and is_running:
            check_port = svc_config.get('status_port', port)
            return self.check_port(check_port)

        return is_running

    def _check_launchd_service(self, launchd_name: str) -> bool:
        try:
            result = subprocess.run(
                ['launchctl', 'list', launchd_name],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0 and '"PID"' in result.stdout
        except Exception:
            return False

    def _check_docker_container(self, container_name: str) -> bool:
        try:
            result = subprocess.run(
                ['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Names}}'],
                capture_output=True, text=True, timeout=5
            )
            return container_name in result.stdout
        except Exception:
            return False

    def _check_pm2_process(self, pm2_name: str) -> bool:
        try:
            result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                pm2_list = json.loads(result.stdout)
                for proc in pm2_list:
                    if proc.get('name') == pm2_name and proc.get('pm2_env', {}).get('status') == 'online':
                        return True
        except Exception:
            pass
        return False

    def _check_homebrew_service(self, service_name: str) -> bool:
        try:
            result = subprocess.run(['brew', 'services', 'list'], capture_output=True, text=True, timeout=5)
            for line in result.stdout.split('\n'):
                if service_name in line and 'started' in line:
                    return True
        except Exception:
            pass
        return False

    def start_service(self, service_id: str, config: Dict) -> bool:
        svc_config = config.get('services', {}).get(service_id, {})
        launchd = svc_config.get('launchd', '')

        try:
            if launchd.startswith('docker:'):
                compose_dir = svc_config.get('compose_dir')
                if compose_dir:
                    subprocess.run(['docker', 'compose', 'start'], cwd=compose_dir, check=True)
                    return True
            elif launchd.startswith('pm2:'):
                pm2_name = launchd.replace('pm2:', '')
                subprocess.run(['pm2', 'start', pm2_name], check=True)
                return True
            elif launchd.startswith('homebrew'):
                service_name = launchd.replace('homebrew.mxcl.', '')
                subprocess.run(['brew', 'services', 'start', service_name], check=True)
                return True
            else:
                plist_path = os.path.expanduser(f'~/Library/LaunchAgents/{launchd}.plist')
                subprocess.run(['launchctl', 'load', plist_path], check=True)
                return True
        except Exception:
            pass
        return False

    def stop_service(self, service_id: str, config: Dict) -> bool:
        svc_config = config.get('services', {}).get(service_id, {})
        launchd = svc_config.get('launchd', '')

        try:
            if launchd.startswith('docker:'):
                compose_dir = svc_config.get('compose_dir')
                if compose_dir:
                    subprocess.run(['docker', 'compose', 'stop'], cwd=compose_dir, check=True)
                    return True
            elif launchd.startswith('pm2:'):
                pm2_name = launchd.replace('pm2:', '')
                subprocess.run(['pm2', 'stop', pm2_name], check=True)
                return True
            elif launchd.startswith('homebrew'):
                service_name = launchd.replace('homebrew.mxcl.', '')
                subprocess.run(['brew', 'services', 'stop', service_name], check=True)
                return True
            else:
                plist_path = os.path.expanduser(f'~/Library/LaunchAgents/{launchd}.plist')
                subprocess.run(['launchctl', 'unload', plist_path], check=True)
                return True
        except Exception:
            pass
        return False

    def restart_service(self, service_id: str, config: Dict) -> bool:
        self.stop_service(service_id, config)
        time.sleep(1)
        return self.start_service(service_id, config)

    def get_service_logs(self, service_id: str, config: Dict, lines: int = 100) -> str:
        svc_config = config.get('services', {}).get(service_id, {})
        log_paths = svc_config.get('log_paths', [])

        all_logs = []
        for log_path in log_paths:
            expanded = os.path.expanduser(log_path)
            if '*' in expanded:
                files = glob.glob(expanded)
            elif os.path.exists(expanded):
                files = [expanded]
            else:
                continue

            for f in files:
                try:
                    result = subprocess.run(
                        ['tail', '-n', str(lines)],
                        capture_output=True, text=True,
                        stdin=open(f)
                    )
                    if result.stdout.strip():
                        all_logs.append(result.stdout.strip())
                except Exception:
                    continue

        return '\n'.join(all_logs) if all_logs else "No logs found"
