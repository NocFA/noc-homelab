# Architecture

## Overview

The NOC Homelab is a distributed service management system spanning multiple machines connected via Tailscale mesh VPN. The primary dashboard on `noc-local` (macOS) serves as the central control plane, with agents on each machine providing local service management.

## Network Topology

```
                         ┌─────────────────────────────────────┐
                         │           Tailscale Mesh            │
                         │         (100.x.x.x network)         │
                         └─────────────────────────────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              │                           │                           │
              ▼                           ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
    │   noc-local     │         │  noc-tux   │         │   (future)      │
    │    (macOS)      │         │   (Linux)     │         │                 │
    │                 │         │                 │         │                 │
    │ ┌─────────────┐ │         │ ┌─────────────┐ │         │                 │
    │ │  Dashboard  │◄┼─────────┼─┤   Agent     │ │         │                 │
    │ │  :8080      │ │  HTTP   │ │   :8080     │ │         │                 │
    │ └─────────────┘ │         │ └─────────────┘ │         │                 │
    │                 │         │                 │         │                 │
    │ Services:       │         │ Services:       │         │                 │
    │ - Copyparty     │         │ - TBD           │         │                 │
    │ - Maloja        │         │ - TBD           │         │                 │
    │ - TeamSpeak     │         │                 │         │                 │
    │ - Nextcloud     │         │                 │         │                 │
    │ - etc.          │         │                 │         │                 │
    └─────────────────┘         └─────────────────┘         └─────────────────┘
```

## Machine Configuration

### noc-local (macOS) - Primary

| Role | Description |
|------|-------------|
| **Dashboard** | Central web UI at port 8080 |
| **Service Manager** | LaunchAgents, Docker, PM2, Homebrew services |
| **Coordination** | Aggregates status from all machines |

**Hostnames**: `noc-local`, `100.x.x.x` (Tailscale IP)

### noc-tux (Linux) - Secondary

| Role | Description |
|------|-------------|
| **Agent** | Lightweight HTTP API at port 8080 |
| **Service Manager** | systemd (user + system), Docker |
| **Reporter** | Reports status to primary dashboard |

**Hostnames**: `noc-tux`, `100.x.x.x` (Tailscale IP)

## Agent API Specification

Each machine runs an agent that implements a standard HTTP API. The primary dashboard queries these agents to aggregate status.

### Base URL

```
http://{machine-hostname}:8080/api/agent
```

### Endpoints

#### `GET /api/agent/info`

Returns machine metadata.

```json
{
  "hostname": "noc-tux",
  "platform": "linux",
  "version": "1.0.0",
  "uptime": 86400,
  "services_count": 5
}
```

#### `GET /api/agent/services`

Returns all services managed by this agent.

```json
{
  "services": [
    {
      "id": "plex",
      "name": "Plex Media Server",
      "type": "windows-service",
      "port": 32400,
      "status": "online",
      "description": "Media streaming"
    }
  ]
}
```

#### `GET /api/agent/status`

Returns status of all services (lightweight).

```json
{
  "plex": true,
  "sonarr": true,
  "radarr": false
}
```

#### `POST /api/agent/service/{action}`

Control a service. Actions: `start`, `stop`, `restart`, `logs`

**Request:**
```json
{
  "service": "plex"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Service started"
}
```

#### `GET /api/agent/health`

Health check endpoint for monitoring.

