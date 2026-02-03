<p align="center">
  <img src="https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/home-assistant.svg" width="100" />
</p>

<h1 align="center">NOC Homelab</h1>

<p align="center">
  <em>A distributed homelab spanning macOS and Windows machines, connected via Tailscale mesh VPN</em>
</p>

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-services">Services</a> •
  <a href="#-getting-started">Getting Started</a> •
  <a href="docs/architecture.md">Docs</a>
</p>

---

## 📖 Overview

This repository contains the configuration and management tools for a personal homelab infrastructure running across multiple machines. The primary dashboard provides unified control over all services regardless of which machine they're running on.

### Key Features

- **Multi-machine management** - Single dashboard controls services on macOS and Windows
- **Tailscale mesh networking** - Secure, zero-config connectivity between all machines
- **Cross-platform agent** - Unified API for service management on any platform
- **Web-based dashboard** - Modern UI for monitoring and controlling all services

## 🖥️ Machines

| Machine | Platform | Role | Services |
|---------|----------|------|----------|
| **noc-local** | macOS | Primary | Dashboard, media scrobbling, file sharing, TeamSpeak |
| **noc-winlocal** | Windows | Media | Emby, Plex, Sunshine, Real-Debrid streaming |

## 🏗️ Architecture

```
                    ┌──────────────────────────────────────────┐
                    │            Tailscale Mesh VPN            │
                    └──────────────────────────────────────────┘
                                        │
            ┌───────────────────────────┴───────────────────────────┐
            │                                                       │
            ▼                                                       ▼
  ┌───────────────────┐                               ┌───────────────────┐
  │    noc-local      │                               │   noc-winlocal    │
  │     (macOS)       │         HTTP API              │    (Windows)      │
  │                   │◄─────────────────────────────►│                   │
  │  ┌─────────────┐  │                               │  ┌─────────────┐  │
  │  │  Dashboard  │  │                               │  │   Agent     │  │
  │  │   :8080     │  │                               │  │   :8080     │  │
  │  └─────────────┘  │                               │  └─────────────┘  │
  │                   │                               │                   │
  │  Services:        │                               │  Services:        │
  │  • Copyparty      │                               │  • Emby           │
  │  • Maloja         │                               │  • Plex           │
  │  • TeamSpeak      │                               │  • Sunshine       │
  │  • Nextcloud      │                               │  • Zurg/Rclone    │
  │  • Syncthing      │                               │  • Playnite       │
  └───────────────────┘                               └───────────────────┘
```

<details>
<summary>📂 Repository Structure</summary>

```
noc-homelab/
├── dashboard/           # Flask-based control dashboard
│   ├── app.py          # Main application
│   ├── template.html   # Dashboard UI
│   └── static/         # Assets
├── agent/              # Cross-platform service agent
│   ├── agent.py        # Agent HTTP API
│   └── platforms/      # Platform-specific handlers
│       ├── darwin.py   # macOS implementation
│       └── windows.py  # Windows implementation
├── launchagents/       # macOS LaunchAgent plists
├── services/           # Docker Compose services
│   ├── gatus/          # Status monitoring
│   ├── nextcloud/      # Cloud storage
│   └── ts3audiobot/    # TeamSpeak music bot
├── scripts/            # Utility scripts
│   ├── tailscale_manager.py
│   └── teamspeak_manager.py
├── configs/            # Service configurations
└── docs/               # Documentation
    └── architecture.md
```

</details>

## 🚀 Services

### noc-local (macOS)

| Service | Port | Description |
|---------|------|-------------|
| **Dashboard** | 8080 | Central control plane |
| **Copyparty** | 8081 | File server with web UI |
| **Maloja** | 42010 | Music scrobbler |
| **Multi-Scrobbler** | 9078 | Scrobbler aggregator |
| **Gatus** | 3001 | Status page & monitoring |
| **TeamSpeak** | 9987 | Voice chat server |
| **TS3AudioBot** | 58913 | TeamSpeak music bot |
| **Nextcloud** | 9080 | Cloud storage |
| **Syncthing** | 8384 | File synchronization |
| **VoiceSeq** | 61998 | iOS audio upload server |
| **Tailscale** | 5252 | VPN webclient |

### noc-winlocal (Windows)

| Service | Port | Description |
|---------|------|-------------|
| **Emby** | 8096 | Media streaming |
| **Plex** | 32400 | Media streaming |
| **Sunshine** | 47990 | Game streaming |
| **Zurg** | 9999 | Real-Debrid WebDAV |
| **Playnite** | - | Game library |

## 🛠️ Getting Started

### Prerequisites

- **macOS**: Homebrew, Python 3.9+, Docker
- **Windows**: Python 3.9+, Docker Desktop, NSSM (optional)
- **Both**: Tailscale installed and configured

### Quick Start (macOS)

```bash
# Clone the repository
git clone https://github.com/NocFA/noc-homelab.git
cd noc-homelab

# Install LaunchAgents
cd launchagents
for plist in *.plist; do
  ln -sf "$(pwd)/$plist" ~/Library/LaunchAgents/
done

# Start the dashboard
launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist

# Access at http://localhost:8080
```

### Quick Start (Windows)

```powershell
# Clone the repository
git clone https://github.com/NocFA/noc-homelab.git
cd noc-homelab\agent

# Install dependencies
pip install -r requirements.txt

# Copy and edit config
copy config.example.yaml config.yaml
notepad config.yaml

# Run the agent
python agent.py --port 8080
```

## 📚 Documentation

- [Architecture Overview](docs/architecture.md) - System design and multi-machine API spec
- [macOS Setup](docs/setup-macos.md) - Installation and service management
- [Windows Setup](docs/setup-windows.md) - Agent deployment and configuration

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <sub>Built with ☕ and late nights</sub>
</p>
