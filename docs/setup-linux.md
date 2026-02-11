# Linux Setup Guide (Ubuntu)

## Prerequisites

- Ubuntu 24.04 LTS (recommended)
- Python 3.12+
- Docker & Docker Compose
- Tailscale ([tailscale.com](https://tailscale.com))
- Git, SOPS, Age

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/NocFA/noc-homelab.git ~/noc-homelab
cd ~/noc-homelab
```

### 2. Set Up the Agent

The agent provides an HTTP API that the primary dashboard queries for service status and control.

```bash
cd agent
sudo apt update
sudo apt install -y python3-flask python3-yaml

# Create your machine config from the example
cp config.example.yaml config.yaml
nano config.yaml
```

Edit `config.yaml` with your Linux services. Example:

```yaml
machine:
  id: noc-tux
  display_name: noc-tux
  role: agent

services:
  gatus:
    name: Gatus
    manager: systemd
    service_name: gatus
    scope: user
    port: 3001
    description: Service health monitoring

  glances:
    name: Glances
    manager: systemd
    service_name: glances
    scope: system
    port: 61999
    description: System Metrics & Monitoring

  zurg:
    name: Zurg
    manager: systemd
    service_name: zurg
    scope: user
    port: 9999
    description: Real-Debrid WebDAV
```

### 3. Install as a Systemd Service

```bash
# Create service file
cat > homelab-agent.service <<EOF
[Unit]
Description=NOC Homelab Agent
After=network.target docker.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/noc-homelab/agent
ExecStart=/usr/bin/python3 agent.py --port 8080 --config config.yaml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Install and start
sudo mv homelab-agent.service /etc/systemd/system/homelab-agent.service
sudo systemctl daemon-reload
sudo systemctl enable homelab-agent.service
sudo systemctl start homelab-agent.service
```

### 4. Verify

The primary dashboard on noc-local should now show your Linux services. You can also check directly:

```bash
curl http://localhost:8080/api/agent/health
curl http://localhost:8080/api/agent/services
```

## Service Management

### Systemd

```bash
# List status
systemctl status <name>

# Start/stop
sudo systemctl start <name>
sudo systemctl stop <name>
```

### Docker

```bash
# View containers
docker ps

# Compose actions
docker compose up -d
docker compose stop
```

## Tailscale

Ensure Tailscale is running and the machine is reachable from noc-local:

```bash
# Check status
tailscale status

# Verify connectivity
ping noc-local
```

## Troubleshooting

### Agent not reachable from dashboard

1. Verify Tailscale is connected: `tailscale status`
2. Check agent is running: `curl http://localhost:8080/api/agent/health`
3. Check firewall allows port 8080: `sudo ufw allow 8080/tcp`
4. Test from noc-local: `curl http://noc-tux:8080/api/agent/health`
