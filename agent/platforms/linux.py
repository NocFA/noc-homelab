import subprocess
import platform
import time
import os
import glob
from typing import Dict, List
from .base import PlatformHandler, ServiceInfo


class LinuxHandler(PlatformHandler):
    """Linux-specific service handler."""

    def get_platform_info(self) -> Dict:
        return {
            "platform": "linux",
            "version": platform.version(),
            "arch": platform.machine(),
            "hostname": platform.node()
        }

    def get_system_uptime(self) -> int:
        try:
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.readline().split()[0])
                return int(uptime_seconds)
        except Exception:
            pass
        return 0

    def list_services(self, config: Dict) -> List[ServiceInfo]:
        services = []
        for svc_id, svc_config in config.get("services", {}).items():
            status = "online" if self.get_service_status(svc_id, config) else "offline"
            services.append(ServiceInfo(
                id=svc_id,
                name=svc_config.get("name", svc_id),
                type=self._get_service_type(svc_config),
                port=svc_config.get("port"),
                status=status,
                description=svc_config.get("description", "")
            ))
        return services

    def _get_service_type(self, svc_config: Dict) -> str:
        manager = svc_config.get("manager", "systemd")
        return manager

    def get_service_status(self, service_id: str, config: Dict) -> bool:
        svc_config = config.get("services", {}).get(service_id, {})
        manager = svc_config.get("manager", "systemd")
        service_name = svc_config.get("service_name", service_id)
        scope = svc_config.get("scope", "system")
        port = svc_config.get("port")

        is_running = False

        if manager == "docker":
            container = svc_config.get("container", service_id)
            is_running = self._check_docker_container(container)
        elif manager == "systemd":
            is_running = self._check_systemd_service(service_name, scope)
        elif manager == "process":
            process_name = svc_config.get("process_name")
            is_running = self._check_process(process_name) if process_name else False

        # Also check port if defined
        if port and is_running:
            check_port = svc_config.get("status_port", port)
            return self.check_port(check_port)

        return is_running

    def _user_env(self) -> Dict:
        """Environment for systemctl --user commands."""
        env = os.environ.copy()
        uid = os.getuid()
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
        return env

    def _check_systemd_service(self, service_name: str, scope: str = "system") -> bool:
        try:
            cmd = ["systemctl"]
            env = None
            if scope == "user":
                cmd.append("--user")
                env = self._user_env()
            cmd.extend(["is-active", service_name])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, env=env)
            return result.stdout.strip() == "active"
        except Exception:
            return False

    def _check_docker_container(self, container_name: str) -> bool:
        try:
            # Use sudo for docker ps
            result = subprocess.run(
                ["sudo", "docker", "ps", "--filter", f"name=^/{container_name}$", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=5
            )
            return container_name in result.stdout
        except Exception:
            return False

    def _check_process(self, process_name: str) -> bool:
        try:
            result = subprocess.run(
                ["pgrep", "-x", process_name],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _run_systemctl(self, action: str, service_name: str, scope: str = "system") -> subprocess.CompletedProcess:
        if scope == "user":
            cmd = ["systemctl", "--user", action, service_name]
            return subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=self._user_env(), check=True)
        cmd = ["sudo", "systemctl", action, service_name]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=True)

    def start_service(self, service_id: str, config: Dict) -> bool:
        svc_config = config.get("services", {}).get(service_id, {})
        manager = svc_config.get("manager", "systemd")
        service_name = svc_config.get("service_name", service_id)
        scope = svc_config.get("scope", "system")

        try:
            if manager == "docker":
                compose_dir = svc_config.get("compose_dir")
                if compose_dir:
                    subprocess.run(["sudo", "docker", "compose", "up", "-d"], cwd=compose_dir, check=True)
                    return True
            elif manager == "systemd":
                self._run_systemctl("start", service_name, scope)
                return True
            elif manager == "process":
                start_cmd = svc_config.get("start_cmd")
                if start_cmd:
                    subprocess.Popen(start_cmd, shell=True)
                    return True
        except Exception:
            pass
        return False

    def stop_service(self, service_id: str, config: Dict) -> bool:
        svc_config = config.get("services", {}).get(service_id, {})
        manager = svc_config.get("manager", "systemd")
        service_name = svc_config.get("service_name", service_id)
        scope = svc_config.get("scope", "system")

        try:
            if manager == "docker":
                compose_dir = svc_config.get("compose_dir")
                if compose_dir:
                    subprocess.run(["sudo", "docker", "compose", "stop"], cwd=compose_dir, check=True)
                    return True
            elif manager == "systemd":
                self._run_systemctl("stop", service_name, scope)
                return True
            elif manager == "process":
                stop_cmd = svc_config.get("stop_cmd")
                if stop_cmd:
                    subprocess.run(stop_cmd, shell=True, check=True)
                    return True
        except Exception:
            pass
        return False

    def restart_service(self, service_id: str, config: Dict) -> bool:
        svc_config = config.get("services", {}).get(service_id, {})
        manager = svc_config.get("manager", "systemd")
        service_name = svc_config.get("service_name", service_id)
        scope = svc_config.get("scope", "system")

        try:
            if manager == "systemd":
                self._run_systemctl("restart", service_name, scope)
                return True
        except Exception:
            pass

        self.stop_service(service_id, config)
        time.sleep(1)
        return self.start_service(service_id, config)

    def get_service_logs(self, service_id: str, config: Dict, lines: int = 100) -> str:
        svc_config = config.get("services", {}).get(service_id, {})
        manager = svc_config.get("manager", "systemd")
        service_name = svc_config.get("service_name", service_id)
        scope = svc_config.get("scope", "system")

        if manager == "systemd":
            try:
                cmd = ["journalctl", "-n", str(lines), "--no-pager"]
                env = None
                if scope == "user":
                    cmd.extend(["--user-unit", service_name])
                    env = self._user_env()
                else:
                    cmd.extend(["-u", service_name])
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=env)
                return result.stdout
            except Exception:
                pass
        
        if manager == "docker":
            container = svc_config.get("container", service_id)
            try:
                result = subprocess.run(
                    ["sudo", "docker", "logs", "--tail", str(lines), container],
                    capture_output=True, text=True, timeout=10
                )
                return result.stdout if result.stdout else result.stderr
            except Exception:
                pass

        log_paths = svc_config.get("log_paths", [])
        all_logs = []
        for log_path in log_paths:
            expanded = os.path.expanduser(log_path)
            if "*" in expanded:
                files = glob.glob(expanded)
            elif os.path.exists(expanded):
                files = [expanded]
            else:
                continue

            for f in files:
                try:
                    result = subprocess.run(
                        ["tail", "-n", str(lines), f],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.stdout.strip():
                        all_logs.append(result.stdout.strip())
                except Exception:
                    continue

        return "\n".join(all_logs) if all_logs else "No logs found"
