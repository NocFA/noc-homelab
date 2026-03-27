from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ServiceInfo:
    """Service information returned by the agent."""
    id: str
    name: str
    type: str  # launchd, docker, windows-service, etc.
    port: Optional[int]
    status: str  # online, offline, unknown
    description: str = ""
    url: Optional[str] = None


class PlatformHandler(ABC):
    """Abstract base class for platform-specific service handlers."""

    @abstractmethod
    def get_platform_info(self) -> Dict:
        """Return platform metadata."""
        pass

    @abstractmethod
    def get_system_uptime(self) -> int:
        """Return system uptime in seconds."""
        pass

    @abstractmethod
    def list_services(self, config: Dict) -> List[ServiceInfo]:
        """List all configured services and their status."""
        pass

    @abstractmethod
    def get_service_status(self, service_id: str, config: Dict) -> bool:
        """Check if a service is running."""
        pass

    @abstractmethod
    def start_service(self, service_id: str, config: Dict) -> bool:
        """Start a service."""
        pass

    @abstractmethod
    def stop_service(self, service_id: str, config: Dict) -> bool:
        """Stop a service."""
        pass

    @abstractmethod
    def restart_service(self, service_id: str, config: Dict) -> bool:
        """Restart a service."""
        pass

    @abstractmethod
    def get_service_logs(self, service_id: str, config: Dict, lines: int = 100) -> str:
        """Get recent logs for a service."""
        pass

    def check_port(self, port: int, host: str = '127.0.0.1', timeout: float = 0.5) -> bool:
        """Check if a port is listening."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
