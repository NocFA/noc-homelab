# noc-homelab

A two-machine homelab running macOS and Linux, connected over Tailscale. Manages media streaming, Matrix communications, game streaming, and monitoring through a central dashboard and agent API.

![Dashboard](docs/dashboard.png)

---

## Machines

| Machine | OS | Role | Connectivity |
|---|---|---|---|
| **noc-local** | macOS (Sonoma) | Dashboard host, local services | LAN + Tailscale |
| **noc-tux** | Ubuntu 24.04 LTS | Agent, media, Matrix, streaming | Tailscale `100.91.104.124` |

## Architecture

```
noc-local (macOS)                          noc-tux (Ubuntu)
┌──────────────────────┐                   ┌──────────────────────┐
│  Dashboard :8080     │◄── Agent API ───► │  Agent :8080         │
│                      │    (Tailscale)    │                      │
│  Copyparty           │                   │  Matrix Stack        │
│  Maloja              │                   │    Synapse           │
│  Multi-Scrobbler     │                   │    Element Web       │
│  TeamSpeak           │                   │    Synapse Admin     │
│  Nextcloud           │                   │    Postgres/Traefik  │
│  Syncthing           │                   │    Coturn (TURN)     │
│  Gatus               │                   │                      │
│  Glances             │                   │  Media Pipeline      │
│  Caddy               │                   │    Zurg → Rclone     │
│  Beads UI            │                   │    FileBot           │
│  Tailscale           │                   │    Emby / Jellyfin   │
│  VoiceSeq            │                   │                      │
└──────────────────────┘                   │  Sunshine / NoMachine│
                                           │  Gatus / Glances     │
                                           │  Arcane (Docker UI)  │
                                           └──────────────────────┘
```

The dashboard on noc-local polls the agent API on noc-tux for real-time service status. Service control (start/stop/restart) is forwarded through the agent, which manages systemd units and Docker containers.

## Services

### noc-local

| Service | Port | Manager | Description |
|---|---|---|---|
| Dashboard | 8080 | launchd | Central control plane |
| Copyparty | 8081 | launchd | File server with web UI |
| Maloja | 42010 | launchd | Music scrobble server |
| Multi-Scrobbler | 9078 | launchd | Scrobbler aggregator |
| TeamSpeak | 9987 | launchd | Voice chat server |
| TS3AudioBot | 58913 | launchd | TeamSpeak music bot |
| Nextcloud | 9080 | Docker | Cloud storage |
| Syncthing | 8384 | launchd | File sync |
| Gatus | 3001 | launchd | Health monitoring |
| Glances | 61999 | launchd | System metrics API |
| Caddy | 80/443 | launchd | Reverse proxy |
| Beads UI | 3000 | launchd | Issue tracker dashboard |
| VoiceSeq | 61998 | launchd | iOS audio upload |
| Tailscale | -- | system | Mesh VPN |

### noc-tux

| Service | Port | Manager | Description |
|---|---|---|---|
| **Matrix Synapse** | -- | systemd | Matrix homeserver |
| **Element Web** | -- | systemd | Matrix web client |
| **Synapse Admin** | -- | systemd | Matrix admin UI |
| Matrix Postgres | -- | systemd | Matrix database |
| Matrix Traefik | 443 | systemd | Matrix reverse proxy + TLS |
| Matrix Coturn | 3478 | systemd | TURN/STUN for calls |
| Emby | 8096 | systemd | Media streaming |
| Jellyfin | 8097 | systemd | Media streaming |
| Zurg | 9999 | systemd (user) | Real-Debrid WebDAV |
| Rclone Zurg | -- | systemd (user) | FUSE mount at `/mnt/zurg` |
| Sunshine | 47990 | systemd (user) | Game streaming (HEVC/AV1) |
| NoMachine | 4000 | systemd | Remote desktop |
| Gatus | 3001 | systemd (user) | Health monitoring |
| Glances | 61999 | systemd | System metrics API |
| Arcane | 3552 | Docker | Docker management UI |