```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

## Dashboard Architecture

### Current (Single Machine)

```
┌─────────────────────────────────────────────────────┐
│                    dashboard/app.py                  │
├─────────────────────────────────────────────────────┤
│  SERVICES dict                                       │
│  ├─ copyparty: {launchd, port, logs}                │
│  ├─ maloja: {launchd, port, logs}                   │
│  └─ ...                                             │
├─────────────────────────────────────────────────────┤
│  check_service_running()                            │
│  ├─ launchctl check                                 │
│  ├─ docker ps check                                 │
│  ├─ pm2 jlist check                                 │
│  └─ port check                                      │
└─────────────────────────────────────────────────────┘
```

### Proposed (Multi-Machine)

```
┌─────────────────────────────────────────────────────┐
│                    dashboard/app.py                  │
├─────────────────────────────────────────────────────┤
│  MACHINES config                                     │
│  ├─ noc-local: {hostname, type: "primary"}          │
│  └─ noc-tux: {hostname, type: "agent"}         │
├─────────────────────────────────────────────────────┤
│  SERVICES dict (local services)                     │
│  ├─ copyparty: {machine: "noc-local", ...}         │
│  └─ ...                                             │
├─────────────────────────────────────────────────────┤
│  fetch_remote_services(machine)                     │
│  ├─ GET /api/agent/services                         │
│  └─ Cache with TTL                                  │
├─────────────────────────────────────────────────────┤
│  aggregate_all_services()                           │
│  ├─ Local services                                  │
│  └─ Remote services (via agent API)                 │
└─────────────────────────────────────────────────────┘
```

## Configuration Structure

### machines.json (new)

```json
{
  "machines": [
    {
      "id": "noc-local",
      "hostname": "noc-local",
      "display_name": "Mac Mini (Primary)",
      "platform": "darwin",
      "role": "primary",
      "agent_port": 8080
    },
    {
      "id": "noc-tux",
      "hostname": "noc-tux",
      "display_name": "noc-tux",
      "platform": "linux",
      "role": "agent",
      "agent_port": 8080
    }
  ]
}
```

## Service Management by Platform

### macOS (noc-local)

| Type | Start | Stop | Status |
|------|-------|------|--------|
| LaunchAgent | `launchctl load` | `launchctl unload` | `launchctl list` |
| Homebrew | `brew services start` | `brew services stop` | `brew services list` |
| Docker | `docker compose up -d` | `docker compose down` | `docker ps` |
| PM2 | `pm2 start` | `pm2 stop` | `pm2 jlist` |

### Linux (noc-tux)

| Type | Start | Stop | Status |
|------|-------|------|--------|
| systemd (system) | `sudo systemctl start` | `sudo systemctl stop` | `systemctl is-active` |
| systemd (user) | `systemctl --user start` | `systemctl --user stop` | `systemctl --user is-active` |
| Docker | `docker compose up -d` | `docker compose down` | `docker ps` |
| Process | Custom start cmd | Custom stop cmd | `pgrep` |

## Security Considerations

1. **Tailscale ACLs**: Restrict agent API access to only the primary dashboard machine
2. **No external exposure**: Agent ports are only accessible via Tailscale
3. **Authentication**: Consider adding API keys for agent authentication (future)
4. **TLS**: Tailscale provides encryption, but local TLS can be added for defense in depth

## Implementation Phases

### Phase 1: Agent API Design (Current)
- Define API contract
- Document endpoints
- Create reference implementation

### Phase 2: Windows Agent
- Implement Python agent for Windows
- Support Windows Services, Docker, NSSM
- Package as Windows Service itself

### Phase 3: Dashboard Integration
- Add machines configuration
- Implement remote service fetching
- Update UI to show machine grouping

### Phase 4: Advanced Features
- Cross-machine dependencies
- Aggregated logging
- Health monitoring across machines
- Alert routing

## File Structure

```
noc-homelab/
├── dashboard/
│   ├── app.py              # Main dashboard (extended for multi-machine)
│   ├── machines.json       # Machine configuration
│   └── templates/
├── agent/                  # Cross-platform agent (new)
│   ├── agent.py           # Agent implementation
│   ├── platforms/
│   │   ├── darwin.py      # macOS-specific handlers
│   │   └── windows.py     # Windows-specific handlers
│   └── requirements.txt
├── docs/
│   ├── architecture.md    # This file
│   ├── setup-macos.md
│   └── setup-windows.md
└── ...
```

## Repository Structure (Monorepo)

Single repository deployed to all machines. Each machine runs relevant components.

```
noc-homelab/
├── dashboard/              # Central dashboard (runs on noc-local)
│   ├── app.py
│   ├── machines.json
│   └── templates/
├── agent/                  # Cross-platform agent
│   ├── agent.py           # Main agent (runs on all machines)
│   ├── config.yaml        # Machine-specific config (gitignored template)
│   └── platforms/
│       ├── __init__.py
│       ├── base.py        # Abstract base class
│       ├── darwin.py      # macOS service handlers
│       ├── linux.py       # Linux service handlers
│       └── windows.py     # Windows service handlers
├── services/              # Docker Compose services
│   ├── gatus/
│   ├── nextcloud/
│   └── ...
├── launchagents/          # macOS LaunchAgent plists
├── scripts/               # Utility scripts
├── configs/               # Service configurations
└── docs/                  # Documentation
```

### Deployment

**noc-local (macOS)**:
- Runs: Dashboard + Agent + Local services
- Clone: `git clone` to `/Users/noc/noc-homelab`

**noc-tux (Linux)**:
- Runs: Agent only (dashboard queries it via HTTP)
- Clone: `git clone` to `/home/noc/noc-homelab`
- Agent as systemd user service
