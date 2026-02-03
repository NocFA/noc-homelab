import subprocess
import platform
from typing import Dict, List
from .base import PlatformHandler, ServiceInfo


class WindowsHandler(PlatformHandler):
    """Windows-specific service handler."""

    def get_platform_info(self) -> Dict:
        return {
            "platform": "windows",
            "version": platform.version(),
            "arch": platform.machine(),
            "hostname": platform.node()
        }

    def get_system_uptime(self) -> int:
        try:
            # Use wmic to get boot time
            result = subprocess.run(
                ['wmic', 'os', 'get', 'LastBootUpTime', '/value'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                # Parse WMI datetime format: 20250115103000.000000-480
                import re
                from datetime import datetime
                match = re.search(r'LastBootUpTime=(\d{14})', result.stdout)
                if match:
                    boot_str = match.group(1)
                    boot_time = datetime.strptime(boot_str, '%Y%m%d%H%M%S')
                    return int((datetime.now() - boot_time).total_seconds())
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
                description=svc_config.get('description', '')
            ))
        return services

    def _get_service_type(self, svc_config: Dict) -> str:
        manager = svc_config.get('manager', 'windows-service')
        return manager

    def get_service_status(self, service_id: str, config: Dict) -> bool:
        svc_config = config.get('services', {}).get(service_id, {})
        manager = svc_config.get('manager', 'windows-service')
        service_name = svc_config.get('service_name', service_id)
        port = svc_config.get('port')

        is_running = False

        if manager == 'docker':
            container = svc_config.get('container', service_id)
            is_running = self._check_docker_container(container)
        elif manager == 'nssm':
            is_running = self._check_nssm_service(service_name)
        else:  # windows-service
            is_running = self._check_windows_service(service_name)

        # Also check port if defined
        if port and is_running:
            check_port = svc_config.get('status_port', port)
            return self.check_port(check_port)

        return is_running

    def _check_windows_service(self, service_name: str) -> bool:
        try:
            result = subprocess.run(
                ['sc', 'query', service_name],
                capture_output=True, text=True, timeout=10
            )
            return 'RUNNING' in result.stdout
        except Exception:
            return False

    def _check_nssm_service(self, service_name: str) -> bool:
        try:
            result = subprocess.run(
                ['nssm', 'status', service_name],
                capture_output=True, text=True, timeout=10
            )
            return 'SERVICE_RUNNING' in result.stdout
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

    def start_service(self, service_id: str, config: Dict) -> bool:
        svc_config = config.get('services', {}).get(service_id, {})
        manager = svc_config.get('manager', 'windows-service')
        service_name = svc_config.get('service_name', service_id)

        try:
            if manager == 'docker':
                compose_dir = svc_config.get('compose_dir')
                if compose_dir:
                    subprocess.run(['docker', 'compose', 'up', '-d'], cwd=compose_dir, check=True)
                    return True
            elif manager == 'nssm':
                subprocess.run(['nssm', 'start', service_name], check=True)
                return True
            else:
                subprocess.run(['sc', 'start', service_name], check=True)
                return True
        except Exception:
            pass
        return False

    def stop_service(self, service_id: str, config: Dict) -> bool:
        svc_config = config.get('services', {}).get(service_id, {})
        manager = svc_config.get('manager', 'windows-service')
        service_name = svc_config.get('service_name', service_id)

        try:
            if manager == 'docker':
                compose_dir = svc_config.get('compose_dir')
                if compose_dir:
                    subprocess.run(['docker', 'compose', 'down'], cwd=compose_dir, check=True)
                    return True
            elif manager == 'nssm':
                subprocess.run(['nssm', 'stop', service_name], check=True)
                return True
            else:
                subprocess.run(['sc', 'stop', service_name], check=True)
                return True
        except Exception:
            pass
        return False

    def restart_service(self, service_id: str, config: Dict) -> bool:
        import time
        self.stop_service(service_id, config)
        time.sleep(2)
        return self.start_service(service_id, config)

    def get_service_logs(self, service_id: str, config: Dict, lines: int = 100) -> str:
        svc_config = config.get('services', {}).get(service_id, {})
        log_paths = svc_config.get('log_paths', [])

        all_logs = []
        for log_path in log_paths:
            try:
                # Use PowerShell to get last N lines
                result = subprocess.run(
                    ['powershell', '-Command', f'Get-Content -Path "{log_path}" -Tail {lines}'],
                    capture_output=True, text=True, timeout=10
                )
                if result.stdout.strip():
                    all_logs.append(result.stdout.strip())
            except Exception:
                continue

        return '\n'.join(all_logs) if all_logs else "No logs found"
