# Windows Setup Guide

## Prerequisites

- Windows 10/11
- Python 3.9+ ([python.org](https://python.org) or `scoop install python`)
- Tailscale ([tailscale.com](https://tailscale.com))
- Git (`scoop install git` or [git-scm.com](https://git-scm.com))
- OpenSSH Server (optional, for remote management)

## Installation

### 1. Clone the Repository

```powershell
git clone https://github.com/NocFA/noc-homelab.git C:\Users\noc\noc-homelab
cd C:\Users\noc\noc-homelab
```

### 2. Set Up the Agent

The agent provides an HTTP API that the primary dashboard queries for service status and control.

```powershell
cd agent
pip install -r requirements.txt

# Create your machine config from the example
copy config.example.yaml config.yaml
notepad config.yaml
```

Edit `config.yaml` with your Windows services. Example:

```yaml
machine:
  id: noc-winlocal
  display_name: Windows PC
  role: agent

services:
  emby:
    name: Emby
    manager: windows-service
    service_name: EmbyServer
    port: 8096
    description: Media streaming server

  sunshine:
    name: Sunshine
    manager: windows-service
    service_name: ApolloService
    port: 47990
    description: Game streaming

  zurg:
    name: Zurg
    manager: nssm
    service_name: Zurg
    port: 9999
    description: Real-Debrid WebDAV
```

### 3. Run the Agent

```powershell
python agent.py --port 8080
```

### 4. Install as a Windows Service (Optional)

Use [NSSM](https://nssm.cc) to run the agent as a persistent service:

```powershell
# Install NSSM
scoop install nssm

# Install agent as service
nssm install NocHomelabAgent "C:\Users\noc\AppData\Local\Programs\Python\Python312\python.exe"
nssm set NocHomelabAgent AppParameters "C:\Users\noc\noc-homelab\agent\agent.py --port 8080"
nssm set NocHomelabAgent AppDirectory "C:\Users\noc\noc-homelab\agent"
nssm set NocHomelabAgent AppStdout "C:\Users\noc\noc-homelab\logs\agent.log"
nssm set NocHomelabAgent AppStderr "C:\Users\noc\noc-homelab\logs\agent-error.log"

# Start the service
nssm start NocHomelabAgent
```

### 5. Verify

The primary dashboard on noc-local should now show your Windows services. You can also check directly:

```powershell
curl http://localhost:8080/api/agent/health
curl http://localhost:8080/api/agent/services
```

## Service Types

### Windows Services

Services managed by the Windows Service Control Manager:

```powershell
# List running services
Get-Service | Where-Object Status -eq Running

# Start/stop
Start-Service <name>
Stop-Service <name>
```

### NSSM Services

For applications that aren't native Windows services, use NSSM:

```powershell
nssm install <name> <path-to-exe>
nssm start <name>
nssm status <name>
nssm stop <name>
```

### Scheduled Tasks

For services that need to run at logon:

```powershell
# View tasks
schtasks /query /fo list /v | findstr "Task Name"

# Run a task
schtasks /run /tn "<task-name>"
```

## Tailscale

Ensure Tailscale is running and the machine is reachable from noc-local:

```powershell
# Check status
tailscale status

# Verify connectivity
ping noc-local
```

## Troubleshooting

### Agent not reachable from dashboard

1. Verify Tailscale is connected: `tailscale status`
2. Check agent is running: `curl http://localhost:8080/api/agent/health`
3. Check Windows Firewall allows port 8080
4. Test from noc-local: `curl http://noc-winlocal:8080/api/agent/health`

### Service detection issues

```powershell
# Check if port is listening
netstat -an | findstr :<port>

# Check service status
sc query <service-name>
nssm status <service-name>
```