## Media Pipeline

```
Real-Debrid Cloud
       │ (API poll every 10s)
       ▼
Zurg (WebDAV, port 9999)
       │
       ▼
Rclone FUSE mount (/mnt/zurg)
       │ (on_library_update hook)
       ▼
library-update.sh
  ├── Cleanup stale symlinks
  ├── FileBot: movies → media/movies/
  ├── FileBot: shows  → media/shows/
  ├── Emby /Library/Refresh
  └── Jellyfin /Library/Refresh
       │
       ▼
Emby (8096) + Jellyfin (8097)
```

Content stays in the Real-Debrid cloud — no local storage needed. Zurg exposes it as a WebDAV mount, Rclone makes it a local filesystem, FileBot organizes with symlinks, and both media servers auto-scan.

## Matrix Stack

Self-hosted Matrix homeserver at `matrix.nocfa.net` with Element Web at `element.nocfa.net`. Provides encrypted messaging, voice/video calls, and screen sharing — replacing Stoat Chat.

All six services run as native systemd units (no Docker). Traefik handles TLS termination and routing. Coturn provides TURN/STUN for NAT traversal on calls.

Admin interface at `matrix.nocfa.net/synapse-admin/`.

## Secrets Management

Uses **SOPS + age** encryption with a plaintext-at-rest workflow:

- Configs are **plaintext on disk** for easy editing and direct use by services
- A **pre-commit hook** auto-encrypts sensitive files before they enter git
- A **post-merge hook** auto-decrypts after `git pull`
- Git always stores encrypted content; the working tree always has plaintext

Covered paths: `configs/*`, `*.env`, `linux/services/*/config.*`, `services/*/config/*`, `services/*/vars*`.

Age recipient: `age1jdd07e42w6hgjncpsz0uxe0nruqgpexsl8nhh2vauwn9w0r53paqm9s87h`

## Repository Structure

```
noc-homelab/
├── agent/                  # REST API agent (runs on noc-tux)
│   ├── agent.py            # Flask app, port 8080
│   ├── config.yaml         # Service definitions (gitignored)
│   └── platforms/           # Linux/macOS/Windows handlers
├── dashboard/              # Control dashboard (runs on noc-local)
│   ├── app.py              # Flask app, port 8080
│   ├── template.html       # Dashboard UI
│   └── machines.json       # Machine + service registry
├── linux/
│   ├── scripts/            # Automation (library-update, filebot, ddns)
│   ├── services/           # Native service configs (gatus, zurg)
│   └── systemd/            # Systemd unit files
├── services/               # Docker Compose stacks
│   ├── arcane/             # Docker management UI
│   └── matrix/             # Matrix deployment scripts + vars
├── configs/                # SOPS-encrypted service configs
├── launchagents/           # macOS LaunchAgent plists
├── scripts/                # Utility scripts (tailscale, teamspeak)
├── setup/
│   ├── setup-linux.sh      # noc-tux deployment
│   └── setup-monitoring.sh # Glances + Gatus setup
└── docs/
    ├── architecture.md
    ├── setup-linux.md
    └── setup-macos.md
```

## Deployment

### noc-tux (Linux)

```bash
git clone https://github.com/NocFA/noc-homelab.git
cd noc-homelab
./setup/setup-linux.sh
```

The setup script installs dependencies, deploys systemd services, configures the media pipeline, and starts the agent.

### noc-local (macOS)

```bash
git clone https://github.com/NocFA/noc-homelab.git
cd noc-homelab

# Install LaunchAgents
cd launchagents
for plist in *.plist; do
  ln -sf "$(pwd)/$plist" ~/Library/LaunchAgents/
done

# Start the dashboard
launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist
```

Dashboard available at `http://localhost:8080`.

## License

MIT
